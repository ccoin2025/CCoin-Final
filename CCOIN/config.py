from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "CTG_COIN_BOT")  # اضافه کردن username Bot
TELEGRAM_CHANNEL_USERNAME = os.getenv("TELEGRAM_CHANNEL_USERNAME")
SOLANA_RPC = os.getenv("SOLANA_RPC")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
SECRET_KEY = os.getenv("SECRET_KEY")
REDIS_URL = os.getenv("REDIS_URL")
COMMISSION_AMOUNT = float(os.getenv("COMMISSION_AMOUNT", 0.1))
ADMIN_WALLET = os.getenv("ADMIN_WALLET")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
X_API_KEY = os.getenv("X_API_KEY", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# متغیرهای اضافه شده قبلی
APP_DOMAIN = os.getenv("APP_DOMAIN", "https://ccoin-final.onrender.com")
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN")
ADMIN_PRIVATE_KEY = os.getenv("ADMIN_PRIVATE_KEY")
