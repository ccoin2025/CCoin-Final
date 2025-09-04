from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from CCOIN.database import get_db

router = APIRouter()
templates = Jinja2Templates(directory="CCOIN/templates")

@router.get("/wallet-connect")
async def wallet_connect_page(request: Request):
    """صفحه اتصال به کیف پول"""
    return templates.TemplateResponse("wallet_connect.html", {"request": request})

@router.get("/wallet-callback")
async def wallet_callback(request: Request, db: Session = Depends(get_db)):
    """صفحه callback بعد از اتصال به wallet"""
    telegram_id = request.session.get("telegram_id")
    
    # هدایت به صفحه airdrop
    return RedirectResponse(url="/airdrop")
