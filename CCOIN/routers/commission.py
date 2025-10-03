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
from solders.pubkey import Pubkey
import time

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
    print(f"💳 Commission browser payment for telegram_id: {telegram_id}")

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
            "already_paid": True,
            "bot_username": BOT_USERNAME
        })

    # بررسی اتصال کیف پول
    if not user.wallet_address:
        print(f"⚠️ No wallet connected for user: {telegram_id}")
        raise HTTPException(status_code=400, detail="Wallet not connected. Please connect your wallet first.")

    return templates.TemplateResponse("commission_browser_pay.html", {
        "request": request,
        "telegram_id": telegram_id,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET,
        "bot_username": BOT_USERNAME
    })


@router.get("/check_status", response_class=JSONResponse)
@limiter.limit("20/minute")
async def check_commission_status(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """✅ بررسی وضعیت پرداخت کمیسیون"""
    print(f"📊 Checking commission status for: {telegram_id}")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "commission_paid": user.commission_paid,
        "wallet_connected": bool(user.wallet_address),
        "wallet_address": user.wallet_address,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET,
        "payment_date": user.commission_payment_date.isoformat() if user.commission_payment_date else None,
        "transaction_hash": user.commission_transaction_hash
    }


@router.post("/confirm_commission", response_class=JSONResponse)
@limiter.limit("5/minute")
async def confirm_commission(
    request: Request,
    db: Session = Depends(get_db)
):
    """✅ تایید پرداخت کمیسیون"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        signature = body.get("signature")
        amount = body.get("amount")
        recipient = body.get("recipient")

        print(f"📥 Commission confirmation request:")
        print(f"   telegram_id: {telegram_id}")
        print(f"   signature: {signature}")
        print(f"   amount: {amount}")
        print(f"   recipient: {recipient}")

        # Validation
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        if not signature:
            raise HTTPException(status_code=400, detail="Missing transaction signature")

        # بررسی کاربر
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            print(f"❌ User not found: {telegram_id}")
            raise HTTPException(status_code=404, detail="User not found")

        # بررسی اینکه قبلاً پرداخت نشده باشد
        if user.commission_paid:
            print(f"✅ Commission already paid for user: {telegram_id}")
            return {
                "success": True,
                "message": "Commission already confirmed",
                "already_paid": True
            }

        # بررسی اتصال کیف پول
        if not user.wallet_address:
            print(f"❌ No wallet connected for user: {telegram_id}")
            raise HTTPException(status_code=400, detail="No wallet connected")

        # ✅ تایید تراکنش در بلاکچین با Retry
        client = Client(SOLANA_RPC)
        max_retries = 5
        retry_delay = 2

        transaction_confirmed = False

        for attempt in range(max_retries):
            try:
                print(f"🔍 Verifying transaction (attempt {attempt + 1}/{max_retries}): {signature}")

                tx = client.get_transaction(
                    signature,
                    encoding="json",
                    max_supported_transaction_version=0
                )

                if tx.value:
                    # بررسی خطا
                    if tx.value.meta and tx.value.meta.err:
                        print(f"❌ Transaction failed on blockchain: {tx.value.meta.err}")
                        raise HTTPException(status_code=400, detail="Transaction failed on blockchain")

                    # ✅ تراکنش موفق
                    transaction_confirmed = True
                    print(f"✅ Transaction confirmed on blockchain")
                    break
                else:
                    print(f"⚠️ Transaction not found yet (attempt {attempt + 1})")

                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 1.5  # Exponential backoff
                    else:
                        print(f"❌ Transaction not found after {max_retries} attempts")
                        raise HTTPException(status_code=404, detail="Transaction not found on blockchain")

            except HTTPException:
                raise
            except Exception as e:
                print(f"⚠️ Verification attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 1.5
                else:
                    raise HTTPException(status_code=500, detail=f"Transaction verification failed: {str(e)}")

        if transaction_confirmed:
            # ✅ آپدیت دیتابیس
            user.commission_paid = True
            user.commission_transaction_hash = signature
            user.commission_payment_date = datetime.utcnow()
            db.commit()

            print(f"✅ Commission confirmed successfully for user: {telegram_id}")
            print(f"   Transaction hash: {signature}")

            return {
                "success": True,
                "message": "Commission confirmed successfully!",
                "transaction_hash": signature,
                "redirect_url": f"https://t.me/{BOT_USERNAME}"
            }
        else:
            raise HTTPException(status_code=500, detail="Transaction confirmation failed")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Commission confirmation error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Confirmation failed: {str(e)}")


@router.post("/verify_payment_auto", response_class=JSONResponse)
@limiter.limit("10/minute")
async def verify_payment_auto(
    request: Request,
    db: Session = Depends(get_db)
):
    """🔍 Auto-detect payment by checking recent transactions to admin wallet"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")

        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            return {
                "success": True,
                "payment_found": True,
                "message": "Commission already paid",
                "transaction_hash": user.commission_transaction_hash
            }

        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="No wallet connected")

        # بررسی تراکنش‌های اخیر به admin wallet
        client = AsyncClient(SOLANA_RPC)
        
        try:
            admin_pubkey = Pubkey.from_string(ADMIN_WALLET)
            user_pubkey = Pubkey.from_string(user.wallet_address)

            print(f"🔍 Checking payments to admin wallet from user: {telegram_id}")
            print(f"   User wallet: {user.wallet_address}")
            print(f"   Admin wallet: {ADMIN_WALLET}")

            # دریافت تراکنش‌های اخیر admin wallet
            signatures_response = await client.get_signatures_for_address(
                admin_pubkey,
                limit=30  # آخرین 30 تراکنش
            )

            if not signatures_response.value:
                await client.close()
                print(f"⚠️ No recent transactions found for admin wallet")
                return {
                    "success": True,
                    "payment_found": False,
                    "message": "No recent transactions found"
                }

            expected_lamports = int(COMMISSION_AMOUNT * 1_000_000_000)
            tolerance = int(0.005 * 1_000_000_000)  # 0.005 SOL tolerance

            print(f"   Expected amount: {expected_lamports / 1_000_000_000} SOL")
            print(f"   Checking {len(signatures_response.value)} recent transactions...")

            # بررسی هر تراکنش
            for idx, sig_info in enumerate(signatures_response.value):
                try:
                    tx = await client.get_transaction(
                        sig_info.signature,
                        encoding="json",
                        max_supported_transaction_version=0
                    )

                    if not tx.value or not tx.value.meta or tx.value.meta.err:
                        continue

                    meta = tx.value.meta
                    transaction = tx.value.transaction

                    # بررسی balance changes
                    if hasattr(meta, 'pre_balances') and hasattr(meta, 'post_balances'):
                        # Get account keys
                        account_keys = []
                        if hasattr(transaction.value, 'message'):
                            if hasattr(transaction.value.message, 'account_keys'):
                                account_keys = transaction.value.message.account_keys

                        # بررسی هر account
                        for acc_idx, (pre, post) in enumerate(zip(meta.pre_balances, meta.post_balances)):
                            # اگر این account پول دریافت کرده
                            if post > pre:
                                received = post - pre
                                
                                # بررسی مقدار (با tolerance)
                                if abs(received - expected_lamports) <= tolerance:
                                    # بررسی اینکه این account، admin wallet هست
                                    if acc_idx < len(account_keys):
                                        if str(account_keys[acc_idx]) == ADMIN_WALLET:
                                            print(f"✅ Payment detected!")
                                            print(f"   Signature: {sig_info.signature}")
                                            print(f"   Amount received: {received / 1_000_000_000} SOL")
                                            print(f"   Expected: {expected_lamports / 1_000_000_000} SOL")
                                            
                                            # آپدیت دیتابیس
                                            user.commission_paid = True
                                            user.commission_transaction_hash = str(sig_info.signature)
                                            user.commission_payment_date = datetime.utcnow()
                                            db.commit()

                                            await client.close()

                                            return {
                                                "success": True,
                                                "payment_found": True,
                                                "message": "Payment detected and confirmed!",
                                                "transaction_hash": str(sig_info.signature),
                                                "amount": received / 1_000_000_000
                                            }

                except Exception as e:
                    print(f"⚠️ Error checking transaction {sig_info.signature}: {e}")
                    continue

            await client.close()

            print(f"⚠️ No matching payment found in {len(signatures_response.value)} recent transactions")

            return {
                "success": True,
                "payment_found": False,
                "message": "No matching payment found in recent transactions"
            }

        except Exception as e:
            await client.close()
            raise e

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Auto-verify error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.post("/verify_manual", response_class=JSONResponse)
@limiter.limit("3/minute")
async def verify_commission_manual(
    request: Request,
    db: Session = Depends(get_db)
):
    """🔍 بررسی manual تراکنش‌های اخیر کاربر"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")

        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="No wallet connected")

        if user.commission_paid:
            return {
                "success": True,
                "message": "Commission already paid",
                "already_paid": True
            }

        # بررسی تراکنش‌های اخیر
        client = AsyncClient(SOLANA_RPC)
        user_pubkey = Pubkey.from_string(user.wallet_address)
        admin_pubkey = Pubkey.from_string(ADMIN_WALLET)

        # دریافت signatures اخیر
        signatures = await client.get_signatures_for_address(user_pubkey, limit=10)

        expected_amount = int(COMMISSION_AMOUNT * 1_000_000_000)  # Convert to lamports

        for sig_info in signatures.value:
            try:
                tx = await client.get_transaction(
                    sig_info.signature,
                    encoding="json",
                    max_supported_transaction_version=0
                )

                if tx.value and tx.value.meta and not tx.value.meta.err:
                    # بررسی transfer به admin wallet
                    post_balances = tx.value.meta.post_balances
                    pre_balances = tx.value.meta.pre_balances

                    # TODO: بررسی دقیق‌تر مقدار transfer

                    # اگر تراکنش معتبر بود
                    user.commission_paid = True
                    user.commission_transaction_hash = str(sig_info.signature)
                    user.commission_payment_date = datetime.utcnow()
                    db.commit()

                    await client.close()

                    return {
                        "success": True,
                        "message": "Payment verified successfully!",
                        "transaction_hash": str(sig_info.signature)
                    }

            except Exception as e:
                print(f"Error checking transaction {sig_info.signature}: {e}")
                continue

        await client.close()

        return {
            "success": False,
            "message": "No valid payment found in recent transactions"
        }

    except Exception as e:
        print(f"Manual verification error: {e}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")
