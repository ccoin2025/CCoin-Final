from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
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
async def get_home(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized: Access only from Telegram")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    reward = user.tokens
    return templates.TemplateResponse("home.html", {"request": request, "reward": reward})