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
    """Commission payment page in browser"""
    print(f"💳 Commission browser payment for telegram_id: {telegram_id}")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        print(f"❌ User not found: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")

    if user.commission_paid:
        print(f"✅ Commission already paid for user: {telegram_id}")
        return templates.TemplateResponse("commission_success.html", {
            "request": request,
            "telegram_id": telegram_id,
            "success_message": "Commission already paid!",
            "already_paid": True,
            "bot_username": BOT_USERNAME
        })

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


@router.get("/success", response_class=HTMLResponse)
async def commission_success(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Commission success page"""
    print(f"✅ Commission success page for: {telegram_id}")

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
    """Confirm commission payment"""
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

        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        if not signature:
            raise HTTPException(status_code=400, detail="Missing transaction signature")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            print(f"❌ User not found: {telegram_id}")
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            print(f"✅ Commission already paid for user: {telegram_id}")
            return {
                "success": True,
                "message": "Commission already confirmed",
                "already_paid": True
            }

        if not user.wallet_address:
            print(f"❌ No wallet connected for user: {telegram_id}")
            raise HTTPException(status_code=400, detail="No wallet connected")

        # Verify transaction on blockchain
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
                    if tx.value.meta and tx.value.meta.err:
                        print(f"❌ Transaction failed on blockchain: {tx.value.meta.err}")
                        raise HTTPException(status_code=400, detail="Transaction failed on blockchain")

                    transaction_confirmed = True
                    print(f"✅ Transaction confirmed on blockchain")
                    break
                else:
                    print(f"⚠️ Transaction not found yet (attempt {attempt + 1})")

                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 1.5
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
@limiter.limit("15/minute")
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

        # Check transactions FROM user wallet
        client = AsyncClient(SOLANA_RPC)
        
        try:
            user_pubkey = Pubkey.from_string(user.wallet_address)

            print(f"🔍 Checking payments from user wallet: {telegram_id}")
            print(f"   User wallet: {user.wallet_address}")
            print(f"   Admin wallet: {ADMIN_WALLET}")

            # Get recent transactions from USER wallet
            signatures_response = await client.get_signatures_for_address(
                user_pubkey,
                limit=20
            )

            if not signatures_response.value:
                await client.close()
                print(f"⚠️ No recent transactions found for user wallet")
                return {
                    "success": True,
                    "payment_found": False,
                    "message": "No recent transactions found"
                }

            expected_lamports = int(COMMISSION_AMOUNT * 1_000_000_000)
            tolerance = int(0.01 * 1_000_000_000)  # 0.01 SOL tolerance

            print(f"   Expected amount: {expected_lamports / 1_000_000_000} SOL")
            print(f"   Checking {len(signatures_response.value)} recent transactions...")

            # Check each transaction
            for idx, sig_info in enumerate(signatures_response.value):
                try:
                    # Add delay to avoid rate limiting
                    if idx > 0 and idx % 3 == 0:
                        await asyncio.sleep(0.5)
                    
                    tx_response = await client.get_transaction(
                        sig_info.signature,
                        encoding="json",
                        max_supported_transaction_version=0
                    )

                    if not tx_response or not tx_response.value:
                        continue

                    tx = tx_response.value
                    
                    # Check for errors in transaction
                    if hasattr(tx, 'meta') and tx.meta and tx.meta.err:
                        continue

                    # Get meta and transaction data
                    meta = getattr(tx, 'meta', None)
                    if not meta:
                        continue

                    transaction = getattr(tx, 'transaction', None)
                    if not transaction:
                        continue

                    # Get account keys
                    account_keys = []
                    if hasattr(transaction, 'message'):
                        message = transaction.message
                        if hasattr(message, 'account_keys'):
                            account_keys = message.account_keys

                    # Check if admin wallet is in the transaction
                    admin_in_tx = False
                    for key in account_keys:
                        if str(key) == ADMIN_WALLET:
                            admin_in_tx = True
                            break

                    if not admin_in_tx:
                        continue

                    # Check balance changes
                    pre_balances = getattr(meta, 'pre_balances', [])
                    post_balances = getattr(meta, 'post_balances', [])
                    
                    if not pre_balances or not post_balances:
                        continue

                    for acc_idx, (pre, post) in enumerate(zip(pre_balances, post_balances)):
                        # Check if user wallet SENT money
                        if pre > post and acc_idx < len(account_keys) and str(account_keys[acc_idx]) == user.wallet_address:
                            sent = pre - post
                            
                            # Check if amount matches (with tolerance for fees)
                            if abs(sent - expected_lamports) <= tolerance + int(sent * 0.02):  # +2% for fees
                                print(f"✅ Payment detected from user wallet!")
                                print(f"   Signature: {sig_info.signature}")
                                print(f"   Amount sent: {sent / 1_000_000_000} SOL")
                                print(f"   Expected: {expected_lamports / 1_000_000_000} SOL")
                                
                                # Update database
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
                                    "amount": sent / 1_000_000_000
                                }

                except Exception as e:
                    print(f"⚠️ Error checking transaction {sig_info.signature}: {e}")
                    continue

            await client.close()

            print(f"⚠️ No matching payment found in recent transactions")

            return {
                "success": True,
                "payment_found": False,
                "message": "No matching payment found. Please wait 30-60 seconds after payment."
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
