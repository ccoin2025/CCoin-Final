import os
from dotenv import load_dotenv
import structlog

logger = structlog.get_logger()

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    logger.warning("BOT_TOKEN is not set in environment variables")

BOT_USERNAME = os.getenv("BOT_USERNAME", "CTG_COIN_BOT")
TELEGRAM_CHANNEL_USERNAME = os.getenv("TELEGRAM_CHANNEL_USERNAME", "CCOIN_OFFICIAL")

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "ccoin_official")
X_USERNAME = os.getenv("X_USERNAME", "CCOIN_OFFICIAL")
YOUTUBE_CHANNEL_HANDLE = os.getenv("YOUTUBE_CHANNEL_HANDLE", "@CCOIN_OFFICIAL")

SOLANA_RPC = os.getenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
SOLANA_RPC_FALLBACK_1 = os.getenv("SOLANA_RPC_FALLBACK_1", "https://mainnet.helius-rpc.com/?api-key=")
SOLANA_RPC_FALLBACK_2 = os.getenv("SOLANA_RPC_FALLBACK_2", "https://solana-mainnet.rpc.extrnode.com")

RPC_MAX_RETRIES = int(os.getenv("RPC_MAX_RETRIES", "3"))
RPC_RETRY_DELAY = int(os.getenv("RPC_RETRY_DELAY", "2")) 
RPC_TIMEOUT = int(os.getenv("RPC_TIMEOUT", "30")) 

TX_SCAN_LIMIT = int(os.getenv("TX_SCAN_LIMIT", "5"))  
TX_FINALIZATION_WAIT = int(os.getenv("TX_FINALIZATION_WAIT", "5"))  

ADMIN_WALLET = os.getenv("ADMIN_WALLET", "5YFFCvmi2f4ZWZYUWWBuMSmmjXrYA1QptaTaLG8vi15K")
COMMISSION_AMOUNT = float(os.getenv("COMMISSION_AMOUNT", "0.01"))
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "TokenkegQfeZyiNwAJbNbGK7Qx6m")
if not CONTRACT_ADDRESS:
    logger.warning("CONTRACT_ADDRESS is not set in environment variables")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    logger.warning("SECRET_KEY is not set in environment variables")

CSRF_SECRET_KEY = os.getenv("CSRF_SECRET_KEY", SECRET_KEY)

DAPP_PRIVATE_KEY = os.getenv("DAPP_PRIVATE_KEY")
if not DAPP_PRIVATE_KEY:
    logger.warning("DAPP_PRIVATE_KEY is not set in environment variables")

ADMIN_PRIVATE_KEY = os.getenv("ADMIN_PRIVATE_KEY")
if not ADMIN_PRIVATE_KEY:
    logger.warning("ADMIN_PRIVATE_KEY is not set in environment variables")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
X_API_KEY = os.getenv("X_API_KEY", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

APP_DOMAIN = os.getenv("APP_DOMAIN", "https://ccoin2025.onrender.com")
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN")
if not WEBHOOK_TOKEN:
    logger.warning("WEBHOOK_TOKEN is not set in environment variables")

CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))

RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
GLOBAL_RATE_LIMIT = os.getenv("GLOBAL_RATE_LIMIT", "100/minute")

ENV = os.getenv("ENV", "production")
DEBUG = ENV == "development"

RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "")
RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY", "")
