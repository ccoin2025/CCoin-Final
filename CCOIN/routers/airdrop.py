from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from solana.rpc.api import Client
from solana.transaction import Transaction
from fastapi.templating import Jinja2Templates
import os
import redis
from slowapi import Limiter
from slowapi.util import get_remote_address
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.utils.telegram_security import get_current_user
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET, REDIS_URL
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from datetime import datetime
import base58
import base64
import time  # برای retry

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
solana_client = Client(SOLANA_RPC)

# Initialize Redis client with error handling
try:
    redis_client = redis.Redis.from_url(REDIS_URL) if REDIS_URL else None
except:
    redis_client = None

@router.get("/", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def get_airdrop(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    end_date = datetime(2025, 12, 31)  # Fixed year to 2025
    countdown = end_date - datetime.now()

    # بررسی دقیق‌تر وضعیت tasks
    tasks_completed = False
    if user.tasks:
        completed_tasks = [t for t in user.tasks if t.completed]
        tasks_completed = len(completed_tasks) > 0

    # بررسی دقیق‌تر وضعیت referrals - اصلاح شده
    invited = False
    if hasattr(user, 'referrals') and user.referrals:
        # Check if user has actually invited someone (referrals list is not empty)
        invited = len(user.referrals) > 0
    else:
        # Alternative check: count users who were referred by this user
        referral_count = db.query(User).filter(User.referred_by == user.id).count()
        invited = referral_count > 0

    wallet_connected = bool(user.wallet_address)
    commission_paid = user.commission_paid

    # بررسی eligibility برای airdrop
    if tasks_completed and invited and wallet_connected and commission_paid:
        if hasattr(user, 'airdrop') and user.airdrop:
            user.airdrop.eligible = True
            db.commit()

    # اضافه کردن config به context
    from CCOIN import config

    return templates.TemplateResponse("airdrop.html", {
        "request": request,
        "countdown": countdown,
        "value": 0.02,
        "tasks_completed": tasks_completed,
        "invited": invited,
        "wallet_connected": wallet_connected,
        "commission_paid": commission_paid,
        "config": config,
        "user_wallet_address": user.wallet_address if user.wallet_address else ""
    })

@router.post("/connect_wallet")
@limiter.limit("5/minute")
async def connect_wallet(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")

    body = await request.json()
    wallet = body.get("wallet")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # اگر wallet خالی است، یعنی disconnect
    if not wallet or wallet == "":
        user.wallet_address = None
        db.commit()

        # Clear cache
        if redis_client:
            cache_key = f"wallet:{telegram_id}"
            redis_client.delete(cache_key)

        return {"success": True, "message": "Wallet disconnected successfully"}

    # Validate wallet address format
    if not isinstance(wallet, str) or len(wallet) < 32:
        raise HTTPException(status_code=400, detail="Invalid wallet address")

    try:
        # Validate Solana public key format
        Pubkey.from_string(wallet)

        # Check if wallet already exists for another user
        existing_user = db.query(User).filter(
            User.wallet_address == wallet,
            User.id != user.id
        ).first()

        if existing_user:
            raise HTTPException(status_code=400, detail="Wallet already connected to another account")

        user.wallet_address = wallet
        db.commit()

        # Cache wallet address
        if redis_client:
            cache_key = f"wallet:{telegram_id}"
            redis_client.setex(cache_key, 3600, wallet)

        return {"success": True, "message": "Wallet connected successfully"}

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Solana wallet address")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to connect wallet: {str(e)}")

@router.post("/confirm_commission")
@limiter.limit("3/minute")
async def confirm_commission(request: Request, db: Session = Depends(get_db)):
    """✅ اصلاح شده: گرفتن telegram_id از body به جای session"""

    body = await request.json()
    telegram_id = body.get("telegram_id")
    tx_signature = body.get("signature")
    amount = body.get("amount", COMMISSION_AMOUNT)
    recipient = body.get("recipient", ADMIN_WALLET)
    reference = body.get("reference")

    print(f"📥 Commission confirmation request: telegram_id={telegram_id}, signature={tx_signature}")

    if not telegram_id:
        raise HTTPException(status_code=400, detail="Missing telegram_id")

    if not tx_signature:
        raise HTTPException(status_code=400, detail="Missing transaction signature")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        print(f"❌ User not found: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")

    if user.commission_paid:
        print(f"✅ Commission already paid for user: {telegram_id}")
        return {"success": True, "message": "Commission already paid"}

    if not user.wallet_address:
        print(f"❌ No wallet connected for user: {telegram_id}")
        raise HTTPException(status_code=400, detail="No wallet connected")

    try:
        # بررسی cache ابتدا
        cache_key = f"tx:{tx_signature}"
        if redis_client:
            cached_result = redis_client.get(cache_key)
            if cached_result:
                print(f"✅ Transaction found in cache: {tx_signature}")
                user.commission_paid = True
                db.commit()
                return {"success": True, "message": "Commission already confirmed"}

        # Retry logic for Solana RPC (exponential backoff)
        retries = 5
        delay = 1
        for attempt in range(retries):
            try:
                print(f"🔍 Verifying transaction (attempt {attempt + 1}/{retries}): {tx_signature}")

                tx_info = solana_client.get_transaction(
                    tx_signature,
                    encoding="json",
                    commitment="confirmed"
                )

                if tx_info.value and tx_info.value.meta and not tx_info.value.meta.err:
                    # ✅ Transaction تایید شد
                    user.commission_paid = True
                    user.commission_transaction_hash = tx_signature
                    user.commission_payment_date = datetime.utcnow()
                    db.commit()

                    print(f"✅ Commission confirmed successfully for user: {telegram_id}")
                    print(f"   Transaction: {tx_signature}")

                    # Cache کردن نتیجه
                    if redis_client:
                        redis_client.setex(cache_key, 3600, "confirmed")

                    # ✅ Return با redirect URL
                    return {
                        "success": True, 
                        "message": "Commission confirmed successfully!",
                        "redirect_url": f"/airdrop?telegram_id={telegram_id}"
                    }
                else:
                    error_msg = "Transaction failed or not found on blockchain"
                    print(f"❌ {error_msg}: {tx_signature}")
                    raise HTTPException(status_code=400, detail=error_msg)

            except HTTPException:
                raise
            except Exception as e:
                if attempt < retries - 1:
                    print(f"⚠️ Retry {attempt + 1}/{retries} failed: {e}")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    print(f"❌ Verification failed after {retries} retries: {e}")
                    raise HTTPException(status_code=500, detail=f"Confirmation failed after retries: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Commission confirmation error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Transaction confirmation failed: {str(e)}")

@router.get("/commission_status")
@limiter.limit("10/minute")
async def get_commission_status(
    request: Request,
    telegram_id: str = Query(None),  # ✅ اضافه شد
    db: Session = Depends(get_db)
):
    """✅ اصلاح شده: گرفتن telegram_id از query parameter یا session"""
    
    # اول از query parameter بگیر
    if not telegram_id:
        telegram_id = request.session.get("telegram_id")
    
    if not telegram_id:
        raise HTTPException(status_code=400, detail="Missing telegram_id")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        print(f"❌ User not found for status check: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")

    print(f"📊 Commission status for {telegram_id}: paid={user.commission_paid}, wallet={bool(user.wallet_address)}")

    return {
        "commission_paid": user.commission_paid,
        "wallet_connected": bool(user.wallet_address),
        "wallet_address": user.wallet_address,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET
    }

@router.get("/referral_status")
@limiter.limit("10/minute")
async def get_referral_status(request: Request, db: Session = Depends(get_db)):
    """Check if user has successfully invited friends"""
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # روش اول: شمارش کاربرانی که توسط این کاربر دعوت شده‌اند
    referral_count = db.query(User).filter(User.referred_by == user.id).count()

    # روش دوم: چک کردن relationship اگر درست کار کند
    relationship_count = 0
    try:
        if hasattr(user, 'referrals') and user.referrals:
            relationship_count = len(user.referrals)
    except:
        pass

    # انتخاب بهترین روش
    final_count = max(referral_count, relationship_count)
    has_referrals = final_count > 0

    print(f"Referral check for user {telegram_id}: referral_count={referral_count}, relationship_count={relationship_count}, final={final_count}")

    return {
        "has_referrals": has_referrals,
        "referral_count": final_count,
        "referral_code": user.referral_code,
        "debug_info": {
            "direct_count": referral_count,
            "relationship_count": relationship_count
        }
    }

@router.get("/tasks_status")
@limiter.limit("10/minute")
async def get_tasks_status(request: Request, db: Session = Depends(get_db)):
    """Check if user has completed tasks"""
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check completed tasks
    tasks_completed = False
    total_tasks = 0
    completed_count = 0

    if user.tasks:
        total_tasks = len(user.tasks)
        completed_tasks = [t for t in user.tasks if t.completed]
        completed_count = len(completed_tasks)
        tasks_completed = completed_count > 0

    print(f"Tasks check for user {telegram_id}: total={total_tasks}, completed={completed_count}, status={tasks_completed}")

    return {
        "tasks_completed": tasks_completed,
        "total_tasks": total_tasks,
        "completed_count": completed_count
    }

# Deprecated endpoint - kept for backward compatibility
@router.get("/pay/commission")
async def pay_commission_get(request: Request):
    raise HTTPException(status_code=405, detail="This endpoint only supports POST requests.")

@router.get("/check_wallet_status")
async def check_wallet_status(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    return JSONResponse({
        "connected": user.wallet_address is not None,
        "wallet_address": user.wallet_address
    })

@router.post("/verify_commission_manual")
@limiter.limit("3/minute")
async def verify_commission_manual(request: Request, db: Session = Depends(get_db)):
    """
    بررسی manual تراکنش‌های اخیر از wallet کاربر به admin wallet
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            return {"success": True, "message": "Commission already paid", "already_paid": True}

        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="No wallet connected")

        print(f"🔍 Manual verification for user {telegram_id}, wallet: {user.wallet_address}")

        # بررسی تراکنش‌های اخیر
        from solders.pubkey import Pubkey
        
        try:
            user_pubkey = Pubkey.from_string(user.wallet_address)
            admin_pubkey = Pubkey.from_string(ADMIN_WALLET)
            
            # گرفتن signatures اخیر
            signatures = solana_client.get_signatures_for_address(
                user_pubkey,
                limit=20  # 20 تراکنش اخیر
            )
            
            if not signatures.value:
                print(f"❌ No recent transactions found for {user.wallet_address}")
                return {"success": False, "message": "No recent transactions found"}

            print(f"📋 Found {len(signatures.value)} recent transactions")

            # بررسی هر تراکنش
            for sig_info in signatures.value:
                sig = str(sig_info.signature)
                
                try:
                    tx_info = solana_client.get_transaction(
                        sig,
                        encoding="json",
                        commitment="confirmed"
                    )
                    
                    if not tx_info.value or not tx_info.value.transaction:
                        continue
                    
                    # بررسی اینکه آیا به admin wallet ارسال شده
                    tx_data = tx_info.value.transaction
                    
                    # گرفتن account keys
                    if hasattr(tx_data, 'message') and hasattr(tx_data.message, 'account_keys'):
                        account_keys = tx_data.message.account_keys
                        
                        # بررسی اینکه آیا admin wallet در لیست accounts هست
                        admin_in_tx = any(str(key) == ADMIN_WALLET for key in account_keys)
                        
                        if admin_in_tx:
                            # بررسی مبلغ
                            meta = tx_info.value.meta
                            if meta and not meta.err:
                                # محاسبه تغییرات balance
                                pre_balances = meta.pre_balances
                                post_balances = meta.post_balances
                                
                                # پیدا کردن index admin wallet
                                admin_index = None
                                for i, key in enumerate(account_keys):
                                    if str(key) == ADMIN_WALLET:
                                        admin_index = i
                                        break
                                
                                if admin_index is not None:
                                    balance_change = post_balances[admin_index] - pre_balances[admin_index]
                                    amount_sol = balance_change / 1_000_000_000
                                    
                                    print(f"💰 Found TX: {sig[:16]}...Amount: {amount_sol} SOL")
                                    
                                    # بررسی اینکه مبلغ کافی هست (با tolerance برای fee)
                                    if amount_sol >= (COMMISSION_AMOUNT * 0.95):  # 95% tolerance
                                        # ✅ تراکنش معتبر پیدا شد!
                                        user.commission_paid = True
                                        user.commission_transaction_hash = sig
                                        user.commission_payment_date = datetime.utcnow()
                                        db.commit()
                                        
                                        print(f"✅ Commission verified and confirmed for user {telegram_id}")
                                        print(f"   TX: {sig}")
                                        print(f"   Amount: {amount_sol} SOL")
                                        
                                        return {
                                            "success": True,
                                            "message": "Commission verified successfully!",
                                            "transaction": sig,
                                            "amount": amount_sol
                                        }
                
                except Exception as e:
                    print(f"⚠️ Error checking TX {sig[:16]}...: {e}")
                    continue
            
            print(f"❌ No valid commission payment found in recent transactions")
            return {"success": False, "message": "No valid commission payment found"}
            
        except Exception as e:
            print(f"❌ Error verifying transactions: {e}")
            raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Manual verification error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

@router.get("/check_commission_status")
async def check_commission_status(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    return JSONResponse({
        "paid": user.commission_paid
    })

@router.post("/auto_verify_commission")
@limiter.limit("5/minute")
async def auto_verify_commission(request: Request, db: Session = Depends(get_db)):
    """
    ✅ بررسی خودکار تراکنش‌های اخیر کاربر به admin wallet
    این endpoint بدون نیاز به signature، تراکنش‌ها را چک می‌کند
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")

        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            return {"success": True, "message": "Commission already paid", "already_paid": True}

        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="No wallet connected")

        print(f"🔍 Auto-verifying commission for user: {telegram_id}, wallet: {user.wallet_address}")

        # دریافت تراکنش‌های اخیر wallet کاربر
        from solders.pubkey import Pubkey
        
        user_pubkey = Pubkey.from_string(user.wallet_address)
        admin_pubkey = Pubkey.from_string(ADMIN_WALLET)

        # گرفتن آخرین تراکنش‌ها (10 تا اخیر)
        signatures = solana_client.get_signatures_for_address(
            user_pubkey,
            limit=10
        )

        if not signatures.value:
            return {"success": False, "message": "No transactions found"}

        # بررسی هر تراکنش
        for sig_info in signatures.value:
            try:
                signature = str(sig_info.signature)
                
                # دریافت جزئیات تراکنش
                tx = solana_client.get_transaction(
                    signature,
                    encoding="json",
                    max_supported_transaction_version=0
                )

                if not tx.value or not tx.value.transaction:
                    continue

                # بررسی اینکه تراکنش خطا نداشته باشد
                if tx.value.meta and tx.value.meta.err:
                    continue

                # بررسی postBalances و preBalances
                if not tx.value.meta or not tx.value.meta.post_balances:
                    continue

                # استخراج account keys
                if hasattr(tx.value.transaction, 'message'):
                    message = tx.value.transaction.message
                    
                    # بررسی اینکه admin wallet در account keys باشد
                    account_keys = []
                    if hasattr(message, 'account_keys'):
                        account_keys = [str(key) for key in message.account_keys]
                    
                    # چک کردن اینکه admin wallet گیرنده باشد
                    if ADMIN_WALLET in account_keys:
                        admin_index = account_keys.index(ADMIN_WALLET)
                        
                        # محاسبه مقدار transfer شده
                        pre_balance = tx.value.meta.pre_balances[admin_index] if admin_index < len(tx.value.meta.pre_balances) else 0
                        post_balance = tx.value.meta.post_balances[admin_index] if admin_index < len(tx.value.meta.post_balances) else 0
                        
                        transfer_amount_lamports = post_balance - pre_balance
                        transfer_amount_sol = transfer_amount_lamports / 1_000_000_000
                        
                        print(f"📊 Found transfer: {transfer_amount_sol} SOL (expected: {COMMISSION_AMOUNT})")
                        
                        # بررسی مقدار (با tolerance 1%)
                        expected = COMMISSION_AMOUNT
                        tolerance = expected * 0.01
                        
                        if abs(transfer_amount_sol - expected) <= tolerance:
                            # ✅ تراکنش معتبر پیدا شد!
                            print(f"✅ Valid commission payment found: {signature}")
                            
                            user.commission_paid = True
                            user.commission_transaction_hash = signature
                            user.commission_payment_date = datetime.utcnow()
                            db.commit()
                            
                            return {
                                "success": True,
                                "message": "Commission verified and confirmed!",
                                "signature": signature,
                                "amount": transfer_amount_sol
                            }

            except Exception as e:
                print(f"⚠️ Error checking transaction {sig_info.signature}: {e}")
                continue

        # هیچ تراکنش معتبر پیدا نشد
        return {
            "success": False,
            "message": "No valid commission payment found in recent transactions"
        }

    except Exception as e:
        print(f"❌ Auto-verify error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

