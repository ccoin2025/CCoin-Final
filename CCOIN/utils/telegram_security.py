from fastapi import HTTPException, Request, Depends
from sqlalchemy.orm import Session
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from CCOIN.models.user import User
from CCOIN.database import get_db
from CCOIN.config import BOT_TOKEN, TELEGRAM_CHANNEL_USERNAME
import requests
import uuid
import structlog

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
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db: Session = next(get_db())  # Get session from generator
    telegram_id = str(update.message.from_user.id)
    username = update.message.from_user.username
    first_name = update.message.from_user.first_name
    last_name = update.message.from_user.last_name
    referral_code = context.args[0] if context.args else None

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
                user.referred_by = referrer.id
                referrer.tokens += 50
        db.commit()
        db.refresh(user)

    await update.message.reply_text("Welcome! Go to /load")
    logger.info(f"User {telegram_id} started bot")
    return {"ok": True}

# Add command handler
app.add_handler(CommandHandler("start", start))
