# routes/commission.py
import os
import time
import secrets
import base64
import structlog
from datetime import datetime

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# solana-py (stable) imports
from solana.rpc.async_api import AsyncClient
from solana.publickey import PublicKey
from solana.transaction import Transaction
from solana.system_program import TransferParams, transfer

# project imports - adjust to your project layout
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET, BOT_USERNAME

logger = structlog.get_logger(__name__)
router = APIRouter()  # NO prefix here (main includes with prefix="/commission")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

# Simple in-memory session store (TTL)
_session_store = {}  # session_id -> {telegram_id, amount, recipient, wallet_address, created_at}

def _set_session(session_id: str, data: dict, ttl: int = 600):
    _session_store[session_id] = {
        "data": data,
        "expires_at": time.time() + ttl
    }

def _get_session(session_id: str):
    s = _session_store.get(session_id)
    if not s:
        return None
    if time.time() > s["expires_at"]:
        _session_store.pop(session_id, None)
        return None
    return s["data"]

def _pop_session(session_id: str):
    return _session_store.pop(session_id, None)

# -------------------------
# Browser page (render)
# -------------------------
@router.get("/browser/pay", response_class=HTMLResponse)
async def commission_browser_pay(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    logger.info("Render commission browser pay", extra={"telegram_id": telegram_id})
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.warning("User not found", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    if user.commission_paid:
        return templates.TemplateResponse("commission_success.html", {
            "request": request,
            "telegram_id": telegram_id,
            "success_message": "Commission already paid!",
            "already_paid": True,
            "bot_username": BOT_USERNAME
        })

    if not user.wallet_address:
        raise HTTPException(status_code=400, detail="Wallet not connected. Please connect your wallet first.")

    return templates.TemplateResponse("commission_browser_pay.html", {
        "request": request,
        "telegram_id": telegram_id,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET,
        "bot_username": BOT_USERNAME,
        "solana_rpc": SOLANA_RPC
    })


# -------------------------
# Create payment session
# -------------------------
@router.post("/create_payment_session", response_class=JSONResponse)
async def create_payment_session(request: Request, db: Session = Depends(get_db)):
    """
    Body JSON: { "telegram_id": "...", "amount": optional, "recipient": optional }
    Returns: { success: True, session_id: "...", transaction: "<base64>", expires_in: 600 }
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        amount = float(body.get("amount", COMMISSION_AMOUNT))
        recipient = body.get("recipient", ADMIN_WALLET)

        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            return JSONResponse({"success": False, "error": "Commission already paid"}, status_code=400)

        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="Wallet not connected")

        session_id = secrets.token_urlsafe(32)

        # Build unsigned Transaction using solana-py Transaction()
        client = AsyncClient(SOLANA_RPC)
        try:
            # get latest blockhash
            blockhash_resp = await client.get_latest_blockhash()
            recent_blockhash = blockhash_resp.value.blockhash

            from_pubkey = PublicKey(user.wallet_address)
            to_pubkey = PublicKey(recipient)
            lamports = int(amount * 1_000_000_000)

            tx = Transaction()
            tx.add(
                transfer(
                    TransferParams(
                        from_pubkey=from_pubkey,
                        to_pubkey=to_pubkey,
                        lamports=lamports
                    )
                )
            )

            # set blockhash and fee_payer (fee_payer should be user wallet; Phantom will sign)
            tx.recent_blockhash = recent_blockhash
            tx.fee_payer = from_pubkey

            # serialize transaction (wire format)
            tx_bytes = tx.serialize()  # solana-py method: returns bytes
            tx_base64 = base64.b64encode(tx_bytes).decode("utf-8")

            await client.close()
        except Exception as e:
            await client.close()
            logger.error("Transaction creation failed", extra={"error": str(e)}, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")

        session_data = {
            "telegram_id": telegram_id,
            "amount": amount,
            "recipient": recipient,
            "wallet_address": user.wallet_address,
            "created_at": datetime.utcnow().isoformat()
        }
        _set_session(session_id, session_data, ttl=600)

        logger.info("Payment session created", extra={"session_id": session_id, "telegram_id": telegram_id})
        return {"success": True, "session_id": session_id, "transaction": tx_base64, "expires_in": 600}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_payment_session error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Phantom callback (render)
# -------------------------
@router.get("/phantom_callback", response_class=HTMLResponse)
async def phantom_callback(request: Request):
    """
    Phantom redirect target.
    Successful redirect example:
      /commission/phantom_callback?session=<id>&signature=<txsig>&telegram_id=...
    Or Phantom may return errorCode & errorMessage on failure.
    """
    params = dict(request.query_params)
    logger.info("Phantom callback", extra={"params": params})

    session = params.get("session")
    signature = params.get("signature")
    telegram_id = params.get("telegram_id")

    # Phantom error
    if params.get("errorCode") or params.get("errorMessage"):
        err = params.get("errorMessage") or f"Phantom error {params.get('errorCode')}"
        return templates.TemplateResponse("commission_callback.html", {
            "request": request,
            "success": False,
            "error": err,
            "telegram_id": telegram_id,
            "bot_username": BOT_USERNAME
        })

    if signature and session:
        # store signature in session (short TTL)
        s = _get_session(session)
        if s:
            s["signature"] = signature
            _set_session(session, s, ttl=3600)
        return templates.TemplateResponse("commission_callback.html", {
            "request": request,
            "success": None,
            "message": "Transaction submitted. Verifying...",
            "telegram_id": telegram_id,
            "bot_username": BOT_USERNAME,
            "signature": signature
        })

    # default
    return templates.TemplateResponse("commission_callback.html", {
        "request": request,
        "success": None,
        "message": "No callback data received. If you completed payment, click 'Check Status'.",
        "telegram_id": telegram_id,
        "bot_username": BOT_USERNAME
    })


# -------------------------
# Verify signature (explicit verification)
# -------------------------
@router.post("/verify_signature", response_class=JSONResponse)
async def verify_signature(request: Request, db: Session = Depends(get_db)):
    """
    Body: { telegram_id, session_id, signature }
    Verifies the provided signature on-chain and marks user as paid if valid.
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        session_id = body.get("session_id")
        signature = body.get("signature")

        if not telegram_id or not session_id or not signature:
            raise HTTPException(status_code=400, detail="Missing parameters")

        session_data = _get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=400, detail="Invalid or expired session")

        if session_data.get("telegram_id") != telegram_id:
            raise HTTPException(status_code=400, detail="Session does not belong to telegram_id")

        client = AsyncClient(SOLANA_RPC)
        try:
            tx_resp = await client.get_transaction(signature, encoding="jsonParsed", max_supported_transaction_version=0)
            if not tx_resp.value:
                await client.close()
                return {"verified": False, "message": "Transaction not found on chain (yet)"}

            # parsed tx verification
            expected_lamports = int(float(session_data.get("amount", COMMISSION_AMOUNT)) * 1_000_000_000)
            user_wallet = session_data.get("wallet_address")
            admin_addr = ADMIN_WALLET if isinstance(ADMIN_WALLET, str) else str(ADMIN_WALLET)

            # try robustly to read instructions
            instructions = []
            try:
                parsed_msg = tx_resp.value.transaction.transaction.message
                instructions = getattr(parsed_msg, "instructions", []) or []
            except Exception:
                # fallback to raw dict
                instructions = (tx_resp.value.transaction.get("transaction", {}) or {}).get("message", {}).get("instructions", [])

            found = False
            for ix in instructions:
                parsed = getattr(ix, "parsed", None) or (ix.get("parsed") if isinstance(ix, dict) else None)
                if isinstance(parsed, dict) and parsed.get("type") == "transfer":
                    info = parsed.get("info", {})
                    source = info.get("source")
                    destination = info.get("destination")
                    lamports = info.get("lamports", 0)
                    if source == user_wallet and destination == admin_addr:
                        if int(expected_lamports * 0.98) <= int(lamports) <= int(expected_lamports * 1.02):
                            found = True
                            break

            await client.close()

            if found:
                user = db.query(User).filter(User.telegram_id == telegram_id).first()
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")

                if not user.commission_paid:
                    user.commission_paid = True
                    user.commission_transaction_hash = signature
                    user.commission_payment_date = datetime.utcnow()
                    db.commit()

                # cleanup session
                _pop_session(session_id)
                logger.info("Payment verified and recorded", extra={"telegram_id": telegram_id, "signature": signature})
                return {"verified": True, "signature": signature}

            return {"verified": False, "message": "Transaction does not match expected transfer"}

        except Exception as e:
            await client.close()
            logger.error("verify_signature RPC error", extra={"error": str(e)}, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    except Exception as e:
        logger.error("verify_signature error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Fallback verify (scan recent txs)
# -------------------------
@router.post("/verify", response_class=JSONResponse)
async def verify_commission_payment(request: Request, db: Session = Depends(get_db)):
    """
    Body: { telegram_id }
    Scans recent transactions from user's wallet and matches transfer to admin wallet.
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            return {"success": True, "verified": True, "already_paid": True, "message": "Payment already confirmed"}

        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="Wallet not connected")

        connection = AsyncClient(SOLANA_RPC)
        try:
            user_pubkey = PublicKey(user.wallet_address)
            logger.info("Scanning recent transactions", extra={"user_wallet": user.wallet_address})

            signatures_resp = await connection.get_signatures_for_address(user_pubkey, limit=40)
            expected_lamports = int(COMMISSION_AMOUNT * 1_000_000_000)

            if signatures_resp.value:
                for sig_info in signatures_resp.value:
                    sig = str(sig_info.signature)
                    existing_user = db.query(User).filter(User.commission_transaction_hash == sig).first()
                    if existing_user:
                        continue

                    tx_resp = await connection.get_transaction(sig, encoding="jsonParsed", max_supported_transaction_version=0)
                    if not tx_resp.value:
                        continue

                    instructions = []
                    try:
                        parsed_msg = tx_resp.value.transaction.transaction.message
                        instructions = getattr(parsed_msg, "instructions", []) or []
                    except Exception:
                        instructions = (tx_resp.value.transaction.get("transaction", {}) or {}).get("message", {}).get("instructions", [])

                    for ix in instructions:
                        parsed = getattr(ix, "parsed", None) or (ix.get("parsed") if isinstance(ix, dict) else None)
                        if isinstance(parsed, dict) and parsed.get("type") == "transfer":
                            info = parsed.get("info", {})
                            source = info.get("source")
                            destination = info.get("destination")
                            lamports = info.get("lamports", 0)
                            admin_addr = ADMIN_WALLET if isinstance(ADMIN_WALLET, str) else str(ADMIN_WALLET)
                            if source == user.wallet_address and destination == admin_addr:
                                min_amount = int(expected_lamports * 0.98)
                                max_amount = int(expected_lamports * 1.02)
                                if min_amount <= lamports <= max_amount:
                                    user.commission_paid = True
                                    user.commission_transaction_hash = sig
                                    user.commission_payment_date = datetime.utcnow()
                                    db.commit()
                                    await connection.close()
                                    logger.info("Commission verified by scanning", extra={"telegram_id": telegram_id, "signature": sig})
                                    return {"success": True, "verified": True, "signature": sig, "amount": lamports / 1_000_000_000, "message": "Payment verified successfully!"}

            await connection.close()
            logger.info("No matching payment found", extra={"telegram_id": telegram_id})
            return {"success": True, "verified": False, "message": "Payment not found yet. Please wait and try again."}

        except Exception as e:
            await connection.close()
            logger.error("Blockchain scanning error", extra={"error": str(e)}, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    except Exception as e:
        logger.error("verify error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Success page
# -------------------------
@router.get("/success", response_class=HTMLResponse)
async def commission_success(request: Request, telegram_id: str = Query(..., description="Telegram user ID"), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return templates.TemplateResponse("commission_success.html", {
        "request": request,
        "telegram_id": telegram_id,
        "bot_username": BOT_USERNAME
    })


# -------------------------
# Quick check status
# -------------------------
@router.get("/check_status", response_class=JSONResponse)
async def check_commission_status(request: Request, telegram_id: str = Query(..., description="Telegram user ID"), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "commission_paid": user.commission_paid,
        "wallet_connected": bool(user.wallet_address),
        "wallet_address": user.wallet_address,
        "commission_amount": COMMISSION_AMOUNT
    }
