from fastapi import APIRouter, Request, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
from datetime import datetime, timezone
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.config import SOLANA_RPC
from solders.pubkey import Pubkey
import structlog
from typing import Optional

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
logger = structlog.get_logger()

# Cache برای جلوگیری از تکرار validation (جدید)
_address_cache = {}

@router.get("/browser/connect", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def wallet_browser_connect(
    request: Request, 
    telegram_id: str = Query(..., description="Telegram user ID", min_length=1, max_length=50)
):
    """نمایش صفحه اتصال کیف پول در مرورگر"""
    # Sanitize input
    telegram_id = telegram_id.strip()
    
    logger.info(f"Wallet connect request", extra={"telegram_id": telegram_id})
    
    return templates.TemplateResponse("wallet_browser_connect.html", {
        "request": request,
        "telegram_id": telegram_id
    })

@router.post("/connect", response_class=JSONResponse)
@limiter.limit("5/minute")
async def wallet_connect(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """اتصال کیف پول کاربر با امنیت بهبود یافته"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        wallet_address = body.get("wallet_address")

        # Input Validation
        if not telegram_id or not isinstance(telegram_id, str):
            logger.warning("Invalid telegram_id", extra={"telegram_id": telegram_id})
            raise HTTPException(status_code=400, detail="Invalid Telegram ID")
        
        if not wallet_address or not isinstance(wallet_address, str):
            logger.warning("Invalid wallet_address", extra={"telegram_id": telegram_id})
            raise HTTPException(status_code=400, detail="Invalid wallet address")

        # Sanitize inputs
        telegram_id = telegram_id.strip()
        wallet_address = wallet_address.strip()

        # Find user
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            logger.error("User not found", extra={"telegram_id": telegram_id})
            raise HTTPException(status_code=404, detail="User not found")

        # بررسی اینکه آیا قبلاً کیف پول متصل شده
        if user.wallet_address and user.wallet_address != wallet_address:
            logger.warning("User attempting to change wallet", extra={
                "telegram_id": telegram_id,
                "old_wallet": user.wallet_address,
                "new_wallet": wallet_address
            })
            raise HTTPException(
                status_code=400, 
                detail="Wallet already connected. Contact support to change."
            )

        # Validate Solana address (بهبود یافته)
        if not is_valid_solana_address(wallet_address):
            logger.error("Invalid Solana address", extra={
                "telegram_id": telegram_id,
                "wallet_address": wallet_address
            })
            raise HTTPException(status_code=400, detail="Invalid Solana wallet address")

        # بررسی تکراری بودن آدرس
        existing_wallet = db.query(User).filter(
            User.wallet_address == wallet_address,
            User.telegram_id != telegram_id
        ).first()
        
        if existing_wallet:
            logger.warning("Duplicate wallet address attempt", extra={
                "telegram_id": telegram_id,
                "wallet_address": wallet_address
            })
            raise HTTPException(
                status_code=400, 
                detail="This wallet is already connected to another account"
            )

        # به‌روزرسانی آدرس کیف پول کاربر
        user.wallet_address = wallet_address
        user.wallet_connected = True
        user.wallet_connection_date = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(user)

        logger.info("Wallet connected successfully", extra={
            "telegram_id": telegram_id,
            "wallet_address": wallet_address
        })
        
        # Log در background
        background_tasks.add_task(log_wallet_connection, telegram_id, wallet_address)

        return {
            "success": True,
            "message": "Wallet connected successfully",
            "wallet_address": wallet_address
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Unexpected error in wallet connect", extra={
            "telegram_id": telegram_id if 'telegram_id' in locals() else 'unknown',
            "error": str(e)
        }, exc_info=True)
        # عدم افشای اطلاعات خطا به کاربر
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again.")

@router.get("/status", response_class=JSONResponse)
@limiter.limit("20/minute")
async def get_wallet_status(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID", min_length=1, max_length=50),
    db: Session = Depends(get_db)
):
    """دریافت وضعیت اتصال کیف پول"""
    telegram_id = telegram_id.strip()
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error("User not found for wallet status", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "wallet_connected": user.wallet_connected,
        "wallet_address": user.wallet_address,
        "connection_date": user.wallet_connection_date.isoformat() if user.wallet_connection_date else None
    }

@router.get("/callback", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def wallet_callback(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID", min_length=1, max_length=50),
    db: Session = Depends(get_db)
):
    """صفحه callback بعد از اتصال کیف پول"""
    telegram_id = telegram_id.strip()
    
    logger.info("Wallet callback", extra={"telegram_id": telegram_id})

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error("User not found for wallet callback", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    return templates.TemplateResponse("wallet_callback.html", {
        "request": request,
        "telegram_id": telegram_id,
        "wallet_address": user.wallet_address,
        "success_message": "Wallet connected successfully!" if user.wallet_connected else "Wallet connection failed."
    })

# Helper function برای بررسی اعتبار آدرس Solana (بهبود یافته)
def is_valid_solana_address(address: str) -> bool:
    """
    بررسی دقیق اعتبار آدرس کیف پول Solana
    با استفاده از کتابخانه solders
    """
    if not address or not isinstance(address, str):
        return False

    # بررسی طول
    if len(address) < 32 or len(address) > 44:
        return False

    # Check cache
    if address in _address_cache:
        return _address_cache[address]

    # Validate با solders
    try:
        Pubkey.from_string(address)
        _address_cache[address] = True
        return True
    except Exception as e:
        logger.debug(f"Invalid Solana address validation failed", extra={
            "address": address,
            "error": str(e)
        })
        _address_cache[address] = False
        return False

# Helper function برای لاگ اتصال کیف پول (بهبود یافته)
async def log_wallet_connection(telegram_id: str, wallet_address: str):
    """ثبت لاگ اتصال کیف پول به صورت async"""
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "telegram_id": telegram_id,
        "wallet_address": wallet_address,
        "type": "wallet_connection"
    }
    
    logger.info("Wallet connection logged", extra=log_entry)

    # ذخیره لاگ در فایل (اختیاری)
    try:
        with open('logs/wallet_connections.log', 'a') as f:
            import json
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        logger.error(f"Failed to write wallet log to file: {e}")

@router.get("/test-return")
async def test_return_to_telegram(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID")
):
    """تست بازگشت به تلگرام"""
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <body>
        <h1>Test Return to Telegram</h1>
        <button onclick="returnToTelegram()">Return to Telegram</button>
        <script>
            function returnToTelegram() {{
                const telegramUrl = 'https://t.me/CTG_COIN_BOT/app?startapp=test';
                window.location.href = telegramUrl;
            }}
        </script>
    </body>
    </html>
    """)
