from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.models.usertask import UserTask
from CCOIN.tasks.social_check import PLATFORM_REWARD, check_social_follow
from fastapi.templating import Jinja2Templates
import os
import redis
from CCOIN.config import REDIS_URL

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
redis_client = redis.Redis.from_url(REDIS_URL)

@router.get("/", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def get_earn(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    tasks = [
        {"label": "Join Telegram", "reward": PLATFORM_REWARD["telegram"], "platform": "telegram", "icon": "Telegram.png", "completed": any(t.platform == "telegram" and t.completed for t in user.tasks)},
        {"label": "Follow Instagram", "reward": PLATFORM_REWARD.get("instagram", 300), "platform": "instagram", "icon": "Instagram.png", "completed": any(t.platform == "instagram" and t.completed for t in user.tasks)},
        {"label": "Follow X", "reward": PLATFORM_REWARD.get("x", 300), "platform": "x", "icon": "X.png", "completed": any(t.platform == "x" and t.completed for t in user.tasks)},
        {"label": "Subscribe YouTube", "reward": PLATFORM_REWARD.get("youtube", 300), "platform": "youtube", "icon": "YouTube.png", "completed": any(t.platform == "youtube" and t.completed for t in user.tasks)},
    ]
    return templates.TemplateResponse("earn.html", {"request": request, "tasks": tasks})

@router.post("/verify-task")
@limiter.limit("5/minute")
async def verify_task(platform: str, request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    cache_key = f"task_verify:{telegram_id}:{platform}"
    cached_result = redis_client.get(cache_key)
    if cached_result:
        return {"success": bool(cached_result)}
    if check_social_follow(user.telegram_id, platform):
        redis_client.setex(cache_key, 3600, "1")
        return {"success": True}
    else:
        redis_client.setex(cache_key, 3600, "0")
        return {"success": False, "error": "Not followed"}

@router.post("/claim-reward")
@limiter.limit("5/minute")
async def claim_reward(platform: str, request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    task = db.query(UserTask).filter(UserTask.user_id == user.id, UserTask.platform == platform).first()
    if task and not task.completed:
        task.completed = True
        user.tokens += PLATFORM_REWARD.get(platform, 0)
        db.commit()
        redis_client.delete(f"task_verify:{telegram_id}:{platform}")
        return {"success": True}
    return {"success": False, "error": "Task already claimed or not verified"}
