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
from CCOIN.utils.telegram_security import get_current_user
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET, REDIS_URL
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from datetime import datetime, timezone
import base58
import base64
import time
import structlog
from typing import Optional

# ✅ اضافه کردن imports جدید برای امنیت
from fastapi_csrf_protect import CsrfProtect
from CCOIN.utils.anti_sybil import check_wallet_age, check_wallet_activity, check_duplicate_pattern
from CCOIN.utils.captcha import verify_recaptcha

logger = structlog.get_logger()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
solana_client = Client(SOLANA_RPC)

# Initialize Redis client with error handling
try:
    redis_client = redis.Redis.from_url(REDIS_URL) if REDIS_URL else None
    if redis_client:
        logger.info("Redis connected successfully for airdrop module")
except Exception as e:
    logger.error("Redis connection failed", extra={"error": str(e)})
    redis_client = None

@router.get("/", response_class=HTMLResponse)
@limiter.limit("30/hour")  # ✅ تغییر از 10/minute
async def get_airdrop(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        logger.warning("Unauthorized access to airdrop")
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")

    # Sanitize input
    telegram_id = str(telegram_id).strip()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error("User not found", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    end_date = datetime(2025, 12, 31, tzinfo=timezone.utc)
    countdown = end_date - datetime.now(timezone.utc)

    # ✅ بررسی دقیق‌تر وضعیت tasks - همه 4 تسک باید کامل شده باشند
    tasks_completed = False
    if user.tasks:
        # فقط وقتی هر 4 تسک (telegram, instagram, x, youtube) کامل شده باشند
        required_platforms = ['telegram', 'instagram', 'x', 'youtube']
        completed_platforms = [t.platform for t in user.tasks if t.completed]
        
        # بررسی اینکه همه 4 پلتفرم در لیست completed باشند
        tasks_completed = all(platform in completed_platforms for platform in required_platforms)
        
        logger.info("Tasks completion check", extra={
            "telegram_id": telegram_id,
            "required_platforms": required_platforms,
            "completed_platforms": completed_platforms,
            "all_completed": tasks_completed
        })

    # بررسی دقیق‌تر وضعیت referrals - اصلاح شده
    invited = False
    if hasattr(user, 'referrals') and user.referrals:
        # Check if user has actually invited someone (referrals list is not empty)
        invited = len(user.referrals) > 0
    else:
        # Alternative check: count users who were referred by this user
        referral_count = db.query(User).filter(User.referred_by == user.id).count()
        invited = referral_count > 0

    wallet_connected = bool(user.wallet_address)
    commission_paid = user.commission_paid

    # بررسی eligibility برای airdrop
    if tasks_completed and invited and wallet_connected and commission_paid:
        if hasattr(user, 'airdrop') and user.airdrop:
            user.airdrop.eligible = True
            db.commit()

    # اضافه کردن config به context
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
@limiter.limit("10/day")  # ✅ تغییر از 5/minute
@limiter.limit("3/hour")  # ✅ اضافه کردن محدودیت ساعتی
async def connect_wallet(
    request: Request,
    csrf_protect: CsrfProtect = Depends(),  # ✅ CSRF Protection
    db: Session = Depends(get_db)
):
    # ✅ تأیید CSRF
    await csrf_protect.validate_csrf(request)
    
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        logger.warning("Unauthorized wallet connection attempt")
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")

    # Sanitize input
    telegram_id = str(telegram_id).strip()

    body = await request.json()
    wallet = body.get("wallet")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error("User not found for wallet connection", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    # اگر wallet خالی است، یعنی disconnect
    if not wallet or wallet == "":
        user.wallet_address = None
        if hasattr(user, 'wallet_connected'):
            user.wallet_connected = False
        if hasattr(user, 'updated_at'):
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

    # Validate wallet address format
    wallet = wallet.strip()
    
    if not isinstance(wallet, str) or len(wallet) < 32:
        logger.warning("Invalid wallet format", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=400, detail="Invalid wallet address")

    try:
        # Validate با base58 decode
        decoded = base58.b58decode(wallet)
        if len(decoded) != 32:
            raise ValueError("Invalid key length")
        
        # Validate Solana public key format
        Pubkey.from_string(wallet)

        # Check if wallet already exists for another user
        existing_user = db.query(User).filter(
            User.wallet_address == wallet,
            User.id != user.id
        ).first()

        if existing_user:
            logger.warning("Duplicate wallet attempt", extra={
                "telegram_id": telegram_id,
                "wallet": wallet
            })
            raise HTTPException(status_code=400, detail="Wallet already connected to another account")

        # ✅ Anti-Sybil Check 1: بررسی سن کیف پول
        if not check_wallet_age(wallet):
            logger.warning("Wallet too new", extra={"telegram_id": telegram_id, "wallet": wallet})
            raise HTTPException(
                status_code=400,
                detail="Wallet is too new. Please use a wallet with at least 7 days of activity."
            )

        # ✅ Anti-Sybil Check 2: بررسی فعالیت کیف پول
        activity = check_wallet_activity(wallet)
        if activity["risk_score"] > 70:
            logger.warning("High risk wallet", extra={
                "telegram_id": telegram_id,
                "wallet": wallet,
                "risk_score": activity["risk_score"]
            })
            raise HTTPException(
                status_code=400,
                detail="Wallet has insufficient activity. Please use an active wallet."
            )

        # ✅ Anti-Sybil Check 3: بررسی الگوهای مشکوک (IP)
        client_ip = request.client.host
        if not check_duplicate_pattern(db, telegram_id, client_ip):
            logger.warning("Suspicious pattern detected", extra={
                "telegram_id": telegram_id,
                "ip": client_ip
            })
            raise HTTPException(
                status_code=429,
                detail="Suspicious activity detected. Please try again later."
            )

        user.wallet_address = wallet
        user.last_ip = client_ip  # ✅ ذخیره IP
        user.last_active = datetime.now(timezone.utc)  # ✅ ذخیره زمان
        if hasattr(user, 'wallet_connected'):
            user.wallet_connected = True
        if hasattr(user, 'wallet_connection_date'):
            user.wallet_connection_date = datetime.now(timezone.utc)
        if hasattr(user, 'updated_at'):
            user.updated_at = datetime.now(timezone.utc)
        db.commit()

        # Cache wallet address
        if redis_client:
            cache_key = f"wallet:{telegram_id}"
            try:
                redis_client.setex(cache_key, 3600, wallet)
            except Exception as e:
                logger.warning("Cache set failed", extra={"error": str(e)})

        logger.info("Wallet connected successfully", extra={
            "telegram_id": telegram_id,
            "wallet": wallet,
            "risk_score": activity["risk_score"]
        })

        return {"success": True, "message": "Wallet connected successfully"}

    except ValueError as e:
        logger.warning("Invalid Solana address", extra={
            "telegram_id": telegram_id,
            "error": str(e)
        })
        raise HTTPException(status_code=400, detail="Invalid Solana wallet address")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Wallet connection error", extra={
            "telegram_id": telegram_id,
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to connect wallet: {str(e)}")

@router.post("/confirm_commission")
@limiter.limit("3/hour")  # ✅ تغییر از 3/minute
@limiter.limit("5/day")   # ✅ اضافه کردن محدودیت روزانه
async def confirm_commission(
    request: Request,
    csrf_protect: CsrfProtect = Depends(),  # ✅ CSRF Protection
    db: Session = Depends(get_db)
):
    """✅ اصلاح شده: گرفتن telegram_id از body به جای session"""

    # ✅ تأیید CSRF
    await csrf_protect.validate_csrf(request)

    body = await request.json()
    telegram_id = body.get("telegram_id")
    tx_signature = body.get("signature")
    amount = body.get("amount", COMMISSION_AMOUNT)
    recipient = body.get("recipient", ADMIN_WALLET)
    reference = body.get("reference")
    captcha_token = body.get("captcha_token")  # ✅ دریافت captcha

    print(f"📥 Commission confirmation request: telegram_id={telegram_id}, signature={tx_signature}")
    logger.info("Commission confirmation request", extra={
        "telegram_id": telegram_id,
        "signature": tx_signature
    })

    if not telegram_id:
        raise HTTPException(status_code=400, detail="Missing telegram_id")

    if not tx_signature:
        raise HTTPException(status_code=400, detail="Missing transaction signature")

    # ✅ تأیید Captcha
    if not await verify_recaptcha(captcha_token, request.client.host):
        logger.warning("Captcha verification failed", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=400, detail="Captcha verification failed")

    # Sanitize inputs
    telegram_id = str(telegram_id).strip()
    tx_signature = tx_signature.strip()

    # Validate transaction signature format
    try:
        base58.b58decode(tx_signature)
    except Exception:
        logger.warning("Invalid transaction signature format", extra={"signature": tx_signature})
        raise HTTPException(status_code=400, detail="Invalid transaction signature format")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        print(f"❌ User not found: {telegram_id}")
        logger.error("User not found", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    if user.commission_paid:
        print(f"✅ Commission already paid for user: {telegram_id}")
        logger.info("Commission already paid", extra={"telegram_id": telegram_id})
        return {"success": True, "message": "Commission already paid"}

    if not user.wallet_address:
        print(f"❌ No wallet connected for user: {telegram_id}")
        logger.warning("No wallet connected", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=400, detail="No wallet connected")

    try:
        # بررسی cache ابتدا
        cache_key = f"tx:{tx_signature}"
        if redis_client:
            try:
                cached_result = redis_client.get(cache_key)
                if cached_result:
                    print(f"✅ Transaction found in cache: {tx_signature}")
                    logger.info("Transaction found in cache", extra={"signature": tx_signature})
                    user.commission_paid = True
                    if hasattr(user, 'updated_at'):
                        user.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    return {"success": True, "message": "Commission already confirmed"}
            except Exception as e:
                logger.warning("Cache check failed", extra={"error": str(e)})

        # Retry logic for Solana RPC (exponential backoff)
        retries = 5
        delay = 1
        for attempt in range(retries):
            try:
                print(f"🔍 Verifying transaction (attempt {attempt + 1}/{retries}): {tx_signature}")
                logger.debug("Verifying transaction", extra={
                    "attempt": attempt + 1,
                    "signature": tx_signature
                })

                tx_info = solana_client.get_transaction(
                    tx_signature,
                    encoding="json",
                    commitment="confirmed",
                    max_supported_transaction_version=0
                )

                if tx_info.value and tx_info.value.meta and not tx_info.value.meta.err:
                    # ✅ Transaction تایید شد
                    user.commission_paid = True
                    user.commission_transaction_hash = tx_signature
                    user.commission_payment_date = datetime.now(timezone.utc)
                    user.last_active = datetime.now(timezone.utc)  # ✅ به‌روزرسانی فعالیت
                    if hasattr(user, 'updated_at'):
                        user.updated_at = datetime.now(timezone.utc)
                    db.commit()

                    print(f"✅ Commission confirmed successfully for user: {telegram_id}")
                    print(f"   Transaction: {tx_signature}")
                    logger.info("Commission confirmed successfully", extra={
                        "telegram_id": telegram_id,
                        "signature": tx_signature
                    })

                    # Cache کردن نتیجه
                    if redis_client:
                        try:
                            redis_client.setex(cache_key, 3600, "confirmed")
                        except Exception as e:
                            logger.warning("Cache set failed", extra={"error": str(e)})

                    # ✅ Return با redirect URL
                    return {
                        "success": True,
                        "message": "Commission confirmed successfully!",
                        "redirect_url": f"/airdrop?telegram_id={telegram_id}"
                    }
                else:
                    error_msg = "Transaction failed or not found on blockchain"
                    print(f"❌ {error_msg}: {tx_signature}")
                    logger.warning(error_msg, extra={"signature": tx_signature})
                    raise HTTPException(status_code=400, detail=error_msg)

            except HTTPException:
                raise
            except Exception as e:
                if attempt < retries - 1:
                    print(f"⚠️ Retry {attempt + 1}/{retries} failed: {e}")
                    logger.warning("Retry attempt failed", extra={
                        "attempt": attempt + 1,
                        "error": str(e)
                    })
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    print(f"❌ Verification failed after {retries} retries: {e}")
                    logger.error("Verification failed after retries", extra={
                        "telegram_id": telegram_id,
                        "error": str(e)
                    }, exc_info=True)
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to verify transaction. Please try again later."
                    )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Commission confirmation error", extra={
            "telegram_id": telegram_id,
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/referral_status")
@limiter.limit("10/minute")
async def get_referral_status(request: Request, db: Session = Depends(get_db)):
    """Check if user has successfully invited friends"""
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Sanitize input
    telegram_id = str(telegram_id).strip()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # روش اول: شمارش کاربرانی که توسط این کاربر دعوت شده‌اند
    referral_count = db.query(User).filter(User.referred_by == user.id).count()

    # روش دوم: چک کردن relationship اگر درست کار کند
    relationship_count = 0
    try:
        if hasattr(user, 'referrals') and user.referrals:
            relationship_count = len(user.referrals)
    except:
        pass

    # انتخاب بهترین روش
    final_count = max(referral_count, relationship_count)
    has_referrals = final_count > 0

    print(f"Referral check for user {telegram_id}: referral_count={referral_count}, relationship_count={relationship_count}, final={final_count}")
    logger.debug("Referral status check", extra={
        "telegram_id": telegram_id,
        "referral_count": final_count
    })

    return {
        "has_referrals": has_referrals,
        "referral_count": final_count,
        "referral_code": user.referral_code,
        "debug_info": {
            "direct_count": referral_count,
            "relationship_count": relationship_count
        }
    }

@router.get("/tasks_status")
@limiter.limit("10/minute")
async def get_tasks_status(request: Request, db: Session = Depends(get_db)):
    """Check if user has completed tasks"""
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Sanitize input
    telegram_id = str(telegram_id).strip()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check completed tasks
    tasks_completed = False
    total_tasks = 0
    completed_count = 0

    if user.tasks:
        total_tasks = len(user.tasks)
        completed_tasks = [t for t in user.tasks if t.completed]
        completed_count = len(completed_tasks)
        tasks_completed = completed_count > 0

    print(f"Tasks check for user {telegram_id}: total={total_tasks}, completed={completed_count}, status={tasks_completed}")
    logger.debug("Tasks status check", extra={
        "telegram_id": telegram_id,
        "completed_count": completed_count
    })

    return {
        "tasks_completed": tasks_completed,
        "total_tasks": total_tasks,
        "completed_count": completed_count
    }

# Deprecated endpoint - kept for backward compatibility
@router.get("/pay/commission")
async def pay_commission_get(request: Request):
    raise HTTPException(status_code=405, detail="This endpoint only supports POST requests.")

@router.get("/check_wallet_status")
async def check_wallet_status(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    return JSONResponse({
        "connected": user.wallet_address is not None,
        "wallet_address": user.wallet_address
    })

@router.post("/verify_commission_manual")
@limiter.limit("3/minute")
async def verify_commission_manual(request: Request, db: Session = Depends(get_db)):
    """
    بررسی manual تراکنش‌های اخیر از wallet کاربر به admin wallet
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")

        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        # Sanitize input
        telegram_id = str(telegram_id).strip()

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="No wallet connected")

        # Get recent transactions
        try:
            from solders.signature import Signature
            
            user_pubkey = Pubkey.from_string(user.wallet_address)
            admin_pubkey = Pubkey.from_string(ADMIN_WALLET)
            
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

            verified_transactions = []
            for sig_info in signatures.value:
                tx_sig = str(sig_info.signature)
                
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
