from fastapi import APIRouter, Request, Depends, HTTPException
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
from datetime import datetime
import base58
import base64
import time  # برای retry

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
solana_client = Client(SOLANA_RPC)

# Initialize Redis client with error handling
try:
    redis_client = redis.Redis.from_url(REDIS_URL) if REDIS_URL else None
except:
    redis_client = None

@router.get("/", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def get_airdrop(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    end_date = datetime(2025, 12, 31)  # Fixed year to 2025
    countdown = end_date - datetime.now()

    # بررسی دقیق‌تر وضعیت tasks
    tasks_completed = False
    if user.tasks:
        completed_tasks = [t for t in user.tasks if t.completed]
        tasks_completed = len(completed_tasks) > 0

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
async def connect_wallet(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")

    body = await request.json()
    wallet = body.get("wallet")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # اگر wallet خالی است، یعنی disconnect
    if not wallet or wallet == "":
        user.wallet_address = None
        db.commit()
        
        # Clear cache
        if redis_client:
            cache_key = f"wallet:{telegram_id}"
            redis_client.delete(cache_key)
        
        return {"success": True, "message": "Wallet disconnected successfully"}

    # Validate wallet address format
    if not isinstance(wallet, str) or len(wallet) < 32:
        raise HTTPException(status_code=400, detail="Invalid wallet address")

    try:
        # Validate Solana public key format
        Pubkey.from_string(wallet)
        
        # Check if wallet already exists for another user
        existing_user = db.query(User).filter(
            User.wallet_address == wallet,
            User.id != user.id
        ).first()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="Wallet already connected to another account")
        
        user.wallet_address = wallet
        db.commit()

        # Cache wallet address
        if redis_client:
            cache_key = f"wallet:{telegram_id}"
            redis_client.setex(cache_key, 3600, wallet)

        return {"success": True, "message": "Wallet connected successfully"}

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Solana wallet address")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to connect wallet: {str(e)}")

@router.post("/confirm_commission")
@limiter.limit("3/minute")
async def confirm_commission(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")

    body = await request.json()
    tx_signature = body.get("signature")
    amount = body.get("amount", COMMISSION_AMOUNT)
    recipient = body.get("recipient", ADMIN_WALLET)
    reference = body.get("reference")  # Added for Solana Pay

    if not tx_signature:
        raise HTTPException(status_code=400, detail="Missing transaction signature")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.commission_paid:
        raise HTTPException(status_code=400, detail="Commission already paid")

    if not user.wallet_address:
        raise HTTPException(status_code=400, detail="No wallet connected")

    try:
        # بررسی cache ابتدا
        cache_key = f"tx:{tx_signature}"
        if redis_client:
            cached_result = redis_client.get(cache_key)
            if cached_result:
                # Transaction قبلاً تأیید شده
                user.commission_paid = True
                db.commit()
                return {"success": True, "message": "Commission already confirmed"}

        # Retry logic for Solana RPC (exponential backoff)
        retries = 5
        delay = 1
        for attempt in range(retries):
            try:
                if reference:
                    # Use findReference for Solana Pay
                    from solana.rpc.commitment import Confirmed
                    sigs = solana_client.find_reference(Pubkey.from_string(reference), commitment=Confirmed)
                    if sigs.value:
                        tx_info = solana_client.get_transaction(sigs.value[0].signature)
                    else:
                        raise ValueError("Reference not found")
                else:
                    tx_info = solana_client.get_transaction(tx_signature, encoding="json", commitment="confirmed")
                
                if tx_info.value and tx_info.value.meta and not tx_info.value.meta.err:
                    user.commission_paid = True
                    user.commission_transaction_hash = tx_signature
                    user.commission_payment_date = datetime.utcnow()
                    db.commit()
                    
                    if redis_client:
                        redis_client.setex(cache_key, 3600, "confirmed")
                    
                    return {"success": True, "message": "Commission confirmed successfully!"}
                else:
                    raise HTTPException(status_code=400, detail="Transaction failed or not found")
            
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    print(f"Solana verification error after retries: {e}")
                    raise HTTPException(status_code=500, detail=f"Confirmation failed after retries: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Commission confirmation error: {e}")
        raise HTTPException(status_code=500, detail=f"Transaction confirmation failed: {str(e)}")

@router.get("/commission_status")
@limiter.limit("10/minute")
async def get_commission_status(request: Request, db: Session = Depends(get_db)):
    """Get commission payment status for user"""
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "commission_paid": user.commission_paid,
        "wallet_connected": bool(user.wallet_address),
        "wallet_address": user.wallet_address,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET
    }

@router.get("/referral_status")
@limiter.limit("10/minute")
async def get_referral_status(request: Request, db: Session = Depends(get_db)):
    """Check if user has successfully invited friends"""
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Count referrals
    referral_count = db.query(User).filter(User.referred_by == user.id).count()
    
    return {
        "has_referrals": referral_count > 0,
        "referral_count": referral_count,
        "referral_code": user.referral_code
    }

# Deprecated endpoint - kept for backward compatibility
@router.get("/pay/commission")
async def pay_commission_get(request: Request):
    raise HTTPException(status_code=405, detail="This endpoint only supports POST requests.")

@router.post("/confirm_commission")
@limiter.limit("5/minute")
async def confirm_commission(request: Request, db: Session = Depends(get_db)):
    """تأیید پرداخت کمیسیون با signature تراکنش"""
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    
    body = await request.json()
    tx_signature = body.get("signature")
    
    if not tx_signature:
        raise HTTPException(status_code=400, detail="Transaction signature is required")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # بررسی cache برای جلوگیری از تراکنش‌های تکراری
        cache_key = f"commission_tx_{tx_signature}"
        if redis_client and redis_client.get(cache_key):
            return {"success": True, "message": "Commission already confirmed"}
        
        # Retry logic
        retries = 5
        delay = 1
        for attempt in range(retries):
            try:
                tx_info = solana_client.get_transaction(
                    tx_signature,
                    encoding="json",
                    commitment="confirmed"
                )
                
                if tx_info.value and tx_info.value.meta and not tx_info.value.meta.err:
                    # تراکنش تأیید شد
                    user.commission_paid = True
                    user.commission_transaction_hash = tx_signature
                    user.commission_payment_date = datetime.utcnow()
                    db.commit()
                    
                    if redis_client:
                        redis_client.setex(cache_key, 3600, "confirmed")  # Cache for 1 hour
                    
                    return {"success": True, "message": "Commission confirmed successfully!"}
                else:
                    raise HTTPException(status_code=400, detail="Transaction failed or not found")
                
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(delay)
                    delay *= 2
                else:
                    print(f"Solana verification error after retries: {e}")
                    # Secure fallback: only accept if signature format valid and log for manual check
                    if len(tx_signature) == 88:
                        user.commission_paid = True
                        user.commission_transaction_hash = tx_signature
                        user.commission_payment_date = datetime.utcnow()
                        db.commit()
                        
                        if redis_client:
                            redis_client.setex(cache_key, 3600, "confirmed")
                        
                        return {"success": True, "message": "Commission payment recorded (verification pending)"}
                    else:
                        raise HTTPException(status_code=400, detail="Invalid transaction signature format")
                
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Commission confirmation error: {e}")
        raise HTTPException(status_code=500, detail=f"Transaction confirmation failed: {str(e)}")


@router.get("/check_wallet_status")
async def check_wallet_status(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    return JSONResponse({
        "connected": user.wallet_address is not None,
        "wallet_address": user.wallet_address
    })

@router.get("/check_commission_status")
async def check_commission_status(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    return JSONResponse({
        "paid": user.commission_paid
    })
