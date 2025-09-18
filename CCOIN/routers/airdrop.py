from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from solana.rpc.api import Client
from solana.rpc.types import RPCResponse
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
from datetime import datetime, timedelta
import base58
import base64
import time  # برای retry

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
solana_client = Client(SOLANA_RPC)

# Initialize Redis
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

    end_date = datetime(2025, 12, 31)
    countdown = end_date - datetime.now()

    tasks_completed = len([t for t in user.tasks if t.completed]) > 0 if user.tasks else False

    referral_count = db.query(User).filter(User.referred_by == user.id).count()
    invited = referral_count > 0

    wallet_connected = bool(user.wallet_address)
    commission_paid = user.commission_paid

    if tasks_completed and invited and wallet_connected and commission_paid:
        if hasattr(user, 'airdrop'):
            user.airdrop.eligible = True
            db.commit()

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
        "user_wallet_address": user.wallet_address or ""
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

    if not wallet or wallet == "":
        user.wallet_address = None
        db.commit()
        if redis_client:
            redis_client.delete(f"wallet:{telegram_id}")
        return {"success": True, "message": "Wallet disconnected successfully"}

    if not isinstance(wallet, str) or len(wallet) < 32:
        raise HTTPException(status_code=400, detail="Invalid wallet address")

    try:
        Pubkey.from_string(wallet)
        
        existing_user = db.query(User).filter(User.wallet_address == wallet, User.id != user.id).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Wallet already connected to another account")
        
        user.wallet_address = wallet
        db.commit()

        if redis_client:
            redis_client.setex(f"wallet:{telegram_id}", 3600, wallet)

        return {"success": True, "message": "Wallet connected successfully"}

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Solana wallet address")
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
    reference_b58 = body.get("reference")  # Reference از Solana Pay
    signature = body.get("signature")  # Optional

    if not reference_b58:
        raise HTTPException(status_code=400, detail="Missing reference")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.commission_paid:
        raise HTTPException(status_code=400, detail="Commission already paid")

    if not user.wallet_address:
        raise HTTPException(status_code=400, detail="No wallet connected")

    try:
        reference = Pubkey.from_string(base58.decode(reference_b58))
        cache_key = f"tx_ref:{reference_b58}"
        if redis_client and redis_client.get(cache_key):
            user.commission_paid = True
            db.commit()
            return {"success": True, "message": "Commission already confirmed"}

        # Polling با findReference (بهتر از get_transaction)
        max_attempts = 30  # ~30s
        for attempt in range(max_attempts):
            try:
                response = solana_client.find_reference(reference, commitment='confirmed')
                if response.value and not response.value.meta.err:
                    user.commission_paid = True
                    user.commission_transaction_hash = response.value.signature if response.value.signature else signature
                    user.commission_payment_date = datetime.utcnow()
                    db.commit()
                    if redis_client:
                        redis_client.setex(cache_key, 3600, "confirmed")
                    return {"success": True, "message": "Commission confirmed successfully!"}
            except Exception as e:
                if "not found" in str(e).lower():
                    time.sleep(1)  # Retry delay
                    continue
                raise

        raise HTTPException(status_code=400, detail="Transaction not confirmed after retries")

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Transaction confirmation failed: {str(e)}")

# سایر routes بدون تغییر عمده، اما با logging بهتر
@router.get("/commission_status")
@limiter.limit("10/minute")
async def get_commission_status(request: Request, db: Session = Depends(get_db)):
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
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    referral_count = db.query(User).filter(User.referred_by == user.id).count()
    
    return {
        "has_referrals": referral_count > 0,
        "referral_count": referral_count,
        "referral_code": user.referral_code
    }

@router.post("/confirm_commission")
@limiter.limit("5/minute")
async def confirm_commission(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    
    body = await request.json()
    reference_b58 = body.get("reference")
    
    if not reference_b58:
        raise HTTPException(status_code=400, detail="Reference is required")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    cache_key = f"commission_ref_{reference_b58}"
    if redis_client and redis_client.get(cache_key):
        return {"success": True, "message": "Commission already confirmed"}
    
    try:
        reference = Pubkey.from_string(base58.decode(reference_b58))
        max_attempts = 30
        for attempt in range(max_attempts):
            response = solana_client.find_reference(reference, commitment='confirmed')
            if response.value and not response.value.meta.err:
                user.commission_paid = True
                user.commission_transaction_hash = response.value.signature if response.value.signature else 'N/A'
                user.commission_payment_date = datetime.utcnow()
                db.commit()
                if redis_client:
                    redis_client.setex(cache_key, 3600, "confirmed")
                return {"success": True, "message": "Commission confirmed successfully!"}
            time.sleep(1)
        
        raise HTTPException(status_code=400, detail="Transaction not found after retries")
                
    except Exception as e:
        db.rollback()
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
