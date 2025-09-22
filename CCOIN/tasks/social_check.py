from celery import Celery
from sqlalchemy.orm import Session
from CCOIN.database import SessionLocal
from CCOIN.models.user import User
from CCOIN.models.usertask import UserTask
from CCOIN.config import REDIS_URL, INSTAGRAM_ACCESS_TOKEN, X_API_KEY, YOUTUBE_API_KEY, BOT_TOKEN, TELEGRAM_CHANNEL_USERNAME
import aiohttp
import structlog
import redis
import requests
import asyncio
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

# تنظیم Celery
app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)
app.conf.update(
    task_track_started=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json"
)

# Redis client
redis_client = redis.Redis.from_url(REDIS_URL)

# پاداش‌های پلتفرم‌ها
PLATFORM_REWARD = {
    "telegram": 500,
    "instagram": 500,
    "x": 500,
    "youtube": 500,
}

def is_user_in_telegram_channel(user_id: int) -> bool:
    """بررسی عضویت کاربر در کانال تلگرام"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        params = {"chat_id": f"@{TELEGRAM_CHANNEL_USERNAME}", "user_id": user_id}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                status = data.get("result", {}).get("status")
                is_member = status in ["member", "administrator", "creator"]
                logger.info(f"Telegram membership check for user {user_id}: {status} - {'Member' if is_member else 'Not member'}")
                return is_member
            else:
                error_description = data.get("description", "Unknown error")
                logger.error(f"Telegram API error: {error_description}")
                return False
        else:
            logger.error(f"Telegram API HTTP error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error checking Telegram channel membership: {e}")
        return False

async def check_instagram_follow(user_id: str, access_token: str = None) -> bool:
    """بررسی فالو کردن اینستاگرام"""
    if not INSTAGRAM_ACCESS_TOKEN and not access_token:
        logger.error("Instagram API key not configured")
        return False
    
    token = access_token or INSTAGRAM_ACCESS_TOKEN
    
    async with aiohttp.ClientSession() as session:
        try:
            # بررسی followers صفحه رسمی
            async with session.get(
                f"https://graph.instagram.com/v12.0/me/followers?access_token={token}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # بررسی اینکه آیا user_id در لیست followers هست
                    followers = data.get("data", [])
                    is_following = any(follower["id"] == user_id for follower in followers)
                    logger.info(f"Instagram follow check for user {user_id}: {'Following' if is_following else 'Not following'}")
                    return is_following
                else:
                    error_text = await response.text()
                    logger.error(f"Instagram API error: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error checking Instagram follow: {e}")
            return False

async def check_x_follow(user_id: str, access_token: str = None) -> bool:
    """بررسی فالو کردن X (Twitter)"""
    if not X_API_KEY and not access_token:
        logger.error("X API key not configured")
        return False
    
    token = access_token or X_API_KEY
    
    async with aiohttp.ClientSession() as session:
        try:
            # بررسی following list کاربر
            async with session.get(
                f"https://api.twitter.com/2/users/{user_id}/following",
                headers={"Authorization": f"Bearer {token}"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # بررسی اینکه آیا صفحه رسمی CCOIN را فالو کرده
                    following = data.get("data", [])
                    # باید ID صفحه رسمی را اینجا قرار دهید
                    official_account_id = "CCOIN_OFFICIAL_ID"  # این باید ID واقعی باشد
                    is_following = any(followee["id"] == official_account_id for followee in following)
                    logger.info(f"X follow check for user {user_id}: {'Following' if is_following else 'Not following'}")
                    return is_following
                else:
                    error_text = await response.text()
                    logger.error(f"X API error: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error checking X follow: {e}")
            return False

async def check_youtube_subscribe(user_id: str, access_token: str = None) -> bool:
    """بررسی subscribe کردن یوتیوب"""
    if not YOUTUBE_API_KEY and not access_token:
        logger.error("YouTube API key not configured")
        return False
    
    api_key = YOUTUBE_API_KEY
    token = access_token
    
    async with aiohttp.ClientSession() as session:
        try:
            # بررسی subscriptions کاربر
            params = {
                "part": "snippet",
                "forChannelId": "CCOIN_OFFICIAL_CHANNEL_ID",  # ID کانال رسمی
                "key": api_key
            }
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            async with session.get(
                "https://www.googleapis.com/youtube/v3/subscriptions",
                params=params,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get("items", [])
                    is_subscribed = len(items) > 0
                    logger.info(f"YouTube subscribe check for user {user_id}: {'Subscribed' if is_subscribed else 'Not subscribed'}")
                    return is_subscribed
                else:
                    error_text = await response.text()
                    logger.error(f"YouTube API error: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error checking YouTube subscription: {e}")
            return False

def check_social_follow(user_id: str, platform: str, access_token: str = None) -> bool:
    """تابع اصلی برای بررسی follow status در پلتفرم‌های مختلف"""
    cache_key = f"social_check:{user_id}:{platform}"
    cached_result = redis_client.get(cache_key)
    
    if cached_result:
        result = cached_result.decode() == "1"
        logger.info(f"Cache hit for user {user_id} platform {platform}: {result}")
        return result
    
    result = False
    
    try:
        logger.info(f"Checking {platform} follow status for user {user_id}")
        
        if platform == "telegram":
            result = is_user_in_telegram_channel(int(user_id))
        elif platform == "instagram":
            result = asyncio.run(check_instagram_follow(user_id, access_token))
        elif platform == "x":
            result = asyncio.run(check_x_follow(user_id, access_token))
        elif platform == "youtube":
            result = asyncio.run(check_youtube_subscribe(user_id, access_token))
        else:
            logger.warning(f"Unknown platform: {platform}")
            result = False
            
    except Exception as e:
        logger.error(f"Error checking {platform} follow for user {user_id}: {e}")
        result = False
    
    # Cache result for 10 minutes
    redis_client.setex(cache_key, 600, "1" if result else "0")
    logger.info(f"Follow check result for user {user_id} platform {platform}: {result}")
    
    return result

def get_detailed_telegram_status(user_id: int) -> dict:
    """دریافت جزئیات کامل وضعیت عضویت در تلگرام"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        params = {"chat_id": f"@{TELEGRAM_CHANNEL_USERNAME}", "user_id": user_id}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                result = data.get("result", {})
                return {
                    "is_member": result.get("status") in ["member", "administrator", "creator"],
                    "status": result.get("status"),
                    "user_id": result.get("user", {}).get("id"),
                    "username": result.get("user", {}).get("username"),
                    "first_name": result.get("user", {}).get("first_name"),
                    "error": None
                }
            else:
                return {
                    "is_member": False,
                    "status": None,
                    "error": data.get("description", "Unknown error")
                }
        else:
            return {
                "is_member": False,
                "status": None,
                "error": f"HTTP {response.status_code}: {response.text}"
            }
            
    except Exception as e:
        logger.error(f"Error getting detailed Telegram status: {e}")
        return {
            "is_member": False,
            "status": None,
            "error": str(e)
        }

