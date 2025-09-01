from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from CCOIN.models.user import User
from CCOIN.database import get_db
import os
import secrets

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user

def generate_referral_link(code: str) -> str:
    # بررسی کنید که کد خالی نباشد
    if not code or code.strip() == "":
        # در صورت خالی بودن کد، یک کد جدید تولید کنید
        print("Warning: Empty referral code provided to generate_referral_link")
        return "https://t.me/CTG_COIN_BOT"
    
    # نام Bot واقعی شما را از متغیر محیطی بگیرید
    bot_username = os.getenv("BOT_USERNAME", "CTG_COIN_BOT")
    
    # اطمینان از اینکه کد شامل فضای خالی نباشد
    clean_code = code.strip()
    
    return f"https://t.me/{bot_username}?start={clean_code}"

def generate_unique_referral_code(db: Session) -> str:
    """تابع جداگانه برای تولید کد رفرال یکتا"""
    max_attempts = 20
    
    for attempt in range(max_attempts):
        # تولید کد 8 کاراختری
        new_code = secrets.token_hex(4).upper()
        
        # بررسی یکتا بودن
        existing = db.query(User).filter(User.referral_code == new_code).first()
        
        if not existing:
            return new_code
    
    # اگر پس از 20 تلاش موفق نشد، از timestamp استفاده کنید
    import time
    return f"REF{int(time.time())}"[-8:]
