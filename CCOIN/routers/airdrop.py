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
import time # برای retry

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

    end_date = datetime(2025, 12, 31) # Fixed year to 2025
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
    if not wallet or wallet == "null" or wallet is None:
        user.wallet_address = None
        db.commit()
        return {"success": True, "message": "Wallet disconnected successfully"}

    # بررسی معتبر بودن آدرس Solana
    try:
        # تبدیل آدرس به base58 و اعتبارسنجی
        pubkey = Pubkey.from_string(wallet)

        # بررسی اینکه آدرس قبلاً استفاده نشده باشد (اختیاری)
        existing_user = db.query(User).filter(User.wallet_address == wallet, User.id != user.id).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="This wallet address is already connected to another account")

        user.wallet_address = wallet
        db.commit()

        print(f"Wallet connected successfully for user {telegram_id}: {wallet}")

        return {
            "success": True,
            "message": "Wallet connected successfully",
            "wallet_address": wallet
        }
    except Exception as e:
        print(f"Invalid wallet address for user {telegram_id}: {wallet}, error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid wallet address: {str(e)}")

@router.get("/referral_status")
@limiter.limit("10/minute")
async def get_referral_status(request: Request, db: Session = Depends(get_db)):
    """Check if user has invited friends"""
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # روش اول: شمارش مستقیم از جدول
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

    return {
        "tasks_completed": tasks_completed,
        "total_tasks": total_tasks,
        "completed_count": completed_count
    }

# اضافه کردن endpoint debug جدید
@router.get("/debug/wallet_status")
async def debug_wallet_status(request: Request, db: Session = Depends(get_db)):
    """Debug endpoint to check wallet status"""
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        return {"error": "No telegram_id in session", "session_keys": list(request.session.keys())}

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        return {"error": "User not found", "telegram_id": telegram_id}

    return {
        "success": True,
        "telegram_id": telegram_id,
        "user_id": user.id,
        "wallet_address": user.wallet_address,
        "wallet_connected": bool(user.wallet_address),
        "commission_paid": user.commission_paid,
        "commission_payment_date": user.commission_payment_date.isoformat() if user.commission_payment_date else None,
        "session_data": dict(request.session)
    }

@router.post("/pay/commission")
@limiter.limit("3/minute")
async def pay_commission(request: Request, db: Session = Depends(get_db)):
    """Handle commission payment"""
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        print("❌ No telegram_id in session for commission payment")
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        print(f"❌ User not found for telegram_id: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")

    # اضافه کردن debug log
    print(f"🔍 Commission payment debug for user {telegram_id}:")
    print(f"  - User ID: {user.id}")
    print(f"  - Wallet address: {user.wallet_address}")
    print(f"  - Commission paid: {user.commission_paid}")

    if not user.wallet_address:
        print(f"❌ No wallet connected for user {telegram_id}")
        raise HTTPException(status_code=400, detail="Wallet not connected. Please connect your wallet first.")

    # Check if commission already paid
    if user.commission_paid:
        print(f"ℹ️ Commission already paid for user {telegram_id}")
        return {"success": True, "message": "Commission already paid"}

    try:
        body = await request.json()
        transaction_hash = body.get("transaction_hash")

        if not transaction_hash:
            raise HTTPException(status_code=400, detail="Transaction hash is required")

        # Verify transaction on Solana (optional - can be added later)
        # try:
        #     tx_info = solana_client.get_transaction(transaction_hash)
        #     if not tx_info or not tx_info.get('result'):
        #         raise HTTPException(status_code=400, detail="Invalid transaction hash")
        # except:
        #     pass # Skip verification for now

        # Mark commission as paid
        user.commission_paid = True
        user.commission_payment_date = datetime.utcnow()
        user.commission_transaction_hash = transaction_hash
        db.commit()

        print(f"✅ Commission paid by user {telegram_id}: {transaction_hash}")

        return {
            "success": True,
            "message": "Commission payment recorded successfully",
            "transaction_hash": transaction_hash
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Commission payment error for user {telegram_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Payment processing failed: {str(e)}")

# Deprecated endpoint - kept for backward compatibility
@router.get("/pay/commission")
async def pay_commission_get(request: Request):
    raise HTTPException(status_code=405, detail="This endpoint only supports POST requests.")

@router.get("/check_wallet_status")
async def check_wallet_status(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return JSONResponse({
        "connected": user.wallet_address is not None,
        "wallet_address": user.wallet_address
    })

@router.get("/check_commission_status")
async def check_commission_status(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return JSONResponse({
        "paid": user.commission_paid,
        "payment_date": user.commission_payment_date.isoformat() if user.commission_payment_date else None,
        "transaction_hash": user.commission_transaction_hash
    })

@router.get("/check_all_status")
@limiter.limit("10/minute")
async def check_all_status(request: Request, db: Session = Depends(get_db)):
    """Check all airdrop requirements status"""
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check tasks
    tasks_completed = False
    completed_count = 0
    total_tasks = 0
    if user.tasks:
        total_tasks = len(user.tasks)
        completed_tasks = [t for t in user.tasks if t.completed]
        completed_count = len(completed_tasks)
        tasks_completed = completed_count > 0

    # Check referrals
    referral_count = db.query(User).filter(User.referred_by == user.id).count()
    invited = referral_count > 0

    # Check wallet
    wallet_connected = bool(user.wallet_address)

    # Check commission
    commission_paid = user.commission_paid

    # Check if eligible for airdrop
    eligible = tasks_completed and invited and wallet_connected and commission_paid

    return {
        "tasks_completed": tasks_completed,
        "tasks_count": completed_count,
        "total_tasks": total_tasks,
        "friends_invited": invited,
        "referral_count": referral_count,
        "wallet_connected": wallet_connected,
        "wallet_address": user.wallet_address,
        "commission_paid": commission_paid,
        "commission_payment_date": user.commission_payment_date.isoformat() if user.commission_payment_date else None,
        "commission_transaction_hash": user.commission_transaction_hash,
        "eligible": eligible,
        "user_info": {
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "tokens": user.tokens,
            "referral_code": user.referral_code
        }
    }

@router.post("/verify_transaction")
@limiter.limit("5/minute")
async def verify_transaction(request: Request, db: Session = Depends(get_db)):
    """Verify a Solana transaction"""
    try:
        body = await request.json()
        tx_hash = body.get("transaction_hash")

        if not tx_hash:
            raise HTTPException(status_code=400, detail="Transaction hash is required")

        # Try to get transaction info from Solana
        try:
            tx_info = solana_client.get_transaction(tx_hash)
            if tx_info and tx_info.get('result'):
                return {
                    "success": True,
                    "verified": True,
                    "transaction_info": tx_info['result']
                }
            else:
                return {
                    "success": True,
                    "verified": False,
                    "message": "Transaction not found or not confirmed yet"
                }
        except Exception as e:
            return {
                "success": True,
                "verified": False,
                "message": f"Could not verify transaction: {str(e)}"
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")
