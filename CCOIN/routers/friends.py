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
    
    invited_users = db.query(User).filter(User.referred_by == user.id).all()
    referral_link = generate_referral_link(user.referral_code)
    
    logger.info(f"Generated referral link for user {telegram_id}: {referral_link}")
    
    return templates.TemplateResponse("friends.html", {
        "request": request,
        "invited_users": invited_users,
        "referral_link": referral_link,
        "user": user
    })
