from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from CCOIN.database import get_db
from CCOIN.models.user import User
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

@router.get("/load", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def get_load(request: Request, db: Session = Depends(get_db)):
    # ابتدا telegram_id را از query parameter بگیرید
    telegram_id = request.query_params.get("telegram_id") or request.session.get("telegram_id")
    
    if not telegram_id:
        logger.info("No telegram_id found, redirecting to bot")
        return RedirectResponse(url="https://t.me/CTG_COIN_BOT")
    
    # telegram_id را در session تنظیم کنید
    request.session["telegram_id"] = telegram_id
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.info(f"User not found for telegram_id: {telegram_id}")
        raise HTTPException(status_code=404, detail="User not found")
    
    # بررسی کنید که آیا این اولین ورود است
    if not user.first_login:
        logger.info(f"User {telegram_id} is not first login, redirecting to home")
        return RedirectResponse(url="/home")
    
    reward = user.tokens
    
    # فقط اگر first_login=True باشد، آن را False کنید
    if user.first_login:
        user.first_login = False
        db.commit()
        db.refresh(user)
        logger.info(f"User {telegram_id} completed first login, set first_login=False")
    
    logger.info(f"Rendering load.html for user {telegram_id}, reward: {reward}")
    
    return templates.TemplateResponse("load.html", {
        "request": request, 
        "reward": reward,
        "user": user
    })

@router.get("/load/", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def get_load_with_slash(request: Request, db: Session = Depends(get_db)):
    return await get_load(request, db)
