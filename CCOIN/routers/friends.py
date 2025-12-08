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
import secrets
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

def generate_unique_referral_code_internal(db: Session) -> str:
    """Generate unique referral code"""
    print("===== GENERATING UNIQUE REFERRAL CODE =====")
    logger.info("Starting to generate unique referral code")
    
    max_attempts = 20
    
    for attempt in range(max_attempts):
        new_code = secrets.token_hex(4).upper()
        print(f"Attempt {attempt+1}: Generated code {new_code}")
        logger.info(f"Attempt {attempt+1}: Generated code {new_code}")
        
        existing = db.query(User).filter(User.referral_code == new_code).first()
        if not existing:
            print(f"Code {new_code} is unique, returning it")
            logger.info(f"Code {new_code} is unique, returning it")
            return new_code
        else:
            print(f"Code {new_code} already exists, trying again")
            logger.warning(f"Code {new_code} already exists, trying again")
    
    fallback_code = f"REF{int(time.time())}"[-8:]
    print(f"Using fallback code: {fallback_code}")
    logger.warning(f"Using fallback code: {fallback_code}")
    return fallback_code

def validate_referral_code(code: str) -> bool:
    """Validate referral code"""
    if not code:
        return False
    
    code_str = str(code).strip()
    if code_str == "" or code_str == "None" or code_str == "null":
        return False
    
    if len(code_str) < 3:  
        return False
    
    return True

@router.get("/", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def get_friends(request: Request, db: Session = Depends(get_db)):
    print("===== FRIENDS ENDPOINT CALLED =====")
    logger.info("=== FRIENDS ENDPOINT CALLED ===")
    
    telegram_id = request.query_params.get("telegram_id") or request.session.get("telegram_id")
    print(f"telegram_id: {telegram_id}")
    
    if not telegram_id:
        print("No telegram_id found for friends")
        logger.error("No telegram_id found for friends, redirecting to bot")
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    
    request.session["telegram_id"] = telegram_id
    print(f"Processing friends request for telegram_id: {telegram_id}")
    logger.info(f"Processing friends request for telegram_id: {telegram_id}")
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        print(f"User not found for telegram_id: {telegram_id}")
        logger.error(f"User not found for telegram_id: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")
    
    print(f"User found: {user.username}, current referral_code: '{user.referral_code}'")
    logger.info(f"User found: {user.username}, current referral_code: '{user.referral_code}', type: {type(user.referral_code)}")
    
    if not validate_referral_code(user.referral_code):
        print(f"User {telegram_id} needs a new referral code. Current code: '{user.referral_code}'")
        logger.info(f"User {telegram_id} needs a new referral code. Current code: '{user.referral_code}'")
        
        try:
            new_code = generate_unique_referral_code_internal(db)
            print(f"Generated new code: {new_code}")
            logger.info(f"Generated new code: {new_code}")
            
            user.referral_code = new_code
            print(f"Set user.referral_code to: {new_code}")
            logger.info(f"Set user.referral_code to: {new_code}")
            
            db.commit()
            print("Database committed")
            logger.info("Database committed")
            
            db.refresh(user)
            print(f"User refreshed, final referral_code: '{user.referral_code}'")
            logger.info(f"User refreshed, final referral_code: '{user.referral_code}'")
            
        except Exception as e:
            print(f"Error generating referral code: {str(e)}")
            logger.error(f"Error generating referral code for user {telegram_id}: {str(e)}")
            db.rollback()
            
            temp_code = f"U{telegram_id}"[-8:].upper()
            print(f"Creating temporary code: {temp_code}")
            logger.info(f"Creating temporary code: {temp_code}")
            
            try:
                user.referral_code = temp_code
                db.commit()
                db.refresh(user)
                print(f"Saved temporary referral code: {temp_code}")
                logger.info(f"Saved temporary referral code for user {telegram_id}: {temp_code}")
            except Exception as commit_error:
                print(f"Failed to save temporary referral code: {commit_error}")
                logger.error(f"Failed to save temporary referral code: {commit_error}")
                raise HTTPException(status_code=500, detail="Database error")
    
    if not validate_referral_code(user.referral_code):
        print("CRITICAL: User still has no valid referral code!")
        logger.error(f"CRITICAL: User {telegram_id} still has no valid referral code after all attempts")
        
        emergency_code = f"E{telegram_id}"[-8:].upper()
        try:
            user.referral_code = emergency_code
            db.commit()
            db.refresh(user)
            print(f"Emergency referral code set: {emergency_code}")
            logger.info(f"Emergency referral code set: {emergency_code}")
        except Exception as e:
            logger.error(f"Failed to set emergency referral code: {e}")
            raise HTTPException(status_code=500, detail="Critical database error")
    
    try:
        invited_users = db.query(User).filter(User.referred_by == user.id).all()
        print(f"Found {len(invited_users)} invited users")
        logger.info(f"Found {len(invited_users)} invited users for {telegram_id}")
    except Exception as e:
        print(f"Error fetching invited users: {e}")
        logger.error(f"Error fetching invited users: {e}")
        invited_users = []
    
    try:
        final_code = user.referral_code
        
        if not validate_referral_code(final_code):
            print("Final code is still invalid!")
            logger.error(f"Final code is still invalid: '{final_code}'")
            final_code = f"EMERGENCY{telegram_id}"[-8:]
            
            try:
                user.referral_code = final_code
                db.commit()
                db.refresh(user)
                logger.warning(f"Set emergency final code: {final_code}")
            except Exception as e:
                logger.error(f"Failed to save emergency final code: {e}")
        
        bot_username = os.getenv("BOT_USERNAME", "CTG_COIN_BOT")
        referral_link = f"https://t.me/{bot_username}?start={final_code}"
        
        if not referral_link.split("?start=")[1]:
            logger.error("CRITICAL: Referral link has empty start parameter")
            referral_link = f"https://t.me/{bot_username}?start=ERROR{telegram_id}"[-8:]
        
        print(f"Final referral link: {referral_link}")
        logger.info(f"Final referral link for user {telegram_id}: {referral_link}")
        
        link_code = referral_link.split("?start=")[1]
        if not link_code or len(link_code) < 3:
            logger.error(f"Generated referral link has invalid code: '{link_code}'")
            referral_link = f"https://t.me/{bot_username}?start=FALLBACK{int(time.time())}"[-8:]
            logger.warning(f"Using fallback referral link: {referral_link}")
        
    except Exception as e:
        print(f"Error generating referral link: {e}")
        logger.error(f"Error generating referral link: {e}")
        bot_username = os.getenv("BOT_USERNAME", "CTG_COIN_BOT")
        referral_link = f"https://t.me/{bot_username}?start=ERROR{int(time.time())}"[-8:]
        logger.warning(f"Using error referral link: {referral_link}")
    
    print("===== FRIENDS ENDPOINT COMPLETED =====")
    logger.info("=== FRIENDS ENDPOINT COMPLETED ===")
    
    logger.info(f"Final output - User: {telegram_id}, Code: '{user.referral_code}', Link: '{referral_link}'")
    
    return templates.TemplateResponse("friends.html", {
        "request": request,
        "invited_users": invited_users,
        "referral_link": referral_link,
        "referral_code": user.referral_code,
        "user": user
    })
