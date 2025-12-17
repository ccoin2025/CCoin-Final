import uuid
import os
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from telegram import Update, Bot
from starlette.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from CCOIN.database import Base, engine, get_db, get_db_health
from CCOIN.routers import home, load, leaders, friends, earn, airdrop, about, usertasks, users, wallet, commission
from CCOIN.models.user import User
from CCOIN.models.transaction import Transaction as TransactionModel 
from CCOIN.utils.telegram_security import app as telegram_app
from CCOIN.config import (
    BOT_TOKEN, BOT_USERNAME, SECRET_KEY, SOLANA_RPC, CONTRACT_ADDRESS,
    ADMIN_WALLET, REDIS_URL, ENV, CACHE_ENABLED, RATE_LIMIT_ENABLED,
    GLOBAL_RATE_LIMIT, APP_DOMAIN, TELEGRAM_CHANNEL_USERNAME
)
from apscheduler.schedulers.background import BackgroundScheduler
from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction as SolanaTransaction
from solders.system_program import TransferParams, transfer
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from urllib.parse import parse_qs
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional
import structlog
import pytz
import ipaddress
import secrets
import hmac
import hashlib
import time
import mimetypes


load_dotenv()

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

RATE_LIMITING_ENABLED = False
limiter = None

try:
    if REDIS_URL and RATE_LIMIT_ENABLED:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.util import get_remote_address
        from slowapi.errors import RateLimitExceeded

        limiter = Limiter(
            key_func=get_remote_address,
            storage_uri=REDIS_URL,
            default_limits=[GLOBAL_RATE_LIMIT] 
        )
        RATE_LIMITING_ENABLED = True
        logger.info("✅ Redis connected - Rate limiting enabled")
    else:
        logger.warning("⚠️ No REDIS_URL provided or Rate limiting disabled")
except ImportError:
    logger.warning("⚠️ slowapi not available - Rate limiting disabled")
except Exception as e:
    logger.error(f"⚠️ Redis connection failed - Rate limiting disabled", extra={"error": str(e)})

TELEGRAM_IP_RANGES = [
    ipaddress.IPv4Network("149.154.160.0/20"),
    ipaddress.IPv4Network("91.108.4.0/22"),
    ipaddress.IPv4Network("91.108.56.0/22"),
    ipaddress.IPv6Network("2001:b28:f23d::/48"),
    ipaddress.IPv6Network("2001:b28:f23f::/48"),
]

app = FastAPI(
    debug=ENV == "development",
    title="CCoin API",
    version="1.0.0",
    docs_url="/docs" if ENV == "development" else None,
    redoc_url="/redoc" if ENV == "development" else None,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "ccoin2025.onrender.com",
        "*.onrender.com",
        "localhost",
        "127.0.0.1"
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ccoin2025.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CsrfSettings(BaseModel):
    secret_key: str = SECRET_KEY
    cookie_samesite: str = 'lax'
    cookie_secure: bool = ENV == "production"

class StaticFilesCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        if request.url.path.startswith('/static/') or request.url.path == '/metadata.html':
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = '*'
            response.headers['Cache-Control'] = 'public, max-age=31536000'
        
        return response

app.add_middleware(StaticFilesCORSMiddleware)

@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings()

@app.exception_handler(CsrfProtectError)
async def csrf_protect_exception_handler(request: Request, exc: CsrfProtectError):
    logger.warning("CSRF validation failed", extra={"ip": request.client.host})
    return JSONResponse(
        status_code=403,
        content={"detail": "CSRF validation failed"}
    )
    
if RATE_LIMITING_ENABLED and limiter:
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
        logger.warning("Rate limit exceeded", extra={"ip": request.client.host})
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."}
        )

Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory="CCOIN/static"), name="static")
templates = Jinja2Templates(directory="CCOIN/templates")

app.add_middleware(GZipMiddleware, minimum_size=1000) 

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=True if ENV == "production" else False,
    max_age=86400, 
    same_site="lax"
)

if ENV == "production":
    allowed_hosts = [APP_DOMAIN.replace("https://", "").replace("http://", "")]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://telegram.org https://unpkg.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com https://unpkg.com; "
        "font-src 'self' data: https://cdnjs.cloudflare.com https://fonts.gstatic.com https://unpkg.com; "
        "img-src 'self' data: https: blob:; "
        "connect-src 'self' https://api.telegram.org https:; "
        "frame-src 'self' https://telegram.org;"
    )
    
    return response

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    if process_time > 1.0:
        logger.warning("Slow request detected", extra={
            "path": request.url.path,
            "method": request.method,
            "process_time": process_time
        })
    
    return response

