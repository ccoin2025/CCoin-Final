from fastapi import HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import WebAppInfo  # این import مهم است
from CCOIN.models.user import User
from CCOIN.database import get_db
from CCOIN.config import BOT_TOKEN, TELEGRAM_CHANNEL_USERNAME
import requests
import uuid
import structlog
import os
from urllib.parse import urlencode

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

# Initialize Telegram Bot Application
app = ApplicationBuilder().token(BOT_TOKEN).build()

def is_user_in_telegram_channel(user_id: int) -> bool:
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        params = {"chat_id": f"@{TELEGRAM_CHANNEL_USERNAME}", "user_id": user_id}
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("result", {}).get("status")
            return status in ["member", "administrator", "creator"]
        
        logger.error(f"Telegram API error: {response.status_code} - {response.text}")
        return False
    except Exception as e:
        logger.error(f"Error checking Telegram channel membership: {e}")
        return False

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        return RedirectResponse(url="https://t.me/CTG_COIN_BOT")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from CCOIN.database import SessionLocal
    
    db = SessionLocal()
    try:
        telegram_id = str(update.message.from_user.id)
        username = update.message.from_user.username
        first_name = update.message.from_user.first_name
        last_name = update.message.from_user.last_name
        referral_code = context.args[0] if context.args else None
        
        logger.info(f"Processing /start command for user {telegram_id}")
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                referral_code=str(uuid.uuid4())[:8],
                tokens=2000,  # welcome bonus
                first_login=True,
            )
            db.add(user)
            
            if referral_code:
                referrer = db.query(User).filter(User.referral_code == referral_code).first()
                if referrer:
                    user.referred_by = referrer.id
                    referrer.tokens += 50
            
            db.commit()
            db.refresh(user)
            logger.info(f"New user created: {telegram_id}")
        else:
            logger.info(f"Existing user: {telegram_id}")
        
        # Create Web App URL
        base_url = os.getenv('APP_DOMAIN', 'https://ccoin-final.onrender.com')
        web_app_url = f"{base_url}/load?telegram_id={telegram_id}"
        
        # استفاده از WebAppInfo بجای url
        web_app = WebAppInfo(url=web_app_url)
        
        # Create button with web_app parameter
        keyboard = [
            [InlineKeyboardButton("🚀 Open CCoin App", web_app=web_app)]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_message = (
            "💰 **Welcome to CCoin!**\n\n"
            "🎉 Your crypto journey starts here!\n"
            "💎 Earn tokens, complete tasks, and build your wealth!\n\n"
            "👇 Click the button below to open the app:"
        )
        
        await update.message.reply_text(
            welcome_message, 
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    finally:
        db.close()

# Add command handler
app.add_handler(CommandHandler("start", start))
