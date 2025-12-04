from fastapi import HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
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
        
        # بررسی اینکه آیا کاربر قبلاً وجود دارد
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        
        is_new_user = False
        
        if not user:
            # کاربر جدید است
            is_new_user = True
            logger.info(f"Creating new user: {telegram_id}")
            
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                referral_code=str(uuid.uuid4())[:8],
                tokens=2000,  # welcome bonus
                first_login=True,
            )
            
            # فقط برای کاربران جدید کد رفرال پردازش می‌شود
            if referral_code:
                referrer = db.query(User).filter(User.referral_code == referral_code).first()
                if referrer:
                    user.referred_by = referrer.id
                    referrer.tokens += 50  # جایزه برای صاحب رفرال
                    logger.info(f"New user {telegram_id} referred by {referrer.telegram_id}")
                else:
                    logger.warning(f"Invalid referral code: {referral_code}")
            else:
                logger.info(f"New user {telegram_id} joined without referral code")
            
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"New user created: {telegram_id} with 2000 tokens")
        
        else:
            # کاربر قبلاً وجود داشته
            logger.info(f"Existing user: {telegram_id}, first_login={user.first_login}")
            
            # اگر کاربر قبلاً وجود داشته باشد، کد رفرال پردازش نمی‌شود
            if referral_code:
                logger.info(f"Ignoring referral code {referral_code} for existing user {telegram_id}")
            
            # فقط اطلاعات کاربر را به‌روزرسانی می‌کنیم (در صورت نیاز)
            if user.username != username:
                user.username = username
            if user.first_name != first_name:
                user.first_name = first_name
            if user.last_name != last_name:
                user.last_name = last_name
            
            db.commit()
            db.refresh(user)
        
        # Create Web App URL based on user status
        base_url = os.getenv('APP_DOMAIN', 'https://ccoin2025.onrender.com')
        
        # اگر کاربر جدید است یا first_login=True است، به load برود
        if user.first_login:
            web_app_url = f"{base_url}/load?telegram_id={telegram_id}"
        else:
            web_app_url = f"{base_url}/home?telegram_id={telegram_id}"
        
        # استفاده از WebAppInfo
        try:
            from telegram import WebAppInfo
            web_app = WebAppInfo(url=web_app_url)
            keyboard = [
                [InlineKeyboardButton("🚀 Open CCoin App", web_app=web_app)]
            ]
            logger.info("Using WebAppInfo for inline button")
        except ImportError:
            keyboard = [
                [InlineKeyboardButton("🚀 Open CCoin App", url=web_app_url)]
            ]
            logger.info("WebAppInfo not available, using URL")
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if is_new_user:
            if user.referred_by:
                welcome_message = (
                    "💰 **Welcome to CCoin!**\n\n"
                    "🎉 Your crypto journey starts here!\n"
                    "💎 You received 2000 CCoin as welcome bonus!\n"
                    "🎯 Complete tasks and earn more tokens!\n"
                    "👥 Thanks for using a referral link!\n\n"
                    "👇 Click the button below to open the app:"
                )
            else:
                welcome_message = (
                    "💰 **Welcome to CCoin!**\n\n"
                    "🎉 Your crypto journey starts here!\n"
                    "💎 You received 2000 CCoin as welcome bonus!\n"
                    "🎯 Complete tasks and earn more tokens!\n\n"
                    "👇 Click the button below to open the app:"
                )
        else:
            welcome_message = (
                "💰 **Welcome back to CCoin!**\n\n"
                f"💎 You have {user.tokens} tokens\n"
                "🎯 Ready to earn more?\n\n"
                "👇 Click the button below to open the app:"
            )
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        logger.info(f"Start message sent to user {telegram_id}")
    
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text("خطایی رخ داد. لطفاً دوباره تلاش کنید.")
    
    finally:
        db.close()


async def send_commission_payment_link(telegram_id: str, bot_token: str):
    """
    ارسال لینک پرداخت کمیشن به کاربر از طریق Bot
    این لینک در مرورگر خارجی باز می‌شود
    """
    from telegram import Bot

    try:
        bot = Bot(token=bot_token)
        
        # ساخت URL کامل
        base_url = os.getenv('APP_DOMAIN', 'https://ccoin2025.onrender.com')
        commission_url = f"{base_url}/commission/browser/pay?telegram_id={telegram_id}"

        # ✅ ارسال لینک بدون دکمه - این 100% در مرورگر خارجی باز می‌شود
        message_text = (
            "💰 **Commission Payment Required**\n\n"
            "To complete your airdrop eligibility, please pay the commission fee.\n\n"
            "🌐 **Click the link below** to open in your browser:\n"
            f"{commission_url}\n\n"
            "✅ After payment, return to the bot and your status will update automatically."
        )

        await bot.send_message(
            chat_id=telegram_id,
            text=message_text,
            parse_mode='Markdown',
            disable_web_page_preview=False
        )
        
        logger.info(f"✅ Commission payment link sent to user {telegram_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error sending payment link to {telegram_id}: {e}", exc_info=True)
        return False
