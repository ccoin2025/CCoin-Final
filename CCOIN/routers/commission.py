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
from solana.publickey import PublicKey  # Added for Solana Pay
from solana.keypair import Keypair
from solana_pay import encodeURL, BigNumber  # Assume installed or import

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

@router.get("/pay", response_class=JSONResponse)  # Changed to JSON for JS integration
@limiter.limit("10/minute")
async def commission_payment_page(
    request: Request, 
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """ایجاد Solana Pay URL برای پرداخت"""
    
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
    
    # Create Solana Pay URL
    recipient = PublicKey(ADMIN_WALLET)
    amount = BigNumber(COMMISSION_AMOUNT)
    reference = Keypair().public_key
    label = 'CCoin Commission'
    message = 'Payment for airdrop'
    memo = f'User: {telegram_id}'
    
    pay_url = encodeURL({
        'recipient': recipient,
        'amount': amount,
        'reference': reference,
        'label': label,
        'message': message,
        'memo': memo
    })
    
    print(f"Generated Solana Pay URL for user: {telegram_id}")
    
    return {
        "pay_url": pay_url,
        "reference": str(reference),
        "amount": COMMISSION_AMOUNT,
        "recipient": ADMIN_WALLET
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
    
    print(f"Commission success page for telegram_id: {telegram_id}")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    success_message = "Commission payment completed successfully!" 
    if already_paid:
        success_message = "Commission already paid!"
    
    print(f"Success message: {success_message}")
    
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
    """دریافت وضعیت پرداخت commission برای کاربر"""
    
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
    """تأیید پرداخت commission"""
    
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        signature = body.get("signature")
        reference = body.get("reference")
        
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Telegram ID required")
            
        if not signature:
            raise HTTPException(status_code=400, detail="Transaction signature required")
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.commission_paid:
            return {
                "success": True,
                "message": "Commission already paid",
                "already_paid": True
            }
        
        # Confirm with reference (Solana Pay)
        if reference:
            from solana.rpc.commitment import Confirmed
            sigs = solana_client.find_reference(Pubkey.from_string(reference), commitment=Confirmed)
            if sigs.value:
                signature = sigs.value[0].signature  # Override if needed
        
        # به‌روزرسانی وضعیت کاربر
        user.commission_paid = True
        user.commission_transaction_hash = signature
        user.commission_payment_date = datetime.utcnow()
        
        # اضافه کردن reference اگر موجود باشد
        if reference and hasattr(user, 'commission_reference'):
            user.commission_reference = reference
        
        db.commit()
        
        print(f"Commission payment confirmed for user {telegram_id} with signature {signature}")
        
        log_commission_transaction(telegram_id, signature, COMMISSION_AMOUNT)
        
        return {
            "success": True,
            "message": "Commission payment confirmed successfully!",
            "signature": signature,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        print(f"Error confirming commission payment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to confirm payment: {str(e)}")

@router.get("/config", response_class=JSONResponse)
@limiter.limit("20/minute")
async def get_commission_config(request: Request):
    """دریافت تنظیمات پرداخت commission"""
    
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
    """Webhook برای دریافت اطلاعات پرداخت از سرویس‌های خارجی"""
    
    try:
        body = await request.json()
        print(f"Commission webhook received: {body}")
        
        # پردازش webhook data
        # این قسمت بسته به سرویس ارائه‌دهنده پرداخت متفاوت است
        
        return {
            "success": True,
            "message": "Webhook processed successfully"
        }
        
    except Exception as e:
        print(f"Commission webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

# Helper function برای بررسی اعتبار آدرس Solana
def is_valid_solana_address(address: str) -> bool:
    """بررسی اعتبار آدرس کیف پول Solana"""
    if not address or not isinstance(address, str):
        return False
    
    # بررسی طول آدرس (32-44 کاراکتر معمولاً)
    if len(address) < 32 or len(address) > 44:
        return False
    
    # بررسی کاراکترهای مجاز (Base58)
    allowed_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    return all(c in allowed_chars for c in address)

# Helper function برای لاگ تراکنش‌ها
def log_commission_transaction(telegram_id: str, signature: str, amount: float):
    """ثبت لاگ تراکنش commission"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "telegram_id": telegram_id,
        "signature": signature,
        "amount": amount,
        "type": "commission_payment"
    }
    print(f"Commission transaction log: {log_entry}")
    
    # می‌توانید این لاگ‌ها را در فایل یا دیتابیس ذخیره کنید (e.g., to file)
    with open('commission_logs.txt', 'a') as f:
        f.write(str(log_entry) + '\n')
    
    return log_entry
