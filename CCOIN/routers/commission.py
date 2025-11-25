from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
from datetime import datetime, timedelta
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET, BOT_USERNAME
from solana.rpc.api import Client
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solders.message import Message
from solders.system_program import TransferParams, transfer
from solders.keypair import Keypair
import nacl.public
import nacl.utils
import base58
import base64
import time
import asyncio
import structlog
import secrets
import json

logger = structlog.get_logger()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

# Memory cache for rate limiting and session management
memory_cache = {}
phantom_sessions = {}

def get_from_cache(key: str):
    """Get from memory cache"""
    if key in memory_cache:
        value, expiry = memory_cache[key]
        if time.time() < expiry:
            return value
        else:
            del memory_cache[key]
    return None

def set_in_cache(key: str, value, ttl: int):
    """Set in memory cache"""
    memory_cache[key] = (value, time.time() + ttl)

def clear_cache(key: str):
    """Clear cache"""
    if key in memory_cache:
        del memory_cache[key]

@router.get("/browser/pay", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def commission_browser_pay(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Commission payment page in browser"""
    logger.info("Commission browser payment", extra={"telegram_id": telegram_id})

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.error("User not found", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    if user.commission_paid:
        logger.info("Commission already paid", extra={"telegram_id": telegram_id})
        return templates.TemplateResponse("commission_success.html", {
            "request": request,
            "telegram_id": telegram_id,
            "success_message": "Commission already paid!",
            "already_paid": True,
            "bot_username": BOT_USERNAME
        })

    if not user.wallet_address:
        logger.warning("No wallet connected", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=400, detail="Wallet not connected. Please connect your wallet first.")

    return templates.TemplateResponse("commission_browser_pay.html", {
        "request": request,
        "telegram_id": telegram_id,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET,
        "bot_username": BOT_USERNAME,
        "solana_rpc": SOLANA_RPC
    })

@router.post("/create_payment_session", response_class=JSONResponse)
@limiter.limit("10/minute")
async def create_payment_session(
    request: Request,
    db: Session = Depends(get_db)
):
    """Create encrypted payment session for Phantom Deep Links"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        amount = body.get("amount")
        recipient = body.get("recipient")

        if not telegram_id or not amount or not recipient:
            raise HTTPException(status_code=400, detail="Missing required parameters")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            raise HTTPException(status_code=400, detail="Commission already paid")

        # Generate ephemeral keypair for this session
        dapp_keypair = nacl.public.PrivateKey.generate()
        dapp_public_key = bytes(dapp_keypair.public_key)
        dapp_secret_key = bytes(dapp_keypair)

        # Create session ID
        session_id = secrets.token_urlsafe(32)

        # Create transaction
        try:
            connection = AsyncClient(SOLANA_RPC)
            
            # Get latest blockhash
            blockhash_resp = await connection.get_latest_blockhash()
            recent_blockhash = blockhash_resp.value.blockhash

            # Create transfer instruction
            from_pubkey = Pubkey.from_string(user.wallet_address)
            to_pubkey = Pubkey.from_string(recipient)
            lamports = int(float(amount) * 1_000_000_000)

            transfer_ix = transfer(
                TransferParams(
                    from_pubkey=from_pubkey,
                    to_pubkey=to_pubkey,
                    lamports=lamports
                )
            )

            # ✅ FIX: Correct way to build transaction with solders
            from solders.message import Message
            
            message = Message.new_with_blockhash(
                [transfer_ix],
                from_pubkey,
                recent_blockhash
            )
            
            transaction = Transaction.new_unsigned(message)

            # Serialize transaction
            serialized_tx = base58.b58encode(bytes(transaction)).decode('utf-8')

            await connection.close()

            logger.info("Transaction created", extra={
                "session_id": session_id,
                "telegram_id": telegram_id,
                "amount": amount
            })

        except Exception as e:
            logger.error("Transaction creation failed", extra={"error": str(e)})
            raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")

        # Prepare payload for encryption
        payload = {
            "transaction": serialized_tx,
            "session": session_id
        }

        # Generate nonce for encryption
        nonce = nacl.utils.random(24)
        nonce_b58 = base58.b58encode(nonce).decode('utf-8')

        # Store session (expires in 5 minutes)
        session_data = {
            "telegram_id": telegram_id,
            "dapp_public_key": base58.b58encode(dapp_public_key).decode('utf-8'),
            "dapp_secret_key": base58.b58encode(dapp_secret_key).decode('utf-8'),
            "amount": amount,
            "recipient": recipient,
            "created_at": datetime.utcnow().isoformat(),
            "nonce": nonce_b58,
            "payload": json.dumps(payload)
        }

        phantom_sessions[session_id] = session_data
        set_in_cache(f"phantom_session_{session_id}", session_data, ttl=300)

        logger.info("Payment session created", extra={
            "session_id": session_id,
            "telegram_id": telegram_id
        })

        return {
            "success": True,
            "session_id": session_id,
            "dapp_public_key": base58.b58encode(dapp_public_key).decode('utf-8'),
            "nonce": nonce_b58,
            "payload": base58.b58encode(json.dumps(payload).encode()).decode('utf-8'),
            "expires_in": 300
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Session creation error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")

@router.get("/phantom_callback", response_class=HTMLResponse)
async def phantom_callback(
    request: Request,
    session: str = Query(..., description="Session ID"),
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Handle Phantom Deep Link callback"""
    logger.info("Phantom callback received", extra={
        "session": session,
        "telegram_id": telegram_id
    })

    # Parse URL parameters from Phantom
    params = dict(request.query_params)
    
    error_code = params.get("errorCode")
    error_message = params.get("errorMessage")
    phantom_public_key = params.get("phantom_encryption_public_key")
    nonce = params.get("nonce")
    data = params.get("data")

    # Check for errors
    if error_code:
        logger.error("Phantom returned error", extra={
            "error_code": error_code,
            "error_message": error_message
        })
        
        return templates.TemplateResponse("commission_callback.html", {
            "request": request,
            "success": False,
            "error": error_message or f"Payment failed (code: {error_code})",
            "telegram_id": telegram_id,
            "bot_username": BOT_USERNAME
        })

    # Retrieve session
    session_data = get_from_cache(f"phantom_session_{session}")
    if not session_data:
        session_data = phantom_sessions.get(session)
    
    if not session_data:
        logger.error("Session not found or expired", extra={"session": session})
        return templates.TemplateResponse("commission_callback.html", {
            "request": request,
            "success": False,
            "error": "Session expired. Please try again.",
            "telegram_id": telegram_id,
            "bot_username": BOT_USERNAME
        })

    # Verify the response contains transaction signature
    if data and phantom_public_key and nonce:
        try:
            # Decrypt response
            dapp_secret_key = base58.b58decode(session_data['dapp_secret_key'])
            phantom_pk = base58.b58decode(phantom_public_key)
            nonce_bytes = base58.b58decode(nonce)
            encrypted_data = base58.b58decode(data)

            # Create shared secret
            dapp_private_key = nacl.public.PrivateKey(dapp_secret_key)
            phantom_public = nacl.public.PublicKey(phantom_pk)
            shared_secret = nacl.public.Box(dapp_private_key, phantom_public)

            # Decrypt
            decrypted = shared_secret.decrypt(encrypted_data, nonce_bytes)
            response_data = json.loads(decrypted.decode('utf-8'))

            signature = response_data.get("signature")

            if signature:
                logger.info("Transaction signature received", extra={
                    "signature": signature,
                    "telegram_id": telegram_id
                })

                # Verify and mark as paid
                user = db.query(User).filter(User.telegram_id == telegram_id).first()
                if user and not user.commission_paid:
                    
                    # Check duplicate transaction
                    existing = db.query(User).filter(
                        User.commission_transaction_hash == signature
                    ).first()

                    if existing:
                        logger.warning("Transaction already used", extra={"signature": signature})
                        return templates.TemplateResponse("commission_callback.html", {
                            "request": request,
                            "success": False,
                            "error": "This transaction has already been used",
                            "telegram_id": telegram_id,
                            "bot_username": BOT_USERNAME
                        })

                    user.commission_paid = True
                    user.commission_transaction_hash = signature
                    user.commission_payment_date = datetime.utcnow()
                    db.commit()

                    # Clear session
                    clear_cache(f"phantom_session_{session}")
                    if session in phantom_sessions:
                        del phantom_sessions[session]

                    logger.info("Payment confirmed via callback", extra={
                        "telegram_id": telegram_id,
                        "signature": signature
                    })

                    return templates.TemplateResponse("commission_callback.html", {
                        "request": request,
                        "success": True,
                        "message": "Payment confirmed successfully!",
                        "signature": signature,
                        "telegram_id": telegram_id,
                        "bot_username": BOT_USERNAME
                    })

        except Exception as e:
            logger.error("Callback decryption error", extra={"error": str(e)}, exc_info=True)

    # Default success page (will verify later)
    return templates.TemplateResponse("commission_callback.html", {
        "request": request,
        "success": True,
        "message": "Payment initiated. Verification in progress...",
        "telegram_id": telegram_id,
        "bot_username": BOT_USERNAME
    })

@router.get("/success", response_class=HTMLResponse)
async def commission_success(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Commission success page"""
    logger.info("Commission success page", extra={"telegram_id": telegram_id})

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return templates.TemplateResponse("commission_success.html", {
        "request": request,
        "telegram_id": telegram_id,
        "bot_username": BOT_USERNAME
    })

@router.get("/check_status", response_class=JSONResponse)
@limiter.limit("20/minute")
async def check_commission_status(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Check commission payment status"""
    logger.info("Checking commission status", extra={"telegram_id": telegram_id})

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "commission_paid": user.commission_paid,
        "wallet_connected": bool(user.wallet_address),
        "wallet_address": user.wallet_address,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET,
        "payment_date": user.commission_payment_date.isoformat() if user.commission_payment_date else None,
        "transaction_hash": user.commission_transaction_hash
    }

@router.post("/verify_payment", response_class=JSONResponse)
@limiter.limit("10/minute")
async def verify_payment(
    request: Request,
    db: Session = Depends(get_db)
):
    """Verify payment with transaction signature (for Extension flow)"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        signature = body.get("signature")

        if not telegram_id or not signature:
            raise HTTPException(status_code=400, detail="Missing required parameters")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            return {
                "status": "verified",
                "message": "Commission already paid"
            }

        # Check duplicate transaction
        existing = db.query(User).filter(
            User.commission_transaction_hash == signature
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="Transaction already used")

        # Verify on blockchain
        client = Client(SOLANA_RPC)
        
        try:
            tx = client.get_transaction(
                signature,
                encoding="json",
                max_supported_transaction_version=0
            )

            if tx.value:
                if tx.value.meta and tx.value.meta.err:
                    raise HTTPException(status_code=400, detail="Transaction failed on blockchain")

                user.commission_paid = True
                user.commission_transaction_hash = signature
                user.commission_payment_date = datetime.utcnow()
                db.commit()

                logger.info("Payment verified", extra={
                    "telegram_id": telegram_id,
                    "signature": signature
                })

                return {
                    "status": "verified",
                    "message": "Payment confirmed successfully",
                    "signature": signature
                }
            else:
                raise HTTPException(status_code=404, detail="Transaction not found")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Verification error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify_payment_auto", response_class=JSONResponse)
@limiter.limit("10/minute")
async def verify_payment_auto(
    request: Request,
    db: Session = Depends(get_db)
):
    """Auto-detect payment by checking user wallet transactions"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")

        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            return {
                "status": "verified",
                "payment_found": True,
                "message": "Commission already paid",
                "transaction_hash": user.commission_transaction_hash
            }

        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="No wallet connected")

        # Rate limiting
        cache_key = f'payment_check_attempts_{telegram_id}'
        attempt_count = get_from_cache(cache_key)

        if attempt_count is None:
            attempt_count = 0

        if attempt_count >= 5:
            return {
                "status": "pending",
                "payment_found": False,
                "message": "Maximum verification attempts reached. Please wait 2 minutes.",
                "max_attempts_reached": True
            }

        set_in_cache(cache_key, attempt_count + 1, ttl=120)

        client = AsyncClient(SOLANA_RPC)

        try:
            user_pubkey = Pubkey.from_string(user.wallet_address)

            logger.info(f"Payment check attempt {attempt_count + 1}/5", extra={"telegram_id": telegram_id})

            signatures_response = await client.get_signatures_for_address(
                user_pubkey,
                limit=10
            )

            if not signatures_response.value:
                await client.close()
                return {
                    "status": "pending",
                    "payment_found": False,
                    "message": "No transactions found"
                }

            expected_lamports = int(COMMISSION_AMOUNT * 1_000_000_000)
            tolerance = int(0.015 * 1_000_000_000)

            for idx, sig_info in enumerate(signatures_response.value):
                try:
                    if idx > 0:
                        await asyncio.sleep(0.5)

                    sig = str(sig_info.signature)

                    # Check transaction age (5 minutes window)
                    tx_time = sig_info.block_time
                    current_time = time.time()

                    if tx_time and (current_time - tx_time) > 300:
                        continue

                    # Check duplicate
                    existing = db.query(User).filter(
                        User.commission_transaction_hash == sig
                    ).first()

                    if existing:
                        logger.warning(f"Transaction already used", extra={"signature": sig[:20]})
                        continue

                    tx_response = await client.get_transaction(
                        sig_info.signature,
                        encoding="json",
                        max_supported_transaction_version=0
                    )

                    if not tx_response or not tx_response.value:
                        continue

                    tx_obj = tx_response.value
                    tx_json_str = tx_obj.to_json()
                    tx = json.loads(tx_json_str)

                    meta = tx.get('meta')
                    if not meta or meta.get('err'):
                        continue

                    pre_balances = meta.get('preBalances', [])
                    post_balances = meta.get('postBalances', [])

                    if not pre_balances or not post_balances:
                        continue

                    transaction = tx.get('transaction', {})
                    message = transaction.get('message', {})
                    account_keys = message.get('accountKeys', [])

                    if not account_keys or ADMIN_WALLET not in account_keys:
                        continue

                    for acc_idx in range(min(len(pre_balances), len(post_balances), len(account_keys))):
                        account = account_keys[acc_idx]
                        pre = pre_balances[acc_idx]
                        post = post_balances[acc_idx]

                        if account == user.wallet_address and pre > post:
                            sent = pre - post

                            if abs(sent - expected_lamports) <= tolerance:
                                user.commission_paid = True
                                user.commission_transaction_hash = sig
                                user.commission_payment_date = datetime.utcnow()
                                db.commit()

                                clear_cache(cache_key)
                                await client.close()

                                logger.info("Payment verified successfully", extra={
                                    "telegram_id": telegram_id,
                                    "signature": sig
                                })

                                return {
                                    "status": "verified",
                                    "payment_found": True,
                                    "message": "Payment verified successfully!",
                                    "transaction_hash": sig
                                }

                except Exception as e:
                    logger.warning(f"Transaction check error", extra={"error": str(e)})
                    continue

            await client.close()
            return {
                "status": "pending",
                "payment_found": False,
                "message": "Payment not found yet"
            }

        except Exception as e:
            await client.close()
            logger.error("Auto-verification error", extra={"error": str(e)}, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Auto-verification error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/phantom_redirect", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def commission_phantom_redirect(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """
    Solana Pay redirect page for commission payment
    Uses standard Solana Pay URL scheme compatible with all wallets
    """
    logger.info("Phantom redirect page", extra={"telegram_id": telegram_id})

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.commission_paid:
        return RedirectResponse(
            url=f"/commission/success?telegram_id={telegram_id}",
            status_code=302
        )

    if not user.wallet_address:
        raise HTTPException(status_code=400, detail="Wallet not connected")

    # Generate session ID for tracking
    session_id = secrets.token_urlsafe(32)

    # Store session
    session_data = {
        "telegram_id": telegram_id,
        "amount": COMMISSION_AMOUNT,
        "recipient": ADMIN_WALLET,
        "created_at": datetime.utcnow().isoformat(),
        "wallet_address": user.wallet_address
    }

    phantom_sessions[session_id] = session_data
    set_in_cache(f"phantom_session_{session_id}", session_data, ttl=600)  # 10 minutes

    logger.info("Payment session created for redirect", extra={
        "session_id": session_id,
        "telegram_id": telegram_id
    })

    # Render Solana Pay page
    return templates.TemplateResponse("commission_phantom_redirect.html", {
        "request": request,
        "telegram_id": telegram_id,
        "session_id": session_id,
        "admin_wallet": ADMIN_WALLET,
        "redirect_url": f"{os.getenv('APP_DOMAIN', 'https://ccoin2025.onrender.com')}/commission/verify",
        "bot_username": BOT_USERNAME,
        "commission_amount": COMMISSION_AMOUNT
    })



@router.post("/verify", response_class=JSONResponse)
@limiter.limit("30/minute")
async def verify_commission_payment(
    request: Request,
    db: Session = Depends(get_db)
):
    """Verify commission payment on Solana blockchain"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")

        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        logger.info("Verifying commission payment", extra={"telegram_id": telegram_id})

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            return {
                "success": True,
                "verified": True,
                "already_paid": True,
                "message": "Payment already confirmed"
            }

        # Check blockchain
        connection = AsyncClient(SOLANA_RPC)
        
        try:
            user_pubkey = Pubkey.from_string(user.wallet_address)
            
            # Get recent transactions
            signatures_resp = await connection.get_signatures_for_address(user_pubkey, limit=20)

            if signatures_resp.value:
                expected_lamports = int(COMMISSION_AMOUNT * 1_000_000_000)
                
                for sig_info in signatures_resp.value:
                    sig = str(sig_info.signature)
                    
                    # Skip if already used
                    if db.query(User).filter(User.commission_transaction_hash == sig).first():
                        continue
                    
                    # Get transaction
                    tx_resp = await connection.get_transaction(
                        sig,
                        encoding="jsonParsed",
                        max_supported_transaction_version=0
                    )

                    if tx_resp.value and tx_resp.value.transaction:
                        message = tx_resp.value.transaction.transaction.message
                        
                        for ix in message.instructions:
                            if hasattr(ix, 'parsed'):
                                parsed = ix.parsed
                                if parsed.get('type') == 'transfer':
                                    info = parsed.get('info', {})
                                    
                                    if (info.get('source') == user.wallet_address and
                                        info.get('destination') == ADMIN_WALLET):
                                        
                                        lamports = info.get('lamports', 0)
                                        
                                        # Check amount (allow 2% tolerance)
                                        if abs(lamports - expected_lamports) < (expected_lamports * 0.02):
                                            # Payment found!
                                            user.commission_paid = True
                                            user.commission_transaction_hash = sig
                                            user.commission_payment_date = datetime.utcnow()
                                            db.commit()

                                            logger.info("Payment verified!", extra={
                                                "telegram_id": telegram_id,
                                                "signature": sig
                                            })

                                            await connection.close()
                                            return {
                                                "success": True,
                                                "verified": True,
                                                "signature": sig,
                                                "message": "Payment verified!"
                                            }

            await connection.close()
            return {
                "success": True,
                "verified": False,
                "message": "Payment not found. Please wait 10-30 seconds after payment."
            }

        finally:
            await connection.close()

    except Exception as e:
        logger.error("Verification error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
