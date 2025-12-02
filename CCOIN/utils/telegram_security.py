from fastapi import HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import TelegramError
from CCOIN.models.user import User
from CCOIN.database import get_db
from CCOIN.config import BOT_TOKEN, TELEGRAM_CHANNEL_USERNAME
import requests
import uuid
import structlog
import os

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
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
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            status = response.json().get("result", {}).get("status")
            return status in ["member", "administrator", "creator"]
        logger.error("Telegram getChatMember error", extra={"status": response.status_code, "text": response.text})
        return False
    except Exception as e:
        logger.error("Error checking channel membership", extra={"error": str(e)})
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
        username = update.message.from_user.username or ""
        first_name = update.message.from_user.first_name or ""
        last_name = update.message.from_user.last_name or ""
        referral_code = context.args[0] if context.args else None

        logger.info("Processing /start", extra={"telegram_id": telegram_id})

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        is_new_user = False

        if not user:
            is_new_user = True
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                referral_code=str(uuid.uuid4())[:8],
                tokens=2000,
                first_login=True,
            )
            db.add(user)

            if referral_code:
                referrer = db.query(User).filter(User.referral_code == referral_code).first()
                if referrer:
                    user.referred_by = referrer.id
                    referrer.tokens += 50
                    logger.info("Referral applied", extra={"referrer": referrer.telegram_id})

            db.commit()
            db.refresh(user)

        else:
            # Update info if changed
            updated = False
            if user.username != username:
                user.username = username
                updated = True
            if user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if user.last_name != last_name:
                user.last_name = last_name
                updated = True
            if updated:
                db.commit()

        base_url = os.getenv("APP_DOMAIN", "https://ccoin2025.onrender.com")
        web_app_url = f"{base_url}/load?telegram_id={telegram_id}" if user.first_login else f"{base_url}/home?telegram_id={telegram_id}"

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🚀 Open CCoin App", web_app=WebAppInfo(url=web_app_url))
        ]])

        if is_new_user:
            text = "💰 **Welcome to CCoin!**\n\n🎉 Your journey starts now!\n💎 2000 CCoin welcome bonus added!\n\n👇 Open the app:"
        else:
            text = f"💰 **Welcome back!**\n\n💎 You have {user.tokens:,} CCoin\n\n👇 Open the app:"

        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
        logger.info("Start message sent", extra={"telegram_id": telegram_id})

    except Exception as e:
        logger.error("Error in /start", extra={"error": str(e)})
        await update.message.reply_text("An error occurred. Please try again.")
    finally:
        db.close()


async def send_commission_payment_link(telegram_id: str, bot_token: str = BOT_TOKEN) -> bool:
    bot = Bot(token=bot_token)
    url = f"https://ccoin2025.onrender.com/commission/browser/pay?telegram_id={telegram_id}"

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("💳 Pay Commission (Open in Browser)", url=url)
    ]])

    text = (
        "💰 **Commission Payment Required**\n\n"
        "To complete your airdrop eligibility, please pay the commission fee.\n\n"
        "Click the button below to open the payment page in your browser."
    )

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        logger.info("Commission payment link sent", extra={"telegram_id": telegram_id})
        return True
    except TelegramError as e:
        logger.error("Telegram error sending commission link", extra={"telegram_id": telegram_id, "error": str(e)})
        return False
    except Exception as e:
        logger.error("Unexpected error sending commission link", extra={"telegram_id": telegram_id, "error": str(e)})
        return False


app.add_handler(CommandHandler("start", start))
