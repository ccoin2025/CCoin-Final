import uuid
import os
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from telegram import Update, Bot
from starlette.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from CCOIN.database import Base, engine, get_db
from CCOIN.routers import home, load, leaders, friends, earn, airdrop, about, usertasks, users
from CCOIN.tasks.social_check import check_social_tasks
from CCOIN.models.user import User
from CCOIN.utils.telegram_security import app as telegram_app
from CCOIN.config import BOT_TOKEN, SECRET_KEY, SOLANA_RPC, CONTRACT_ADDRESS, ADMIN_WALLET
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

load_dotenv()
ENV = os.getenv("ENV", "production")

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
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory="CCOIN/static"), name="static")
templates = Jinja2Templates(directory="CCOIN/templates")

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=True if ENV == "production" else False
)

# Redirect root to /load
@app.get("/")
async def root():
    return RedirectResponse(url="/load")

# Anti-bot verification middleware
async def verify_telegram_init_data(request: Request):
    init_data = request.headers.get("X-Telegram-Init-Data") or request.query_params.get("initData")
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing Telegram Web App init data")
    data_check_string = "\n".join(sorted([f"{k}={v[0]}" for k, v in parse_qs(init_data).items() if k != "hash"]))
    secret_key = hmac.new("WebAppData".encode(), BOT_TOKEN.encode(), hashlib.sha256).digest()
    data_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not secrets.compare_digest(data_hash, parse_qs(init_data).get("hash", [""])[0]):
        raise HTTPException(status_code=401, detail="Invalid Telegram init data")
    return init_data

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/telegram_webhook/{webhook_token}")
async def telegram_webhook(webhook_token: str, request: Request, db: Session = Depends(get_db)):
    if webhook_token != os.getenv("WEBHOOK_TOKEN"):
        raise HTTPException(status_code=403, detail="Invalid webhook token")
    # Temporarily disable IP check for testing
    # if not any(ipaddress.ip_address(request.client.host) in network for network in TELEGRAM_IP_RANGES):
    #     raise HTTPException(status_code=403, detail="Request not from Telegram")

    # Read raw JSON data from request
    update_data = await request.json()
    try:
        bot = Bot(token=BOT_TOKEN)
        update = Update.de_json(update_data, bot=bot)  # Pass bot instance to Update
        if not update or not update.message:
            raise HTTPException(status_code=400, detail="Invalid Telegram update")
    except Exception as e:
        logger.error(f"Error parsing Telegram update: {e}")
        raise HTTPException(status_code=400, detail="Invalid Telegram update")

    telegram_id = str(update.message.from_user.id)
    username = update.message.from_user.username
    first_name = update.message.from_user.first_name
    last_name = update.message.from_user.last_name
    referral_code = update.message.text.split()[1] if update.message.text and len(update.message.text.split()) > 1 else None
    if referral_code and len(referral_code) > 50:
        raise HTTPException(status_code=400, detail="Invalid referral code")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            referral_code=str(uuid.uuid4())[:8],
            tokens=0,
            first_login=True,
        )
        db.add(user)
        if referral_code:
            referrer = db.query(User).filter(User.referral_code == referral_code).first()
            if referrer:
                referrer.tokens += 50
                user.referred_by = referrer.id
        db.commit()
        db.refresh(user)

    request.session["telegram_id"] = telegram_id
    request.session["csrf_token"] = secrets.token_hex(16)
    await telegram_app.process_update(update)
    return {"ok": True}

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
    async with AsyncClient(SOLANA_RPC) as client:
        admin_keypair = Keypair.from_base58_string(os.getenv("ADMIN_PRIVATE_KEY", ""))
        if not admin_keypair:
            raise HTTPException(status_code=500, detail="Admin keypair not configured")
        amount = int(user.tokens * 1_000_000_000)  # Convert to lamports
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

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."}
    )

app.include_router(load.router, prefix="/load")
app.include_router(home.router, prefix="/home")
app.include_router(leaders.router, prefix="/leaders")
app.include_router(friends.router, prefix="/friends")
app.include_router(earn.router, prefix="/earn")
app.include_router(airdrop.router, prefix="/airdrop")
app.include_router(about.router, prefix="/about")
app.include_router(usertasks.router, prefix="/usertasks")
app.include_router(users.router, prefix="/users")

scheduler = BackgroundScheduler(timezone=pytz.UTC)
scheduler.add_job(check_social_tasks, "interval", hours=24)
scheduler.start()

@app.on_event("startup")
async def startup():
    logger.info("App started")
    bot = Bot(token=BOT_TOKEN)
    webhook_url = f"https://ccoin-final.onrender.com/telegram_webhook/{os.getenv('WEBHOOK_TOKEN')}"
    await telegram_app.initialize()  # Initialize Telegram Application
    await bot.set_webhook(url=webhook_url)
    logger.info("Telegram webhook set")

@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()
    logger.info("App shutdown")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
