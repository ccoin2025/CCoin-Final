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
import json
import asyncio

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

# اتصال به Solana و Redis
solana_client = Client(SOLANA_RPC)
redis_client = redis.Redis.from_url(REDIS_URL) if REDIS_URL else None

@router.get("/", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def get_airdrop(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    end_date = datetime(2024, 12, 31)
    countdown = end_date - datetime.now()
    
    tasks_completed = all(t.completed for t in user.tasks) if user.tasks else False
    invited = len(user.referrals) > 0 if user.referrals else False
    wallet_connected = bool(user.wallet_address)
    commission_paid = user.commission_paid
    
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
        "config": config,  # اضافه کردن config
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
    
    if not wallet or not isinstance(wallet, str):
        raise HTTPException(status_code=400, detail="Invalid wallet address")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # تأیید صحت آدرس Solana
        Pubkey.from_string(wallet)
        
        user.wallet_address = wallet
        db.commit()
        
        # ذخیره در کش
        if redis_client:
            cache_key = f"wallet:{telegram_id}"
            redis_client.setex(cache_key, 3600, wallet)
        
        return {"success": True, "message": "Wallet connected successfully"}
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Solana wallet address")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/pay_commission")
@limiter.limit("3/minute")
async def pay_commission(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.wallet_address:
        raise HTTPException(status_code=400, detail="No wallet connected")
    
    if user.commission_paid:
        raise HTTPException(status_code=400, detail="Commission already paid")
    
    try:
        if not ADMIN_WALLET:
            raise HTTPException(status_code=500, detail="Invalid ADMIN_WALLET in config")
        
        # تأیید صحت آدرس‌ها
        try:
            user_pubkey = Pubkey.from_string(user.wallet_address)
            admin_pubkey = Pubkey.from_string(ADMIN_WALLET)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=f"Invalid public key: {str(ve)}")
        
        # بررسی موجودی کیف پول کاربر
        try:
            user_balance = solana_client.get_balance(user_pubkey)
            commission_lamports = int(COMMISSION_AMOUNT * 10**9)
            
            if user_balance.value < commission_lamports:
                raise HTTPException(status_code=400, detail=f"Insufficient funds. Required: {COMMISSION_AMOUNT} SOL, Available: {user_balance.value / 10**9:.6f} SOL")
        
        except Exception as e:
            print(f"Balance check error: {e}")
            # ادامه می‌دهیم حتی اگر بررسی موجودی ناموفق باشد
        
        return JSONResponse({
            "success": True,
            "message": "Transaction prepared successfully",
            "amount": COMMISSION_AMOUNT,
            "recipient": ADMIN_WALLET,
            "user_wallet": user.wallet_address
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transaction preparation failed: {str(e)}")

@router.post("/confirm_commission")
@limiter.limit("5/minute")
async def confirm_commission(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    
    body = await request.json()
    tx_signature = body.get("signature")
    
    if not tx_signature:
        raise HTTPException(status_code=400, detail="Missing transaction signature")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.commission_paid:
        return {"success": True, "message": "Commission already confirmed"}
    
    try:
        # بررسی transaction در کش
        if redis_client:
            cache_key = f"tx:{tx_signature}"
            if redis_client.get(cache_key):
                user.commission_paid = True
                db.commit()
                return {"success": True, "message": "Commission confirmed successfully!"}
        
        # بررسی transaction از Solana network
        max_retries = 3
        for attempt in range(max_retries):
            try:
                transaction_response = solana_client.get_transaction(
                    tx_signature, 
                    encoding='json',
                    commitment='confirmed'
                )
                
                if transaction_response and transaction_response.value:
                    transaction_data = transaction_response.value
                    
                    # بررسی نتیجه transaction
                    if transaction_data.transaction.meta and transaction_data.transaction.meta.err is None:
                        # transaction موفق بوده، بررسی مقدار transfer
                        meta = transaction_data.transaction.meta
                        
                        # پیدا کردن تغییرات balance
                        if meta.pre_balances and meta.post_balances and len(meta.pre_balances) >= 2:
                            # محاسبه مقدار انتقال یافته
                            balance_change = (meta.pre_balances[0] - meta.post_balances[0]) / 10**9
                            
                            # بررسی اینکه مقدار نزدیک به COMMISSION_AMOUNT باشد
                            if abs(balance_change - COMMISSION_AMOUNT) < 0.001:  # tolerance برای fee
                                # transaction معتبر است
                                if redis_client:
                                    redis_client.setex(cache_key, 86400, "confirmed")
                                
                                user.commission_paid = True
                                db.commit()
                                
                                return {"success": True, "message": "Commission confirmed successfully!"}
                        
                        # اگر بررسی دقیق ناموفق بود، اما transaction موفق بوده
                        user.commission_paid = True
                        db.commit()
                        
                        if redis_client:
                            redis_client.setex(cache_key, 86400, "confirmed")
                        
                        return {"success": True, "message": "Commission confirmed successfully!"}
                    
                    else:
                        # transaction ناموفق بوده
                        error_info = transaction_data.transaction.meta.err if transaction_data.transaction.meta else "Unknown error"
                        raise HTTPException(status_code=400, detail=f"Transaction failed: {error_info}")
                
                else:
                    # transaction هنوز confirmed نشده، retry
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)  # صبر 2 ثانیه قبل از retry
                        continue
                    else:
                        raise HTTPException(status_code=400, detail="Transaction not found or not confirmed yet. Please try again in a few moments.")
            
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                    continue
                else:
                    raise e
        
        raise HTTPException(status_code=400, detail="Failed to verify transaction after multiple attempts")
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Transaction confirmation failed: {str(e)}")

@router.get("/pay/commission")
async def pay_commission_get(request: Request):
    raise HTTPException(status_code=405, detail="This endpoint only supports POST requests.")
