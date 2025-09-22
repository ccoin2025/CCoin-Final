import uuid
import os
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from telegram import Update, Bot
from starlette.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from sqlalchemy.orm import Session
from CCOIN.database import Base, engine, get_db
from CCOIN.routers import home, load, leaders, friends, earn, airdrop, about, usertasks, users, wallet, commission
#from CCOIN.tasks.social_check import check_social_tasks
from CCOIN.models.user import User
from CCOIN.utils.telegram_security import app as telegram_app
from CCOIN.config import BOT_TOKEN, SECRET_KEY, SOLANA_RPC, CONTRACT_ADDRESS, ADMIN_WALLET, REDIS_URL
from apscheduler.schedulers.background import BackgroundScheduler
from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from solders.system_program import TransferParams, transfer
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from fastapi.responses import JSONResponse
import structlog
import pytz
import ipaddress
import secrets
from urllib.parse import parse_qs
import hmac
import hashlib
from dotenv import load_dotenv
from CCOIN.routers import wallet

load_dotenv()

ENV = os.getenv("ENV", "production")

# Redis و Rate Limiting Setup (اختیاری)
RATE_LIMITING_ENABLED = False
limiter = None

try:
    if REDIS_URL:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.util import get_remote_address
        from slowapi.errors import RateLimitExceeded
        
        limiter = Limiter(
            key_func=get_remote_address,
            storage_uri=REDIS_URL
        )
        RATE_LIMITING_ENABLED = True
        print("✅ Redis connected - Rate limiting enabled")
    else:
        print("⚠️ No REDIS_URL provided - Rate limiting disabled")
except ImportError:
    print("⚠️ slowapi not available - Rate limiting disabled")
except Exception as e:
    print(f"⚠️ Redis connection failed - Rate limiting disabled: {e}")

TELEGRAM_IP_RANGES = [
    ipaddress.IPv4Network("149.154.160.0/20"),
    ipaddress.IPv4Network("91.108.0.0/22"),
]

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

app = FastAPI(debug=ENV == "development")

# فقط اگر Rate Limiting فعال باشد
if RATE_LIMITING_ENABLED and limiter:
    app.state.limiter = limiter
    
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please try again later."}
        )

Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory="CCOIN/static"), name="static")
templates = Jinja2Templates(directory="CCOIN/templates")

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=True if ENV == "production" else False
)

# Redirect root based on first_login
@app.get("/")
async def root(request: Request, db: Session = Depends(get_db)):
    # telegram_id را از query parameter یا session بگیرید
    telegram_id = request.query_params.get("telegram_id") or request.session.get("telegram_id")

    if not telegram_id:
        logger.info("No telegram_id in session for root, rendering landing.html")
        return templates.TemplateResponse("landing.html", {"request": request})

    # telegram_id را در session تنظیم کنید
    request.session["telegram_id"] = telegram_id

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.info("User not found for root, rendering landing.html")
        return templates.TemplateResponse("landing.html", {"request": request})

    # هدایت براساس وضعیت first_login
    if user.first_login:
        logger.info(f"User {telegram_id} first login, redirecting to load")
        return RedirectResponse(url=f"/load?telegram_id={telegram_id}")
    else:
        logger.info(f"User {telegram_id} returning user, redirecting to home")
        return RedirectResponse(url=f"/home?telegram_id={telegram_id}")

# Anti-bot verification middleware
async def verify_telegram_init_data(request: Request):
    init_data = request.headers.get("X-Telegram-Init-Data") or request.query_params.get("initData")
    if not init_data:
        logger.info("Missing Telegram init data")
        raise HTTPException(status_code=401, detail="Missing Telegram Web App init data")

    data_check_string = "\n".join(sorted([f"{k}={v[0]}" for k, v in parse_qs(init_data).items() if k != "hash"]))
    secret_key = hmac.new("WebAppData".encode(), BOT_TOKEN.encode(), hashlib.sha256).digest()
    data_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not secrets.compare_digest(data_hash, parse_qs(init_data).get("hash", [""])[0]):
        logger.info("Invalid Telegram init data")
        raise HTTPException(status_code=401, detail="Invalid Telegram init data")

    return init_data

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        logger.info("No telegram_id in session for get_current_user, redirecting to bot")
        return RedirectResponse(url="https://t.me/CTG_COIN_BOT")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.info(f"User not found for telegram_id: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")

    return user

@app.api_route("/telegram_webhook/{webhook_token}", methods=["GET", "POST"])
async def telegram_webhook(webhook_token: str, request: Request, db: Session = Depends(get_db)):
    if webhook_token != os.getenv("WEBHOOK_TOKEN"):
        logger.info("Invalid webhook token")
        raise HTTPException(status_code=403, detail="Invalid webhook token")

    # اگر GET request است، فقط تایید کنید
    if request.method == "GET":
        logger.info("GET request to webhook - verification")
        return {"ok": True, "message": "Webhook endpoint is active"}

    # ادامه کد برای POST request
    update_data = await request.json()
    logger.info(f"Received webhook data: {update_data}")

    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.initialize()
        update = Update.de_json(update_data, bot=bot)

        if not update:
            logger.info("Invalid Telegram update")
            raise HTTPException(status_code=400, detail="Invalid Telegram update")

        # پردازش update با telegram app
        await telegram_app.process_update(update)

        await bot.shutdown()

        logger.info("Update processed successfully")
        return {"ok": True}

    except Exception as e:
        logger.error(f"Error processing Telegram update: {e}")
        return {"ok": False, "error": str(e)}

