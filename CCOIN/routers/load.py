from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from CCOIN.database import get_db
from CCOIN.models.user import User
from fastapi.templating import Jinja2Templates
import os

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

@router.get("/load", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def get_load(request: Request, db: Session = Depends(get_db)):
    telegram_id = request.session.get("telegram_id")
    if not telegram_id:
        return RedirectResponse(url="https://t.me/CTG_COIN_BOT")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    reward = user.tokens
    return templates.TemplateResponse("load.html", {"request": request, "reward": reward})

@router.get("/load/", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def get_load_with_slash(request: Request, db: Session = Depends(get_db)):
    return await get_load(request, db)
