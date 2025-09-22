from sqlalchemy.orm import Session
from CCOIN.database import SessionLocal
from CCOIN.models.user import User
from CCOIN.models.usertask import UserTask
from CCOIN.config import (BOT_TOKEN, TELEGRAM_CHANNEL_USERNAME)
import structlog
import requests
import time
from datetime import datetime

# تنظیم لاگ‌گیری
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

# Memory cache
memory_cache = {}

# پاداش‌های پلتفرم‌ها
PLATFORM_REWARD = {
    "telegram": 500,
    "instagram": 500,
    "x": 500,
    "youtube": 500,
}

def get_from_cache(key):
    """دریافت از memory cache"""
    if key in memory_cache:
        value, expiry = memory_cache[key]
        if time.time() < expiry:
            return value
        else:
            del memory_cache[key]
    return None

def set_in_cache(key, value, ttl):
    """ذخیره در memory cache"""
    memory_cache[key] = (value, time.time() + ttl)

def is_user_in_telegram_channel(user_id: int) -> bool:
    """بررسی عضویت کاربر در کانال تلگرام"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        params = {"chat_id": "@CCOIN_OFFICIAL", "user_id": user_id}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                status = data.get("result", {}).get("status")
                is_member = status in ["member", "administrator", "creator"]
                logger.info(f"Telegram membership check for user {user_id}: {status}")
                return is_member
            else:
                error_description = data.get("description", "Unknown error")
                logger.error(f"Telegram API error: {error_description}")
                return False
        else:
            logger.error(f"Telegram API HTTP error: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error checking Telegram channel membership: {e}")
        return False

def check_social_follow(user_id: str, platform: str) -> bool:
    """تابع اصلی برای بررسی follow status"""
    cache_key = f"social_check:{user_id}:{platform}"
    
    # بررسی cache
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        result = cached_result == "1"
        logger.info(f"Cache hit for user {user_id} platform {platform}: {result}")
        return result
    
    result = False
    
    try:
        logger.info(f"Checking {platform} follow status for user {user_id}")
        
        if platform == "telegram":
            result = is_user_in_telegram_channel(int(user_id))
        elif platform in ["instagram", "x", "youtube"]:
            # فعلاً برای سایر پلتفرم‌ها True برمی‌گردانیم
            result = True
            logger.info(f"{platform} follow check for user {user_id}: Mock check - returning True")
        else:
            logger.warning(f"Unknown platform: {platform}")
            result = False
            
    except Exception as e:
        logger.error(f"Error checking {platform} follow for user {user_id}: {e}")
        result = False
    
    # Cache result for 10 minutes
    set_in_cache(cache_key, "1" if result else "0", 600)
    logger.info(f"Follow check result for user {user_id} platform {platform}: {result}")
    
    return result
