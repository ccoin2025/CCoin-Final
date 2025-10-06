from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.models.usertask import UserTask
from CCOIN.tasks.social_check import PLATFORM_REWARD, check_social_follow, check_and_update_all_user_tasks
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, validator
import os
import time
import structlog
from datetime import datetime, timezone
from typing import Optional

logger = structlog.get_logger()

class TaskRequest(BaseModel):
    platform: str

    @validator('platform')
    def validate_platform(cls, v):
        allowed_platforms = ['telegram', 'instagram', 'x', 'youtube']
        if v not in allowed_platforms:
            raise ValueError(f'Platform must be one of {allowed_platforms}')
        return v.lower()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

# Memory cache برای جایگزین Redis
memory_cache = {}
CACHE_EXPIRY = 300  # 5 دقیقه

def get_from_cache(key: str) -> Optional[any]:
    """دریافت از memory cache با expiry check"""
    if key in memory_cache:
        value, expiry = memory_cache[key]
        if time.time() < expiry:
            return value
        else:
            del memory_cache[key]
    return None

def set_in_cache(key: str, value: any, ttl: int = CACHE_EXPIRY):
    """ذخیره در memory cache"""
    memory_cache[key] = (value, time.time() + ttl)

def clear_user_cache(telegram_id: str):
    """پاک کردن تمام cache های یک کاربر"""
    keys_to_delete = [k for k in memory_cache.keys() if telegram_id in k]
    for key in keys_to_delete:
        del memory_cache[key]

