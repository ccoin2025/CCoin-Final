import os
from dotenv import load_dotenv
import structlog

# تنظیم لاگ‌گیری
logger = structlog.get_logger()

# بارگذاری environment variables از فایل .env (برای توسعه لوکال)
load_dotenv()

# تنظیمات Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.warning("BOT_TOKEN is not set in environment variables")

BOT_USERNAME = os.getenv("BOT_USERNAME", "CTG_COIN_BOT")
TELEGRAM_CHANNEL_USERNAME = os.getenv("TELEGRAM_CHANNEL_USERNAME", "CCOIN_OFFICIAL")

# تنظیمات شبکه‌های اجتماعی
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "ccoin_official")
X_USERNAME = os.getenv("X_USERNAME", "CCOIN_OFFICIAL")
YOUTUBE_CHANNEL_HANDLE = os.getenv("YOUTUBE_CHANNEL_HANDLE", "@CCOIN_OFFICIAL")

# تنظیمات Solana
SOLANA_RPC = os.getenv("SOLANA_RPC", "https://api.devnet.solana.com")
ADMIN_WALLET = os.getenv("ADMIN_WALLET", "5YFFCvmi2f4ZWZYUWWBuMSmmjXrYA1QptaTaLG8vi15K")
COMMISSION_AMOUNT = float(os.getenv("COMMISSION_AMOUNT", "0.1"))
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "TokenkegQfeZyiNwAJbNbGK7Qx6m")  # پیش‌فرض برای SPL Token
if not CONTRACT_ADDRESS:
    logger.warning("CONTRACT_ADDRESS is not set in environment variables")

# کلیدهای امنیتی
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    logger.warning("SECRET_KEY is not set in environment variables")

DAPP_PRIVATE_KEY = os.getenv("DAPP_PRIVATE_KEY")
if not DAPP_PRIVATE_KEY:
    logger.warning("DAPP_PRIVATE_KEY is not set in environment variables")

ADMIN_PRIVATE_KEY = os.getenv("ADMIN_PRIVATE_KEY")
if not ADMIN_PRIVATE_KEY:
    logger.warning("ADMIN_PRIVATE_KEY is not set in environment variables")

# تنظیمات Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# تنظیمات APIهای خارجی
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
X_API_KEY = os.getenv("X_API_KEY", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# تنظیمات برنامه
APP_DOMAIN = os.getenv("APP_DOMAIN", "https://ccoin-final.onrender.com")
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN")
if not WEBHOOK_TOKEN:
    logger.warning("WEBHOOK_TOKEN is not set in environment variables")
