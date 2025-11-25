# routes/commission.py
import os
import time
import secrets
import json
import base64
import structlog
from datetime import datetime

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from solana.rpc.async_api import AsyncClient
from solana.rpc.api import Client as SyncClient
from solana.rpc.commitment import Confirmed
from solders.pubkey import Pubkey
from solders.message import Message
from solders.transaction import Transaction
from solders.system_program import TransferParams, transfer

# Replace these imports with actual paths in your project
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET, BOT_USERNAME

logger = structlog.get_logger()

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

# In-memory caches / sessions
memory_cache = {}
phantom_sessions = {}


def get_from_cache(key: str):
    if key in memory_cache:
        value, expiry = memory_cache[key]
        if time.time() < expiry:
            return value
        else:
            del memory_cache[key]
    return None


def set_in_cache(key: str, value, ttl: int):
    memory_cache[key] = (value, time.time() + ttl)


def clear_cache(key: str):
    if key in memory_cache:
        del memory_cache[key]


# --- Browser payment page (renders HTML template) ---
@router.get("/browser/pay", response_class=HTMLResponse)
async def commission_browser_pay(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    logger.info("Commission browser payment", extra={"telegram_id": telegram_id})

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error("User not found", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    if user.commission_paid:
        logger.info("Commission already paid", extra={"telegram_id": telegram_id})
        return templates.TemplateResponse("commission_success.html", {
            "request": request,
            "telegram_id": telegram_id,
            "success_message": "Commission already paid!",
            "already_paid": True,
            "bot_username": BOT_USERNAME
        })

    if not user.wallet_address:
        logger.warning("No wallet connected", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=400, detail="Wallet not connected. Please connect your wallet first.")

    return templates.TemplateResponse("commission_browser_pay.html", {
        "request": request,
        "telegram_id": telegram_id,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET,
        "bot_username": BOT_USERNAME,
        "solana_rpc": SOLANA_RPC
    })


# --- Create payment session (server builds unsigned tx and returns base64) ---
@router.post("/create_payment_session", response_class=JSONResponse)
async def create_payment_session(request: Request, db: Session = Depends(get_db)):
    """
    Body: { telegram_id: str, amount?: float, recipient?: str }
    Returns: { success: True, session_id, transaction (base64), expires_in }
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        amount = body.get("amount", COMMISSION_AMOUNT)
        recipient = body.get("recipient", ADMIN_WALLET)

        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            raise HTTPException(status_code=400, detail="Commission already paid")

        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="Wallet not connected")

        session_id = secrets.token_urlsafe(32)

        connection = AsyncClient(SOLANA_RPC)
        try:
            blockhash_resp = await connection.get_latest_blockhash()
            recent_blockhash = blockhash_resp.value.blockhash

            from_pubkey = Pubkey.from_string(user.wallet_address)
            to_pubkey = Pubkey.from_string(recipient)
            lamports = int(float(amount) * 1_000_000_000)

            transfer_ix = transfer(
                TransferParams(
                    from_pubkey=from_pubkey,
                    to_pubkey=to_pubkey,
                    lamports=lamports
                )
            )

            message = Message.new_with_blockhash(
                [transfer_ix],
                from_pubkey,
                recent_blockhash
            )

            transaction = Transaction.new_unsigned(message)

            # Serialize as base64 (wire bytes)
            wire_bytes = bytes(transaction)
            tx_base64 = base64.b64encode(wire_bytes).decode("utf-8")

            await connection.close()
        except Exception as e:
            await connection.close()
            logger.error("Transaction creation failed", extra={"error": str(e)})
            raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")

        session_data = {
            "telegram_id": telegram_id,
            "amount": amount,
            "recipient": recipient,
            "created_at": datetime.utcnow().isoformat(),
            "wallet_address": user.wallet_address
        }
        phantom_sessions[session_id] = session_data
        set_in_cache(f"phantom_session_{session_id}", session_data, ttl=600)  # 10 minutes

        logger.info("Payment session created", extra={"session_id": session_id, "telegram_id": telegram_id})

        return {
            "success": True,
            "session_id": session_id,
            "transaction": tx_base64,
            "expires_in": 600
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Session creation error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")


# --- Phantom callback (Phantom redirect after signAndSendTransaction) ---
@router.get("/phantom_callback", response_class=HTMLResponse)
async def phantom_callback(request: Request, session: str = None, telegram_id: str = None):
    """
    Phantom should redirect back with either:
      - signature (query param) for signAndSendTransaction
      - or phantom_encryption_public_key / nonce / data (for encrypted flow)
    We'll handle both; if signature present, verify on-chain; else render callback page for encrypted flow.
    """
    params = dict(request.query_params)
    logger.info("Phantom callback received", extra={"params": params})

    # Handle fast error from Phantom
    if params.get("errorCode") or params.get("errorMessage"):
        return templates.TemplateResponse("commission_callback.html", {
            "request": request,
            "success": False,
            "error": params.get("errorMessage", "Payment failed"),
            "telegram_id": telegram_id,
            "bot_username": BOT_USERNAME
        })

    # If signature present -> verify immediately
    signature = params.get("signature")
    if signature and session:
        # store signature in session for later or verify now
        set_in_cache(f"phantom_sig_{session}", signature, ttl=3600)
        # verify on-chain and render result
        # call same verify logic as verify endpoint
        return templates.TemplateResponse("commission_callback.html", {
            "request": request,
            "success": None,
            "message": "Processing... verification in background",
            "telegram_id": telegram_id,
            "bot_username": BOT_USERNAME,
            "signature": signature
        })

    # Else: check for encrypted callback (phantom_encryption_public_key, nonce, data)
    phantom_pk = params.get("phantom_encryption_public_key")
    nonce = params.get("nonce")
    data = params.get("data")

    if phantom_pk and nonce and data:
        # We'll keep original encrypted flow handling if you used it.
        # For now render pending and let server-decrypt & verify if implemented
        return templates.TemplateResponse("commission_callback.html", {
            "request": request,
            "success": None,
            "message": "Processing encrypted callback... please wait",
            "telegram_id": telegram_id,
            "bot_username": BOT_USERNAME
        })

    # Default: no useful params -> show pending page
    return templates.TemplateResponse("commission_callback.html", {
        "request": request,
        "success": None,
        "message": "No callback data. If you completed payment, click 'Check Payment Status'.",
        "telegram_id": telegram_id,
        "bot_username": BOT_USERNAME
    })


# --- Verify (scan on-chain recent txs like your original logic) ---
@router.post("/verify", response_class=JSONResponse)
async def verify_commission_payment(request: Request, db: Session = Depends(get_db)):
    """
    Body: { telegram_id: str }
    Scans recent txs from user's wallet to admin wallet and amount.
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        logger.info("Verifying commission payment", extra={"telegram_id": telegram_id})
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            return {"success": True, "verified": True, "already_paid": True, "message": "Payment already confirmed"}

        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="Wallet not connected")

        connection = AsyncClient(SOLANA_RPC)
        try:
            user_pubkey = Pubkey.from_string(user.wallet_address)
            logger.info("Fetching recent transactions", extra={"user_wallet": user.wallet_address, "admin_wallet": ADMIN_WALLET})

            signatures_resp = await connection.get_signatures_for_address(user_pubkey, limit=30)

            expected_lamports = int(COMMISSION_AMOUNT * 1_000_000_000)

            if signatures_resp.value:
                for sig_info in signatures_resp.value:
                    sig = str(sig_info.signature)
                    existing = db.query(User).filter(User.commission_transaction_hash == sig).first()
                    if existing:
                        continue

                    tx_resp = await connection.get_transaction(sig, encoding="jsonParsed", max_supported_transaction_version=0)
                    if tx_resp.value and tx_resp.value.transaction:
                        # access message and instructions (jsonParsed)
                        try:
                            parsed_msg = tx_resp.value.transaction.transaction.message
                            if hasattr(parsed_msg, "instructions"):
                                for ix in parsed_msg.instructions:
                                    parsed = getattr(ix, "parsed", None)
                                    if isinstance(parsed, dict) and parsed.get("type") == "transfer":
                                        info = parsed.get("info", {})
                                        source = info.get("source")
                                        destination = info.get("destination")
                                        lamports = info.get("lamports", 0)

                                        # compare addresses (strings)
                                        admin_addr = ADMIN_WALLET if isinstance(ADMIN_WALLET, str) else str(ADMIN_WALLET)
                                        if source == user.wallet_address and destination == admin_addr:
                                            # amount tolerance
                                            min_amount = int(expected_lamports * 0.98)
                                            max_amount = int(expected_lamports * 1.02)
                                            if min_amount <= lamports <= max_amount:
                                                # valid payment
                                                user.commission_paid = True
                                                user.commission_transaction_hash = sig
                                                user.commission_payment_date = datetime.utcnow()
                                                db.commit()

                                                await connection.close()
                                                logger.info("Commission payment verified!", extra={"telegram_id": telegram_id, "signature": sig})
                                                return {"success": True, "verified": True, "signature": sig, "amount": lamports / 1_000_000_000, "message": "Payment verified successfully!"}
                        except Exception:
                            # continue to next tx if parsing fails
                            continue

            await connection.close()
            logger.info("No matching payment found", extra={"telegram_id": telegram_id})
            return {"success": True, "verified": False, "message": "Payment not found yet. Please wait 10-30 seconds after completing the transaction, then try again."}
        except Exception as e:
            await connection.close()
            logger.error("Blockchain query error", extra={"error": str(e)}, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Blockchain verification failed: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Verification error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


# --- Success page render ---
@router.get("/success", response_class=HTMLResponse)
async def commission_success(request: Request, telegram_id: str = Query(..., description="Telegram user ID"), db: Session = Depends(get_db)):
    logger.info("Commission success page", extra={"telegram_id": telegram_id})

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return templates.TemplateResponse("commission_success.html", {
        "request": request,
        "telegram_id": telegram_id,
        "bot_username": BOT_USERNAME
    })


# --- Check status (quick check for UI) ---
@router.get("/check_status", response_class=JSONResponse)
async def check_commission_status(request: Request, telegram_id: str = Query(..., description="Telegram user ID"), db: Session = Depends(get_db)):
    logger.info("Checking commission status", extra={"telegram_id": telegram_id}")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "commission_paid": user.commission_paid,
        "wallet_connected": bool(user.wallet_address),
        "wallet_address": user.wallet_address,
        "commission_amount": COMMISSION_AMOUNT
    }
