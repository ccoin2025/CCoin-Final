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
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET, BOT_USERNAME
from solana.rpc.api import Client
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.transaction import Transaction
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.system_program import TransferParams, transfer
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
import base58
import base64

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
    print(f"Commission browser payment for telegram_id: {telegram_id}")

    # بررسی کاربر
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        print(f"User not found: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")

    # بررسی اینکه آیا قبلاً پرداخت شده
    if user.commission_paid:
        print(f"Commission already paid for user: {telegram_id}")
        return templates.TemplateResponse("commission_success.html", {
            "request": request,
            "telegram_id": telegram_id,
            "success_message": "Commission already paid!",
            "already_paid": True
        })

    # بررسی اتصال کیف پول
    if not user.wallet_address:
        print(f"No wallet connected for user: {telegram_id}")
        raise HTTPException(status_code=400, detail="Wallet not connected")

    return templates.TemplateResponse("commission_browser_pay.html", {
        "request": request,
        "telegram_id": telegram_id,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET,
        "bot_username": BOT_USERNAME
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
    amount = COMMISSION_AMOUNT
    reference = str(Keypair().public_key)
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

@router.post("/prepare_transaction", response_class=JSONResponse)
@limiter.limit("10/minute")
async def prepare_transaction(
    request: Request,
    db: Session = Depends(get_db)
):
    """⭐ آماده‌سازی تراکنش با فی بهینه شده (حداقل فی)"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        amount = body.get("amount", COMMISSION_AMOUNT)
        recipient = body.get("recipient", ADMIN_WALLET)

        print(f"Preparing optimized transaction for telegram_id: {telegram_id}")

        # بررسی کاربر
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            print(f"User not found: {telegram_id}")
            raise HTTPException(status_code=404, detail="User not found")

        if not user.wallet_address:
            print(f"No wallet connected for user: {telegram_id}")
            raise HTTPException(status_code=400, detail="Wallet not connected")

        # ✅ ساخت تراکنش با solders در backend
        from solana.rpc.async_api import AsyncClient
        
        # ✅ استفاده از RPC endpoint خودتان (نه public endpoint)
        client = AsyncClient(SOLANA_RPC)

        # ساخت public keys
        from_pubkey = Pubkey.from_string(user.wallet_address)
        to_pubkey = Pubkey.from_string(recipient)

        # ساخت instructions
        instructions = []

        # INSTRUCTION 1: تنظیم Compute Unit Limit
        compute_limit_ix = set_compute_unit_limit(200_000)
        instructions.append(compute_limit_ix)

        # INSTRUCTION 2: تنظیم Compute Unit Price (حداقل)
        compute_price_ix = set_compute_unit_price(1)
        instructions.append(compute_price_ix)

        # INSTRUCTION 3: Transfer اصلی
        lamports = int(amount * 1_000_000_000)
        transfer_ix = transfer(
            TransferParams(
                from_pubkey=from_pubkey,
                to_pubkey=to_pubkey,
                lamports=lamports
            )
        )
        instructions.append(transfer_ix)

        # دریافت recent blockhash
        recent_blockhash_resp = await client.get_latest_blockhash()
        recent_blockhash = recent_blockhash_resp.value.blockhash

        # ساخت Message
        from solders.message import Message
        message = Message.new_with_blockhash(
            instructions,
            from_pubkey,
            recent_blockhash
        )

        # ساخت Transaction
        from solders.transaction import Transaction as SoldersTransaction
        transaction = SoldersTransaction.new_unsigned(message)

        # Serialize کردن تراکنش
        serialized_bytes = bytes(transaction)
        serialized = base64.b64encode(serialized_bytes).decode('utf-8')

        await client.close()

        print(f"✅ Transaction prepared successfully for user: {telegram_id}")

        return {
            "success": True,
            "transaction": serialized,
            "message": "Transaction prepared with minimal fee (~0.000005 SOL)"
        }

    except Exception as e:
        import traceback
        print(f"❌ Error preparing transaction: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to prepare transaction: {str(e)}")

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
    """دریافت وضعیت پرداخت commission"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        print(f"User not found for commission status: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "commission_paid": user.commission_paid,
        "wallet_connected": bool(user.wallet_address),
        "wallet_address": user.wallet_address,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET
    }


@router.get("/check_payment", response_class=JSONResponse)
@limiter.limit("30/minute")
async def check_payment(
    request: Request,
    telegram_id: str = Query(...),
    reference: str = Query(...),
    db: Session = Depends(get_db)
):
    """چک کردن پرداخت با reference"""
    try:
        from solana.rpc.api import Client
        from solders.pubkey import Pubkey
        import base58
        
        print(f"🔍 Checking payment for {telegram_id}, reference: {reference[:16]}...")
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user or not user.wallet_address:
            return {"status": "error", "message": "User or wallet not found"}

        # جستجوی تراکنش‌های اخیر admin wallet
        client = Client(SOLANA_RPC)
        
        try:
            # Decode reference
            reference_bytes = base58.b58decode(reference)
            reference_pubkey = Pubkey.from_bytes(reference_bytes)
            
            # Get signatures for reference
            signatures = client.get_signatures_for_address(
                reference_pubkey,
                limit=10
            )
            
            if signatures.value and len(signatures.value) > 0:
                # پیدا شد! بررسی تراکنش
                tx_signature = str(signatures.value[0].signature)
                
                print(f"✅ Found transaction: {tx_signature}")
                
                # بررسی جزئیات تراکنش
                tx = client.get_transaction(tx_signature, encoding="json", max_supported_transaction_version=0)
                
                if tx.value and tx.value.meta and not tx.value.meta.err:
                    print(f"✅ Transaction confirmed: {tx_signature}")
                    return {
                        "status": "confirmed",
                        "signature": tx_signature
                    }
            
            # هنوز پیدا نشد
            return {"status": "pending"}
            
        except Exception as e:
            print(f"⚠️ Check error: {e}")
            return {"status": "pending"}
            
    except Exception as e:
        print(f"❌ Error checking payment: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