@app.get("/connect-wallet")
async def connect_wallet(request: Request, db: Session = Depends(get_db)):
    await verify_telegram_init_data(request)
    user = await get_current_user(request, db)
    return JSONResponse({"message": "Connect Phantom Wallet", "telegram_id": user.telegram_id})

@app.post("/submit-wallet")
async def submit_wallet(request: Request, wallet_address: str, db: Session = Depends(get_db)):
    await verify_telegram_init_data(request)
    user = await get_current_user(request, db)
    user.wallet_address = wallet_address
    db.commit()
    return JSONResponse({"message": "Wallet connected successfully"})

@app.post("/airdrop-tokens")
async def airdrop_tokens(request: Request, db: Session = Depends(get_db)):
    await verify_telegram_init_data(request)
    user = await get_current_user(request, db)

    if not user.wallet_address:
        raise HTTPException(status_code=400, detail="No wallet connected")

    admin_private_key = os.getenv("ADMIN_PRIVATE_KEY")
    if not admin_private_key:
        raise HTTPException(status_code=500, detail="Admin keypair not configured")

    async with AsyncClient(SOLANA_RPC) as client:
        admin_keypair = Keypair.from_base58_string(admin_private_key)

        amount = int(user.tokens * 1_000_000_000)

        transaction = Transaction().add(
            transfer(TransferParams(
                from_pubkey=Pubkey.from_string(ADMIN_WALLET),
                to_pubkey=Pubkey.from_string(user.wallet_address),
                lamports=amount
            ))
        )

        await client.send_transaction(transaction, admin_keypair)

        user.tokens = 0
        db.commit()

        return JSONResponse({"message": "Tokens airdropped successfully"})

# Route جدید برای تست webhook
@app.get("/webhook-info")
async def webhook_info():
    """endpoint برای بررسی وضعیت webhook"""
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.initialize()
        webhook_info = await bot.get_webhook_info()
        await bot.shutdown()

        return {
            "webhook_url": webhook_info.url,
            "has_custom_certificate": webhook_info.has_custom_certificate,
            "pending_update_count": webhook_info.pending_update_count,
            "last_error_date": webhook_info.last_error_date,
            "last_error_message": webhook_info.last_error_message,
            "max_connections": webhook_info.max_connections,
            "allowed_updates": webhook_info.allowed_updates
        }
    except Exception as e:
        return {"error": str(e)}

# اضافه کردن endpoint برای fix کردن کاربرهای موجود
@app.get("/fix-referral-codes")
async def fix_referral_codes(db: Session = Depends(get_db)):
    """Fix users without referral codes - فقط برای admin"""
    users_without_code = db.query(User).filter(
        (User.referral_code == None) | (User.referral_code == "")
    ).all()

    fixed_count = 0
    for user in users_without_code:
        # تولید کد رفرال جدید
        while True:
            new_code = str(uuid.uuid4())[:8]
            # بررسی کنید که کد تکراری نباشد
            existing = db.query(User).filter(User.referral_code == new_code).first()
            if not existing:
                user.referral_code = new_code
                fixed_count += 1
                break

    db.commit()

    return {
        "message": f"Fixed {fixed_count} users without referral codes",
        "fixed_users": fixed_count
    }

# Status endpoint برای بررسی سلامت برنامه
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "rate_limiting": RATE_LIMITING_ENABLED,
        "redis_available": REDIS_URL is not None,
        "environment": ENV
    }

app.include_router(load.router)
app.include_router(home.router, prefix="/home")
app.include_router(leaders.router, prefix="/leaders")
app.include_router(friends.router, prefix="/friends")
app.include_router(earn.router, prefix="/earn")
app.include_router(airdrop.router, prefix="/airdrop")
app.include_router(about.router, prefix="/about")
app.include_router(usertasks.router, prefix="/usertasks")
app.include_router(users.router, prefix="/users")
app.include_router(wallet.router, prefix="/wallet")
app.include_router(commission.router, prefix="/commission")

scheduler = BackgroundScheduler(timezone=pytz.UTC)
#scheduler.add_job(check_social_tasks, "interval", hours=24)
scheduler.start()

@app.on_event("startup")
async def startup():
    logger.info(f"App started - Rate limiting: {RATE_LIMITING_ENABLED}")

    webhook_token = os.getenv('WEBHOOK_TOKEN')
    if not webhook_token:
        logger.error("WEBHOOK_TOKEN not set!")
        return

    bot = Bot(token=BOT_TOKEN)
    await bot.initialize()

    webhook_url = f"https://ccoin-final.onrender.com/telegram_webhook/{webhook_token}"

    try:
        # تنظیم webhook
        await bot.set_webhook(url=webhook_url)
        logger.info(f"Telegram webhook set to: {webhook_url}")

        # تنظیم Menu Button برای Web App
        try:
            from telegram import MenuButtonWebApp, WebAppInfo
            menu_button = MenuButtonWebApp(
                text="🚀 Open CCoin",
                web_app=WebAppInfo(url="https://ccoin-final.onrender.com")
            )
            await bot.set_chat_menu_button(menu_button=menu_button)
            logger.info("Menu button set successfully")
        except ImportError:
            logger.info("MenuButtonWebApp not available in this version")
        except Exception as e:
            logger.error(f"Error setting menu button: {e}")

        webhook_info = await bot.get_webhook_info()
        logger.info(f"Webhook info: {webhook_info}")

    except Exception as e:
        logger.error(f"Error setting webhook: {e}")

    try:
        await telegram_app.initialize()
        logger.info("Telegram app initialized")
    except Exception as e:
        logger.error(f"Error initializing telegram app: {e}")

    await bot.shutdown()

@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()
    logger.info("App shutdown")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
