import os
from dotenv import load_dotenv
import structlog

logger = structlog.get_logger()

load_dotenv()

# Telegram Bot Settings
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.warning("BOT_TOKEN is not set in environment variables")

BOT_USERNAME = os.getenv("BOT_USERNAME", "CTG_COIN_BOT")
TELEGRAM_CHANNEL_USERNAME = os.getenv("TELEGRAM_CHANNEL_USERNAME", "CCOIN_OFFICIAL")

# Social Media Settings
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "ccoin_official")
X_USERNAME = os.getenv("X_USERNAME", "CCOIN_OFFICIAL")
YOUTUBE_CHANNEL_HANDLE = os.getenv("YOUTUBE_CHANNEL_HANDLE", "@CCOIN_OFFICIAL")

# Solana Settings - CHANGED TO MAINNET
SOLANA_RPC = os.getenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
ADMIN_WALLET = os.getenv("ADMIN_WALLET", "5YFFCvmi2f4ZWZYUWWBuMSmmjXrYA1QptaTaLG8vi15K")
COMMISSION_AMOUNT = float(os.getenv("COMMISSION_AMOUNT", "0.001"))
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "TokenkegQfeZyiNwAJbNbGK7Qx6m")
if not CONTRACT_ADDRESS:
    logger.warning("CONTRACT_ADDRESS is not set in environment variables")

# Security Keys
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    logger.warning("SECRET_KEY is not set in environment variables")

DAPP_PRIVATE_KEY = os.getenv("DAPP_PRIVATE_KEY")
if not DAPP_PRIVATE_KEY:
    logger.warning("DAPP_PRIVATE_KEY is not set in environment variables")

ADMIN_PRIVATE_KEY = os.getenv("ADMIN_PRIVATE_KEY")
if not ADMIN_PRIVATE_KEY:
    logger.warning("ADMIN_PRIVATE_KEY is not set in environment variables")

# Redis Settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# External APIs Settings
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
X_API_KEY = os.getenv("X_API_KEY", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# App Settings
APP_DOMAIN = os.getenv("APP_DOMAIN", "https://ccoin-final.onrender.com")
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN")
if not WEBHOOK_TOKEN:
    logger.warning("WEBHOOK_TOKEN is not set in environment variables")
