from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.utils.helpers import generate_referral_link, generate_unique_referral_code
from fastapi.templating import Jinja2Templates
import os
import uuid
import structlog

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

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

@router.get("/", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def get_friends(request: Request, db: Session = Depends(get_db)):
    # telegram_id را از query parameter یا session بگیرید
    telegram_id = request.query_params.get("telegram_id") or request.session.get("telegram_id")
    
    if not telegram_id:
        logger.info("No telegram_id found for friends, redirecting to bot")
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    
    # telegram_id را در session تنظیم کنید
    request.session["telegram_id"] = telegram_id
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    
    if not user:
        logger.info(f"User not found for telegram_id: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")
    
    logger.info(f"User found: {user.username}, current referral_code: '{user.referral_code}'")
    
    # بررسی و تولید کد رفرال اگر موجود نباشد
    if not user.referral_code or user.referral_code.strip() == "":
        try:
            logger.info(f"Generating new referral code for user {telegram_id}")
            
            # استفاده از تابع جداگانه برای تولید کد یکتا
            new_code = generate_unique_referral_code(db)
            
            # تنظیم کد جدید
            user.referral_code = new_code
            
            # ذخیره در دیتابیس
            db.commit()
            db.refresh(user)
            
            logger.info(f"Successfully generated new referral code for user {telegram_id}: {new_code}")
            
        except Exception as e:
            logger.error(f"Error generating referral code for user {telegram_id}: {str(e)}")
            db.rollback()
            
            # در صورت خطا، کد موقت بر اساس telegram_id ایجاد کنید
            temp_code = f"U{telegram_id}"[-8:]
            try:
                user.referral_code = temp_code
                db.commit()
                db.refresh(user)
                logger.info(f"Created temporary referral code for user {telegram_id}: {temp_code}")
            except Exception as commit_error:
                logger.error(f"Failed to save temporary referral code: {commit_error}")
                raise HTTPException(status_code=500, detail="Database error")
    
    # اطمینان از اینکه کد رفرال وجود دارد
    if not user.referral_code:
        logger.error(f"User {telegram_id} still has no referral code after generation attempt")
        raise HTTPException(status_code=500, detail="Failed to generate referral code")
    
    # دریافت کاربران دعوت شده
    try:
        invited_users = db.query(User).filter(User.referred_by == user.id).all()
        logger.info(f"Found {len(invited_users)} invited users for {telegram_id}")
    except Exception as e:
        logger.error(f"Error fetching invited users: {e}")
        invited_users = []
    
    # تولید لینک رفرال
    try:
        referral_link = generate_referral_link(user.referral_code)
        logger.info(f"Generated referral link for user {telegram_id}: {referral_link}")
        
        # بررسی اضافی که لینک درست تولید شده
        if referral_link.endswith("?start="):
            logger.error(f"Generated invalid referral link for user {telegram_id}")
            raise Exception("Invalid referral link generated")
            
    except Exception as e:
        logger.error(f"Error generating referral link: {e}")
        # لینک پیش‌فرض در صورت خطا
        bot_username = os.getenv("BOT_USERNAME", "CTG_COIN_BOT")
        referral_link = f"https://t.me/{bot_username}?start={user.referral_code}"
        logger.info(f"Using fallback referral link: {referral_link}")
    
    return templates.TemplateResponse("friends.html", {
        "request": request,
        "invited_users": invited_users,
        "referral_link": referral_link,
        "referral_code": user.referral_code,
        "user": user
    })
