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

# Memory cache برای جایگزین Redis
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

def clear_expired_cache():
    """پاک کردن cache های منقضی شده"""
    current_time = time.time()
    expired_keys = []
    
    for key, (value, expiry) in memory_cache.items():
        if current_time >= expiry:
            expired_keys.append(key)
    
    for key in expired_keys:
        del memory_cache[key]
    
    if expired_keys:
        logger.info(f"Cleared {len(expired_keys)} expired cache entries")

def is_user_in_telegram_channel(user_id: int) -> bool:
    """بررسی عضویت کاربر در کانال تلگرام CCOIN_OFFICIAL"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        params = {"chat_id": "@CCOIN_OFFICIAL", "user_id": user_id}
        
        logger.info(f"Checking Telegram membership for user {user_id}")
        logger.info(f"API URL: {url}")
        logger.info(f"Parameters: {params}")
        
        response = requests.get(url, params=params, timeout=15)
        
        logger.info(f"Telegram API response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Telegram API response data: {data}")
            
            if data.get("ok"):
                result = data.get("result", {})
                status = result.get("status")
                user_info = result.get("user", {})
                
                is_member = status in ["member", "administrator", "creator"]
                
                logger.info(f"User {user_id} status in channel: {status}")
                logger.info(f"User info: {user_info}")
                logger.info(f"Is member: {is_member}")
                
                return is_member
            else:
                error_description = data.get("description", "Unknown error")
                error_code = data.get("error_code", "Unknown")
                
                logger.error(f"Telegram API error: {error_code} - {error_description}")
                
                # تشخیص انواع خطاها
                if error_code == 400:
                    if "chat not found" in error_description.lower():
                        logger.error("❌ Channel @CCOIN_OFFICIAL not found or bot has no access")
                        logger.error("🔧 Solution: Add bot to channel as administrator")
                    elif "user not found" in error_description.lower():
                        logger.info(f"ℹ️ User {user_id} not found in Telegram")
                    elif "bot was blocked" in error_description.lower():
                        logger.error(f"❌ Bot was blocked by user {user_id}")
                    else:
                        logger.error(f"❌ Unknown 400 error: {error_description}")
                elif error_code == 403:
                    logger.error("❌ Bot forbidden to access channel")
                    logger.error("🔧 Solution: Make bot administrator of the channel")
                
                return False
        else:
            response_text = response.text
            logger.error(f"Telegram API HTTP error: {response.status_code}")
            logger.error(f"Response text: {response_text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"Timeout while checking Telegram membership for user {user_id}")
        return False
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error while checking Telegram membership for user {user_id}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking Telegram channel membership: {e}")
        return False

def check_instagram_follow(user_id: str) -> bool:
    """بررسی فالو کردن اینستاگرام ccoin_official"""
    try:
        # فعلاً برای تست True برمی‌گردانیم
        # در آینده API اینستاگرام پیاده‌سازی خواهد شد
        logger.info(f"Instagram follow check for user {user_id}: Mock verification - returning True")
        return True
    except Exception as e:
        logger.error(f"Error checking Instagram follow for user {user_id}: {e}")
        return False

def check_x_follow(user_id: str) -> bool:
    """بررسی فالو کردن X CCOIN_OFFICIAL"""
    try:
        # فعلاً برای تست True برمی‌گردانیم
        # در آینده API X پیاده‌سازی خواهد شد
        logger.info(f"X follow check for user {user_id}: Mock verification - returning True")
        return True
    except Exception as e:
        logger.error(f"Error checking X follow for user {user_id}: {e}")
        return False

def check_youtube_subscribe(user_id: str) -> bool:
    """بررسی subscribe کردن یوتیوب @CCOIN_OFFICIAL"""
    try:
        # فعلاً برای تست True برمی‌گردانیم
        # در آینده API YouTube پیاده‌سازی خواهد شد
        logger.info(f"YouTube subscribe check for user {user_id}: Mock verification - returning True")
        return True
    except Exception as e:
        logger.error(f"Error checking YouTube subscription for user {user_id}: {e}")
        return False

def check_social_follow(user_id: str, platform: str) -> bool:
    """تابع اصلی برای بررسی follow status در پلتفرم‌های مختلف"""
    
    # پاک کردن cache های منقضی شده
    clear_expired_cache()
    
    cache_key = f"social_check:{user_id}:{platform}"
    
    # بررسی cache
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        result = cached_result == "1"
        logger.info(f"📋 Cache hit for user {user_id} platform {platform}: {result}")
        return result
    
    result = False
    
    try:
        logger.info(f"🔍 Checking {platform} follow status for user {user_id}")
        
        if platform == "telegram":
            result = is_user_in_telegram_channel(int(user_id))
        elif platform == "instagram":
            result = check_instagram_follow(user_id)
        elif platform == "x":
            result = check_x_follow(user_id)
        elif platform == "youtube":
            result = check_youtube_subscribe(user_id)
        else:
            logger.warning(f"⚠️ Unknown platform: {platform}")
            result = False
            
    except ValueError as e:
        logger.error(f"❌ Invalid user_id format for {platform}: {user_id} - {e}")
        result = False
    except Exception as e:
        logger.error(f"❌ Error checking {platform} follow for user {user_id}: {e}")
        result = False
    
    # Cache result for 10 minutes
    set_in_cache(cache_key, "1" if result else "0", 600)
    logger.info(f"✅ Follow check result for user {user_id} platform {platform}: {result}")
    
    return result

def get_detailed_telegram_status(user_id: int) -> dict:
    """دریافت جزئیات کامل وضعیت عضویت در تلگرام"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        params = {"chat_id": "@CCOIN_OFFICIAL", "user_id": user_id}
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                result = data.get("result", {})
                user_info = result.get("user", {})
                
                return {
                    "success": True,
                    "is_member": result.get("status") in ["member", "administrator", "creator"],
                    "status": result.get("status"),
                    "user_id": user_info.get("id"),
                    "username": user_info.get("username"),
                    "first_name": user_info.get("first_name"),
                    "last_name": user_info.get("last_name"),
                    "is_bot": user_info.get("is_bot"),
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "is_member": False,
                    "status": None,
                    "error": data.get("description", "Unknown error"),
                    "error_code": data.get("error_code")
                }
        else:
            return {
                "success": False,
                "is_member": False,
                "status": None,
                "error": f"HTTP {response.status_code}: {response.text}",
                "error_code": response.status_code
            }
            
    except Exception as e:
        logger.error(f"Error getting detailed Telegram status: {e}")
        return {
            "success": False,
            "is_member": False,
            "status": None,
            "error": str(e),
            "error_code": None
        }

