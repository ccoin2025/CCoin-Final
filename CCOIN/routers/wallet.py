from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from CCOIN.database import get_db
from CCOIN.models.user import User

router = APIRouter()
templates = Jinja2Templates(directory="CCOIN/templates")

@router.get("/wallet-connect")
async def wallet_connect_page(request: Request):
    """صفحه اتصال به کیف پول"""
    return templates.TemplateResponse("wallet_connect.html", {"request": request})

@router.get("/wallet-browser-connect")
async def wallet_browser_connect(request: Request):
    """صفحه اتصال در مرورگر خارجی"""
    return templates.TemplateResponse("wallet_browser_connect.html", {"request": request})

@router.get("/phantom-callback")
async def phantom_callback(request: Request, db: Session = Depends(get_db)):
    """صفحه callback برای Phantom Deep Link"""
    telegram_id = request.query_params.get("telegram_id")
    phantom_encryption_public_key = request.query_params.get("phantom_encryption_public_key")
    
    if telegram_id and phantom_encryption_public_key:
        # ذخیره آدرس کیف پول
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
    """بررسی وضعیت اتصال wallet"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user and user.wallet_address:
        return JSONResponse({
            "connected": True,
            "address": user.wallet_address
        })
    else:
        return JSONResponse({
            "connected": False,
            "address": None
        })

@router.post("/api/wallet/save")
async def save_wallet(request: Request, db: Session = Depends(get_db)):
    """ذخیره آدرس wallet"""
    data = await request.json()
    telegram_id = data.get("telegram_id")
    wallet_address = data.get("wallet_address")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user:
        user.wallet_address = wallet_address
        db.commit()
        return JSONResponse({"success": True})
    
    return JSONResponse({"success": False, "error": "User not found"})