def clear_user_cache(user_id: str, platform: str = None):
    """پاک کردن cache کاربر برای پلتفرم خاص یا همه پلتفرم‌ها"""
    if platform:
        cache_key = f"social_check:{user_id}:{platform}"
        redis_client.delete(cache_key)
        logger.info(f"Cleared cache for user {user_id} platform {platform}")
    else:
        # پاک کردن همه cache های کاربر
        patterns = [
            f"social_check:{user_id}:telegram",
            f"social_check:{user_id}:instagram", 
            f"social_check:{user_id}:x",
            f"social_check:{user_id}:youtube"
        ]
        for pattern in patterns:
            redis_client.delete(pattern)
        logger.info(f"Cleared all cache for user {user_id}")

@app.task
def check_social_tasks():
    """Task برای بررسی دوره‌ای follow status کاربران و کم کردن امتیاز در صورت unfollow"""
    db: Session = SessionLocal()
    try:
        logger.info("Starting periodic social tasks check")
        
        # دریافت همه کاربرانی که حداقل یک task completed دارند
        users_with_completed_tasks = db.query(User).join(UserTask).filter(
            UserTask.completed == True
        ).distinct().all()
        
        logger.info(f"Found {len(users_with_completed_tasks)} users with completed tasks")
        
        for user in users_with_completed_tasks:
            logger.info(f"Checking tasks for user {user.telegram_id}")
            
            for task in user.tasks:
                if task.completed:
                    logger.info(f"Checking {task.platform} task for user {user.telegram_id}")
                    
                    # پاک کردن cache برای بررسی جدید
                    clear_user_cache(user.telegram_id, task.platform)
                    
                    # بررسی مجدد follow status
                    still_following = check_social_follow(user.telegram_id, task.platform)
                    
                    if not still_following:
                        # کاربر unfollow کرده، کم کردن امتیاز
                        reward = PLATFORM_REWARD.get(task.platform, 0)
                        user.tokens = max(0, user.tokens - reward)  # جلوگیری از منفی شدن
                        task.completed = False
                        task.completed_at = None
                        
                        logger.info(f"User {user.telegram_id} unfollowed {task.platform}. "
                                  f"Deducted {reward} tokens. New balance: {user.tokens}")
                    else:
                        logger.info(f"User {user.telegram_id} still following {task.platform}")
        
        db.commit()
        logger.info("Periodic social tasks check completed successfully")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in check_social_tasks: {e}")
        raise
    finally:
        db.close()

@app.task
def verify_single_user_task(user_id: str, platform: str):
    """Task برای بررسی یک task خاص کاربر"""
    try:
        logger.info(f"Verifying {platform} task for user {user_id}")
        
        # پاک کردن cache
        clear_user_cache(user_id, platform)
        
        # بررسی follow status
        result = check_social_follow(user_id, platform)
        
        logger.info(f"Verification result for user {user_id} platform {platform}: {result}")
        return {
            "user_id": user_id,
            "platform": platform,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error verifying task for user {user_id} platform {platform}: {e}")
        return {
            "user_id": user_id,
            "platform": platform,
            "result": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# تنظیم schedule برای check کردن دوره‌ای
from celery.schedules import crontab

app.conf.beat_schedule = {
    'check-social-tasks-daily': {
        'task': 'CCOIN.tasks.social_check.check_social_tasks',
        'schedule': crontab(hour=0, minute=0),  # هر روز ساعت 00:00
    },
}

app.conf.timezone = 'UTC'
