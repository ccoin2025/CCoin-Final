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

# solders imports (همه چیز مربوط به تراکنش)
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.message import MessageV0

# فقط برای RPC client
from solana.rpc.async_api import AsyncClient

# project imports
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET, BOT_USERNAME

logger = structlog.get_logger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

# Session ذخیره موقت در حافظه
_SESSION_STORE = {}

def _set_session(session_id: str, data: dict, ttl: int = 600):
    _SESSION_STORE[session_id] = {"data": data, "expires_at": time.time() + ttl}

def _get_session(session_id: str):
    ent = _SESSION_STORE.get(session_id)
    if not ent or time.time() > ent["expires_at"]:
        _SESSION_STORE.pop(session_id, None)
        return None
    return ent["data"]

def _pop_session(session_id: str):
    return _SESSION_STORE.pop(session_id, None)


@router.get("/browser/pay", response_class=HTMLResponse)
async def commission_browser_pay(request: Request, telegram_id: str = Query(...), db: Session = Depends(get_db)):
    logger.info("Render commission browser pay", extra={"telegram_id": telegram_id})
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
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
        raise HTTPException(status_code=400, detail="Wallet not connected")

    return templates.TemplateResponse("commission_browser_pay.html", {
        "request": request,
        "telegram_id": telegram_id,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET,
        "bot_username": BOT_USERNAME,
        "solana_rpc": SOLANA_RPC
    })


