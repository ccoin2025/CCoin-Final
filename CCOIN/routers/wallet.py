from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from CCOIN.database import get_db
from CCOIN.models.user import User
import re

router = APIRouter()
templates = Jinja2Templates(directory="CCOIN/templates")

@router.get("/wallet-browser-connect")
async def wallet_browser_connect(request: Request):
    """صفحه اتصال کیف پول - ساده‌شده"""
    return templates.TemplateResponse("wallet_browser_connect.html", {"request": request})

@router.get("/api/wallet/status")
async def wallet_status(telegram_id: str, db: Session = Depends(get_db)):
    """بررسی وضعیت اتصال wallet"""
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        
        if user and user.wallet_address:
            return JSONResponse({
                "connected": True,
                "address": user.wallet_address,
                "success": True
            })
        else:
            return JSONResponse({
                "connected": False,
                "address": None,
                "success": True
            })
    except Exception as e:
        print(f"Error checking wallet status: {e}")
        return JSONResponse({
            "connected": False,
            "address": None,
            "success": False,
            "error": str(e)
        })

@router.post("/api/wallet/save")
async def save_wallet(request: Request, db: Session = Depends(get_db)):
    """ذخیره آدرس wallet - بهبود یافته"""
    try:
        data = await request.json()
        telegram_id = data.get("telegram_id")
        wallet_address = data.get("wallet_address")

        if not telegram_id or not wallet_address:
            return JSONResponse({
                "success": False,
                "error": "Missing telegram_id or wallet_address"
            })

        # اعتبارسنجی آدرس کیف پول Solana
        if not is_valid_solana_address(wallet_address):
            return JSONResponse({
                "success": False,
                "error": "Invalid Solana wallet address format"
            })

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        
        if user:
            user.wallet_address = wallet_address
            db.commit()
            
            return JSONResponse({
                "success": True,
                "message": "Wallet connected successfully",
                "address": wallet_address
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "User not found"
            })

    except Exception as e:
        print(f"Error saving wallet: {e}")
        db.rollback()
        return JSONResponse({
            "success": False,
            "error": f"Server error: {str(e)}"
        })

@router.post("/api/wallet/disconnect")
async def disconnect_wallet(request: Request, db: Session = Depends(get_db)):
    """قطع اتصال wallet"""
    try:
        data = await request.json()
        telegram_id = data.get("telegram_id")

        if not telegram_id:
            return JSONResponse({
                "success": False,
                "error": "Missing telegram_id"
            })

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        
        if user:
            user.wallet_address = None
            db.commit()
            
            return JSONResponse({
                "success": True,
                "message": "Wallet disconnected successfully"
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "User not found"
            })

    except Exception as e:
        print(f"Error disconnecting wallet: {e}")
        db.rollback()
        return JSONResponse({
            "success": False,
            "error": f"Server error: {str(e)}"
        })

def is_valid_solana_address(address: str) -> bool:
    """اعتبارسنجی آدرس Solana"""
    if not address or not isinstance(address, str):
        return False
    
    # آدرس Solana باید 32-44 کاراکتر باشد و فقط حروف و اعداد base58
    pattern = r'^[1-9A-HJ-NP-Za-km-z]{32,44}$'
    return bool(re.match(pattern, address))

@router.get("/callback")
async def wallet_callback(request: Request, db: Session = Depends(get_db)):
    """Callback handler برای Deep Link Phantom"""
    try:
        # دریافت پارامترهای بازگشتی از Phantom
        telegram_id = request.query_params.get("telegram_id")
        phantom_encryption_public_key = request.query_params.get("phantom_encryption_public_key")
        nonce = request.query_params.get("nonce")
        data = request.query_params.get("data")
        
        # بررسی خطا
        error_code = request.query_params.get("errorCode")
        error_message = request.query_params.get("errorMessage")
        
        if error_code:
            return templates.TemplateResponse("wallet_callback.html", {
                "request": request,
                "success": False,
                "error": f"Connection failed: {error_message} (Code: {error_code})",
                "telegram_id": telegram_id
            })
        
        # در صورت موفقیت
        if telegram_id and phantom_encryption_public_key:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            
            if user:
                # اگر data رمزگذاری شده باشد، باید decrypt کنید
                # برای سادگی فعلاً فقط public key را ذخیره می‌کنیم
                user.wallet_address = phantom_encryption_public_key
                db.commit()
                
                return templates.TemplateResponse("wallet_callback.html", {
                    "request": request,
                    "success": True,
                    "wallet_address": phantom_encryption_public_key,
                    "telegram_id": telegram_id
                })
        
        # در غیر این صورت خطا
        return templates.TemplateResponse("wallet_callback.html", {
            "request": request,
            "success": False,
            "error": "Missing required parameters",
            "telegram_id": telegram_id
        })
        
    except Exception as e:
        print(f"Callback error: {e}")
        return templates.TemplateResponse("wallet_callback.html", {
            "request": request,
            "success": False,
            "error": f"Server error: {str(e)}",
            "telegram_id": request.query_params.get("telegram_id")
        })
