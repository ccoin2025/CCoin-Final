from fastapi import APIRouter, Request, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from solana.rpc.api import Client
from solana.transaction import Transaction
from fastapi.templating import Jinja2Templates
import os
import redis
from slowapi import Limiter
from slowapi.util import get_remote_address
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET, REDIS_URL
from solders.pubkey import Pubkey
from datetime import datetime, timezone
import time
import structlog
from typing import Optional

logger = structlog.get_logger()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
solana_client = Client(SOLANA_RPC)

# Initialize Redis client with error handling
try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None
    if redis_client:
        logger.info("Redis connected successfully for airdrop module")
except Exception as e:
    logger.error("Redis connection failed", extra={"error": str(e)})
    redis_client = None

@router.get("/", response_class=HTMLResponse)
@limiter.limit("20/minute")
async def get_airdrop(request: Request, db: Session = Depends(get_db)):
    """
    صفحه Airdrop با بررسی شرایط eligibility
    """
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        logger.warning("Unauthorized access to airdrop")
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")

    telegram_id = str(telegram_id).strip()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error("User not found", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    # محاسبه countdown
    end_date = datetime(2025, 12, 31, tzinfo=timezone.utc)
    countdown = end_date - datetime.now(timezone.utc)

    # بررسی دقیق وضعیت tasks
    tasks_completed = False
    if user.tasks:
        completed_tasks = [t for t in user.tasks if t.completed]
        tasks_completed = len(completed_tasks) > 0

    # بررسی دقیق وضعیت referrals
    invited = False
    referral_count = db.query(User).filter(User.referred_by == user.id).count()
    invited = referral_count > 0

    # بررسی wallet connection
    wallet_connected = bool(user.wallet_address)
    
    # بررسی commission payment
    commission_paid = user.commission_paid

    # بررسی eligibility برای airdrop
    if tasks_completed and invited and wallet_connected and commission_paid:
        if hasattr(user, 'airdrop') and user.airdrop:
            user.airdrop.eligible = True
            db.commit()

    from CCOIN import config

    logger.info("Airdrop page accessed", extra={
        "telegram_id": telegram_id,
        "tasks_completed": tasks_completed,
        "invited": invited,
        "wallet_connected": wallet_connected,
        "commission_paid": commission_paid
    })

    return templates.TemplateResponse("airdrop.html", {
        "request": request,
        "countdown": countdown,
        "value": 0.02,
        "tasks_completed": tasks_completed,
        "invited": invited,
        "wallet_connected": wallet_connected,
        "commission_paid": commission_paid,
        "config": config,
        "user_wallet_address": user.wallet_address if user.wallet_address else ""
    })

@router.post("/connect_wallet")
@limiter.limit("5/minute")
async def connect_wallet(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    اتصال wallet با validation کامل و امنیت بالا
    """
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        logger.warning("Unauthorized wallet connection attempt")
        raise HTTPException(status_code=401, detail="Unauthorized")

    telegram_id = str(telegram_id).strip()

    try:
        body = await request.json()
        wallet = body.get("wallet")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            logger.error("User not found for wallet connection", extra={"telegram_id": telegram_id})
            raise HTTPException(status_code=404, detail="User not found")

        # Handle disconnect
        if not wallet or wallet == "":
            user.wallet_address = None
            user.wallet_connected = False
            user.updated_at = datetime.now(timezone.utc)
            db.commit()

            # Clear cache
            if redis_client:
                cache_key = f"wallet:{telegram_id}"
                try:
                    redis_client.delete(cache_key)
                except Exception as e:
                    logger.warning("Cache clear failed", extra={"error": str(e)})

            logger.info("Wallet disconnected", extra={"telegram_id": telegram_id})
            return {"success": True, "message": "Wallet disconnected successfully"}

        # Validate wallet format
        wallet = wallet.strip()
        
        if not isinstance(wallet, str) or len(wallet) < 32 or len(wallet) > 44:
            logger.warning("Invalid wallet format", extra={"telegram_id": telegram_id, "wallet_length": len(wallet)})
            raise HTTPException(status_code=400, detail="Invalid wallet address format")

        # Validate Solana public key
        try:
            Pubkey.from_string(wallet)
        except Exception as e:
            logger.warning("Invalid Solana address", extra={"telegram_id": telegram_id, "error": str(e)})
            raise HTTPException(status_code=400, detail="Invalid Solana wallet address")

        # Check for duplicate wallet
        existing_user = db.query(User).filter(
            User.wallet_address == wallet,
            User.id != user.id
        ).first()

        if existing_user:
            logger.warning("Duplicate wallet attempt", extra={
                "telegram_id": telegram_id,
                "wallet": wallet,
                "existing_user": existing_user.telegram_id
            })
            raise HTTPException(status_code=400, detail="Wallet already connected to another account")

        # Update user wallet
        user.wallet_address = wallet
        user.wallet_connected = True
        user.wallet_connection_date = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)
        db.commit()

        # Cache wallet address
        if redis_client:
            try:
                cache_key = f"wallet:{telegram_id}"
                redis_client.setex(cache_key, 3600, wallet)
            except Exception as e:
                logger.warning("Cache set failed", extra={"error": str(e)})

        logger.info("Wallet connected successfully", extra={
            "telegram_id": telegram_id,
            "wallet": wallet
        })

        return {"success": True, "message": "Wallet connected successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Wallet connection error", extra={
            "telegram_id": telegram_id,
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to connect wallet")

@router.post("/confirm_commission")
@limiter.limit("3/minute")
async def confirm_commission(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    تایید پرداخت commission با retry logic و caching
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        tx_signature = body.get("signature")
        amount = body.get("amount", COMMISSION_AMOUNT)
        recipient = body.get("recipient", ADMIN_WALLET)
        reference = body.get("reference")

        logger.info("Commission confirmation request", extra={
            "telegram_id": telegram_id,
            "signature": tx_signature,
            "amount": amount
        })

        # Input validation
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        if not tx_signature or not isinstance(tx_signature, str):
            raise HTTPException(status_code=400, detail="Missing or invalid transaction signature")

        # Sanitize inputs
        telegram_id = str(telegram_id).strip()
        tx_signature = tx_signature.strip()

        # Find user
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            logger.error("User not found for commission", extra={"telegram_id": telegram_id})
            raise HTTPException(status_code=404, detail="User not found")

        # Check if already paid
        if user.commission_paid:
            logger.info("Commission already paid", extra={"telegram_id": telegram_id})
            return {
                "success": True,
                "message": "Commission already paid",
                "redirect_url": f"/airdrop?telegram_id={telegram_id}"
            }

        # Check wallet connection
        if not user.wallet_address:
            logger.warning("No wallet connected for commission", extra={"telegram_id": telegram_id})
            raise HTTPException(status_code=400, detail="No wallet connected")

        # Check cache first
        cache_key = f"tx:{tx_signature}"
        if redis_client:
            try:
                cached_result = redis_client.get(cache_key)
                if cached_result:
                    logger.info("Transaction found in cache", extra={"signature": tx_signature})
                    user.commission_paid = True
                    user.commission_transaction_hash = tx_signature
                    user.commission_payment_date = datetime.now(timezone.utc)
                    user.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    return {
                        "success": True,
                        "message": "Commission already confirmed",
                        "redirect_url": f"/airdrop?telegram_id={telegram_id}"
                    }
            except Exception as e:
                logger.warning("Cache check failed", extra={"error": str(e)})

        # Retry logic with exponential backoff
        retries = 5
        delay = 1

        for attempt in range(retries):
            try:
                logger.debug("Verifying transaction", extra={
                    "attempt": attempt + 1,
                    "retries": retries,
                    "signature": tx_signature
                })

                # Get transaction info from Solana
                tx_info = solana_client.get_transaction(
                    tx_signature,
                    encoding="json",
                    commitment="confirmed",
                    max_supported_transaction_version=0
                )

                if tx_info.value and tx_info.value.meta and not tx_info.value.meta.err:
                    # Transaction confirmed successfully
                    user.commission_paid = True
                    user.commission_transaction_hash = tx_signature
                    user.commission_payment_date = datetime.now(timezone.utc)
                    user.updated_at = datetime.now(timezone.utc)
                    db.commit()

                    logger.info("Commission confirmed successfully", extra={
                        "telegram_id": telegram_id,
                        "signature": tx_signature,
                        "attempt": attempt + 1
                    })

                    # Cache the successful result
                    if redis_client:
                        try:
                            redis_client.setex(cache_key, 3600, "confirmed")
                        except Exception as e:
                            logger.warning("Cache set failed", extra={"error": str(e)})

                    return {
                        "success": True,
                        "message": "Commission confirmed successfully!",
                        "redirect_url": f"/airdrop?telegram_id={telegram_id}"
                    }
                else:
                    error_msg = "Transaction failed or not found on blockchain"
                    logger.warning(error_msg, extra={
                        "signature": tx_signature,
                        "attempt": attempt + 1
                    })
                    
                    if attempt == retries - 1:
                        raise HTTPException(status_code=400, detail=error_msg)

            except HTTPException:
                raise
            except Exception as e:
                if attempt < retries - 1:
                    logger.warning("Retry attempt failed", extra={
                        "attempt": attempt + 1,
                        "retries": retries,
                        "error": str(e)
                    })
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    logger.error("Verification failed after all retries", extra={
                        "telegram_id": telegram_id,
                        "signature": tx_signature,
                        "retries": retries,
                        "error": str(e)
                    }, exc_info=True)
                    raise HTTPException(
                        status_code=500,
                        detail="Transaction verification failed. Please try again later."
                    )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Commission confirmation error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred")

@router.get("/commission_status")
@limiter.limit("20/minute")
async def get_commission_status(
    request: Request,
    telegram_id: Optional[str] = Query(None, min_length=1, max_length=50),
    db: Session = Depends(get_db)
):
    """
    دریافت وضعیت پرداخت commission
    """
    # Get telegram_id from query or session
    if not telegram_id:
        telegram_id = request.session.get("telegram_id")

    if not telegram_id:
        raise HTTPException(status_code=400, detail="Missing telegram_id")

    telegram_id = str(telegram_id).strip()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error("User not found for status", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    logger.debug("Commission status check", extra={
        "telegram_id": telegram_id,
        "commission_paid": user.commission_paid,
        "wallet_connected": bool(user.wallet_address)
    })

    return {
        "commission_paid": user.commission_paid,
        "wallet_connected": bool(user.wallet_address),
        "wallet_address": user.wallet_address,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET,
        "payment_date": user.commission_payment_date.isoformat() if user.commission_payment_date else None,
        "transaction_hash": user.commission_transaction_hash
    }

@router.get("/referral_status")
@limiter.limit("20/minute")
async def get_referral_status(request: Request, db: Session = Depends(get_db)):
    """
    بررسی وضعیت دعوت دوستان (referrals)
    """
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    telegram_id = str(telegram_id).strip()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # شمارش referrals
    referral_count = db.query(User).filter(User.referred_by == user.id).count()
    has_referrals = referral_count > 0

    logger.debug("Referral status check", extra={
        "telegram_id": telegram_id,
        "referral_count": referral_count
    })

    return {
        "has_referrals": has_referrals,
        "referral_count": referral_count,
        "referral_code": user.referral_code
    }

@router.get("/tasks_status")
@limiter.limit("20/minute")
async def get_tasks_status(request: Request, db: Session = Depends(get_db)):
    """
    بررسی وضعیت انجام tasks
    """
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    telegram_id = str(telegram_id).strip()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # بررسی tasks
    tasks_completed = False
    total_tasks = 0
    completed_count = 0

    if user.tasks:
        total_tasks = len(user.tasks)
        completed_tasks = [t for t in user.tasks if t.completed]
        completed_count = len(completed_tasks)
        tasks_completed = completed_count > 0

    logger.debug("Tasks status check", extra={
        "telegram_id": telegram_id,
        "total_tasks": total_tasks,
        "completed_count": completed_count
    })

    return {
        "tasks_completed": tasks_completed,
        "total_tasks": total_tasks,
        "completed_count": completed_count
    }

@router.get("/check_wallet_status")
@limiter.limit("20/minute")
async def check_wallet_status(request: Request, db: Session = Depends(get_db)):
    """
    بررسی وضعیت اتصال wallet
    """
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    telegram_id = str(telegram_id).strip()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return JSONResponse({
        "connected": user.wallet_address is not None,
        "wallet_address": user.wallet_address,
        "connection_date": user.wallet_connection_date.isoformat() if user.wallet_connection_date else None
    })

@router.post("/verify_commission_manual")
@limiter.limit("3/minute")
async def verify_commission_manual(
    request: Request, 
    db: Session = Depends(get_db)
):
    """
    بررسی manual تراکنش‌های اخیر از wallet کاربر به admin wallet
    برای debug و troubleshooting
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")

        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        telegram_id = str(telegram_id).strip()

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="No wallet connected")

        # Get recent transactions from user's wallet
        try:
            from solders.signature import Signature
            
            user_pubkey = Pubkey.from_string(user.wallet_address)
            admin_pubkey = Pubkey.from_string(ADMIN_WALLET)
            
            # Get signatures for address
            signatures = solana_client.get_signatures_for_address(
                user_pubkey,
                limit=10
            )

            if not signatures.value:
                return {
                    "success": False,
                    "message": "No recent transactions found",
                    "transactions": []
                }

            # Check each transaction
            verified_transactions = []
            for sig_info in signatures.value:
                tx_sig = str(sig_info.signature)
                
                # Get transaction details
                tx_info = solana_client.get_transaction(
                    tx_sig,
                    encoding="json",
                    commitment="confirmed",
                    max_supported_transaction_version=0
                )

                if tx_info.value and tx_info.value.meta and not tx_info.value.meta.err:
                    verified_transactions.append({
                        "signature": tx_sig,
                        "timestamp": sig_info.block_time,
                        "status": "confirmed"
                    })

            logger.info("Manual verification completed", extra={
                "telegram_id": telegram_id,
                "transactions_found": len(verified_transactions)
            })

            return {
                "success": True,
                "message": f"Found {len(verified_transactions)} confirmed transactions",
                "transactions": verified_transactions,
                "wallet_address": user.wallet_address,
                "admin_wallet": ADMIN_WALLET
            }

        except Exception as e:
            logger.error("Manual verification error", extra={
                "telegram_id": telegram_id,
                "error": str(e)
            }, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Manual verification error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred")

# Deprecated endpoints - kept for backward compatibility
@router.get("/pay/commission")
async def pay_commission_get(request: Request):
    """Deprecated - use POST method"""
    raise HTTPException(status_code=405, detail="This endpoint only supports POST requests")
