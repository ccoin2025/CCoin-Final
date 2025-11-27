# routes/commission.py
import os
import time
import secrets
import base64
import structlog
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from solders.message import Message
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction

# project imports
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET, BOT_USERNAME

logger = structlog.get_logger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

# ساده‌سازی: session های پرداخت در مموری (TTL)
_SESSION_STORE = {}

def _set_session(session_id: str, data: dict, ttl: int = 600):
    _SESSION_STORE[session_id] = {"data": data, "expires_at": time.time() + ttl}

def _get_session(session_id: str):
    ent = _SESSION_STORE.get(session_id)
    if not ent:
        return None
    if time.time() > ent["expires_at"]:
        _SESSION_STORE.pop(session_id, None)
        return None
    return ent["data"]

def _pop_session(session_id: str):
    return _SESSION_STORE.pop(session_id, None)

# -------------------------
# Render payment page
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

        client = AsyncClient(SOLANA_RPC)
        try:
            # get latest blockhash
            blockhash_resp = await client.get_latest_blockhash()
            recent_blockhash = blockhash_resp.value.blockhash

            # ✅ اصلاح شده: استفاده از Pubkey.from_string
            from_pubkey = Pubkey.from_string(user.wallet_address)
            to_pubkey = Pubkey.from_string(recipient)
            lamports = int(amount * 1_000_000_000)

            tx = Transaction()
            # add transfer instruction
            tx.add(
                transfer(
                    TransferParams(
                        from_pubkey=from_pubkey,
                        to_pubkey=to_pubkey,
                        lamports=lamports
                    )
                )
            )

            transfer_ix = transfer(
                TransferParams(
                    from_pubkey=from_pubkey,
                    to_pubkey=to_pubkey,
                    lamports=lamports
                )  
            )
            # ساخت Message
            message = Message.new_with_blockhash(
                [transfer_ix],
                from_pubkey,
                recent_blockhash
            )
            # ساخت Transaction
            tx = Transaction.new_unsigned(message)

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
# Phantom callback
# -------------------------
@router.get("/phantom_callback", response_class=HTMLResponse)
async def phantom_callback(request: Request):
    """
    Phantom redirect target
    """
    params = dict(request.query_params)
    logger.info("Phantom callback", extra={"params": params})

    session = params.get("session")
    signature = params.get("signature")
    telegram_id = params.get("telegram_id")

    # phantom error
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

    return templates.TemplateResponse("commission_callback.html", {
        "request": request,
        "success": None,
        "message": "No callback data received. If you completed payment, click 'Check Status'.",
        "telegram_id": telegram_id,
        "bot_username": BOT_USERNAME
    })

# -------------------------
# Verify signature
# -------------------------
@router.post("/verify_signature", response_class=JSONResponse)
async def verify_signature(request: Request, db: Session = Depends(get_db)):
    """
    Body: { telegram_id, session_id, signature }
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

            expected_lamports = int(float(session_data.get("amount", COMMISSION_AMOUNT)) * 1_000_000_000)
            user_wallet = session_data.get("wallet_address")
            admin_addr = ADMIN_WALLET if isinstance(ADMIN_WALLET, str) else str(ADMIN_WALLET)

            # robust instruction reading
            instructions = []
            try:
                parsed_msg = tx_resp.value.transaction.transaction.message
                instructions = getattr(parsed_msg, "instructions", []) or []
            except Exception:
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

        client = AsyncClient(SOLANA_RPC)
        try:
            # ✅ اصلاح شده: استفاده از Pubkey.from_string
            user_pubkey = Pubkey.from_string(user.wallet_address)
            logger.info("Scanning recent transactions", extra={"user_wallet": user.wallet_address})

            signatures_resp = await client.get_signatures_for_address(user_pubkey, limit=40)
            expected_lamports = int(COMMISSION_AMOUNT * 1_000_000_000)

            if signatures_resp.value:
                for sig_info in signatures_resp.value:
                    sig = str(sig_info.signature)
                    existing_user = db.query(User).filter(User.commission_transaction_hash == sig).first()
                    if existing_user:
                        continue

                    tx_resp = await client.get_transaction(sig, encoding="jsonParsed", max_supported_transaction_version=0)
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
                            if info.get("source") == user.wallet_address and info.get("destination") == ADMIN_WALLET:
                                lamports = info.get("lamports", 0)
                                if int(expected_lamports * 0.98) <= int(lamports) <= int(expected_lamports * 1.02):
                                    user.commission_paid = True
                                    user.commission_transaction_hash = sig
                                    user.commission_payment_date = datetime.utcnow()
                                    db.commit()
                                    await client.close()
                                    return {"success": True, "verified": True, "signature": sig}

            await client.close()
            return {"success": False, "verified": False, "message": "No valid payment found"}

        except Exception as e:
            await client.close()
            logger.error("Scan error", extra={"error": str(e)}, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    except Exception as e:
        logger.error("verify error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------
# Check status endpoint
# -------------------------
@router.get("/check_status", response_class=JSONResponse)
async def check_commission_status(
    telegram_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """Check if user has paid commission"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "commission_paid": user.commission_paid,
        "transaction_hash": user.commission_transaction_hash if user.commission_paid else None
    }

# -------------------------
# Success page
# -------------------------
@router.get("/success", response_class=HTMLResponse)
async def commission_success(
    request: Request,
    telegram_id: str = Query(...)
):
    """Success page after payment"""
    return templates.TemplateResponse("commission_success.html", {
        "request": request,
        "telegram_id": telegram_id,
        "bot_username": BOT_USERNAME
    })
