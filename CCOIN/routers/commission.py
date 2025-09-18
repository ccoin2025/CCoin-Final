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
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

@router.get("/pay", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def commission_payment_page(
    request: Request, 
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.commission_paid:
        return RedirectResponse(url=f"/commission/success?telegram_id={telegram_id}&already_paid=true")
    
    if not user.wallet_address:
        raise HTTPException(status_code=400, detail="Wallet not connected")
    
    return templates.TemplateResponse("commission_browser_pay.html", {
        "request": request,
        "telegram_id": telegram_id,
        "amount": COMMISSION_AMOUNT,
        "recipient": ADMIN_WALLET,
        "solana_rpc": SOLANA_RPC
    })

@router.get("/success", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def commission_success(
    request: Request, 
    telegram_id: str = Query(..., description="Telegram user ID"),
    reference: str = Query(None, description="Payment reference"),
    signature: str = Query(None, description="Transaction signature"),
    already_paid: bool = Query(False, description="Commission already paid flag"),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    success_message = "Commission payment completed successfully!" if not already_paid else "Commission already paid!"
    
    return templates.TemplateResponse("commission_success.html", {
        "request": request,
        "telegram_id": telegram_id,
        "success_message": success_message,
        "signature": signature,
        "reference": reference
    })

@router.get("/status", response_class=JSONResponse)
@limiter.limit("20/minute")
async def get_commission_status(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "commission_paid": user.commission_paid,
        "wallet_connected": bool(user.wallet_address),
        "wallet_address": user.wallet_address,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET,
        "solana_rpc": SOLANA_RPC,
        "commission_transaction_hash": getattr(user, 'commission_transaction_hash', None),
        "commission_payment_date": getattr(user, 'commission_payment_date', None)
    }

@router.post("/confirm", response_class=JSONResponse)
@limiter.limit("5/minute")
async def confirm_commission_payment(
    request: Request,
    db: Session = Depends(get_db)
):
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        reference_b58 = body.get("reference")
        signature = body.get("signature")  # Optional
        
        if not telegram_id or not reference_b58:
            raise HTTPException(status_code=400, detail="Telegram ID and reference required")
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.commission_paid:
            return {"success": True, "message": "Commission already paid", "already_paid": True}
        
        # Confirm با findReference
        reference = Pubkey.from_string(base58.decode(reference_b58))
        max_attempts = 30
        for attempt in range(max_attempts):
            response = solana_client.find_reference(reference, commitment='confirmed')
            if response.value and not response.value.meta.err:
                user.commission_paid = True
                user.commission_transaction_hash = signature or response.value.signature
                user.commission_payment_date = datetime.utcnow()
                if hasattr(user, 'commission_reference'):
                    user.commission_reference = reference_b58
                db.commit()
                return {"success": True, "message": "Commission payment confirmed successfully!", "signature": signature, "timestamp": datetime.utcnow().isoformat()}
            time.sleep(1)
        
        raise HTTPException(status_code=400, detail="Transaction not confirmed after retries")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to confirm payment: {str(e)}")

@router.get("/config", response_class=JSONResponse)
@limiter.limit("20/minute")
async def get_commission_config(request: Request):
    return {
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET,
        "solana_rpc": SOLANA_RPC,
        "network": "devnet" if "devnet" in SOLANA_RPC else "mainnet"
    }

@router.post("/webhook", response_class=JSONResponse)
@limiter.limit("10/minute")
async def commission_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    try:
        body = await request.json()
        # پردازش webhook (مثل از Phantom یا Solana notifier)
        telegram_id = body.get('telegram_id')
        reference = body.get('reference')
        # Confirm مشابه بالا
        return {"success": True, "message": "Webhook processed successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

def is_valid_solana_address(address: str) -> bool:
    allowed_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    return 32 <= len(address) <= 44 and all(c in allowed_chars for c in address)

def log_commission_transaction(telegram_id: str, signature: str, amount: float):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "telegram_id": telegram_id,
        "signature": signature,
        "amount": amount,
        "type": "commission_payment"
    }
    print(f"Commission transaction log: {log_entry}")
    return log_entry
