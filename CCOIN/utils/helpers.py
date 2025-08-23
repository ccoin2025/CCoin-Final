from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from CCOIN.models.user import User
from CCOIN.database import get_db

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def generate_referral_link(code: str) -> str:
    return f"https://t.me/your_bot?start={code}"