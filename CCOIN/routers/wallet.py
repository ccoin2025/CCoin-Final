from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from CCOIN.database import get_db
from CCOIN.models.user import User

router = APIRouter()
templates = Jinja2Templates(directory="CCOIN/templates")

@router.get("/wallet-browser-connect")
async def wallet_browser_connect(request: Request):
    """صفحه اتصال در مرورگر خارجی - بهبود یافته"""
    
    # دریافت پارامترهای Phantom callback
    phantom_encryption_public_key = request.query_params.get("phantom_encryption_public_key")
    telegram_id = request.query_params.get("telegram_id")
    error_code = request.query_params.get("errorCode")
    error_message = request.query_params.get("errorMessage")
    
    # اگر Phantom public key ارسال کرده، ذخیره کنیم
    if phantom_encryption_public_key and telegram_id:
        try:
            db = next(get_db())
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.wallet_address = phantom_encryption_public_key
                db.commit()
            db.close()
        except Exception as e:
            print(f"Error saving wallet from callback: {e}")
    
    return templates.TemplateResponse("wallet_browser_connect.html", {"request": request})

@router.get("/phantom-callback")
async def phantom_callback(request: Request, db: Session = Depends(get_db)):
    """صفحه callback برای Phantom Deep Link"""
    telegram_id = request.query_params.get("telegram_id")
    phantom_encryption_public_key = request.query_params.get("phantom_encryption_public_key")
    
    if telegram_id and phantom_encryption_public_key:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            user.wallet_address = phantom_encryption_public_key
            db.commit()
    
    return templates.TemplateResponse("phantom_callback.html", {
        "request": request,
        "wallet_address": phantom_encryption_public_key,
        "telegram_id": telegram_id
    })

@router.get("/api/wallet/status")
async def wallet_status(telegram_id: str, db: Session = Depends(get_db)):
    """بررسی وضعیت اتصال wallet - بهبود یافته"""
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
        
        # اعتبارسنجی آدرس کیف پول
        if len(wallet_address) < 32 or len(wallet_address) > 44:
            return JSONResponse({
                "success": False, 
                "error": "Invalid wallet address length"
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
        return JSONResponse({
            "success": False, 
            "error": f"Server error: {str(e)}"
        })

@router.post("/api/wallet/disconnect")
async def disconnect_wallet(request: Request, db: Session = Depends(get_db)):
    """قطع اتصال wallet - بهبود یافته"""
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
        return JSONResponse({
            "success": False, 
            "error": f"Server error: {str(e)}"
        })

# حذف route wallet-connect چون دیگر لازم نیست
# @router.get("/wallet-connect")  # این خط حذف شده
