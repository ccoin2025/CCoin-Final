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
from solders.message import MessageV0, Message
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
    reference = str(Keypair().pubkey())  # ✅ تغییر از public_key به pubkey()
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


# ✅ اضافه شده: GET endpoint برای Transaction Request
@router.get("/transaction_request", response_class=JSONResponse)
@limiter.limit("20/minute")
async def transaction_request_get(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """
    GET endpoint برای Solana Pay Transaction Request
    Phantom ابتدا این را صدا می‌زند تا label و icon را دریافت کند
    """
    print(f"📥 Transaction request GET for telegram_id: {telegram_id}")
    
    # بررسی کاربر
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.commission_paid:
        raise HTTPException(status_code=400, detail="Commission already paid")
    
    if not user.wallet_address:
        raise HTTPException(status_code=400, detail="Wallet not connected")
    
    # برگرداندن label و icon طبق مستندات Solana Pay
    base_url = str(request.base_url).rstrip('/')
    return {
        "label": "CCoin Commission Payment",
        "icon": f"{base_url}/static/images/icon-512x512.png"
    }


# ✅ اضافه شده: POST endpoint برای Transaction Request
@router.post("/transaction_request", response_class=JSONResponse)
@limiter.limit("20/minute")
async def transaction_request_post(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """
    POST endpoint برای Solana Pay Transaction Request
    Phantom wallet address کاربر را ارسال می‌کند و transaction را دریافت می‌کند
    """
    try:
        body = await request.json()
        account = body.get("account")  # wallet address کاربر از Phantom
        
        print(f"📥 Transaction request POST for telegram_id: {telegram_id}, account: {account}")
        
        # بررسی کاربر
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.commission_paid:
            raise HTTPException(status_code=400, detail="Commission already paid")
        
        # ساخت transaction
        client = AsyncClient(SOLANA_RPC)
        
        # ساخت public keys
        from_pubkey = Pubkey.from_string(account)  # wallet کاربر از Phantom
        to_pubkey = Pubkey.from_string(ADMIN_WALLET)
        
        # ساخت reference keypair برای tracking
        reference_keypair = Keypair()
        reference_pubkey = reference_keypair.pubkey()  # ✅ استفاده از pubkey()
        
        # ساخت instructions
        instructions = []
        
        # INSTRUCTION 1: تنظیم Compute Unit Limit
        compute_limit_ix = set_compute_unit_limit(200_000)
        instructions.append(compute_limit_ix)
        
        # INSTRUCTION 2: تنظیم Compute Unit Price
        compute_price_ix = set_compute_unit_price(1)
        instructions.append(compute_price_ix)
        
        # INSTRUCTION 3: Transfer اصلی
        lamports = int(COMMISSION_AMOUNT * 1_000_000_000)
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
        message = Message.new_with_blockhash(
            instructions,
            from_pubkey,  # fee payer
            recent_blockhash
        )
        
        # ساخت Transaction
        from solders.transaction import Transaction as SoldersTransaction
        transaction = SoldersTransaction.new_unsigned(message)
        
        # Serialize کردن
        serialized_bytes = bytes(transaction)
        serialized = base64.b64encode(serialized_bytes).decode('utf-8')
        
        await client.close()
        
        print(f"✅ Transaction created successfully for user: {telegram_id}")
        print(f"   Reference: {str(reference_pubkey)}")
        
        # برگرداندن transaction طبق مستندات Solana Pay
        return {
            "transaction": serialized,
            "message": f"Commission payment: {COMMISSION_AMOUNT} SOL"
        }
        
    except Exception as e:
        import traceback
        print(f"❌ Error creating transaction: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")


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

@router.post("/confirm_commission", response_class=JSONResponse)
@limiter.limit("20/minute")
async def confirm_commission(
    request: Request,
    db: Session = Depends(get_db)
):
    """✅ تایید پرداخت کمیسیون و آپدیت دیتابیس"""
    try:
        body = await request.json()
        signature = body.get("signature")
        telegram_id = body.get("telegramId")
        amount = body.get("amount")
        recipient = body.get("recipient")

        print(f"✅ Confirming commission for telegram_id: {telegram_id}, signature: {signature}")

        # بررسی کاربر
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # بررسی اینکه قبلاً پرداخت نشده باشد
        if user.commission_paid:
            return {
                "success": True,
                "message": "Commission already confirmed",
                "already_paid": True
            }

        # تایید تراکنش در بلاکچین
        client = Client(SOLANA_RPC)

        try:
            # دریافت تراکنش
            tx = client.get_transaction(
                signature,
                encoding="json",
                max_supported_transaction_version=0
            )

            if not tx.value:
                return {"success": False, "message": "Transaction not found"}

            # بررسی خطا
            if tx.value.meta and tx.value.meta.err:
                return {"success": False, "message": "Transaction failed on blockchain"}

            # ✅ آپدیت دیتابیس با نام فیلدهای صحیح
            user.commission_paid = True
            user.commission_transaction_hash = signature
            user.commission_payment_date = datetime.utcnow()
            db.commit()

            print(f"✅ Commission confirmed successfully for user: {telegram_id}")

            return {
                "success": True,
                "message": "Commission payment confirmed",
                "signature": signature
            }

        except Exception as e:
            print(f"❌ Error verifying transaction: {e}")
            return {"success": False, "message": f"Verification error: {str(e)}"}

    except Exception as e:
        print(f"❌ Error confirming commission: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

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

    print(f"📊 Commission status for {telegram_id}: paid={user.commission_paid}, wallet={bool(user.wallet_address)}")

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
        print(f"❌ Error in check_payment: {e}")
        return {"status": "error", "message": str(e)}
