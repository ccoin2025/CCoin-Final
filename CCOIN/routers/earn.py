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
from pydantic import BaseModel
import os
import time
from CCOIN.config import REDIS_URL

class TaskRequest(BaseModel):
    platform: str

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

# Memory cache برای جایگزین Redis
memory_cache = {}
CACHE_EXPIRY = 600  # 10 دقیقه

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
        {"label": "Follow Instagram", "reward": PLATFORM_REWARD.get("instagram", 500), "platform": "instagram", "icon": "Instagram.png", "completed": any(t.platform == "instagram" and t.completed for t in user.tasks)},
        {"label": "Follow X", "reward": PLATFORM_REWARD.get("x", 500), "platform": "x", "icon": "X.png", "completed": any(t.platform == "x" and t.completed for t in user.tasks)},
        {"label": "Subscribe YouTube", "reward": PLATFORM_REWARD.get("youtube", 500), "platform": "youtube", "icon": "YouTube.png", "completed": any(t.platform == "youtube" and t.completed for t in user.tasks)},
    ]
    
    return templates.TemplateResponse("earn.html", {"request": request, "tasks": tasks, "user_id": telegram_id})

@router.post("/verify-task")
@limiter.limit("5/minute")
async def verify_task(task_data: TaskRequest, request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    platform = task_data.platform
    cache_key = f"task_verify:{telegram_id}:{platform}"
    
    # بررسی cache
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        return {"success": bool(int(cached_result))}
    
    # بررسی اینکه آیا کاربر قبلاً این task را complete کرده
    existing_task = db.query(UserTask).filter(
        UserTask.user_id == user.id, 
        UserTask.platform == platform
    ).first()
    
    if existing_task and existing_task.completed:
        return {"success": True, "message": "Already completed"}
    
    # بررسی follow status
    try:
        result = check_social_follow(telegram_id, platform)
        set_in_cache(cache_key, "1" if result else "0", CACHE_EXPIRY)
        return {"success": result}
    except Exception as e:
        print(f"Error in verify_task: {e}")
        return {"success": False, "error": "Verification failed"}

@router.post("/claim-reward")
@limiter.limit("5/minute")
async def claim_reward(task_data: TaskRequest, request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    platform = task_data.platform
    task = db.query(UserTask).filter(UserTask.user_id == user.id, UserTask.platform == platform).first()
    
    if not task:
        # ایجاد task جدید
        task = UserTask(user_id=user.id, platform=platform, completed=False)
        db.add(task)
    
    if not task.completed:
        # بررسی مجدد follow status
        try:
            result = check_social_follow(telegram_id, platform)
            if result:
                task.completed = True
                reward = PLATFORM_REWARD.get(platform, 0)
                user.tokens += reward
                db.commit()
                
                # پاک کردن cache
                cache_key = f"task_verify:{telegram_id}:{platform}"
                if cache_key in memory_cache:
                    del memory_cache[cache_key]
                
                return {"success": True, "tokens_added": reward}
            else:
                return {"success": False, "error": "Follow verification failed"}
        except Exception as e:
            print(f"Error in claim_reward: {e}")
            return {"success": False, "error": "Reward claim failed"}
    
    return {"success": False, "error": "Task already claimed"}
