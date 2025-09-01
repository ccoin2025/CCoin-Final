from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.utils.helpers import generate_referral_link
from fastapi.templating import Jinja2Templates
import os
import uuid
import structlog
import secrets 


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
    
    logger.info(f"User found: {user.username}, current referral_code: {user.referral_code}")
    
    # بررسی و تولید کد رفرال اگر موجود نباشد
    if not user.referral_code:
        try:
            # تولید کد رفرال جدید
            max_attempts = 10  # حداکثر تلاش برای جلوگیری از حلقه بی‌نهایت
            attempts = 0
            
            while attempts < max_attempts:
                attempts += 1
                # استفاده از secrets برای امنیت بیشتر
                new_code = secrets.token_hex(4).upper()  # 8 کاراکتر هگزادسیمال
                
                # بررسی کنید که کد تکراری نباشد
                existing = db.query(User).filter(User.referral_code == new_code).first()
                
                if not existing:
                    user.referral_code = new_code
                    db.commit()
                    db.refresh(user)
                    logger.info(f"Generated new referral code for user {telegram_id}: {new_code}")
                    break
                else:
                    logger.warning(f"Referral code {new_code} already exists, trying again... (attempt {attempts})")
            
            if attempts >= max_attempts:
                logger.error(f"Failed to generate unique referral code after {max_attempts} attempts")
                raise HTTPException(status_code=500, detail="Failed to generate referral code")
                
        except Exception as e:
            logger.error(f"Error generating referral code for user {telegram_id}: {str(e)}")
            db.rollback()
            # در صورت خطا، یک کد موقت ایجاد کنید
            user.referral_code = f"TEMP_{telegram_id}"
            try:
                db.commit()
                db.refresh(user)
                logger.info(f"Created temporary referral code for user {telegram_id}")
            except Exception as commit_error:
                logger.error(f"Failed to save temporary referral code: {commit_error}")
                raise HTTPException(status_code=500, detail="Database error")
    
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
    except Exception as e:
        logger.error(f"Error generating referral link: {e}")
        # لینک پیش‌فرض در صورت خطا
        referral_link = f"https://t.me/CTG_COIN_BOT?start={user.referral_code}"
    
    return templates.TemplateResponse("friends.html", {
        "request": request,
        "invited_users": invited_users,
        "referral_link": referral_link,
        "referral_code": user.referral_code,
        "user": user
    })
