# routes/commission.py
import os
import time
import secrets
import base64
import structlog
from datetime import datetime

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import requests

# solana-py
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction
from solders.message import Message
from solders.hash import Hash
import base58

# project imports
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET, BOT_USERNAME, BOT_TOKEN, APP_DOMAIN

logger = structlog.get_logger(__name__)
router = APIRouter()  # main.py will include this with prefix="/commission"
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

# Simple in-memory session store with TTL
_SESSION_STORE = {}  # session_id -> {"data": {...}, "expires_at": timestamp}

def _set_session(session_id: str, data: dict, ttl: int = 600):
    """Store session data with expiration time"""
    _SESSION_STORE[session_id] = {"data": data, "expires_at": time.time() + ttl}

def _get_session(session_id: str):
    """Get session data if not expired"""
    ent = _SESSION_STORE.get(session_id)
    if not ent:
        return None
    if time.time() > ent["expires_at"]:
        _SESSION_STORE.pop(session_id, None)
        return None
    return ent["data"]

def _pop_session(session_id: str):
    """Remove and return session data"""
    return _SESSION_STORE.pop(session_id, None)

# -------------------------
# NEW ENDPOINT: Send payment link to Telegram chat
# -------------------------
@router.post("/send_link_to_chat", response_class=JSONResponse)
async def send_link_to_chat(request: Request, db: Session = Depends(get_db)):
    """
    Send payment page link to user's Telegram chat bot
    
    Body Parameters:
        - telegram_id: User's Telegram ID
        - payment_url: Payment page URL
    
    Returns:
        - success: Success status
        - message_id: Sent message ID (on success)
        - error: Error message (on failure)
    """
    try:
        # Parse request body
        body = await request.json()
        telegram_id = body.get("telegram_id")
        payment_url = body.get("payment_url")
        
        # Validate required parameters
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")
        
        if not payment_url:
            raise HTTPException(status_code=400, detail="Missing payment_url")
        
        # Check if user exists
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            logger.warning("User not found for send_link_to_chat", extra={"telegram_id": telegram_id})
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if commission already paid
        if user.commission_paid:
            logger.info("User already paid commission", extra={"telegram_id": telegram_id})
            return {
                "success": False,
                "error": "Commission already paid"
            }
        
        # Build message text
        message_text = (
            "💰 <b>CCoin Airdrop Commission Payment</b>\n\n"
            f"Amount: <b>{COMMISSION_AMOUNT} SOL</b>\n\n"
            "Click the button below to pay the airdrop commission.\n"
            "This link will open in an external browser and you can pay using your Phantom wallet.\n\n"
            "⚠️ <i>Note: After payment, return to the app to update your status.</i>"
        )
        
        # Build inline keyboard with buttons
        inline_keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "💳 Pay Commission",
                        "url": payment_url
                    }
                ],
                [
                    {
                        "text": "🔙 Back to App",
                        "url": f"https://t.me/{BOT_USERNAME}/ccoin"
                    }
                ]
            ]
        }
        
        # Telegram API endpoint
        telegram_api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        # Prepare payload
        payload = {
            "chat_id": telegram_id,
            "text": message_text,
            "parse_mode": "HTML",
            "reply_markup": inline_keyboard,
            "disable_web_page_preview": True
        }
        
        logger.info("Sending payment link to Telegram", extra={
            "telegram_id": telegram_id,
            "payment_url": payment_url
        })
        
        # Send request to Telegram API
        response = requests.post(telegram_api_url, json=payload, timeout=10)
        
        # Check response status
        if response.status_code != 200:
            logger.error("Telegram API error", extra={
                "status_code": response.status_code,
                "response": response.text
            })
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to send message: {response.text}"
            )
        
        result = response.json()
        
        # Check Telegram response
        if not result.get("ok"):
            logger.error("Telegram API returned error", extra={"result": result})
            raise HTTPException(
                status_code=500,
                detail=f"Telegram error: {result.get('description', 'Unknown error')}"
            )
        
        # Extract message ID
        message_id = result.get("result", {}).get("message_id")
        
        logger.info("Payment link sent successfully", extra={
            "telegram_id": telegram_id,
            "message_id": message_id
        })
        
        # Return success response
        return {
            "success": True,
            "message_id": message_id,
            "message": "Link sent to chat successfully"
        }
        
    except HTTPException:
        raise
    except requests.exceptions.Timeout:
        logger.error("Telegram API timeout")
        raise HTTPException(status_code=504, detail="Request timeout")
    except requests.exceptions.RequestException as e:
        logger.error("Telegram API request failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Failed to send message")
    except Exception as e:
        logger.error("send_link_to_chat error", extra={
            "error": str(e),
            "error_type": type(e).__name__
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------
# Render payment page
# -------------------------
@router.get("/browser/pay", response_class=HTMLResponse)
async def commission_browser_pay(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Render commission payment page in external browser"""
    logger.info("Render commission browser pay", extra={"telegram_id": telegram_id})
    
    # Find user
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.warning("User not found", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already paid
    if user.commission_paid:
        return templates.TemplateResponse("commission_success.html", {
            "request": request,
            "telegram_id": telegram_id,
            "success_message": "Commission already paid!",
            "already_paid": True,
            "bot_username": BOT_USERNAME
        })

    # Check wallet connection
    if not user.wallet_address:
        raise HTTPException(status_code=400, detail="Wallet not connected. Please connect your wallet first.")

    # Render payment page
    return templates.TemplateResponse("commission_browser_pay.html", {
        "request": request,
        "telegram_id": telegram_id,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET,
        "bot_username": BOT_USERNAME,
        "solana_rpc": SOLANA_RPC
    })

# -------------------------
# Create payment session (server builds unsigned tx and returns base64)
# -------------------------
@router.post("/create_payment_session", response_class=JSONResponse)
async def create_payment_session(request: Request, db: Session = Depends(get_db)):
    """Create a payment session and return unsigned transaction"""
    try:
        # Parse request body
        body = await request.json()
        telegram_id = body.get("telegram_id")
        amount = float(body.get("amount", COMMISSION_AMOUNT))
        recipient = body.get("recipient", ADMIN_WALLET)

        # Validate telegram_id
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        # Find user
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if already paid
        if user.commission_paid:
            return JSONResponse({"success": False, "error": "Commission already paid"}, status_code=400)

        # Check wallet connection
        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="Wallet not connected")

        # Generate session ID
        session_id = secrets.token_urlsafe(32)

        # Connect to Solana RPC
        client = AsyncClient(SOLANA_RPC)
        try:
            # Get latest blockhash
            blockhash_resp = await client.get_latest_blockhash()
            recent_blockhash = blockhash_resp.value.blockhash

            logger.info("Blockhash received", extra={
                "blockhash": str(recent_blockhash),
                "telegram_id": telegram_id
            })

            # Convert addresses
            from_pubkey = Pubkey.from_string(user.wallet_address)
            to_pubkey = Pubkey.from_string(recipient)
            lamports = int(amount * 1_000_000_000)

            # Manual transaction building
            from solders.instruction import Instruction, AccountMeta
            from solders.message import Message
            from solders.transaction import Transaction

            # System Program ID: 11111111111111111111111111111111
            system_program_id = Pubkey.from_string("11111111111111111111111111111111")

            # Transfer instruction data
            # Byte 0: instruction type (2 = transfer)
            # Bytes 1-8: lamports (little-endian u64)
            instruction_data = bytearray([2])  # Transfer instruction
            instruction_data.extend(lamports.to_bytes(8, 'little'))

            # Build accounts list
            accounts = [
                AccountMeta(pubkey=from_pubkey, is_signer=True, is_writable=True),
                AccountMeta(pubkey=to_pubkey, is_signer=False, is_writable=True),
            ]

            # Create transfer instruction
            transfer_instruction = Instruction(
                program_id=system_program_id,
                accounts=accounts,
                data=bytes(instruction_data)
            )

            # Build message
            message = Message.new_with_blockhash(
                instructions=[transfer_instruction],
                payer=from_pubkey,
                blockhash=recent_blockhash
            )

            # Create unsigned transaction
            tx = Transaction.new_unsigned(message)

            # Serialize to base64
            tx_bytes = bytes(tx)
            tx_base64 = base64.b64encode(tx_bytes).decode("utf-8")

            logger.info("Transaction created (manual method)", extra={
                "telegram_id": telegram_id,
                "tx_base64_length": len(tx_base64),
                "tx_bytes_length": len(tx_bytes),
                "first_100_chars": tx_base64[:100]
            })

            await client.close()

        except Exception as e:
            await client.close()
            logger.error("Transaction creation failed", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "telegram_id": telegram_id
            }, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")

        # Store session data
        session_data = {
            "telegram_id": telegram_id,
            "amount": amount,
            "recipient": recipient,
            "wallet_address": user.wallet_address,
            "created_at": datetime.utcnow().isoformat(),
            "transaction_base64": tx_base64,
            "blockhash": str(recent_blockhash)
        }
        _set_session(session_id, session_data, ttl=600)

        logger.info("Payment session created", extra={
            "session_id": session_id,
            "telegram_id": telegram_id
        })

        # Return response
        return {
            "success": True,
            "session_id": session_id,
            "transaction": tx_base64,
            "expires_in": 600
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_payment_session error", extra={
            "error": str(e),
            "error_type": type(e).__name__
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------
# Phantom callback (render)
# -------------------------
@router.get("/phantom_callback", response_class=HTMLResponse)
async def phantom_callback(request: Request):
    """
    Phantom wallet redirect target
    
    Example success URL:
       /commission/phantom_callback?session=<id>&signature=<txsig>&telegram_id=...
    
    On error Phantom may return errorCode & errorMessage.
    """
    params = dict(request.query_params)
    logger.info("Phantom callback", extra={"params": params})

    session = params.get("session")
    signature = params.get("signature")
    telegram_id = params.get("telegram_id")

    # Check for Phantom error
    if params.get("errorCode") or params.get("errorMessage"):
        err = params.get("errorMessage") or f"Phantom error {params.get('errorCode')}"
        return templates.TemplateResponse("commission_callback.html", {
            "request": request,
            "success": False,
            "error": err,
            "telegram_id": telegram_id,
            "bot_username": BOT_USERNAME
        })

    # If signature received, store it
    if signature and session:
        s = _get_session(session)
        if s:
            s["signature"] = signature
            _set_session(session, s, ttl=3600)
        return templates.TemplateResponse("commission_callback.html", {
            "request": request,
            "success": None,
            "message": "Transaction submitted. Verifying...",
            "telegram_id": telegram_id,
            "bot_username": BOT_USERNAME,
            "signature": signature
        })

    # No data received
    return templates.TemplateResponse("commission_callback.html", {
        "request": request,
        "success": None,
        "message": "No callback data received. If you completed payment, click 'Check Status'.",
        "telegram_id": telegram_id,
        "bot_username": BOT_USERNAME
    })

# -------------------------
# Verify signature (explicit verification)
# -------------------------
@router.post("/verify_signature", response_class=JSONResponse)
async def verify_signature(request: Request, db: Session = Depends(get_db)):
    """
    Verify transaction signature on-chain
    
    Body: { telegram_id, session_id, signature }
    
    Verifies provided signature and marks user as paid if valid.
    """
    try:
        # Parse request body
        body = await request.json()
        telegram_id = body.get("telegram_id")
        session_id = body.get("session_id")
        signature = body.get("signature")

        # Validate parameters
        if not telegram_id or not session_id or not signature:
            raise HTTPException(status_code=400, detail="Missing parameters")

        # Get session data
        session_data = _get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=400, detail="Invalid or expired session")

        # Verify session belongs to user
        if session_data.get("telegram_id") != telegram_id:
            raise HTTPException(status_code=400, detail="Session does not belong to telegram_id")

        # Connect to Solana RPC
        client = AsyncClient(SOLANA_RPC)
        try:
            # Get transaction details
            tx_resp = await client.get_transaction(signature, encoding="jsonParsed", max_supported_transaction_version=0)
            if not tx_resp.value:
                await client.close()
                return {"verified": False, "message": "Transaction not found on chain (yet)"}

            # Expected values
            expected_lamports = int(float(session_data.get("amount", COMMISSION_AMOUNT)) * 1_000_000_000)
            user_wallet = session_data.get("wallet_address")
            admin_addr = ADMIN_WALLET if isinstance(ADMIN_WALLET, str) else str(ADMIN_WALLET)

            # Read instructions (robust method)
            instructions = []
            try:
                parsed_msg = tx_resp.value.transaction.transaction.message
                instructions = getattr(parsed_msg, "instructions", []) or []
            except Exception:
                instructions = (tx_resp.value.transaction.get("transaction", {}) or {}).get("message", {}).get("instructions", [])

            # Verify transfer instruction
            found = False
            for ix in instructions:
                parsed = getattr(ix, "parsed", None) or (ix.get("parsed") if isinstance(ix, dict) else None)
                if isinstance(parsed, dict) and parsed.get("type") == "transfer":
                    info = parsed.get("info", {})
                    source = info.get("source")
                    destination = info.get("destination")
                    lamports = info.get("lamports", 0)
                    
                    # Check if matches expected transfer
                    if source == user_wallet and destination == admin_addr:
                        # Allow 2% tolerance
                        if int(expected_lamports * 0.98) <= int(lamports) <= int(expected_lamports * 1.02):
                            found = True
                            break

            await client.close()

            # If valid transfer found, update user
            if found:
                user = db.query(User).filter(User.telegram_id == telegram_id).first()
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")

                if not user.commission_paid:
                    user.commission_paid = True
                    user.commission_transaction_hash = signature
                    user.commission_payment_date = datetime.utcnow()
                    db.commit()

                # Remove session
                _pop_session(session_id)
                
                logger.info("Payment verified and recorded", extra={"telegram_id": telegram_id, "signature": signature})
                return {"verified": True, "signature": signature}

            return {"verified": False, "message": "Transaction does not match expected transfer"}

        except Exception as e:
            await client.close()
            logger.error("verify_signature RPC error", extra={"error": str(e)}, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    except Exception as e:
        logger.error("verify_signature error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------
# Fallback verify (scan recent txs)
# -------------------------
@router.post("/verify", response_class=JSONResponse)
async def verify_commission_payment(request: Request, db: Session = Depends(get_db)):
    """Fallback verification method by scanning recent transactions"""
    try:
        # Parse request body
        body = await request.json()
        telegram_id = body.get("telegram_id")
        
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        # Find user
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if already verified
        if user.commission_paid:
            return {"verified": True, "message": "Already verified"}

        # Check wallet connection
        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="Wallet not connected")

        # Here you would implement logic to scan recent transactions
        # For simplicity, just check if already paid
        
        return {"verified": False, "message": "Payment not found"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("verify error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
