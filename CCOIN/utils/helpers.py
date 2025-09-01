from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from CCOIN.models.user import User
from CCOIN.database import get_db
import os
import secrets
import time
import structlog

logger = structlog.get_logger()

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user

def generate_referral_link(code: str) -> str:
    """تولید لینک رفرال با بررسی دقیق"""
    logger.info(f"generate_referral_link called with code: '{code}'")
    
    # بررسی کنید که کد خالی نباشد
    if not code or str(code).strip() == "" or str(code).strip() == "None":
        logger.error(f"Invalid referral code provided: '{code}'")
        return "https://t.me/CTG_COIN_BOT"
    
    # نام Bot واقعی شما را از متغیر محیطی بگیرید
    bot_username = os.getenv("BOT_USERNAME", "CTG_COIN_BOT")
    
    # اطمینان از اینکه کد شامل فضای خالی نباشد
    clean_code = str(code).strip()
    
    final_link = f"https://t.me/{bot_username}?start={clean_code}"
    logger.info(f"Generated referral link: {final_link}")
    
    return final_link

def generate_unique_referral_code(db: Session) -> str:
    """تابع جداگانه برای تولید کد رفرال یکتا"""
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
