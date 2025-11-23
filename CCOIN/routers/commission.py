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
import asyncio
import structlog

logger = structlog.get_logger()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

memory_cache = {}

def get_from_cache(key: str):
    """دریافت از memory cache"""
    if key in memory_cache:
        value, expiry = memory_cache[key]
        if time.time() < expiry:
            return value
        else:
            del memory_cache[key]
    return None

def set_in_cache(key: str, value, ttl: int):
    """ذخیره در memory cache"""
    memory_cache[key] = (value, time.time() + ttl)

def clear_cache(key: str):
    """پاک کردن cache"""
    if key in memory_cache:
        del memory_cache[key]

@router.get("/browser/pay", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def commission_browser_pay(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Commission payment page in browser"""
    logger.info("Commission browser payment", extra={"telegram_id": telegram_id})

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error("User not found", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    if user.commission_paid:
        logger.info("Commission already paid", extra={"telegram_id": telegram_id})
        return templates.TemplateResponse("commission_success.html", {
            "request": request,
            "telegram_id": telegram_id,
            "success_message": "Commission already paid!",
            "already_paid": True,
            "bot_username": BOT_USERNAME
        })

    if not user.wallet_address:
        logger.warning("No wallet connected", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=400, detail="Wallet not connected. Please connect your wallet first.")

    return templates.TemplateResponse("commission_browser_pay.html", {
        "request": request,
        "telegram_id": telegram_id,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET,
        "bot_username": BOT_USERNAME,
        "solana_rpc": SOLANA_RPC
    })

@router.get("/success", response_class=HTMLResponse)
async def commission_success(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Commission success page"""
    logger.info("Commission success page", extra={"telegram_id": telegram_id})

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return templates.TemplateResponse("commission_success.html", {
        "request": request,
        "telegram_id": telegram_id,
        "bot_username": BOT_USERNAME
    })

@router.get("/check_status", response_class=JSONResponse)
@limiter.limit("20/minute")
async def check_commission_status(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Check commission payment status"""
    logger.info("Checking commission status", extra={"telegram_id": telegram_id})

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
    """Confirm commission payment with blockchain verification"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        signature = body.get("signature")

        logger.info("Commission confirmation request", extra={
            "telegram_id": telegram_id,
            "signature": signature
        })

        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        if not signature:
            raise HTTPException(status_code=400, detail="Missing transaction signature")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            logger.error("User not found", extra={"telegram_id": telegram_id})
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            logger.info("Commission already paid", extra={"telegram_id": telegram_id})
            return {
                "success": True,
                "message": "Commission already confirmed",
                "already_paid": True
            }

        if not user.wallet_address:
            logger.error("No wallet connected", extra={"telegram_id": telegram_id})
            raise HTTPException(status_code=400, detail="No wallet connected")

        # ✅ Verify transaction on blockchain
        client = Client(SOLANA_RPC)
        max_retries = 5
        retry_delay = 2
        transaction_confirmed = False

        for attempt in range(max_retries):
            try:
                logger.info(f"Verifying transaction (attempt {attempt + 1}/{max_retries})", extra={"signature": signature})

                tx = client.get_transaction(
                    signature,
                    encoding="json",
                    max_supported_transaction_version=0
                )

                if tx.value:
                    if tx.value.meta and tx.value.meta.err:
                        logger.error("Transaction failed on blockchain", extra={"error": tx.value.meta.err})
                        raise HTTPException(status_code=400, detail="Transaction failed on blockchain")

                    transaction_confirmed = True
                    logger.info("Transaction confirmed on blockchain", extra={"signature": signature})
                    break
                else:
                    logger.warning(f"Transaction not found yet (attempt {attempt + 1})")

                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 1.5
                    else:
                        logger.error(f"Transaction not found after {max_retries} attempts")
                        raise HTTPException(status_code=404, detail="Transaction not found on blockchain")

            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Verification attempt {attempt + 1} failed", extra={"error": str(e)})
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 1.5
                else:
                    raise HTTPException(status_code=500, detail=f"Transaction verification failed: {str(e)}")

        if transaction_confirmed:
            user.commission_paid = True
            user.commission_transaction_hash = signature
            user.commission_payment_date = datetime.utcnow()
            db.commit()

            logger.info("Commission confirmed successfully", extra={
                "telegram_id": telegram_id,
                "transaction_hash": signature
            })

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
        logger.error("Commission confirmation error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Confirmation failed: {str(e)}")

@router.post("/verify_payment_auto", response_class=JSONResponse)
@limiter.limit("10/minute")
async def verify_payment_auto(
    request: Request,
    db: Session = Depends(get_db)
):
    """Auto-detect payment by checking user wallet transactions"""
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

        # ✅ محدودیت 5 تلاش
        cache_key = f'payment_check_attempts_{telegram_id}'
        attempt_count = get_from_cache(cache_key)

        if attempt_count is None:
            attempt_count = 0

        if attempt_count >= 5:
            return {
                "success": True,
                "payment_found": False,
                "message": "Maximum verification attempts reached. Please wait 2 minutes and refresh the page.",
                "max_attempts_reached": True
            }

        # افزایش تعداد تلاش‌ها
        set_in_cache(cache_key, attempt_count + 1, ttl=120)  # 2 دقیقه

        client = AsyncClient(SOLANA_RPC)

        try:
            user_pubkey = Pubkey.from_string(user.wallet_address)

            logger.info(f"Payment check attempt {attempt_count + 1}/5", extra={"telegram_id": telegram_id})

            signatures_response = await client.get_signatures_for_address(
                user_pubkey,
                limit=10
            )

            if not signatures_response.value:
                await client.close()
                return {
                    "success": True,
                    "payment_found": False,
                    "message": "No transactions found",
                    "attempts_remaining": 5 - (attempt_count + 1)
                }

            expected_lamports = int(COMMISSION_AMOUNT * 1_000_000_000)
            tolerance = int(0.015 * 1_000_000_000)

            for idx, sig_info in enumerate(signatures_response.value):
                try:
                    if idx > 0:
                        await asyncio.sleep(0.5)

                    sig = str(sig_info.signature)

                    tx_response = await client.get_transaction(
                        sig_info.signature,
                        encoding="json",
                        max_supported_transaction_version=0
                    )

                    if not tx_response or not tx_response.value:
                        continue

                    tx_obj = tx_response.value

                    import json
                    tx_json_str = tx_obj.to_json()
                    tx = json.loads(tx_json_str)

                    meta = tx.get('meta')
                    if not meta or meta.get('err'):
                        continue

                    pre_balances = meta.get('preBalances', [])
                    post_balances = meta.get('postBalances', [])

                    if not pre_balances or not post_balances:
                        continue

                    transaction = tx.get('transaction', {})
                    message = transaction.get('message', {})
                    account_keys = message.get('accountKeys', [])

                    if not account_keys or ADMIN_WALLET not in account_keys:
                        continue

                    for acc_idx in range(min(len(pre_balances), len(post_balances), len(account_keys))):
                        acc_key = account_keys[acc_idx]

                        if acc_key == ADMIN_WALLET:
                            balance_change = post_balances[acc_idx] - pre_balances[acc_idx]

                            if expected_lamports - tolerance <= balance_change <= expected_lamports + tolerance:
                                logger.info("Payment found!", extra={
                                    "telegram_id": telegram_id,
                                    "signature": sig,
                                    "expected": expected_lamports,
                                    "found": balance_change
                                })

                                user.commission_paid = True
                                user.commission_transaction_hash = sig
                                user.commission_payment_date = datetime.utcnow()
                                db.commit()

                                clear_cache(cache_key)

                                await client.close()

                                return {
                                    "success": True,
                                    "payment_found": True,
                                    "message": "Payment verified successfully!",
                                    "transaction_hash": sig,
                                    "redirect_url": f"https://t.me/{BOT_USERNAME}"
                                }

                except Exception as tx_error:
                    logger.warning("Error processing transaction", extra={"error": str(tx_error)})
                    continue

            await client.close()

            return {
                "success": True,
                "payment_found": False,
                "message": "No matching payment found in recent transactions",
                "attempts_remaining": 5 - (attempt_count + 1)
            }

        except Exception as e:
            await client.close()
            raise e

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Payment verification error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.get('/redirect_to_phantom')
async def redirect_to_phantom(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID")
):
    """Redirect to payment page - این endpoint دیگر لازم نیست"""
    logger.info("Redirecting to payment page", extra={"telegram_id": telegram_id})
    
    # به همان صفحه commission_browser_pay برگرداندن
    return RedirectResponse(url=f"/commission/browser/pay?telegram_id={telegram_id}")
