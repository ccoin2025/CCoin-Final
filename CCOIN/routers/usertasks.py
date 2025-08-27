from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from CCOIN.models.usertask import UserTask
from CCOIN.models.user import User
from CCOIN.database import get_db
from CCOIN.utils.telegram_security import is_user_in_telegram_channel
import redis
from CCOIN.config import REDIS_URL

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

redis_client = redis.Redis.from_url(REDIS_URL)

def check_platform_task(user, platform):
    if platform == "telegram":
        return is_user_in_telegram_channel(int(user.telegram_id))
    return False

@router.post("/complete/{task_type}")
@limiter.limit("5/minute")
async def complete_task(task_type: str, platform: str, request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    cache_key = f"task:{user.id}:{task_type}:{platform}"
    cached_result = redis_client.get(cache_key)
    if cached_result and cached_result.decode() == "completed":
        return {"status": True}
    task = db.query(UserTask).filter(UserTask.user_id == user.id, UserTask.task_type == task_type, UserTask.platform == platform).first()
    if not task:
        task = UserTask(user_id=user.id, task_type=task_type, platform=platform, reward=100)
        db.add(task)
    if not task.completed and check_platform_task(user, platform):
        task.completed = True
        user.tokens += task.reward
        db.commit()
        redis_client.setex(cache_key, 3600, "completed")
    return {"status": task.completed}

@router.get("/status")
@limiter.limit("10/minute")
async def get_task_status(request: Request, user_id: str, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id or telegram_id != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid user ID")
    user = db.query(User).filter(User.telegram_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    cache_key = f"task_status:{user_id}"
    cached_status = redis_client.get(cache_key)
    if cached_status:
        return eval(cached_status.decode())  # Convert string back to dict
    status = {
        "task": any(t.completed for t in user.tasks),
        "invite": len(user.referrals) > 0,
        "wallet": bool(user.wallet_address),
        "pay": user.commission_paid
    }
    redis_client.setex(cache_key, 3600, str(status))
    return status
