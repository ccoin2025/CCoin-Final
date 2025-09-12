from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from CCOIN.database import get_db
from CCOIN.models.user import User
from datetime import datetime
import re
import os

router = APIRouter()
templates = Jinja2Templates(directory="CCOIN/templates")

@router.get("/wallet/browser/connect")
async def wallet_browser_connect(request: Request):
    """صفحه اتصال کیف پول در مرورگر خارجی"""
    telegram_id = request.query_params.get("telegram_id")
    return templates.TemplateResponse("wallet_browser_connect.html", {
        "request": request,
        "telegram_id": telegram_id
    })

@router.get("/wallet-browser-connect")
async def wallet_browser_connect_old(request: Request):
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

@router.get("/api/tasks/status")
async def tasks_status(telegram_id: str, db: Session = Depends(get_db)):
    """بررسی وضعیت تسک‌ها و دعوت دوستان"""
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            return JSONResponse({
                "tasks_completed": False,
                "friends_invited": False,
                "success": True
            })
        
        # بررسی تکمیل تسک‌ها
        tasks_completed = any(task.completed for task in user.tasks) if user.tasks else False
        
        # بررسی دعوت دوستان
        friends_invited = len(user.referrals) > 0 if user.referrals else False
        
        return JSONResponse({
            "tasks_completed": tasks_completed,
            "friends_invited": friends_invited,
            "success": True
        })
    except Exception as e:
        print(f"Error checking tasks status: {e}")
        return JSONResponse({
            "tasks_completed": False,
            "friends_invited": False,
            "success": False,
            "error": str(e)
        })

@router.get("/api/commission/status")
async def commission_status(telegram_id: str, db: Session = Depends(get_db)):
    """بررسی وضعیت پرداخت کمیسیون"""
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user and user.commission_paid:
            return JSONResponse({
                "paid": True,
                "payment_date": user.commission_payment_date.isoformat() if user.commission_payment_date else None,
                "transaction_hash": user.commission_transaction_hash,
                "success": True
            })
        else:
            return JSONResponse({
                "paid": False,
                "payment_date": None,
                "transaction_hash": None,
                "success": True
            })
    except Exception as e:
        print(f"Error checking commission status: {e}")
        return JSONResponse({
            "paid": False,
            "payment_date": None,
            "transaction_hash": None,
            "success": False,
            "error": str(e)
        })

@router.post("/api/commission/pay")
async def pay_commission(request: Request, db: Session = Depends(get_db)):
    """ایجاد درخواست پرداخت کمیسیون"""
    try:
        data = await request.json()
        telegram_id = data.get("telegram_id")
        wallet_address = data.get("wallet_address")

        if not telegram_id or not wallet_address:
            return JSONResponse({
                "success": False,
                "error": "Missing telegram_id or wallet_address"
            })

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            return JSONResponse({
                "success": False,
                "error": "User not found"
            })

        if user.commission_paid:
            return JSONResponse({
                "success": False,
                "error": "Commission already paid"
            })

        # مبلغ کمیسیون (مثلاً 0.01 SOL)
        commission_amount = 0.01  # SOL
        recipient_address = os.getenv("ADMIN_WALLET", "So11111111111111111111111111111111111111112")

        return JSONResponse({
            "success": True,
            "amount": commission_amount,
            "recipient": recipient_address,
            "reference": telegram_id
        })

    except Exception as e:
        print(f"Error initiating commission payment: {e}")
        return JSONResponse({
            "success": False,
            "error": f"Server error: {str(e)}"
        })

@router.get("/commission/callback")
async def commission_callback(request: Request, db: Session = Depends(get_db)):
    """Callback برای تایید پرداخت کمیسیون"""
    try:
        telegram_id = request.query_params.get("telegram_id")
        signature = request.query_params.get("signature")

        if not telegram_id:
            return templates.TemplateResponse("commission_callback.html", {
                "request": request,
                "success": False,
                "error": "Missing telegram_id",
                "telegram_id": telegram_id
            })

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            return templates.TemplateResponse("commission_callback.html", {
                "request": request,
                "success": False,
                "error": "User not found",
                "telegram_id": telegram_id
            })

        # در صورت وجود signature، پرداخت را تایید کن
        if signature:
            user.commission_paid = True
            user.commission_payment_date = datetime.utcnow()
            user.commission_transaction_hash = signature
            db.commit()

            return templates.TemplateResponse("commission_callback.html", {
                "request": request,
                "success": True,
                "signature": signature,
                "telegram_id": telegram_id
            })
        else:
            return templates.TemplateResponse("commission_callback.html", {
                "request": request,
                "success": False,
                "error": "Payment not confirmed",
                "telegram_id": telegram_id
            })

    except Exception as e:
        print(f"Commission callback error: {e}")
        return templates.TemplateResponse("commission_callback.html", {
            "request": request,
            "success": False,
            "error": f"Server error: {str(e)}",
            "telegram_id": request.query_params.get("telegram_id")
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

@router.get("/wallet/callback")
async def wallet_callback(request: Request, db: Session = Depends(get_db)):
    """Callback handler برای Deep Link Phantom - بهبود یافته"""
    try:
        # دریافت پارامترهای بازگشتی از Phantom
        telegram_id = request.query_params.get("telegram_id")

        # پارامترهای موفقیت
        phantom_encryption_public_key = request.query_params.get("phantom_encryption_public_key")
        nonce = request.query_params.get("nonce")
        data = request.query_params.get("data")
        session = request.query_params.get("session")

        # پارامترهای خطا
        error_code = request.query_params.get("errorCode")
        error_message = request.query_params.get("errorMessage")

        print(f"[PHANTOM CALLBACK] telegram_id: {telegram_id}")
        print(f"[PHANTOM CALLBACK] error_code: {error_code}")
        print(f"[PHANTOM CALLBACK] error_message: {error_message}")
        print(f"[PHANTOM CALLBACK] phantom_key: {phantom_encryption_public_key}")

        if error_code:
            return templates.TemplateResponse("wallet_callback.html", {
                "request": request,
                "success": False,
                "error": f"Phantom Error {error_code}: {error_message}",
                "telegram_id": telegram_id
            })

        # موفقیت - ذخیره اطلاعات
        if telegram_id and phantom_encryption_public_key:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                try:
                    # Phantom public key معمولاً در phantom_encryption_public_key یا data قرار دارد
                    wallet_address = phantom_encryption_public_key

                    # اگر data موجود است، سعی کنید decode کنید
                    if data and nonce:
                        # برای پیاده‌سازی کامل، باید data را decrypt کنید
                        # فعلاً از phantom_encryption_public_key استفاده می‌کنیم
                        print(f"Encrypted data received: {data}")

                    user.wallet_address = wallet_address
                    db.commit()

                    return templates.TemplateResponse("wallet_callback.html", {
                        "request": request,
                        "success": True,
                        "wallet_address": wallet_address,
                        "telegram_id": telegram_id
                    })

                except Exception as decode_error:
                    print(f"Decode error: {decode_error}")
                    return templates.TemplateResponse("wallet_callback.html", {
                        "request": request,
                        "success": False,
                        "error": f"Failed to process wallet data: {str(decode_error)}",
                        "telegram_id": telegram_id
                    })

        # پارامترهای ناقص
        return templates.TemplateResponse("wallet_callback.html", {
            "request": request,
            "success": False,
            "error": "Incomplete connection data received",
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
