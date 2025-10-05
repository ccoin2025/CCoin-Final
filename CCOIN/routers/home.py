from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from CCOIN.database import get_db
from CCOIN.models.user import User
from fastapi.templating import Jinja2Templates
import os
import structlog
from typing import Optional

logger = structlog.get_logger()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

@router.get("/", response_class=HTMLResponse)
@limiter.limit("20/minute")
async def get_home(
    request: Request, 
    telegram_id: Optional[str] = Query(None, min_length=1, max_length=50),
    db: Session = Depends(get_db)
):
    """
    Home page با امنیت بهبود یافته
    """
    # دریافت telegram_id از query یا session
    if not telegram_id:
        telegram_id = request.session.get("telegram_id")

    if not telegram_id:
        logger.warning("No telegram_id found for home")
        return RedirectResponse(url="https://t.me/CTG_COIN_BOT")

    # Sanitize input
    telegram_id = str(telegram_id).strip()
    
    # ذخیره در session
    request.session["telegram_id"] = telegram_id

    # Query user
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error("User not found", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    # بررسی first_login
    if user.first_login:
        logger.info("User first login, redirecting", extra={"telegram_id": telegram_id})
        return RedirectResponse(url=f"/load?telegram_id={telegram_id}")

    reward = user.tokens

    logger.info("Rendering home", extra={
        "telegram_id": telegram_id,
        "tokens": reward
    })

    return templates.TemplateResponse("home.html", {
        "request": request,
        "reward": reward,
        "user": user
    })