@router.post("/create_payment_session", response_class=JSONResponse)
async def create_payment_session(request: Request, db: Session = Depends(get_db)):
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
            # آخرین بلاک‌هش
            blockhash_resp = await client.get_latest_blockhash()
            recent_blockhash = blockhash_resp.value.blockhash

            from_pubkey = Pubkey.from_string(user.wallet_address)
            to_pubkey = Pubkey.from_string(recipient)
            lamports = int(amount * 1_000_000_000)

            # ساخت دستور انتقال
            instruction = transfer(TransferParams(from_pubkey=from_pubkey, to_pubkey=to_pubkey, lamports=lamports))

            # ساخت MessageV0
            message = MessageV0.try_compile(
                payer=from_pubkey,
                instructions=[instruction],
                address_lookup_table_accounts=[],
                recent_blockhash=recent_blockhash,
            )

            # نسخه نهایی و ۱۰۰٪ کارکرده (بدون signer و با serialize_message)
            tx_bytes = bytes(message)                    # مستقیم از message!
            tx_base64 = base64.b64encode(tx_bytes).decode("utf-8")

            
            await client.close()
        except Exception as e:
            await client.close()
            logger.error("Transaction creation failed", extra={"error": str(e)}, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")

        # ذخیره سشن
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


@router.get("/phantom_callback", response_class=HTMLResponse)
async def phantom_callback(request: Request):
    params = dict(request.query_params)
    logger.info("Phantom callback", extra={"params": params})

    session = params.get("session")
    signature = params.get("signature")
    telegram_id = params.get("telegram_id")

    if params.get("errorCode") or params.get("errorMessage"):
        err = params.get("errorMessage") or f"Phantom error {params.get('errorCode')}"
        return templates.TemplateResponse("commission_callback.html", {
            "request": request, "success": False, "error": err,
            "telegram_id": telegram_id, "bot_username": BOT_USERNAME
        })

    return templates.TemplateResponse("commission_callback.html", {
        "request": request,
        "success": None if not signature else True,
        "message": "Transaction submitted. Verifying..." if signature else "Waiting for signature…",
        "telegram_id": telegram_id,
        "bot_username": BOT_USERNAME,
        "signature": signature or ""
    })


@router.post("/verify_signature", response_class=JSONResponse)
async def verify_signature(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        session_id = body.get("session_id")
        signature = body.get("signature")

        if not all([telegram_id, session_id, signature]):
            raise HTTPException(status_code=400, detail="Missing parameters")

        session_data = _get_session(session_id)
        if not session_data or session_data.get("telegram_id") != telegram_id:
            raise HTTPException(status_code=400, detail="Invalid session")

        client = AsyncClient(SOLANA_RPC)
        tx_resp = await client.get_transaction(signature, encoding="jsonParsed", max_supported_transaction_version=0)
        await client.close()

        if not tx_resp.value:
            return {"verified": False, "message": "Not found yet"}

        # بررسی انتقال
        expected = int(float(session_data.get("amount", COMMISSION_AMOUNT)) * 1_000_000_000)
        user_wallet = session_data.get("wallet_address")
        admin_addr = str(ADMIN_WALLET)

        instructions = tx_resp.value.transaction.transaction.message.instructions
        for ix in instructions:
            p = ix.parsed
            if p and p.get("type") == "transfer" and p["info"].get("source") == user_wallet and p["info"].get("destination") == admin_addr:
                lamports = p["info"]["lamports"]
                if int(expected * 0.98) <= lamports <= int(expected * 1.02):
                    user = db.query(User).filter(User.telegram_id == telegram_id).first()
                    if user and not user.commission_paid:
                        user.commission_paid = True
                        user.commission_transaction_hash = signature
                        user.commission_payment_date = datetime.utcnow()
                        db.commit()
                    _pop_session(session_id)
                    return {"verified": True, "signature": signature}

        return {"verified": False, "message": "Transfer not matching"}
    except:
        raise HTTPException(status_code=500)


# بقیه endpoint ها (verify, success, check_status) دقیقاً مثل قبل بدون تغییر
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
            user_pubkey = Pubkey.from_string(user.wallet_address)
            signatures_resp = await client.get_signatures_for_address(user_pubkey, limit=40)
            expected_lamports = int(COMMISSION_AMOUNT * 1_000_000_000)
            admin_addr = str(ADMIN_WALLET) if not isinstance(ADMIN_WALLET, str) else ADMIN_WALLET

            if signatures_resp.value:
                for sig_info in signatures_resp.value:
                    sig = str(sig_info.signature)
                    if db.query(User).filter(User.commission_transaction_hash == sig).first():
                        continue

                    tx_resp = await client.get_transaction(sig, encoding="jsonParsed", max_supported_transaction_version=0)
                    if not tx_resp.value:
                        continue

                    instructions = []
                    try:
                        parsed_msg = tx_resp.value.transaction.transaction.message
                        instructions = getattr(parsed_msg, "instructions", []) or []
                    except:
                        instructions = (tx_resp.value.transaction.get("transaction", {}) or {}).get("message", {}).get("instructions", [])

                    for ix in instructions:
                        parsed = getattr(ix, "parsed", None) or (ix.get("parsed") if isinstance(ix, dict) else None)
                        if isinstance(parsed, dict) and parsed.get("type") == "transfer":
                            info = parsed.get("info", {})
                            source = info.get("source")
                            destination = info.get("destination")
                            lamports = info.get("lamports", 0)
                            if source == user.wallet_address and destination == admin_addr:
                                if int(expected_lamports * 0.98) <= lamports <= int(expected_lamports * 1.02):
                                    user.commission_paid = True
                                    user.commission_transaction_hash = sig
                                    user.commission_payment_date = datetime.utcnow()
                                    db.commit()
                                    await client.close()
                                    logger.info("Commission verified by scanning", extra={"telegram_id": telegram_id, "signature": sig})
                                    return {"success": True, "verified": True, "signature": sig, "message": "Payment verified!"}

            await client.close()
            return {"success": True, "verified": False, "message": "Payment not found yet."}

        except Exception as e:
            await client.close()
            raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    except Exception as e:
        logger.error("verify error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/success", response_class=HTMLResponse)
async def commission_success(request: Request, telegram_id: str = Query(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return templates.TemplateResponse("commission_success.html", {
        "request": request,
        "telegram_id": telegram_id,
        "bot_username": BOT_USERNAME
    })


@router.get("/check_status", response_class=JSONResponse)
async def check_commission_status(request: Request, telegram_id: str = Query(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "commission_paid": user.commission_paid,
        "wallet_connected": bool(user.wallet_address),
        "wallet_address": user.wallet_address,
        "commission_amount": COMMISSION_AMOUNT
    }
