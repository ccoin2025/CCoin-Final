from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
from datetime import datetime, timedelta
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET, BOT_USERNAME
from solana.rpc.api import Client
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solders.message import Message
from solders.system_program import TransferParams, transfer
from solders.keypair import Keypair
import nacl.public
import nacl.utils
import base58  # ✅ فقط برای encryption/decryption
import base64  # ✅ برای تراکنش
import time
import asyncio
import structlog
import secrets
import json

logger = structlog.get_logger()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

# Memory cache for rate limiting and session management
memory_cache = {}
phantom_sessions = {}

def get_from_cache(key: str):
    """Get from memory cache"""
    if key in memory_cache:
        value, expiry = memory_cache[key]
        if time.time() < expiry:
            return value
        else:
            del memory_cache[key]
    return None

def set_in_cache(key: str, value, ttl: int):
    """Set in memory cache"""
    memory_cache[key] = (value, time.time() + ttl)

def clear_cache(key: str):
    """Clear cache"""
    if key in memory_cache:
        del memory_cache[key]

@router.get("/browser/pay", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def commission_browser_pay(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Commission payment page in browser"""
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

@router.post("/create_payment_session", response_class=JSONResponse)
@limiter.limit("10/minute")
async def create_payment_session(
    request: Request,
    db: Session = Depends(get_db)
):
    """Create payment session for Phantom Deep Links"""
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

        # Create session ID
        session_id = secrets.token_urlsafe(32)

        # Create transaction
        connection = AsyncClient(SOLANA_RPC)

        try:
            # Get latest blockhash
            blockhash_resp = await connection.get_latest_blockhash()
            recent_blockhash = blockhash_resp.value.blockhash

            # Create transfer instruction
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

            # Build message and transaction
            message = Message.new_with_blockhash(
                [transfer_ix],
                from_pubkey,
                recent_blockhash
            )

            transaction = Transaction.new_unsigned(message)

            # ✅ Serialize transaction as BASE64 (not base58!)
            wire_bytes = bytes(transaction)
            tx_base64 = base64.b64encode(wire_bytes).decode('utf-8')

            await connection.close()

            logger.info("Transaction created", extra={
                "session_id": session_id,
                "telegram_id": telegram_id,
                "amount": amount
            })

        except Exception as e:
            await connection.close()
            logger.error("Transaction creation failed", extra={"error": str(e)})
            raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")

        # Store session (expires in 10 minutes)
        session_data = {
            "telegram_id": telegram_id,
            "amount": amount,
            "recipient": recipient,
            "created_at": datetime.utcnow().isoformat(),
            "wallet_address": user.wallet_address
        }

        phantom_sessions[session_id] = session_data
        set_in_cache(f"phantom_session_{session_id}", session_data, ttl=600)  # 10 minutes

        logger.info("Payment session created", extra={
            "session_id": session_id,
            "telegram_id": telegram_id
        })

        return {
            "success": True,
            "session_id": session_id,
            "transaction": tx_base64,  # ✅ BASE64 encoded transaction
            "expires_in": 600
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Session creation error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")

@router.post("/verify", response_class=JSONResponse)
@limiter.limit("30/minute")
async def verify_commission_payment(
    request: Request,
    db: Session = Depends(get_db)
):
    """Verify commission payment on Solana blockchain"""
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
            return {
                "success": True,
                "verified": True,
                "already_paid": True,
                "message": "Payment already confirmed"
            }

        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="Wallet not connected")

        # Check blockchain for recent transactions
        connection = AsyncClient(SOLANA_RPC)
        
        try:
            user_pubkey = Pubkey.from_string(user.wallet_address)
            
            logger.info("Fetching recent transactions", extra={
                "user_wallet": user.wallet_address,
                "admin_wallet": ADMIN_WALLET
            })

            # Get recent signatures (last 20 transactions)
            signatures_resp = await connection.get_signatures_for_address(user_pubkey, limit=20)

            if signatures_resp.value:
                expected_lamports = int(COMMISSION_AMOUNT * 1_000_000_000)
                
                for sig_info in signatures_resp.value:
                    sig = str(sig_info.signature)
                    
                    # Skip if already used
                    existing = db.query(User).filter(
                        User.commission_transaction_hash == sig
                    ).first()
                    
                    if existing:
                        continue
                    
                    # Get transaction details
                    tx_resp = await connection.get_transaction(
                        sig,
                        encoding="jsonParsed",
                        max_supported_transaction_version=0
                    )

                    if tx_resp.value and tx_resp.value.transaction:
                        message = tx_resp.value.transaction.transaction.message
                        
                        if hasattr(message, 'instructions'):
                            for ix in message.instructions:
                                if hasattr(ix, 'parsed') and isinstance(ix.parsed, dict):
                                    parsed = ix.parsed
                                    
                                    if parsed.get('type') == 'transfer':
                                        info = parsed.get('info', {})
                                        
                                        source = info.get('source')
                                        destination = info.get('destination')
                                        lamports = info.get('lamports', 0)
                                        
                                        if (source == user.wallet_address and
                                            destination == ADMIN_WALLET):
                                            
                                            # Check amount (allow 2% tolerance for fees)
                                            min_amount = int(expected_lamports * 0.98)
                                            max_amount = int(expected_lamports * 1.02)
                                            
                                            if min_amount <= lamports <= max_amount:
                                                # ✅ Valid payment found!
                                                user.commission_paid = True
                                                user.commission_transaction_hash = sig
                                                user.commission_payment_date = datetime.utcnow()
                                                db.commit()

                                                logger.info("Commission payment verified!", extra={
                                                    "telegram_id": telegram_id,
                                                    "signature": sig,
                                                    "amount_sol": lamports / 1_000_000_000
                                                })

                                                await connection.close()
                                                
                                                return {
                                                    "success": True,
                                                    "verified": True,
                                                    "signature": sig,
                                                    "amount": lamports / 1_000_000_000,
                                                    "message": "Payment verified successfully!"
                                                }

            await connection.close()
            
            logger.info("No matching payment found", extra={"telegram_id": telegram_id})
            
            return {
                "success": True,
                "verified": False,
                "message": "Payment not found yet. Please wait 10-30 seconds after completing the transaction, then try again."
            }

        except Exception as e:
            await connection.close()
            logger.error("Blockchain query error", extra={"error": str(e)}, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Blockchain verification failed: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Verification error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

@router.get("/success", response_class=HTMLResponse)
async def commission_success(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Commission success page"""
    logger.info("Commission success page", extra={"telegram_id": telegram_id})

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return templates.TemplateResponse("commission_success.html", {
        "request": request,
        "telegram_id": telegram_id,
        "bot_username": BOT_USERNAME
    })

@router.get("/check_status", response_class=JSONResponse)
@limiter.limit("20/minute")
async def check_commission_status(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Check commission payment status"""
    logger.info("Checking commission status", extra={"telegram_id": telegram_id})

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "commission_paid": user.commission_paid,
        "wallet_connected": bool(user.wallet_address),
        "wallet_address": user.wallet_address,
        "commission_amount": COMMISSION_AMOUNT
    }
