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
from solana.rpc.api import Client
from solana.rpc.commitment import Confirmed
from solders.pubkey import Pubkey
from solders.keypair import Keypair
import base58

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

@router.get("/browser/pay", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def commission_browser_pay(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """صفحه پرداخت کمیسیون در مرورگر"""
    print(f"💰 Commission browser payment for telegram_id: {telegram_id}")

    # بررسی کاربر
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        print(f"❌ User not found: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")

    # بررسی اینکه آیا قبلاً پرداخت شده
    if user.commission_paid:
        print(f"✅ Commission already paid for user: {telegram_id}")
        return templates.TemplateResponse("commission_success.html", {
            "request": request,
            "telegram_id": telegram_id,
            "success_message": "Commission already paid!",
            "already_paid": True
        })

    # لاگ وضعیت کیف پول برای دیباگ
    print(f"🔍 Wallet status for user {telegram_id}:")
    print(f"  - wallet_address: {user.wallet_address}")
    print(f"  - wallet_connected: {bool(user.wallet_address)}")

    # **حذف بررسی اجباری کیف پول** - اجازه دهید کاربر در صفحه پرداخت کیف پول وصل کند
    # if not user.wallet_address:
    #     print(f"❌ No wallet connected for user: {telegram_id}")
    #     raise HTTPException(status_code=400, detail="Wallet not connected")

    return templates.TemplateResponse("commission_browser_pay.html", {
        "request": request,
        "telegram_id": telegram_id,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET,
        "wallet_connected": bool(user.wallet_address),
        "wallet_address": user.wallet_address or ""
    })

@router.get("/pay", response_class=JSONResponse)
@limiter.limit("10/minute")
async def commission_payment_page(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """ایجاد URL برای پرداخت کمیسیون با فرمت Solana Pay"""
    print(f"Commission payment request for telegram_id: {telegram_id}")

    # بررسی کاربر
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        print(f"User not found: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")

    # بررسی اینکه آیا قبلاً پرداخت شده
    if user.commission_paid:
        print(f"Commission already paid for user: {telegram_id}")
        return RedirectResponse(url=f"/commission/success?telegram_id={telegram_id}&already_paid=true")

    # بررسی اتصال کیف پول
    if not user.wallet_address:
        print(f"No wallet connected for user: {telegram_id}")
        raise HTTPException(status_code=400, detail="Wallet not connected")

    # ایجاد URL پرداخت به سبک Solana Pay
    recipient = ADMIN_WALLET
    amount = COMMISSION_AMOUNT # e.g., 0.01 SOL
    reference = str(Keypair().public_key) # Reference یکتا برای تراکنش
    label = 'CCoin Commission'
    message = 'Payment for airdrop'
    memo = f'User: {telegram_id}'

    # ساخت دستی URL برای Solana Pay
    pay_url = f"solana:{recipient}?amount={amount}&reference={reference}&label={label}&message={message}&memo={memo}"

    print(f"Generated Solana Pay URL for user: {telegram_id}: {pay_url}")

    return {
        "pay_url": pay_url,
        "reference": reference,
        "amount": amount,
        "recipient": recipient
    }

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
    """صفحه موفقیت پرداخت"""
    print(f"🎉 Commission success page for telegram_id: {telegram_id}")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        print(f"❌ User not found in success page: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")

    # بررسی و به‌روزرسانی وضعیت پرداخت
    if signature and not user.commission_paid:
        try:
            # اگر signature وجود دارد، کمیسیون را به عنوان پرداخت شده علامت‌گذاری کن
            user.commission_paid = True
            user.commission_payment_date = datetime.utcnow()
            user.commission_transaction_hash = signature
            db.commit()
            print(f"✅ Commission marked as paid for user: {telegram_id}, signature: {signature}")
        except Exception as e:
            print(f"❌ Error updating commission status: {e}")
            db.rollback()

    # تعیین پیام موفقیت
    if user.commission_paid:
        success_message = "Commission payment completed successfully!"
        if already_paid:
            success_message = "Commission already paid!"
    else:
        success_message = "Payment verification in progress..."

    print(f"📝 Success message: {success_message}")
    print(f"💰 Commission status: {'Paid' if user.commission_paid else 'Not paid'}")

    return templates.TemplateResponse("commission_success.html", {
        "request": request,
        "telegram_id": telegram_id,
        "success_message": success_message,
        "signature": signature,
        "reference": reference,
        "commission_paid": user.commission_paid
    })

@router.get("/status", response_class=JSONResponse)
@limiter.limit("20/minute")
async def get_commission_status(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """دریافت وضعیت پرداخت commission"""
    print(f"🔍 Commission status check for telegram_id: {telegram_id}")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        print(f"❌ User not found for commission status: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")

    result = {
        "commission_paid": user.commission_paid,
        "wallet_connected": bool(user.wallet_address),
        "wallet_address": user.wallet_address,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET
    }
    
    print(f"📊 Commission status result: {result}")
    return result

# سایر توابع بدون تغییر...
