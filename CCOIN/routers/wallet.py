from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from CCOIN.database import get_db
from CCOIN.models.user import User
from datetime import datetime
import re
import os
import json
import base64

router = APIRouter()
templates = Jinja2Templates(directory="CCOIN/templates")

@router.get("/wallet/connect")
async def wallet_connect(request: Request):
    """صفحه اتصال کیف پول در مرورگر خارجی"""
    telegram_id = request.query_params.get("telegram_id")
    return templates.TemplateResponse("wallet_browser_connect.html", {
        "request": request,
        "telegram_id": telegram_id
    })

@router.get("/wallet/callback")
async def wallet_callback(request: Request, db: Session = Depends(get_db)):
    """پردازش callback از Phantom Wallet"""
    telegram_id = request.query_params.get("telegram_id")
    
    # Debug: نمایش تمام پارامترها
    print(f"[WALLET CALLBACK] All params: {dict(request.query_params)}")
    
    # پارامترهای موفقیت - همه احتمالات
    public_key = (
        request.query_params.get("public_key") or
        request.query_params.get("publicKey") or
        request.query_params.get("phantom_encryption_public_key") or
        request.query_params.get("dapp_encryption_public_key")
    )
    
    # پردازش پارامتر data اگر موجود باشد
    data_param = request.query_params.get("data")
    if data_param and not public_key:
        try:
            # تلاش برای decode کردن data
            decoded_data = json.loads(data_param)
            public_key = decoded_data.get("public_key") or decoded_data.get("publicKey")
            print(f"[WALLET CALLBACK] Extracted from data: {public_key}")
        except:
            try:
                # تلاش برای base64 decode
                decoded_bytes = base64.b64decode(data_param)
                decoded_data = json.loads(decoded_bytes)
                public_key = decoded_data.get("public_key") or decoded_data.get("publicKey")
                print(f"[WALLET CALLBACK] Extracted from base64 data: {public_key}")
            except:
                print(f"[WALLET CALLBACK] Could not decode data parameter")
    
    # پارامترهای خطا
    error_code = request.query_params.get("errorCode") or request.query_params.get("error_code")
    error_message = request.query_params.get("errorMessage") or request.query_params.get("error_message")

    print(f"[WALLET CALLBACK] telegram_id: {telegram_id}")
    print(f"[WALLET CALLBACK] public_key: {public_key}")
    print(f"[WALLET CALLBACK] error_code: {error_code}")

    if error_code:
        return templates.TemplateResponse("wallet_callback.html", {
            "request": request,
            "success": False,
            "error": f"Phantom Error {error_code}: {error_message}",
            "telegram_id": telegram_id
        })

    # موفقیت - ذخیره آدرس wallet
    if telegram_id and public_key:
        try:
            user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
            if user:
                wallet_address = public_key
                
                # اعتبارسنجی آدرس
                if is_valid_solana_address(wallet_address):
                    user.wallet_address = wallet_address
                    db.commit()
                    print(f"[WALLET CALLBACK] SUCCESS: Saved wallet {wallet_address[:8]}... for user {telegram_id}")
                    
                    return templates.TemplateResponse("wallet_callback.html", {
                        "request": request,
                        "success": True,
                        "wallet_address": wallet_address,
                        "telegram_id": telegram_id
                    })
                else:
                    print(f"[WALLET CALLBACK] ERROR: Invalid Solana address format: {wallet_address}")
                    return templates.TemplateResponse("wallet_callback.html", {
                        "request": request,
                        "success": False,
                        "error": f"Invalid wallet address format",
                        "telegram_id": telegram_id
                    })
            else:
                print(f"[WALLET CALLBACK] ERROR: User not found for telegram_id: {telegram_id}")
                
        except Exception as e:
            print(f"[WALLET CALLBACK] Database error: {e}")
            return templates.TemplateResponse("wallet_callback.html", {
                "request": request,
                "success": False,
                "error": f"Failed to save wallet: {str(e)}",
                "telegram_id": telegram_id
            })

    # پارامترهای ناقص
    print(f"[WALLET CALLBACK] ERROR: Incomplete data - telegram_id: {telegram_id}, public_key: {public_key}")
    return templates.TemplateResponse("wallet_callback.html", {
        "request": request,
        "success": False,
        "error": f"Incomplete connection data. Please try again.",
        "telegram_id": telegram_id
    })

@router.post("/wallet/disconnect")
async def wallet_disconnect(request: Request, db: Session = Depends(get_db)):
    """حذف اتصال wallet"""
    telegram_id = request.query_params.get("telegram_id")
    
    if not telegram_id:
        return JSONResponse({
            "success": False,
            "error": "No telegram_id provided"
        })
    
    try:
        user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
        if user:
            old_address = user.wallet_address
            user.wallet_address = None  # حذف آدرس
            db.commit()
            
            print(f"[WALLET DISCONNECT] Removed wallet {old_address} for user {telegram_id}")
            
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
        print(f"[WALLET DISCONNECT] Error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        })

@router.get("/api/wallet/status")
async def wallet_status(telegram_id: str, db: Session = Depends(get_db)):
    """بررسی وضعیت اتصال wallet"""
    try:
        user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
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
        user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
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
        user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
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

def is_valid_solana_address(address: str) -> bool:
    """اعتبارسنجی آدرس Solana"""
    if not address or not isinstance(address, str):
        return False
    
    # آدرس Solana باید 32-44 کاراکتر باشد و فقط حروف و اعداد base58
    pattern = r'^[1-9A-HJ-NP-Za-km-z]{32,44}$'
    return bool(re.match(pattern, address))
