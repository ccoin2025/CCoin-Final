from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from CCOIN.database import get_db
from CCOIN.models.user import User
from datetime import datetime
import re
import os
import base58
from tweetnacl import box  # نیاز به pip install tweetnacl-python یا مشابه، اما فرض installed

router = APIRouter()
templates = Jinja2Templates(directory="CCOIN/templates")

@router.get("/wallet/browser/connect")
async def wallet_browser_connect(request: Request):
    telegram_id = request.query_params.get("telegram_id")
    return templates.TemplateResponse("wallet_browser_connect.html", {
        "request": request,
        "telegram_id": telegram_id
    })

@router.get("/wallet-browser-connect")
async def wallet_browser_connect_old(request: Request):
    return templates.TemplateResponse("wallet_browser_connect.html", {"request": request})

@router.get("/api/wallet/status")
async def wallet_status(telegram_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
    if user and user.wallet_address:
        return JSONResponse({"connected": True, "address": user.wallet_address, "success": True})
    return JSONResponse({"connected": False, "address": None, "success": True})

@router.get("/api/tasks/status")
async def tasks_status(telegram_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
    if not user:
        return JSONResponse({"tasks_completed": False, "friends_invited": False, "success": True})
    
    tasks_completed = any(task.completed for task in user.tasks) if user.tasks else False
    friends_invited = len(user.referrals) > 0 if user.referrals else False
    
    return JSONResponse({"tasks_completed": tasks_completed, "friends_invited": friends_invited, "success": True})

@router.get("/api/commission/status")
async def commission_status(telegram_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
    if user and user.commission_paid:
        return JSONResponse({
            "paid": True,
            "payment_date": user.commission_payment_date.isoformat() if user.commission_payment_date else None,
            "transaction_hash": user.commission_transaction_hash,
            "success": True
        })
    return JSONResponse({"paid": False, "payment_date": None, "transaction_hash": None, "success": True})

@router.post("/api/commission/pay")
async def pay_commission(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    telegram_id = str(data.get("telegram_id"))

    if not telegram_id:
        return JSONResponse({"success": False, "error": "Missing telegram_id"})

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        return JSONResponse({"success": False, "error": "User not found"})

    if user.commission_paid:
        return JSONResponse({"success": False, "error": "Commission already paid"})

    if not user.wallet_address:
        return JSONResponse({"success": False, "error": "Wallet not connected"})

    commission_amount = 0.01
    recipient_address = os.getenv("ADMIN_WALLET", "So11111111111111111111111111111111111111112")

    callback_url = f"{request.base_url}commission/callback?telegram_id={telegram_id}"

    return JSONResponse({
        "success": True,
        "amount": commission_amount,
        "recipient": recipient_address,
        "reference": telegram_id,
        "callback_url": callback_url
    })

@router.get("/commission/browser/pay")
async def commission_browser_pay(request: Request):
    telegram_id = request.query_params.get("telegram_id")
    return templates.TemplateResponse("commission_browser_pay.html", {
        "request": request,
        "telegram_id": telegram_id
    })

@router.get("/commission/callback")
async def commission_callback(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.query_params.get("telegram_id")
    reference = request.query_params.get("reference")
    signature = request.query_params.get("signature")

    if not telegram_id:
        return templates.TemplateResponse("commission_callback.html", {"request": request, "success": False, "error": "Missing telegram_id", "telegram_id": telegram_id})

    # Call /confirm_commission (internal)
    # فرض: logic در backend، template فقط display

@router.post("/api/wallet/save")
async def save_wallet(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    telegram_id = str(data.get("telegram_id"))
    wallet_address = data.get("wallet_address")

    if not telegram_id or not wallet_address:
        return JSONResponse({"success": False, "error": "Missing telegram_id or wallet_address"})

    if not is_valid_solana_address(wallet_address):
        return JSONResponse({"success": False, "error": "Invalid Solana wallet address format"})

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user:
        user.wallet_address = wallet_address
        db.commit()
        return JSONResponse({"success": True, "message": "Wallet connected successfully", "address": wallet_address})
    return JSONResponse({"success": False, "error": "User not found"})

@router.post("/api/wallet/disconnect")
async def disconnect_wallet(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    telegram_id = str(data.get("telegram_id"))

    if not telegram_id:
        return JSONResponse({"success": False, "error": "Missing telegram_id"})

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user:
        user.wallet_address = None
        db.commit()
        return JSONResponse({"success": True, "message": "Wallet disconnected successfully"})
    return JSONResponse({"success": False, "error": "User not found"})

def is_valid_solana_address(address: str) -> bool:
    pattern = r'^[1-9A-HJ-NP-Za-km-z]{32,44}$'
    return bool(re.match(pattern, address))

@router.get("/wallet/callback")
async def wallet_callback(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.query_params.get("telegram_id")

    phantom_enc_key = request.query_params.get("phantom_encryption_public_key")
    nonce = request.query_params.get("nonce")
    data = request.query_params.get("data")
    error_code = request.query_params.get("errorCode")
    error_message = request.query_params.get("errorMessage")

    if error_code:
        return templates.TemplateResponse("wallet_callback.html", {
            "request": request,
            "success": False,
            "error": f"Phantom Error {error_code}: {error_message}",
            "telegram_id": telegram_id
        })

    if not phantom_enc_key or not nonce or not data:
        return templates.TemplateResponse("wallet_callback.html", {
            "request": request,
            "success": False,
            "error": "Incomplete connection data received",
            "telegram_id": telegram_id
        })

    try:
        # Decrypt (فرض dapp_private_key از session یا Redis)
        # برای ساده، فرض stored in Redis with key 'dapp_key:{telegram_id}'
        dapp_private_key_b58 = redis_client.get(f"dapp_key:{telegram_id}") if redis_client else None
        if not dapp_private_key_b58:
            raise ValueError("Missing dapp private key")

        dapp_private_key = base58.decode(dapp_private_key_b58)
        phantom_pub_key = base58.decode(phantom_enc_key)
        
        shared_secret = box.before(phantom_pub_key, dapp_private_key)
        decrypted = box.open.after(base58.decode(data), base58.decode(nonce), shared_secret)
        
        json_data = json.loads(decrypted.decode('utf-8'))
        wallet_address = json_data['public_key']  # از decrypted

        user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
        if user:
            user.wallet_address = wallet_address
            db.commit()
            # Delete temp key
            if redis_client:
                redis_client.delete(f"dapp_key:{telegram_id}")
            
            return templates.TemplateResponse("wallet_callback.html", {
                "request": request,
                "success": True,
                "wallet_address": wallet_address,
                "telegram_id": telegram_id
            })

    except Exception as e:
        return templates.TemplateResponse("wallet_callback.html", {
            "request": request,
            "success": False,
            "error": f"Failed to process wallet data: {str(e)}",
            "telegram_id": telegram_id
        })
