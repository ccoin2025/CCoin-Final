from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
from datetime import datetime
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET, BOT_USERNAME
from solana.rpc.api import Client
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.system_program import TransferParams, transfer
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
import base58, base64

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

# ------------------ PAY PAGE ------------------
@router.get("/browser/pay", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def commission_browser_pay(
    request: Request,
    telegram_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """صفحه پرداخت کمیسیون در مرورگر"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.commission_paid:
        return templates.TemplateResponse("commission_success.html", {
            "request": request, "telegram_id": telegram_id,
            "success_message": "Commission already paid!", "already_paid": True
        })

    if not user.wallet_address:
        raise HTTPException(status_code=400, detail="Wallet not connected")

    return templates.TemplateResponse("commission_browser_pay.html", {
        "request": request, "telegram_id": telegram_id,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET, "bot_username": BOT_USERNAME
    })

# ------------------ SOLANA PAY ------------------
@router.get("/pay", response_class=JSONResponse)
async def commission_payment_page(
    telegram_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """ایجاد URL برای پرداخت کمیسیون با فرمت Solana Pay"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.commission_paid:
        return RedirectResponse(url=f"/commission/success?telegram_id={telegram_id}&already_paid=true")

    if not user.wallet_address:
        raise HTTPException(status_code=400, detail="Wallet not connected")

    reference = str(Keypair().pubkey())
    pay_url = f"solana:{ADMIN_WALLET}?amount={COMMISSION_AMOUNT}&reference={reference}&label=CCoin+Commission&message=Payment+for+airdrop&memo=User:{telegram_id}"

    return {"pay_url": pay_url, "reference": reference, "amount": COMMISSION_AMOUNT, "recipient": ADMIN_WALLET}

# ------------------ TRANSACTION REQUEST ------------------
@router.get("/transaction_request", response_class=JSONResponse)
async def transaction_request_get(
    request: Request, telegram_id: str, db: Session = Depends(get_db)
):
    """GET endpoint برای Solana Pay Transaction Request"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or user.commission_paid or not user.wallet_address:
        raise HTTPException(status_code=400, detail="Invalid request")

    base_url = str(request.base_url).rstrip('/')
    return {"label": "CCoin Commission Payment", "icon": f"{base_url}/static/images/icon-512x512.png"}

@router.post("/transaction_request", response_class=JSONResponse)
async def transaction_request_post(
    request: Request, telegram_id: str, db: Session = Depends(get_db)
):
    """POST endpoint برای Transaction Request"""
    body = await request.json()
    account = body.get("account")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or user.commission_paid:
        raise HTTPException(status_code=400, detail="Invalid request")

    client = AsyncClient(SOLANA_RPC)
    from_pubkey = Pubkey.from_string(account)
    to_pubkey = Pubkey.from_string(ADMIN_WALLET)

    instructions = [
        set_compute_unit_limit(200_000),
        set_compute_unit_price(1),
        transfer(TransferParams(from_pubkey=from_pubkey, to_pubkey=to_pubkey, lamports=int(COMMISSION_AMOUNT * 1e9)))
    ]

    recent_blockhash = (await client.get_latest_blockhash()).value.blockhash
    from solders.message import Message
    from solders.transaction import Transaction as SoldersTx
    message = Message.new_with_blockhash(instructions, from_pubkey, recent_blockhash)
    transaction = SoldersTx.new_unsigned(message)
    serialized = base64.b64encode(bytes(transaction)).decode('utf-8')

    await client.close()
    return {"transaction": serialized, "message": f"Commission payment: {COMMISSION_AMOUNT} SOL"}

# ------------------ CONFIRM PAYMENT ------------------
@router.post("/confirm_commission", response_class=JSONResponse)
async def confirm_commission(request: Request, db: Session = Depends(get_db)):
    """تایید پرداخت کمیسیون و آپدیت دیتابیس"""
    body = await request.json()
    signature, telegram_id = body.get("signature"), body.get("telegramId")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.commission_paid:
        return {"success": True, "message": "Already paid", "already_paid": True}

    client = Client(SOLANA_RPC)
    tx = client.get_transaction(signature, encoding="json", max_supported_transaction_version=0)

    if not tx.value:
        return {"success": False, "message": "Transaction not found"}
    if tx.value.meta and tx.value.meta.err:
        return {"success": False, "message": "Transaction failed"}

    user.commission_paid = True
    user.commission_transaction_hash = signature
    user.commission_payment_date = datetime.utcnow()
    db.commit()

    return {"success": True, "message": "Commission confirmed", "signature": signature}

# ------------------ STATUS ------------------
@router.get("/status", response_class=JSONResponse)
async def get_commission_status(telegram_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "commission_paid": user.commission_paid,
        "wallet_connected": bool(user.wallet_address),
        "wallet_address": user.wallet_address,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET
    }

# ------------------ CHECK PAYMENT ------------------
@router.get("/check_payment", response_class=JSONResponse)
async def check_payment(telegram_id: str, reference: str, db: Session = Depends(get_db)):
    """چک کردن پرداخت با reference"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or not user.wallet_address:
        return {"status": "error", "message": "User or wallet not found"}

    client = Client(SOLANA_RPC)
    try:
        ref_pubkey = Pubkey.from_bytes(base58.b58decode(reference))
        signatures = client.get_signatures_for_address(ref_pubkey, limit=10)
        if signatures.value:
            tx_signature = str(signatures.value[0].signature)
            tx = client.get_transaction(tx_signature, encoding="json", max_supported_transaction_version=0)
            if tx.value and tx.value.meta and not tx.value.meta.err:
                return {"status": "confirmed", "signature": tx_signature}
        return {"status": "pending"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
