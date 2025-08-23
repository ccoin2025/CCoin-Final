from celery import Celery
from sqlalchemy.orm import Session
from CCOIN.database import SessionLocal
from CCOIN.models.user import User
from CCOIN.models.usertask import UserTask
from CCOIN.utils.telegram_security import is_user_in_telegram_channel
from CCOIN.config import REDIS_URL, INSTAGRAM_ACCESS_TOKEN, X_API_KEY, YOUTUBE_API_KEY
import aiohttp
import structlog
import redis

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

app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)
app.conf.update(task_track_started=True, task_serializer="json", accept_content=["json"], result_serializer="json")
redis_client = redis.Redis.from_url(REDIS_URL)

PLATFORM_REWARD = {
    "telegram": 500,
    "instagram": 500,
    "x": 500,
    "youtube": 500,
}

async def check_instagram_follow(user_id: str, access_token: str) -> bool:
    if not INSTAGRAM_ACCESS_TOKEN:
        logger.error("Instagram API key not configured")
        return False
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"https://graph.instagram.com/v12.0/me/followers?access_token={access_token}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return any(follower["id"] == user_id for follower in data.get("data", []))
                logger.error(f"Instagram API error: {response.status}")
                return False
        except Exception as e:
            logger.error(f"Error checking Instagram follow: {e}")
            return False

async def check_x_follow(user_id: str, access_token: str) -> bool:
    if not X_API_KEY:
        logger.error("X API key not configured")
        return False
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"https://api.twitter.com/2/users/{user_id}/following",
                headers={"Authorization": f"Bearer {access_token}"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return any(followee["id"] == "CCOIN_OFFICIAL_ID" for followee in data.get("data", []))
                logger.error(f"X API error: {response.status}")
                return False
        except Exception as e:
            logger.error(f"Error checking X follow: {e}")
            return False

async def check_youtube_subscribe(user_id: str, access_token: str) -> bool:
    if not YOUTUBE_API_KEY:
        logger.error("YouTube API key not configured")
        return False
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"https://www.googleapis.com/youtube/v3/subscriptions?part=snippet&forChannelId=CCOIN_OFFICIAL_CHANNEL_ID&key={YOUTUBE_API_KEY}&access_token={access_token}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return len(data.get("items", [])) > 0
                logger.error(f"YouTube API error: {response.status}")
                return False
        except Exception as e:
            logger.error(f"Error checking YouTube subscription: {e}")
            return False

def check_social_follow(user_id: str, platform: str, access_token: str = None) -> bool:
    cache_key = f"social_check:{user_id}:{platform}"
    cached_result = redis_client.get(cache_key)
    if cached_result:
        return cached_result.decode() == "1"
    import asyncio
    if platform == "telegram":
        result = is_user_in_telegram_channel(int(user_id))
    elif platform == "instagram":
        result = asyncio.run(check_instagram_follow(user_id, access_token))
    elif platform == "x":
        result = asyncio.run(check_x_follow(user_id, access_token))
    elif platform == "youtube":
        result = asyncio.run(check_youtube_subscribe(user_id, access_token))
    else:
        result = False
    redis_client.setex(cache_key, 3600, "1" if result else "0")
    return result

@app.task
def check_social_tasks():
    db: Session = SessionLocal()
    try:
        users = db.query(User).all()
        for user in users:
            for task in user.tasks:
                if task.completed:
                    still_following = check_social_follow(user.telegram_id, task.platform, user.access_token)
                    if not still_following:
                        user.tokens -= PLATFORM_REWARD.get(task.platform, 0)
                        task.completed = False
                        logger.info(f"{user.username} unfollowed {task.platform}. Tokens deducted.")
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error in check_social_tasks: {e}")
    finally:
        db.close()