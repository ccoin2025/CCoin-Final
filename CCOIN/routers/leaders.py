from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from CCOIN.database import get_db
from CCOIN.models.user import User
from fastapi.templating import Jinja2Templates
import os

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
router.state = type("State", (), {"limiter": limiter})()
router.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

@router.get("/", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def get_leaders(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    top_leaders = db.query(User).order_by(desc(User.tokens)).limit(100).all()
    user_rank = db.query(User).filter(User.tokens > user.tokens).count() + 1
    user_info = {"username": user.username or 'Guest', "tokens": user.tokens, "rank": user_rank}
    return templates.TemplateResponse("leaders.html", {
        "request": request,
        "top_leaders": top_leaders,
        "user_info": user_info
    })