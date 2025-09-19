from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
from datetime import datetime
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.config import DAPP_PRIVATE_KEY, SOLANA_RPC
from solders.pubkey import Pubkey
import base58
import nacl.public
import nacl.encoding
import structlog
import json

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
logger = structlog.get_logger()

@router.get("/browser/connect", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def wallet_browser_connect(request: Request, telegram_id: str = Query(..., description="Telegram user ID")):
    """نمایش صفحه اتصال کیف پول در مرورگر"""
    logger.info(f"Wallet connect request for telegram_id: {telegram_id}")
    return templates.TemplateResponse("wallet_browser_connect.html", {
        "request": request,
        "telegram_id": telegram_id
    })

@router.post("/connect", response_class=JSONResponse)
@limiter.limit("5/minute")
async def wallet_connect(
    request: Request,
    db: Session = Depends(get_db)
):
    """اتصال کیف پول کاربر"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        wallet_address = body.get("wallet_address")
        
        if not telegram_id or not wallet_address:
            logger.error(f"Missing telegram_id or wallet_address: {telegram_id}")
            raise HTTPException(status_code=400, detail="Telegram ID and wallet address are required")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            logger.error(f"User not found: {telegram_id}")
            raise HTTPException(status_code=404, detail="User not found")

        if not is_valid_solana_address(wallet_address):
            logger.error(f"Invalid Solana address for user {telegram_id}: {wallet_address}")
            raise HTTPException(status_code=400, detail="Invalid Solana wallet address")

        # به‌روزرسانی آدرس کیف پول کاربر
        user.wallet_address = wallet_address
        user.wallet_connected = True
        user.wallet_connection_date = datetime.utcnow()
        db.commit()

        logger.info(f"Wallet connected for user {telegram_id}: {wallet_address}")
        log_wallet_connection(telegram_id, wallet_address)

        return {
            "success": True,
            "message": "Wallet connected successfully",
            "wallet_address": wallet_address
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error connecting wallet for user {telegram_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to connect wallet: {str(e)}")

@router.get("/status", response_class=JSONResponse)
@limiter.limit("20/minute")
async def get_wallet_status(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """دریافت وضعیت اتصال کیف پول"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error(f"User not found for wallet status: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "wallet_connected": getattr(user, 'wallet_connected', False),
        "wallet_address": user.wallet_address,
        "connection_date": getattr(user, 'wallet_connection_date', None)
    }

@router.get("/callback", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def wallet_callback(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """صفحه callback بعد از اتصال کیف پول"""
    logger.info(f"Wallet callback for telegram_id: {telegram_id}")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error(f"User not found for wallet callback: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")

    return templates.TemplateResponse("wallet_callback.html", {
        "request": request,
        "telegram_id": telegram_id,
        "wallet_address": user.wallet_address,
        "success_message": "Wallet connected successfully!" if getattr(user, 'wallet_connected', False) else "Wallet connection failed."
    })

# Helper function برای بررسی اعتبار آدرس Solana
def is_valid_solana_address(address: str) -> bool:
    """بررسی اعتبار آدرس کیف پول Solana"""
    if not address or not isinstance(address, str):
        return False
    
    # بررسی طول آدرس (32-44 کاراکتر)
    if len(address) < 32 or len(address) > 44:
        return False
    
    # بررسی کاراکترهای مجاز (Base58)
    allowed_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    return all(c in allowed_chars for c in address)

# Helper function برای لاگ اتصال کیف پول
def log_wallet_connection(telegram_id: str, wallet_address: str):
    """ثبت لاگ اتصال کیف پول"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "telegram_id": telegram_id,
        "wallet_address": wallet_address,
        "type": "wallet_connection"
    }
    logger.info(f"Wallet connection log: {log_entry}")
    
    # ذخیره لاگ در فایل
    with open('wallet_logs.txt', 'a') as f:
        f.write(str(log_entry) + '\n')
    
    return log_entry