@app.get("/")
async def root(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.query_params.get("telegram_id") or request.session.get("telegram_id")

    if not telegram_id:
        logger.info("No telegram_id in session for root, rendering landing.html")
        return templates.TemplateResponse("landing.html", {
            "request": request,
            "bot_username": BOT_USERNAME  
        })

    telegram_id = str(telegram_id).strip()
    request.session["telegram_id"] = telegram_id

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.info("User not found for root", extra={"telegram_id": telegram_id})
        return templates.TemplateResponse("landing.html", {
            "request": request,
            "bot_username": BOT_USERNAME 
        })

    if user.first_login:
        logger.info("User first login, redirecting to load", extra={"telegram_id": telegram_id})
        return RedirectResponse(url=f"/load?telegram_id={telegram_id}")
    else:
        logger.info("User returning, redirecting to home", extra={"telegram_id": telegram_id})
        return RedirectResponse(url=f"/home?telegram_id={telegram_id}")
        
@app.api_route("/telegram_webhook", methods=["POST"])
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook endpoint with better authentication
    Uses X-Telegram-Bot-Api-Secret-Token
    """
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    expected_token = os.getenv("WEBHOOK_TOKEN")
    
    if not expected_token:
        logger.error("WEBHOOK_TOKEN not configured")
        raise HTTPException(status_code=500, detail="Webhook not configured")
    
    if not secret_token or not secrets.compare_digest(secret_token, expected_token):
        logger.warning("Invalid webhook token", extra={
            "ip": request.client.host,
            "user_agent": request.headers.get("user-agent")
        })
        raise HTTPException(status_code=403, detail="Invalid webhook token")

    client_ip = request.client.host
    is_telegram_ip = False
    
    try:
        ip_obj = ipaddress.ip_address(client_ip)
        for ip_range in TELEGRAM_IP_RANGES:
            if ip_obj in ip_range:
                is_telegram_ip = True
                break
        
        if not is_telegram_ip and ENV == "production":
            logger.warning("Request from non-Telegram IP", extra={"ip": client_ip})
    except ValueError:
        logger.error("Invalid IP address", extra={"ip": client_ip})

    try:
        update_data = await request.json()
        logger.debug("Received webhook data", extra={"update_id": update_data.get("update_id")})

        bot = Bot(token=BOT_TOKEN)
        await bot.initialize()
        update = Update.de_json(update_data, bot=bot)

        if not update:
            logger.warning("Invalid Telegram update received")
            raise HTTPException(status_code=400, detail="Invalid Telegram update")

        await telegram_app.process_update(update)
        await bot.shutdown()

        logger.info("Update processed successfully", extra={"update_id": update.update_id})
        return {"ok": True}

    except Exception as e:
        logger.error("Error processing Telegram update", extra={"error": str(e)}, exc_info=True)
        return {"ok": False, "error": "Internal error"}

@app.get("/health")
async def health_check():
    """
    Health check endpoint با بررسی database
    """
    db_healthy = get_db_health()
    
    health_status = {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "rate_limiting": RATE_LIMITING_ENABLED,
        "cache_enabled": CACHE_ENABLED,
        "redis_available": REDIS_URL is not None,
        "environment": ENV,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    status_code = 200 if db_healthy else 503
    
    if not db_healthy:
        logger.error("Health check failed - database unhealthy")
    
    return JSONResponse(content=health_status, status_code=status_code)

@app.get("/metrics")
async def metrics(db: Session = Depends(get_db)):
    """
    Endpoint برای monitoring
    In production, should be protected with authentication
    """
    if ENV == "production":
        raise HTTPException(status_code=404)
    
    try:
        total_users = db.query(User).count()
        connected_wallets = db.query(User).filter(User.wallet_connected == True).count()
        total_tokens = db.query(func.sum(User.tokens)).scalar() or 0
        
        return {
            "total_users": total_users,
            "connected_wallets": connected_wallets,
            "wallet_connection_rate": f"{(connected_wallets / total_users * 100):.2f}%" if total_users > 0 else "0%",
            "total_tokens_distributed": total_tokens
        }
    except Exception as e:
        logger.error("Error fetching metrics", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")

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
scheduler.start()

@app.on_event("startup")
async def startup():
    logger.info("🚀 Application starting", extra={
        "environment": ENV,
        "rate_limiting": RATE_LIMITING_ENABLED,
        "cache_enabled": CACHE_ENABLED
    })

    webhook_token = os.getenv('WEBHOOK_TOKEN')
    if not webhook_token:
        logger.error("WEBHOOK_TOKEN not set!")
        return

    bot = Bot(token=BOT_TOKEN)
    await bot.initialize()

    webhook_url = f"{APP_DOMAIN}/telegram_webhook"

    try:
        await bot.set_webhook(
            url=webhook_url,
            secret_token=webhook_token,
            drop_pending_updates=True
        )
        logger.info("✅ Telegram webhook set successfully", extra={"url": webhook_url})

        try:
            from telegram import MenuButtonWebApp, WebAppInfo
            menu_button = MenuButtonWebApp(
                text="🚀 Open CCoin",
                web_app=WebAppInfo(url=APP_DOMAIN)
            )
            await bot.set_chat_menu_button(menu_button=menu_button)
            logger.info("✅ Menu button set successfully")
        except ImportError:
            logger.warning("MenuButtonWebApp not available")
        except Exception as e:
            logger.error("Error setting menu button", extra={"error": str(e)})

        webhook_info = await bot.get_webhook_info()
        logger.info("Webhook info retrieved", extra={
            "url": webhook_info.url,
            "pending_updates": webhook_info.pending_update_count
        })

    except Exception as e:
        logger.error("Error setting webhook", extra={"error": str(e)}, exc_info=True)

    try:
        await telegram_app.initialize()
        logger.info("✅ Telegram app initialized")
    except Exception as e:
        logger.error("Error initializing telegram app", extra={"error": str(e)}, exc_info=True)

    await bot.shutdown()

@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()
    logger.info("Application shutdown")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info" if ENV == "production" else "debug",
        access_log=ENV == "development"
    )


@app.get("/metadata.html")
async def serve_metadata():
    return FileResponse("CCOIN/templates/metadata.html", media_type="text/html")
