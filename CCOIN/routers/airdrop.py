from fastapi import APIRouter, Request, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from solana.rpc.api import Client
from solana.transaction import Transaction
from fastapi.templating import Jinja2Templates
import os
import redis
from slowapi import Limiter
from slowapi.util import get_remote_address
from CCOIN.database import get_db, SessionLocal
from CCOIN.models.user import User
from CCOIN.utils.telegram_security import get_current_user, send_commission_payment_link
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET, REDIS_URL, BOT_TOKEN
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from datetime import datetime, timezone
import base58
import base64
import time
import structlog
from typing import Optional
from fastapi_csrf_protect import CsrfProtect


from fastapi_csrf_protect import CsrfProtect
from CCOIN.utils.anti_sybil import check_wallet_age, check_wallet_activity, check_duplicate_pattern
from CCOIN.utils.captcha import verify_recaptcha

logger = structlog.get_logger()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
solana_client = Client(SOLANA_RPC)

try:
    redis_client = redis.Redis.from_url(REDIS_URL) if REDIS_URL else None
    if redis_client:
        logger.info("Redis connected successfully for airdrop module")
except Exception as e:
    logger.error("Redis connection failed", extra={"error": str(e)})
    redis_client = None

@router.get("/", response_class=HTMLResponse)
@limiter.limit("30/hour") 
async def get_airdrop(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        logger.warning("Unauthorized access to airdrop")
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")

    telegram_id = str(telegram_id).strip()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error("User not found", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    end_date = datetime(2025, 12, 31, tzinfo=timezone.utc)
    countdown = end_date - datetime.now(timezone.utc)

    tasks_completed = False
    if user.tasks:
        required_platforms = ['telegram', 'instagram', 'x', 'youtube']
        completed_platforms = [t.platform for t in user.tasks if t.completed]
        
        tasks_completed = all(platform in completed_platforms for platform in required_platforms)
        
        logger.info("Tasks completion check", extra={
            "telegram_id": telegram_id,
            "required_platforms": required_platforms,
            "completed_platforms": completed_platforms,
            "all_completed": tasks_completed
        })

    invited = False
    if hasattr(user, 'referrals') and user.referrals:
        invited = len(user.referrals) > 0
    else:
        referral_count = db.query(User).filter(User.referred_by == user.id).count()
        invited = referral_count > 0

    wallet_connected = bool(user.wallet_address)
    commission_paid = user.commission_paid

    if tasks_completed and invited and wallet_connected and commission_paid:
        if hasattr(user, 'airdrop') and user.airdrop:
            user.airdrop.eligible = True
            db.commit()

    from CCOIN import config

    logger.info("Airdrop page accessed", extra={
        "telegram_id": telegram_id,
        "tasks_completed": tasks_completed,
        "invited": invited,
        "wallet_connected": wallet_connected,
        "commission_paid": commission_paid
    })

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
@limiter.limit("10/day")  
@limiter.limit("3/hour") 
async def connect_wallet(
    request: Request,
    csrf_protect: CsrfProtect = Depends(), 
    db: Session = Depends(get_db)
):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        logger.warning("Unauthorized wallet connection attempt")
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")

    telegram_id = str(telegram_id).strip()

    body = await request.json()
    wallet = body.get("wallet")

    if wallet and wallet != "":
        await csrf_protect.validate_csrf(request)

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error("User not found for wallet connection", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    if not wallet or wallet == "":
        user.wallet_address = None
        if hasattr(user, 'wallet_connected'):
            user.wallet_connected = False
        if hasattr(user, 'updated_at'):
            user.updated_at = datetime.now(timezone.utc)
        db.commit()

        if redis_client:
            cache_key = f"wallet:{telegram_id}"
            try:
                redis_client.delete(cache_key)
            except Exception as e:
                logger.warning("Cache clear failed", extra={"error": str(e)})

        logger.info("Wallet disconnected", extra={"telegram_id": telegram_id})
        return {"success": True, "message": "Wallet disconnected successfully"}

    wallet = wallet.strip()
    
    if not isinstance(wallet, str) or len(wallet) < 32:
        logger.warning("Invalid wallet format", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=400, detail="Invalid wallet address")

    try:
        decoded = base58.b58decode(wallet)
        if len(decoded) != 32:
            raise ValueError("Invalid key length")
        
        Pubkey.from_string(wallet)

        existing_user = db.query(User).filter(
            User.wallet_address == wallet,
            User.id != user.id
        ).first()

        if existing_user:
            logger.warning("Duplicate wallet attempt", extra={
                "telegram_id": telegram_id,
                "wallet": wallet
            })
            raise HTTPException(status_code=400, detail="Wallet already connected to another account")

        if not check_wallet_age(wallet):
            logger.warning("Wallet too new", extra={"telegram_id": telegram_id, "wallet": wallet})
            raise HTTPException(
                status_code=400,
                detail="Wallet is too new. Please use a wallet with at least 7 days of activity."
            )

        activity = check_wallet_activity(wallet)
        if activity["risk_score"] > 70:
            logger.warning("High risk wallet", extra={
                "telegram_id": telegram_id,
                "wallet": wallet,
                "risk_score": activity["risk_score"]
            })
            raise HTTPException(
                status_code=400,
                detail="Wallet has insufficient activity. Please use an active wallet."
            )

        client_ip = request.client.host
        if not check_duplicate_pattern(db, telegram_id, client_ip):
            logger.warning("Suspicious pattern detected", extra={
                "telegram_id": telegram_id,
                "ip": client_ip
            })
            raise HTTPException(
                status_code=429,
                detail="Suspicious activity detected. Please try again later."
            )

        user.wallet_address = wallet
        user.last_ip = client_ip  
        user.last_active = datetime.now(timezone.utc)  
        if hasattr(user, 'wallet_connected'):
            user.wallet_connected = True
        if hasattr(user, 'wallet_connection_date'):
            user.wallet_connection_date = datetime.now(timezone.utc)
        if hasattr(user, 'updated_at'):
            user.updated_at = datetime.now(timezone.utc)
        db.commit()

        if redis_client:
            cache_key = f"wallet:{telegram_id}"
            try:
                redis_client.setex(cache_key, 3600, wallet)
            except Exception as e:
                logger.warning("Cache set failed", extra={"error": str(e)})

        logger.info("Wallet connected successfully", extra={
            "telegram_id": telegram_id,
            "wallet": wallet,
            "risk_score": activity["risk_score"]
        })

        return {"success": True, "message": "Wallet connected successfully"}

    except ValueError as e:
        logger.warning("Invalid Solana address", extra={
            "telegram_id": telegram_id,
            "error": str(e)
        })
        raise HTTPException(status_code=400, detail="Invalid Solana wallet address")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Wallet connection error", extra={
            "telegram_id": telegram_id,
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to connect wallet: {str(e)}")

@router.post("/confirm_commission")
@limiter.limit("3/hour") 
@limiter.limit("5/day")   
async def confirm_commission(
    request: Request,
    csrf_protect: CsrfProtect = Depends(),
    db: Session = Depends(get_db)
):
    """✔️ Fixed: Get telegram_id from request body instead of session"""

    await csrf_protect.validate_csrf(request)

    body = await request.json()
    telegram_id = body.get("telegram_id")
    tx_signature = body.get("signature")
    amount = body.get("amount", COMMISSION_AMOUNT)
    recipient = body.get("recipient", ADMIN_WALLET)
    reference = body.get("reference")
    captcha_token = body.get("captcha_token")  

    print(f"📥 Commission confirmation request: telegram_id={telegram_id}, signature={tx_signature}")
    logger.info("Commission confirmation request", extra={
        "telegram_id": telegram_id,
        "signature": tx_signature
    })

    if not telegram_id:
        raise HTTPException(status_code=400, detail="Missing telegram_id")

    if not tx_signature:
        raise HTTPException(status_code=400, detail="Missing transaction signature")

    if not await verify_recaptcha(captcha_token, request.client.host):
        logger.warning("Captcha verification failed", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=400, detail="Captcha verification failed")

    telegram_id = str(telegram_id).strip()
    tx_signature = tx_signature.strip()

    try:
        base58.b58decode(tx_signature)
    except Exception:
        logger.warning("Invalid transaction signature format", extra={"signature": tx_signature})
        raise HTTPException(status_code=400, detail="Invalid transaction signature format")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        print(f"❌ User not found: {telegram_id}")
        logger.error("User not found", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    if user.commission_paid:
        print(f"✅ Commission already paid for user: {telegram_id}")
        logger.info("Commission already paid", extra={"telegram_id": telegram_id})
        return {"success": True, "message": "Commission already paid"}

    if not user.wallet_address:
        print(f"❌ No wallet connected for user: {telegram_id}")
        logger.warning("No wallet connected", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=400, detail="No wallet connected")

    try:
        cache_key = f"tx:{tx_signature}"
        if redis_client:
            try:
                cached_result = redis_client.get(cache_key)
                if cached_result:
                    print(f"✅ Transaction found in cache: {tx_signature}")
                    logger.info("Transaction found in cache", extra={"signature": tx_signature})
                    user.commission_paid = True
                    if hasattr(user, 'updated_at'):
                        user.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    return {"success": True, "message": "Commission already confirmed"}
            except Exception as e:
                logger.warning("Cache check failed", extra={"error": str(e)})

        retries = 5
        delay = 1
        for attempt in range(retries):
            try:
                print(f"🔍 Verifying transaction (attempt {attempt + 1}/{retries}): {tx_signature}")
                logger.debug("Verifying transaction", extra={
                    "attempt": attempt + 1,
                    "signature": tx_signature
                })

                tx_info = solana_client.get_transaction(
                    tx_signature,
                    encoding="json",
                    commitment="confirmed",
                    max_supported_transaction_version=0
                )

                if tx_info.value and tx_info.value.meta and not tx_info.value.meta.err:
                    user.commission_paid = True
                    user.commission_transaction_hash = tx_signature
                    user.commission_payment_date = datetime.now(timezone.utc)
                    user.last_active = datetime.now(timezone.utc)  
                    if hasattr(user, 'updated_at'):
                        user.updated_at = datetime.now(timezone.utc)
                    db.commit()

                    print(f"✅ Commission confirmed successfully for user: {telegram_id}")
                    print(f"   Transaction: {tx_signature}")
                    logger.info("Commission confirmed successfully", extra={
                        "telegram_id": telegram_id,
                        "signature": tx_signature
                    })

                    if redis_client:
                        try:
                            redis_client.setex(cache_key, 3600, "confirmed")
                        except Exception as e:
                            logger.warning("Cache set failed", extra={"error": str(e)})

                    return {
                        "success": True,
                        "message": "Commission confirmed successfully!",
                        "redirect_url": f"/airdrop?telegram_id={telegram_id}"
                    }
                else:
                    error_msg = "Transaction failed or not found on blockchain"
                    print(f"❌ {error_msg}: {tx_signature}")
                    logger.warning(error_msg, extra={"signature": tx_signature})
                    raise HTTPException(status_code=400, detail=error_msg)

            except HTTPException:
                raise
            except Exception as e:
                if attempt < retries - 1:
                    print(f"⚠️ Retry {attempt + 1}/{retries} failed: {e}")
                    logger.warning("Retry attempt failed", extra={
                        "attempt": attempt + 1,
                        "error": str(e)
                    })
                    time.sleep(delay)
                    delay *= 2 
                else:
                    print(f"❌ Verification failed after {retries} retries: {e}")
                    logger.error("Verification failed after retries", extra={
                        "telegram_id": telegram_id,
                        "error": str(e)
                    }, exc_info=True)
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to verify transaction. Please try again later."
                    )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Commission confirmation error", extra={
            "telegram_id": telegram_id,
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/referral_status")
@limiter.limit("10/minute")
async def get_referral_status(request: Request, db: Session = Depends(get_db)):
    """Check if user has successfully invited friends"""
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    telegram_id = str(telegram_id).strip()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    referral_count = db.query(User).filter(User.referred_by == user.id).count()

    relationship_count = 0
    try:
        if hasattr(user, 'referrals') and user.referrals:
            relationship_count = len(user.referrals)
    except:
        pass

    final_count = max(referral_count, relationship_count)
    has_referrals = final_count > 0

    print(f"Referral check for user {telegram_id}: referral_count={referral_count}, relationship_count={relationship_count}, final={final_count}")
    logger.debug("Referral status check", extra={
        "telegram_id": telegram_id,
        "referral_count": final_count
    })

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

    telegram_id = str(telegram_id).strip()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    tasks_completed = False
    total_tasks = 0
    completed_count = 0

    if user.tasks:
        total_tasks = len(user.tasks)
        completed_tasks = [t for t in user.tasks if t.completed]
        completed_count = len(completed_tasks)
        tasks_completed = completed_count > 0

    print(f"Tasks check for user {telegram_id}: total={total_tasks}, completed={completed_count}, status={tasks_completed}")
    logger.debug("Tasks status check", extra={
        "telegram_id": telegram_id,
        "completed_count": completed_count
    })

    return {
        "tasks_completed": tasks_completed,
        "total_tasks": total_tasks,
        "completed_count": completed_count
    }

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
    Manually check recent transactions from user's wallet to admin wallet
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")

        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        telegram_id = str(telegram_id).strip()

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="No wallet connected")

        try:
            from solders.signature import Signature
            
            user_pubkey = Pubkey.from_string(user.wallet_address)
            admin_pubkey = Pubkey.from_string(ADMIN_WALLET)
            
            signatures = solana_client.get_signatures_for_address(
                user_pubkey,
                limit=10
            )

            if not signatures.value:
                return {
                    "success": False,
                    "message": "No recent transactions found",
                    "transactions": []
                }

            verified_transactions = []
            for sig_info in signatures.value:
                tx_sig = str(sig_info.signature)
                
                tx_info = solana_client.get_transaction(
                    tx_sig,
                    encoding="json",
                    commitment="confirmed",
                    max_supported_transaction_version=0
                )

                if tx_info.value and tx_info.value.meta and not tx_info.value.meta.err:
                    verified_transactions.append({
                        "signature": tx_sig,
                        "timestamp": sig_info.block_time,
                        "status": "confirmed"
                    })

            logger.info("Manual verification completed", extra={
                "telegram_id": telegram_id,
                "transactions_found": len(verified_transactions)
            })

            return {
                "success": True,
                "message": f"Found {len(verified_transactions)} confirmed transactions",
                "transactions": verified_transactions,
                "wallet_address": user.wallet_address,
                "admin_wallet": ADMIN_WALLET
            }

        except Exception as e:
            logger.error("Manual verification error", extra={
                "telegram_id": telegram_id,
                "error": str(e)
            }, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Manual verification error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred")


@router.post("/request_commission_link")
async def request_commission_link(request: Request, db: Session = Depends(get_db)):
    """
    Send commission payment link to user via bot
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")
        
        telegram_id = str(telegram_id).strip()
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.commission_paid:
            return {"success": False, "message": "Commission already paid"}
        
        if not user.wallet_connected:
            return {"success": False, "message": "Please connect wallet first"}
        
        from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
        from CCOIN.config import BOT_TOKEN, APP_DOMAIN
        
        bot = Bot(token=BOT_TOKEN)
        await bot.initialize()
        
        commission_url = f"{APP_DOMAIN}/commission/browser/pay?telegram_id={telegram_id}"
        
        keyboard = [
            [InlineKeyboardButton("💳 Open Payment Page", url=commission_url)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = (
            "💰 *Commission Payment*\n\n"
            "Click the button below to open the payment page in your browser\\.\n\n"
            "✅ The page will open in your default browser \\(not in Telegram\\)\\."
        )
        
        await bot.send_message(
            chat_id=int(telegram_id), 
            text=message_text,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
        
        await bot.shutdown()
        
        logger.info("Commission link sent via bot", extra={"telegram_id": telegram_id})
        return {"success": True, "message": "Payment link sent to your Telegram chat"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error sending commission link", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to send link: {str(e)}")


@router.post("/send_link_to_chat", response_class=JSONResponse)
async def send_link_to_chat(request: Request, db: Session = Depends(get_db)):
    """
    Send commission payment link to user's Telegram chat
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        payment_url = body.get("payment_url")

        if not telegram_id or not payment_url:
            raise HTTPException(status_code=400, detail="Missing required parameters")

        logger.info("Send link to chat request", extra={
            "telegram_id": telegram_id,
            "payment_url": payment_url
        })

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            logger.warning("User not found", extra={"telegram_id": telegram_id})
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            logger.info("Commission already paid", extra={"telegram_id": telegram_id})
            return JSONResponse({
                "success": False,
                "error": "Commission already paid"
            }, status_code=400)

        if not user.wallet_address:
            logger.warning("Wallet not connected", extra={"telegram_id": telegram_id})
            return JSONResponse({
                "success": False,
                "error": "Wallet not connected. Please connect your wallet first."
            }, status_code=400)

        try:
            from telegram import Bot
            from telegram.constants import ParseMode
            
            from CCOIN.config import BOT_TOKEN
            
            if not BOT_TOKEN:
                raise ValueError("BOT_TOKEN not configured")
            
            bot = Bot(token=BOT_TOKEN)
            
            message_text = (
                "🔔 <b>Commission Payment Required</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "Dear User,\n\n"
                "To complete your CCoin airdrop registration, please pay the commission fee.\n\n"
                f"💰 <b>Amount:</b> {COMMISSION_AMOUNT} SOL\n"
                "📱 <b>Method:</b> Phantom Wallet\n\n"
                "<b>📋 Payment Instructions:</b>\n\n"
                "1️⃣ Click the link below\n"
                "2️⃣ Complete payment in Phantom wallet\n"
                "3️⃣ Return to bot after payment\n"
                "4️⃣ Payment will be verified automatically\n\n"
                "👇 <b>Click here to pay:</b>\n"
                f"{payment_url}\n\n"
            )

            await bot.send_message(
                chat_id=int(telegram_id),
                text=message_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False
            )

            logger.info("Payment link sent to chat successfully", extra={
                "telegram_id": telegram_id
            })

            return {
                "success": True,
                "message": "Payment link sent to your chat successfully"
            }

        except Exception as e:
            logger.error("Failed to send Telegram message", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "telegram_id": telegram_id
            }, exc_info=True)
            
            return JSONResponse({
                "success": False,
                "error": f"Failed to send message to Telegram: {str(e)}"
            }, status_code=500)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("send_link_to_chat error", extra={
            "error": str(e),
            "error_type": type(e).__name__
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check_status", response_class=JSONResponse)
async def check_commission_status(
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """
    Check if user has paid commission
    """
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        
        if not user:
            return {
                "commission_paid": False,
                "message": "User not found"
            }
        
        return {
            "commission_paid": user.commission_paid,
            "transaction_hash": user.commission_transaction_hash if user.commission_paid else None,
            "payment_date": user.commission_payment_date.isoformat() if user.commission_paid and user.commission_payment_date else None
        }
        
    except Exception as e:
        logger.error("check_status error", extra={"error": str(e), "telegram_id": telegram_id})
        return {
            "commission_paid": False,
            "error": str(e)
        }


@router.post("/send_commission_link")
async def send_commission_link(request: Request, db: Session = Depends(get_db)):
    """
    Send commission payment link to user's Telegram chat
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        
        if not telegram_id:
            logger.warning("Missing telegram_id in send_commission_link request")
            raise HTTPException(status_code=400, detail="Missing telegram_id")
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            logger.warning("User not found", extra={"telegram_id": telegram_id})
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.commission_paid:
            logger.info("Commission already paid", extra={"telegram_id": telegram_id})
            return JSONResponse({
                "success": False,
                "message": "Commission already paid!"
            })
        
        success = await send_commission_payment_link(telegram_id)
        
        if success:
            logger.info("Commission link sent successfully", extra={"telegram_id": telegram_id})
            return JSONResponse({
                "success": True,
                "message": "Payment link sent to your Telegram chat! Please check your messages."
            })
        else:
            logger.error("Failed to send commission link", extra={"telegram_id": telegram_id})
            return JSONResponse({
                "success": False,
                "message": "Failed to send link. Please try again."
            }, status_code=500)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in send_commission_link", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check_eligibility", response_class=JSONResponse)
async def check_eligibility(
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Check if user is eligible for airdrop claim"""
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        all_tasks_completed = all([
            user.telegram_follow,
            user.instagram_follow,
            user.x_follow,
            user.youtube_follow
        ])
        
        eligible = (
            all_tasks_completed and
            user.invited_user and
            user.wallet_address and
            user.commission_paid
        )
        
        return {
            "success": True,
            "eligible": eligible,
            "tasks_completed": all_tasks_completed,
            "invited": user.invited_user,
            "wallet_connected": bool(user.wallet_address),
            "commission_paid": user.commission_paid
        }
        
    except Exception as e:
        logger.error("check_eligibility error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/claim")
async def claim_airdrop(request: Request):
    """Claim airdrop after completing all tasks"""
    telegram_id = request.session.get("telegram_id")
    
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    from CCOIN.database import SessionLocal
    from CCOIN.models.user import User
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        
        tasks_completed = getattr(user, 'tasks_completed', False)
        
        invited = user.invited_count >= 3
        
        wallet_connected = user.wallet_address is not None and user.wallet_address != ""
        
        commission_paid = user.commission_paid
        
        logger.info(
            "Claim attempt",
            extra={
                "telegram_id": telegram_id,
                "tasks": tasks_completed,
                "invited": invited,
                "wallet": wallet_connected,
                "commission": commission_paid
            }
        )
        
        if not (tasks_completed and invited and wallet_connected and commission_paid):
            raise HTTPException(
                status_code=400,
                detail="All tasks must be completed before claiming"
            )
        
        if hasattr(user, 'airdrop_claimed'):
            user.airdrop_claimed = True
            db.commit()
            logger.info("Airdrop claim status saved", extra={"telegram_id": telegram_id})
        
        logger.info("Airdrop claimed successfully", extra={"telegram_id": telegram_id})
        
        return {
            "success": True,
            "message": "Congratulations! Your request has been registered"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error claiming airdrop",
            extra={"telegram_id": telegram_id, "error": str(e)}
        )
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        db.close()
