import os
import time
import secrets
import base64
import structlog
import asyncio
from datetime import datetime

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction
from solders.message import Message
import base58

from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.config import (
    COMMISSION_AMOUNT, 
    ADMIN_WALLET, 
    BOT_USERNAME, 
    TX_SCAN_LIMIT,
    TX_FINALIZATION_WAIT
)
from CCOIN.utils.redis_session import session_store
from CCOIN.utils.solana_rpc import rpc_client

logger = structlog.get_logger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))


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
        "bot_username": BOT_USERNAME
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

        try:
            blockhash_resp = await rpc_client.get_latest_blockhash()
            recent_blockhash = blockhash_resp.value.blockhash

            from_pubkey = Pubkey.from_string(user.wallet_address)
            to_pubkey = Pubkey.from_string(recipient)
            lamports = int(amount * 1_000_000_000)

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

            tx = Transaction.new_unsigned(message)
            tx_bytes = bytes(tx)
            tx_base64 = base64.b64encode(tx_bytes).decode("utf-8")

        except Exception as e:
            logger.error("Transaction creation failed", extra={"error": str(e)}, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")

        session_data = {
            "telegram_id": telegram_id,
            "amount": amount,
            "recipient": recipient,
            "wallet_address": user.wallet_address,
            "created_at": datetime.utcnow().isoformat()
        }
        session_store.set_session(session_id, session_data, ttl=1800)  # 30 minutes

        logger.info("Payment session created", extra={"session_id": session_id, "telegram_id": telegram_id})
        return {"success": True, "session_id": session_id, "transaction": tx_base64, "expires_in": 1800}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_payment_session error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/phantom_callback", response_class=HTMLResponse)
async def phantom_callback(request: Request):
    """
    Phantom redirect target.
    """
    params = dict(request.query_params)
    logger.info("Phantom callback", extra={"params": params})

    session = params.get("session")
    signature = params.get("signature")
    telegram_id = params.get("telegram_id")

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
        s = session_store.get_session(session)
        if s:
            s["signature"] = signature
            session_store.set_session(session, s, ttl=3600)
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


@router.post("/verify_signature", response_class=JSONResponse)
async def verify_signature(request: Request, db: Session = Depends(get_db)):
    """
    Body: { telegram_id, session_id, signature }
    Verifies provided signature on-chain and marks user as paid if valid.
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        session_id = body.get("session_id")
        signature = body.get("signature")

        if not telegram_id or not session_id or not signature:
            raise HTTPException(status_code=400, detail="Missing parameters")

        session_data = session_store.get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=400, detail="Invalid or expired session")

        if session_data.get("telegram_id") != telegram_id:
            raise HTTPException(status_code=400, detail="Session does not belong to telegram_id")

        logger.info(f"Waiting {TX_FINALIZATION_WAIT} seconds for transaction finalization", signature=signature)
        await asyncio.sleep(TX_FINALIZATION_WAIT)

        try:
            tx_resp = await rpc_client.get_transaction(signature, encoding="jsonParsed", max_supported_transaction_version=0)
            
            if not tx_resp.value:
                return {"verified": False, "message": "Transaction not found on chain yet. Please wait and try again."}

            expected_lamports = int(float(session_data.get("amount", COMMISSION_AMOUNT)) * 1_000_000_000)
            user_wallet = session_data.get("wallet_address")
            admin_addr = ADMIN_WALLET if isinstance(ADMIN_WALLET, str) else str(ADMIN_WALLET)

            instructions = []
            try:
                parsed_msg = tx_resp.value.transaction.transaction.message
                instructions = getattr(parsed_msg, "instructions", []) or []
            except Exception:
                instructions = (tx_resp.value.transaction.get("transaction", {}) or {}).get("message", {}).get(
                    "instructions", [])

            found = False
            for ix in instructions:
                parsed = getattr(ix, "parsed", None) or (ix.get("parsed") if isinstance(ix, dict) else None)
                if isinstance(parsed, dict) and parsed.get("type") == "transfer":
                    info = parsed.get("info", {})
                    source = info.get("source")
                    destination = info.get("destination")
                    lamports = info.get("lamports", 0)
                    
                    logger.info("Checking transfer instruction", 
                               source=source, 
                               destination=destination, 
                               lamports=lamports,
                               expected_source=user_wallet,
                               expected_destination=admin_addr,
                               expected_lamports=expected_lamports)
                    
                    if source == user_wallet and destination == admin_addr:
                        if int(expected_lamports * 0.98) <= int(lamports) <= int(expected_lamports * 1.02):
                            found = True
                            break

            if found:
                user = db.query(User).filter(User.telegram_id == telegram_id).first()
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")

                if not user.commission_paid:
                    user.commission_paid = True
                    user.commission_transaction_hash = signature
                    user.commission_payment_date = datetime.utcnow()
                    db.commit()

                session_store.delete_session(session_id)
                logger.info("Payment verified and recorded", extra={"telegram_id": telegram_id, "signature": signature})
                return {"verified": True, "signature": signature}

            return {"verified": False, "message": "Transaction does not match expected transfer"}

        except Exception as e:
            logger.error("verify_signature RPC error", extra={"error": str(e)}, exc_info=True)
            raise HTTPException(status_code=500, detail=f"RPC Error: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("verify_signature error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify", response_class=JSONResponse)
async def verify_commission_payment(request: Request, db: Session = Depends(get_db)):
    """
    Verify commission payment by scanning recent transactions
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

        try:
            user_pubkey = Pubkey.from_string(user.wallet_address)
            logger.info("Scanning recent transactions", extra={"user_wallet": user.wallet_address, "scan_limit": TX_SCAN_LIMIT})
            
            signatures_resp = await rpc_client.get_signatures_for_address(user_pubkey, limit=TX_SCAN_LIMIT)
            expected_lamports = int(COMMISSION_AMOUNT * 1_000_000_000)
            
            if signatures_resp.value:
                for sig_info in signatures_resp.value:
                    sig = str(sig_info.signature)
                    
                    existing_user = db.query(User).filter(User.commission_transaction_hash == sig).first()
                    if existing_user:
                        logger.debug("Signature already used", signature=sig)
                        continue
                    
                    await asyncio.sleep(0.5)
                    
                    try:
                        tx_resp = await rpc_client.get_transaction(sig, encoding="jsonParsed", max_supported_transaction_version=0)
                    except Exception as tx_error:
                        logger.warning("Failed to get transaction", signature=sig, error=str(tx_error))
                        continue
                    
                    if not tx_resp.value:
                        continue
                    
                    instructions = []
                    try:
                        parsed_msg = tx_resp.value.transaction.transaction.message
                        instructions = getattr(parsed_msg, "instructions", []) or []
                    except Exception:
                        instructions = (tx_resp.value.transaction.get("transaction", {}) or {}).get("message", {}).get("instructions", [])
                    
                    admin_addr = ADMIN_WALLET if isinstance(ADMIN_WALLET, str) else str(ADMIN_WALLET)
                    
                    for ix in instructions:
                        parsed = getattr(ix, "parsed", None) or (ix.get("parsed") if isinstance(ix, dict) else None)
                        if isinstance(parsed, dict) and parsed.get("type") == "transfer":
                            info = parsed.get("info", {})
                            source = info.get("source")
                            destination = info.get("destination")
                            lamports = info.get("lamports", 0)
                            
                            if source == user.wallet_address and destination == admin_addr:
                                if int(expected_lamports * 0.98) <= int(lamports) <= int(expected_lamports * 1.02):
                                    user.commission_paid = True
                                    user.commission_transaction_hash = sig
                                    user.commission_payment_date = datetime.utcnow()
                                    db.commit()
                                    
                                    logger.info("Payment verified and recorded", extra={"telegram_id": telegram_id, "signature": sig})
                                    return {"success": True, "verified": True, "signature": sig}
                
                return {"success": False, "verified": False, "message": "No matching payment found in recent transactions"}
                
        except Exception as e:
            logger.error("verify RPC error", extra={"error": str(e)}, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to verify payment: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("verify_commission_payment error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send_payment_link", response_class=JSONResponse)
async def send_payment_link_to_telegram(request: Request, db: Session = Depends(get_db)):
    """Send payment link to Telegram"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        
        logger.info("send_payment_link called", extra={"telegram_id": telegram_id})
        
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.commission_paid:
            return {"success": False, "message": "Commission already paid"}
        
        if not user.wallet_address:
            return {"success": False, "message": "Wallet not connected. Please connect your wallet first."}
        
        # Send link via telegram utility
        success = await send_commission_payment_link(telegram_id, BOT_TOKEN)
        
        if success:
            logger.info("Payment link sent successfully", extra={"telegram_id": telegram_id})
            return {"success": True, "message": "Payment link sent to Telegram"}
        else:
            logger.error("Failed to send payment link", extra={"telegram_id": telegram_id})
            return {"success": False, "message": "Failed to send payment link"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("send_payment_link error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check_status", response_class=JSONResponse)
async def check_commission_status(
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Check commission payment status"""
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "success": True,
            "commission_paid": user.commission_paid,
            "transaction_hash": user.commission_transaction_hash if user.commission_paid else None,
            "payment_date": user.commission_payment_date.isoformat() if user.commission_paid and user.commission_payment_date else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("check_status error", extra={"error": str(e), "telegram_id": telegram_id}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
