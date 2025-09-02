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
import time

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

def generate_unique_referral_code_internal(db: Session) -> str:
    """تولید کد رفرال یکتا"""
    logger.info("Starting to generate unique referral code")
    
    max_attempts = 20
    
    for attempt in range(max_attempts):
        # تولید کد 8 کاراختری
        new_code = secrets.token_hex(4).upper()
        logger.info(f"Attempt {attempt + 1}: Generated code {new_code}")
        
        # بررسی یکتا بودن
        existing = db.query(User).filter(User.referral_code == new_code).first()
        
        if not existing:
            logger.info(f"Code {new_code} is unique, returning it")
            return new_code
        else:
            logger.warning(f"Code {new_code} already exists, trying again")
    
    # اگر پس از 20 تلاش موفق نشد، از timestamp استفاده کنید
    fallback_code = f"REF{int(time.time())}"[-8:]
    logger.warning(f"Using fallback code: {fallback_code}")
    return fallback_code

@router.get("/", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def get_friends(request: Request, db: Session = Depends(get_db)):
    logger.info("=== FRIENDS ENDPOINT CALLED ===")
    
    # telegram_id را از query parameter یا session بگیرید
    telegram_id = request.query_params.get("telegram_id") or request.session.get("telegram_id")
    
    if not telegram_id:
        logger.info("No telegram_id found for friends, redirecting to bot")
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    
    # telegram_id را در session تنظیم کنید
    request.session["telegram_id"] = telegram_id
    logger.info(f"Processing friends request for telegram_id: {telegram_id}")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    
    if not user:
        logger.info(f"User not found for telegram_id: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")
    
    logger.info(f"User found: {user.username}, current referral_code: '{user.referral_code}', type: {type(user.referral_code)}")
    
    # بررسی و تولید کد رفرال اگر موجود نباشد
    if not user.referral_code or str(user.referral_code).strip() == "" or str(user.referral_code) == "None":
        logger.info(f"User {telegram_id} needs a new referral code")
        
        try:
            # استفاده از تابع داخلی برای تولید کد یکتا
            new_code = generate_unique_referral_code_internal(db)
            logger.info(f"Generated new code: {new_code}")
            
            # تنظیم کد جدید
            user.referral_code = new_code
            logger.info(f"Set user.referral_code to: {new_code}")
            
            # ذخیره در دیتابیس
            db.commit()
            logger.info("Database committed")
            
            db.refresh(user)
            logger.info(f"User refreshed, final referral_code: '{user.referral_code}'")
            
        except Exception as e:
            logger.error(f"Error generating referral code for user {telegram_id}: {str(e)}")
            db.rollback()
            
            # در صورت خطا، کد موقت بر اساس telegram_id ایجاد کنید
            temp_code = f"U{telegram_id}"[-8:].upper()
            logger.info(f"Creating temporary code: {temp_code}")
            
            try:
                user.referral_code = temp_code
                db.commit()
                db.refresh(user)
                logger.info(f"Saved temporary referral code for user {telegram_id}: {temp_code}")
            except Exception as commit_error:
                logger.error(f"Failed to save temporary referral code: {commit_error}")
                raise HTTPException(status_code=500, detail="Database error")
    
    # اطمینان نهایی از وجود کد رفرال
    if not user.referral_code or str(user.referral_code).strip() == "":
        logger.error(f"CRITICAL: User {telegram_id} still has no referral code after all attempts")
        # اجباری یک کد تنظیم کنید
        emergency_code = f"E{telegram_id}"[-8:].upper()
        user.referral_code = emergency_code
        db.commit()
        db.refresh(user)
        logger.info(f"Emergency referral code set: {emergency_code}")
    
    # دریافت کاربران دعوت شده
    try:
        invited_users = db.query(User).filter(User.referred_by == user.id).all()
        logger.info(f"Found {len(invited_users)} invited users for {telegram_id}")
    except Exception as e:
        logger.error(f"Error fetching invited users: {e}")
        invited_users = []
    
    # تولید لینک رفرال
    try:
        # بررسی مستقیم کد رفرال
        final_code = user.referral_code
        if not final_code or str(final_code).strip() == "":
            logger.error("Final code is still empty!")
            final_code = f"EMERGENCY{telegram_id}"[-8:]
        
        bot_username = os.getenv("BOT_USERNAME", "CTG_COIN_BOT")
        referral_link = f"https://t.me/{bot_username}?start={final_code}"
        
        logger.info(f"Final referral link for user {telegram_id}: {referral_link}")
        
    except Exception as e:
        logger.error(f"Error generating referral link: {e}")
        bot_username = os.getenv("BOT_USERNAME", "CTG_COIN_BOT")
        referral_link = f"https://t.me/{bot_username}?start=ERROR"
    
    logger.info("=== FRIENDS ENDPOINT COMPLETED ===")
    
    return templates.TemplateResponse("friends.html", {
        "request": request,
        "invited_users": invited_users,
        "referral_link": referral_link,
        "referral_code": user.referral_code,
        "user": user
    })
