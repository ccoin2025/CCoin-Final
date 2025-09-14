from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

@router.get("/pay", response_class=HTMLResponse)
async def commission_payment_page(request: Request, telegram_id: str, db: Session = Depends(get_db)):
    """صفحه پرداخت commission در مرورگر خارجی"""
    
    # بررسی کاربر
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.commission_paid:
        # اگر قبلاً پرداخت شده، به صفحه موفقیت هدایت کن
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
async def commission_success(
    request: Request, 
    telegram_id: str,
    reference: str = None, 
    signature: str = None,
    already_paid: bool = False,
    db: Session = Depends(get_db)
):
    """صفحه موفقیت پرداخت"""
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    success_message = "Commission payment completed successfully!" 
    if already_paid:
        success_message = "Commission already paid!"
    
    return templates.TemplateResponse("commission_success.html", {
        "request": request,
        "telegram_id": telegram_id,
        "success_message": success_message,
        "signature": signature
    })