def clear_user_cache(user_id: str, platform: str = None):
    """پاک کردن cache کاربر برای پلتفرم خاص یا همه پلتفرم‌ها"""
    if platform:
        cache_key = f"social_check:{user_id}:{platform}"
        if cache_key in memory_cache:
            del memory_cache[cache_key]
            logger.info(f"🧹 Cleared cache for user {user_id} platform {platform}")
    else:
        # پاک کردن همه cache های کاربر
        patterns = [
            f"social_check:{user_id}:telegram",
            f"social_check:{user_id}:instagram", 
            f"social_check:{user_id}:x",
            f"social_check:{user_id}:youtube"
        ]
        cleared_count = 0
        for pattern in patterns:
            if pattern in memory_cache:
                del memory_cache[pattern]
                cleared_count += 1
        
        if cleared_count > 0:
            logger.info(f"🧹 Cleared {cleared_count} cache entries for user {user_id}")

def get_cache_stats():
    """دریافت آمار cache"""
    current_time = time.time()
    active_entries = 0
    expired_entries = 0
    
    for key, (value, expiry) in memory_cache.items():
        if current_time < expiry:
            active_entries += 1
        else:
            expired_entries += 1
    
    return {
        "total_entries": len(memory_cache),
        "active_entries": active_entries,
        "expired_entries": expired_entries,
        "cache_size_mb": len(str(memory_cache)) / (1024 * 1024)
    }

def verify_bot_access():
    """بررسی دسترسی بات به کانال"""
    try:
        if not BOT_TOKEN:
            return {
                "success": False,
                "error": "BOT_TOKEN not configured"
            }
        
        # تست با getMe
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"Bot token invalid: {response.status_code}"
            }
        
        bot_info = response.json()
        
        # تست دسترسی به کانال
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChat"
        params = {"chat_id": "@CCOIN_OFFICIAL"}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            chat_info = response.json()
            return {
                "success": True,
                "bot_info": bot_info.get("result", {}),
                "chat_info": chat_info.get("result", {}),
                "can_access_channel": True
            }
        else:
            return {
                "success": False,
                "bot_info": bot_info.get("result", {}),
                "error": f"Cannot access channel: {response.text}",
                "can_access_channel": False
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# تابع برای manual verification (برای تست)
def manual_verify_user_task(user_id: str, platform: str, force: bool = False):
    """تایید دستی task کاربر"""
    try:
        # پاک کردن cache
        if force:
            clear_user_cache(user_id, platform)
        
        # بررسی مجدد
        result = check_social_follow(user_id, platform)
        
        return {
            "user_id": user_id,
            "platform": platform,
            "result": result,
            "forced": force,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "user_id": user_id,
            "platform": platform,
            "result": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# تابع cleanup برای memory management
def cleanup_cache():
    """پاک کردن کامل cache"""
    global memory_cache
    cache_size = len(memory_cache)
    memory_cache.clear()
    logger.info(f"🧹 Cleared all cache ({cache_size} entries)")
    
    return {
        "cleared_entries": cache_size,
        "timestamp": datetime.utcnow().isoformat()
    }
