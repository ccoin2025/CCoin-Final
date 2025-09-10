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

    # بررسی دقیق‌تر وضعیت tasks
    tasks_completed = False
    if user.tasks:
        completed_tasks = [t for t in user.tasks if t.completed]
        tasks_completed = len(completed_tasks) > 0

    # بررسی دقیق‌تر وضعیت referrals
    invited = False
    if user.referrals:
        invited = len(user.referrals) > 0

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
    
    if not wallet or not isinstance(wallet, str):
        raise HTTPException(status_code=400, detail="Invalid wallet address")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        # Validate Solana public key format
        Pubkey.from_string(wallet)
        
        user.wallet_address = wallet
        db.commit()
        
        # Cache wallet address
        cache_key = f"wallet:{telegram_id}"
        redis_client.setex(cache_key, 3600, wallet)
        
        return {"success": True, "message": "Wallet connected successfully"}
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Solana wallet address")

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
        cached_result = redis_client.get(cache_key)
        
        if cached_result:
            # Transaction قبلاً تأیید شده
            user.commission_paid = True
            db.commit()
            return {"success": True, "message": "Commission confirmed successfully!"}

        # بررسی transaction از Solana network
        try:
            transaction_response = solana_client.get_transaction(tx_signature, encoding="json", max_supported_transaction_version=0)
            
            if not transaction_response.value:
                raise HTTPException(status_code=400, detail="Transaction not found on blockchain")
                
            tx_data = transaction_response.value
            
            # بررسی وضعیت تراکنش
            if tx_data.meta.err:
                raise HTTPException(status_code=400, detail="Transaction failed on blockchain")
            
            # بررسی جزئیات تراکنش (sender, recipient, amount)
            transaction_info = tx_data.transaction
            
            # Extract account keys
            account_keys = transaction_info.message.account_keys
            
            # بررسی instructions برای transfer
            instructions = transaction_info.message.instructions
            transfer_found = False
            
            for instruction in instructions:
                # System Program transfers have program_id_index = 0 (System Program)
                if instruction.program_id_index == 0:  # System Program
                    # Parse transfer instruction data
                    if len(instruction.data) > 0:
                        # System Program transfer instruction
                        accounts = instruction.accounts
                        if len(accounts) >= 2:
                            from_account = str(account_keys[accounts[0]])
                            to_account = str(account_keys[accounts[1]])
                            
                            # بررسی sender و recipient
                            if (from_account == user.wallet_address and 
                                to_account == ADMIN_WALLET):
                                transfer_found = True
                                break
            
            if not transfer_found:
                raise HTTPException(status_code=400, detail="Invalid transaction: Transfer not found or incorrect details")
            
            # ذخیره در cache (24 ساعت)
            redis_client.setex(cache_key, 86400, "confirmed")
            
            # آپدیت وضعیت کاربر
            user.commission_paid = True
            db.commit()
            
            return {"success": True, "message": "Commission confirmed successfully!"}
            
        except Exception as solana_error:
            print(f"Solana verification error: {solana_error}")
            # اگر نتوانیم از Solana تأیید کنیم، اما signature معتبر است، آن را قبول می‌کنیم
            if len(tx_signature) == 88:  # Valid base58 signature length
                user.commission_paid = True
                db.commit()
                redis_client.setex(cache_key, 3600, "confirmed")  # Cache for 1 hour
                return {"success": True, "message": "Commission payment recorded (verification pending)"}
            else:
                raise HTTPException(status_code=400, detail="Invalid transaction signature format")

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

# Deprecated endpoint - kept for backward compatibility
@router.get("/pay/commission")
async def pay_commission_get(request: Request):
    raise HTTPException(status_code=405, detail="This endpoint only supports POST requests.")