@router.get("/", response_class=HTMLResponse)
@limiter.limit("20/minute")
async def get_earn(request: Request, db: Session = Depends(get_db)):
    """
    صفحه Earn با cache و بررسی خودکار
    """
    telegram_id = request.session.get("telegram_id")

    if not telegram_id:
        logger.warning("Unauthorized access to earn page")
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")

    telegram_id = str(telegram_id).strip()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error("User not found", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    # بررسی cache برای tasks
    cache_key = f"tasks:{telegram_id}"
    cached_tasks = get_from_cache(cache_key)

    if not cached_tasks:
        # بررسی و به‌روزرسانی وضعیت همه تسک‌ها
        try:
            update_result = check_and_update_all_user_tasks(telegram_id, db)
        except Exception as e:
            logger.error("Error updating tasks", extra={
                "telegram_id": telegram_id,
                "error": str(e)
            })

        # دریافت تسک‌های کاربر از دیتابیس
        user_tasks = db.query(UserTask).filter(UserTask.user_id == user.id).all()
        
        # ایجاد دیکشنری برای دسترسی سریع
        task_dict = {task.platform: task for task in user_tasks}

        tasks = [
            {
                "label": "Join Telegram",
                "reward": PLATFORM_REWARD["telegram"],
                "platform": "telegram",
                "icon": "Telegram.png",
                "completed": task_dict.get("telegram").completed if task_dict.get("telegram") else False,
                "attempt_count": task_dict.get("telegram").attempt_count if task_dict.get("telegram") else 0
            },
            {
                "label": "Follow Instagram",
                "reward": PLATFORM_REWARD.get("instagram", 500),
                "platform": "instagram",
                "icon": "Instagram.png",
                "completed": task_dict.get("instagram").completed if task_dict.get("instagram") else False,
                "attempt_count": task_dict.get("instagram").attempt_count if task_dict.get("instagram") else 0
            },
            {
                "label": "Follow X",
                "reward": PLATFORM_REWARD.get("x", 500),
                "platform": "x",
                "icon": "X.png",
                "completed": task_dict.get("x").completed if task_dict.get("x") else False,
                "attempt_count": task_dict.get("x").attempt_count if task_dict.get("x") else 0
            },
            {
                "label": "Subscribe YouTube",
                "reward": PLATFORM_REWARD.get("youtube", 500),
                "platform": "youtube",
                "icon": "YouTube.png",
                "completed": task_dict.get("youtube").completed if task_dict.get("youtube") else False,
                "attempt_count": task_dict.get("youtube").attempt_count if task_dict.get("youtube") else 0
            },
        ]

        # Cache tasks
        set_in_cache(cache_key, tasks, ttl=60)  # 1 دقیقه
    else:
        tasks = cached_tasks

    return templates.TemplateResponse("earn.html", {
        "request": request,
        "tasks": tasks,
        "user_id": telegram_id,
        "user_tokens": user.tokens
    })

@router.post("/verify-task")
@limiter.limit("10/minute")
async def verify_task(
    task_data: TaskRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    تایید انجام task با سیستم 3 بار کلیک برای شبکه‌های اجتماعی غیر Telegram
    """
    telegram_id = request.session.get("telegram_id")

    if not telegram_id:
        logger.warning("Unauthorized verify attempt")
        raise HTTPException(status_code=401, detail="Unauthorized")

    telegram_id = str(telegram_id).strip()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error("User not found for verify", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    platform = task_data.platform

    # یافتن یا ایجاد task
    task = db.query(UserTask).filter(
        UserTask.user_id == user.id,
        UserTask.platform == platform
    ).first()

    if not task:
        task = UserTask(user_id=user.id, platform=platform, completed=False, attempt_count=0)
        db.add(task)
        db.flush()

    # ✅ اگر task قبلاً complete شده، دوباره verify نکن
    if task.completed:
        logger.info("Task already completed", extra={
            "telegram_id": telegram_id,
            "platform": platform
        })
        return {"success": True, "already_completed": True}

    # 🔄 افزایش تعداد attempt
    task.attempt_count += 1
    task.last_attempt_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(f"Task attempt #{task.attempt_count}", extra={
        "telegram_id": telegram_id,
        "platform": platform,
        "attempt_count": task.attempt_count
    })

    # 🎯 منطق سه بار کلیک برای Instagram, X, YouTube
    if platform in ['instagram', 'x', 'youtube']:
        # فقط در بار سوم واقعاً verify کن
        if task.attempt_count < 3:
            logger.info(f"Fake verification - attempt {task.attempt_count}/3", extra={
                "telegram_id": telegram_id,
                "platform": platform
            })
            # Fake verification - برگردان false تا کاربر فکر کنه داره چک میکنه
            return {
                "success": False,
                "attempt_count": task.attempt_count,
                "message": "Verification in progress. Please try again."
            }
        else:
            # در بار سوم، واقعاً verify کن (که همیشه true برمی‌گردونه چون API نداریم)
            logger.info(f"Real verification on attempt 3", extra={
                "telegram_id": telegram_id,
                "platform": platform
            })
            result = check_social_follow(telegram_id, platform, force_refresh=True)
            
            logger.info("Task verification result", extra={
                "telegram_id": telegram_id,
                "platform": platform,
                "result": result,
                "attempt_count": task.attempt_count
            })
            
            return {
                "success": result,
                "attempt_count": task.attempt_count
            }
    
    # 📱 برای Telegram همیشه verify واقعی
    elif platform == 'telegram':
        result = check_social_follow(telegram_id, platform, force_refresh=True)
        
        logger.info("Telegram task verification", extra={
            "telegram_id": telegram_id,
            "platform": platform,
            "result": result
        })
        
        return {
            "success": result,
            "attempt_count": task.attempt_count
        }
    
    return {"success": False, "error": "Unknown platform"}

@router.post("/claim-reward")
@limiter.limit("5/minute")
async def claim_reward(
    task_data: TaskRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    دریافت reward با امنیت کامل
    """
    telegram_id = request.session.get("telegram_id")

    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    telegram_id = str(telegram_id).strip()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    platform = task_data.platform

    # Query task
    task = db.query(UserTask).filter(
        UserTask.user_id == user.id,
        UserTask.platform == platform
    ).first()

    if not task:
        # ایجاد task جدید
        task = UserTask(user_id=user.id, platform=platform, completed=False)
        db.add(task)
        db.flush()

    if task.completed:
        logger.warning("Task already claimed", extra={
            "telegram_id": telegram_id,
            "platform": platform
        })
        return {"success": False, "error": "Task already claimed"}

    # بررسی مجدد follow status
    try:
        result = check_social_follow(telegram_id, platform, force_refresh=True)

        if result:
            task.completed = True
            task.completed_at = datetime.now(timezone.utc)
            reward = PLATFORM_REWARD.get(platform, 0)
            user.tokens += reward
            user.updated_at = datetime.now(timezone.utc)
            db.commit()

            # پاک کردن cache
            background_tasks.add_task(clear_user_cache, telegram_id)

            logger.info("Reward claimed", extra={
                "telegram_id": telegram_id,
                "platform": platform,
                "reward": reward,
                "total_tokens": user.tokens,
                "attempt_count": task.attempt_count
            })

            return {
                "success": True,
                "tokens_added": reward,
                "total_tokens": user.tokens,
                "message": f"Congratulations! You earned {reward} tokens!"
            }
        else:
            return {
                "success": False,
                "error": f"Please make sure you have followed/joined our {platform} account first"
            }

    except Exception as e:
        db.rollback()
        logger.error("Claim reward error", extra={
            "telegram_id": telegram_id,
            "platform": platform,
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(status_code=500, detail="Reward claim failed")

@router.get("/check-all-tasks")
@limiter.limit("10/minute")
async def check_all_tasks(request: Request, db: Session = Depends(get_db)):
    """
    بررسی وضعیت همه تسک‌ها
    """
    telegram_id = request.session.get("telegram_id")

    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    telegram_id = str(telegram_id).strip()

    try:
        result = check_and_update_all_user_tasks(telegram_id, db)
        return result
    except Exception as e:
        logger.error("Check all tasks error", extra={
            "telegram_id": telegram_id,
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(status_code=500, detail="Task check failed")

@router.post("/refresh-task-status")
@limiter.limit("10/minute")
async def refresh_task_status(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    بررسی و به‌روزرسانی وضعیت همه تسک‌ها
    """
    telegram_id = request.session.get("telegram_id")

    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    telegram_id = str(telegram_id).strip()

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        # بررسی و به‌روزرسانی
        update_result = check_and_update_all_user_tasks(telegram_id, db)

        # پاک کردن cache در background
        background_tasks.add_task(clear_user_cache, telegram_id)

        if update_result.get("success"):
            return {
                "success": True,
                "message": "Task statuses updated",
                "user_tokens": update_result.get("user_tokens", user.tokens),
                "platforms": update_result.get("platforms", {})
            }
        else:
            return {
                "success": False,
                "error": update_result.get("error", "Update failed")
            }
    except Exception as e:
        logger.error("Refresh task status error", extra={
            "telegram_id": telegram_id,
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(status_code=500, detail="Refresh failed")
