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

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
solana_client = Client(SOLANA_RPC)
redis_client = redis.Redis.from_url(REDIS_URL)

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
        user.airdrop.eligible = True
        db.commit()

    return templates.TemplateResponse("airdrop.html", {
        "request": request,
        "countdown": countdown,
        "value": 0.02,
        "tasks_completed": tasks_completed,
        "invited": invited,
        "wallet_connected": wallet_connected,
        "commission_paid": commission_paid
    })

@router.post("/connect_wallet")
@limiter.limit("5/minute")
async def connect_wallet(wallet: str, request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not wallet or not isinstance(wallet, str):
        raise HTTPException(status_code=400, detail="Invalid wallet address")

    try:
        Pubkey.from_string(wallet)
        user.wallet_address = wallet
        db.commit()

        cache_key = f"wallet:{telegram_id}"
        redis_client.setex(cache_key, 3600, wallet)

        return {"message": "Wallet connected successfully"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Solana wallet address")

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

        # تبدیل مقدار کمیسیون به lamports
        commission_amount = int(COMMISSION_AMOUNT * 10**9)
        
        # ایجاد public keys
        from_pubkey = Pubkey.from_string(user.wallet_address)
        to_pubkey = Pubkey.from_string(ADMIN_WALLET)

        # دریافت recent blockhash
        cache_key = f"blockhash:{telegram_id}"
        cached_blockhash = redis_client.get(cache_key)
        
        if cached_blockhash:
            recent_blockhash = cached_blockhash.decode()
        else:
            recent_blockhash_response = solana_client.get_latest_blockhash()
            recent_blockhash = str(recent_blockhash_response.value.blockhash)
            redis_client.setex(cache_key, 300, recent_blockhash)

        # ایجاد transaction
        tx = Transaction()
        
        # اضافه کردن instruction
        transfer_instruction = transfer(
            TransferParams(
                from_pubkey=from_pubkey,
                to_pubkey=to_pubkey,
                lamports=commission_amount
            )
        )
        
        tx.add(transfer_instruction)
        
        # تنظیم fee payer و recent blockhash
        tx.fee_payer = from_pubkey
        tx.recent_blockhash = recent_blockhash

        # سریالایز کردن transaction برای ارسال به frontend
        serialized_tx = tx.serialize_message()
        encoded_tx = base64.b64encode(serialized_tx).decode('utf-8')

        return JSONResponse({
            "success": True,
            "transaction": encoded_tx,
            "message": "Please sign the transaction in your Phantom wallet to pay the commission.",
            "amount": COMMISSION_AMOUNT,
            "recipient": ADMIN_WALLET
        })

    except ValueError as ve:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid public key: {str(ve)}")
    except Exception as e:
        db.rollback()
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

    try:
        # بررسی transaction در blockchain
        cache_key = f"tx:{tx_signature}"
        
        if redis_client.get(cache_key):
            user.commission_paid = True
            db.commit()
            return {"success": True, "message": "Commission confirmed successfully!"}

        # بررسی transaction از Solana network
        transaction_response = solana_client.get_transaction(tx_signature)
        
        if transaction_response and transaction_response.value:
            # ذخیره در کش
            redis_client.setex(cache_key, 86400, "confirmed")
            
            # آپدیت وضعیت کاربر
            user.commission_paid = True
            db.commit()
            
            return {"success": True, "message": "Commission confirmed successfully!"}
        else:
            raise HTTPException(status_code=400, detail="Transaction not found or not confirmed")

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Transaction confirmation failed: {str(e)}")

@router.get("/pay/commission")
async def pay_commission_get(request: Request):
    raise HTTPException(status_code=405, detail="This endpoint only supports POST requests.")
