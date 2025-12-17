import os
import time
import secrets
import base64
import structlog
import asyncio
import threading
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction
from solders.message import Message
import base58

from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.config import (
    COMMISSION_AMOUNT,
    ADMIN_WALLET,
    BOT_USERNAME,
    BOT_TOKEN,
    APP_DOMAIN,
    TX_SCAN_LIMIT,
    TX_FINALIZATION_WAIT,
    SOLANA_RPC
)
# from CCOIN.utils.redis_session import session_store
# from CCOIN.utils.solana_rpc import rpc_client
from CCOIN.utils.telegram_security import send_commission_payment_link

logger = structlog.get_logger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

@router.get("/browser/pay", response_class=HTMLResponse)
async def commission_browser_pay(
        request: Request,
        telegram_id: str = Query(..., description="Telegram user ID"),
        db: Session = Depends(get_db)
):
    logger.info("Render commission browser pay", extra={"telegram_id": telegram_id})
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        logger.warning("User not found", extra={"telegram_id": telegram_id})
        raise HTTPException(status_code=404, detail="User not found")

    if user.commission_paid:
        return templates.TemplateResponse("commission_success.html", {
            "request": request,
            "telegram_id": telegram_id,
            "success_message": "Commission already paid!",
            "already_paid": True,
            "bot_username": BOT_USERNAME
        })

    if not user.wallet_address:
        raise HTTPException(status_code=400, detail="Wallet not connected. Please connect your wallet first.")

    return templates.TemplateResponse("commission_browser_pay.html", {
        "request": request,
        "telegram_id": telegram_id,
        "commission_amount": COMMISSION_AMOUNT,
        "admin_wallet": ADMIN_WALLET,
        "bot_username": BOT_USERNAME
    })


@router.post("/create_payment_session", response_class=JSONResponse)
async def create_payment_session(request: Request, db: Session = Depends(get_db)):
    """
    ✅ SECURED: Create payment session with user validation
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        amount = float(body.get("amount", COMMISSION_AMOUNT))
        recipient = body.get("recipient", ADMIN_WALLET)
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.commission_paid:
            return JSONResponse(
                {"success": False, "error": "Commission already paid"}, 
                status_code=400
            )
        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="Wallet not connected")
        session_id = secrets.token_urlsafe(32)
        # Store session with user validation data
        session_data = {
            "telegram_id": telegram_id,
            "user_id": user.id,  # ⭐ اضافه شده
            "wallet_address": user.wallet_address,  # ⭐ اضافه شده
            "amount": amount,
            "recipient": recipient,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Save to session store (Redis or similar)
        # session_store.set_session(session_id, session_data, ttl=1800)
        
        # Store in request session temporarily
        request.session[f"payment_{session_id}"] = session_data
        logger.info("Payment session created", extra={
            "session_id": session_id,
            "telegram_id": telegram_id,
            "user_id": user.id,
            "wallet": user.wallet_address
        })
        
        return {
            "success": True,
            "session_id": session_id,
            "expires_in": 1800
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_payment_session error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/phantom_callback", response_class=HTMLResponse)
async def phantom_callback(request: Request):
    """
    Phantom redirect target.
    """
    params = dict(request.query_params)
    logger.info("Phantom callback", extra={"params": params})

    session = params.get("session")
    signature = params.get("signature")
    telegram_id = params.get("telegram_id")

    if params.get("errorCode") or params.get("errorMessage"):
        err = params.get("errorMessage") or f"Phantom error {params.get('errorCode')}"
        return templates.TemplateResponse("commission_callback.html", {
            "request": request,
            "success": False,
            "error": err,
            "telegram_id": telegram_id,
            "bot_username": BOT_USERNAME
        })

    if signature and session:
        s = session_store.get_session(session)
        if s:
            s["signature"] = signature
            session_store.set_session(session, s, ttl=3600)
        return templates.TemplateResponse("commission_callback.html", {
            "request": request,
            "success": None,
            "message": "Transaction submitted. Verifying...",
            "telegram_id": telegram_id,
            "bot_username": BOT_USERNAME,
            "signature": signature
        })

    return templates.TemplateResponse("commission_callback.html", {
        "request": request,
        "success": None,
        "message": "No callback data received. If you completed payment, click 'Check Status'.",
        "telegram_id": telegram_id,
        "bot_username": BOT_USERNAME
    })


@router.post("/verify_signature", response_class=JSONResponse)
async def verify_signature(request: Request, db: Session = Depends(get_db)):
    """
    ✅ SECURED: Verify commission payment with strict validation
    """
    validator = TransactionValidator(db)
    
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        signature = body.get("signature")
        logger.info("Verify signature request", extra={
            "telegram_id": telegram_id,
            "signature": signature,
            "ip": request.client.host
        })
        if not telegram_id or not signature:
            raise HTTPException(status_code=400, detail="Missing telegram_id or signature")
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.commission_paid:
            return {
                "verified": True,
                "message": "Commission already paid",
                "already_paid": True
            }
        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="Wallet not connected")
        duplicate_check = validator.check_duplicate_signature(signature)
        if duplicate_check:
            logger.warning("Duplicate signature attempt", extra={
                "signature": signature,
                "requesting_user": telegram_id,
                "existing_user": duplicate_check["telegram_id"],
                "ip": request.client.host
            })
            return {
                "verified": False,
                "message": "This transaction has already been used by another user"
            }
        ownership = validator.validate_ownership(
            signature, 
            telegram_id, 
            user.wallet_address
        )
        
        if not ownership["valid"]:
            return {
                "verified": False,
                "message": ownership["error"]
            }
        try:
            pending_tx = validator.create_transaction_record(
                user_id=user.id,
                telegram_id=telegram_id,
                signature=signature,
                wallet_address=user.wallet_address,
                amount=COMMISSION_AMOUNT,
                recipient=ADMIN_WALLET,
                status="pending",
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent")
            )
            db.commit()
        except IntegrityError as e:
            db.rollback()
            logger.error("Duplicate signature in database", extra={
                "signature": signature,
                "error": str(e)
            })
            return {
                "verified": False,
                "message": "Transaction signature already exists"
            }
        logger.info("Waiting for transaction finalization", extra={
            "signature": signature,
            "wait_time": TX_FINALIZATION_WAIT
        })
        await asyncio.sleep(TX_FINALIZATION_WAIT)
        blockchain_result = await validator.verify_solana_transaction(
            signature=signature,
            expected_wallet=user.wallet_address,
            expected_amount=COMMISSION_AMOUNT,
            expected_recipient=ADMIN_WALLET
        )
        await validator.close_client()
        if not blockchain_result["verified"]:
            validator.update_transaction_status(pending_tx, "failed")
            db.commit()
            
            return {
                "verified": False,
                "message": blockchain_result.get("error", "Transaction verification failed")
            }
        try:
            validator.update_transaction_status(pending_tx, "verified")
            validator.mark_user_as_paid(user, signature)
            db.commit()
            logger.info("Commission payment verified successfully", extra={
                "telegram_id": telegram_id,
                "user_id": user.id,
                "signature": signature,
                "amount": blockchain_result["amount"]
            })
            for key in list(request.session.keys()):
                if key.startswith("payment_"):
                    del request.session[key]
            return {
                "verified": True,
                "signature": signature,
                "message": "Payment verified successfully! You can now return to the app."
            }
            
        except IntegrityError as e:
            db.rollback()
            logger.error("Race condition detected during commit", extra={
                "signature": signature,
                "error": str(e)
            })
            return {
                "verified": False,
                "message": "Transaction already processed"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("verify_signature error", extra={
            "error": str(e),
            "telegram_id": telegram_id
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await validator.close_client()


@router.post("/verify", response_class=JSONResponse)
async def verify_commission_payment(request: Request, db: Session = Depends(get_db)):
    """
    ✅ FIXED: Verify commission payment with strict validation
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")

        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            return {"success": True, "verified": True, "already_paid": True, "message": "Payment already confirmed"}

        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="Wallet not connected")

        from solana.rpc.async_api import AsyncClient
        from solders.signature import Signature
        from CCOIN.config import SOLANA_RPC

        client = AsyncClient(SOLANA_RPC)

        try:
            user_pubkey = Pubkey.from_string(user.wallet_address)
            logger.info("Scanning recent transactions", extra={
                "user_wallet": user.wallet_address,
                "scan_limit": TX_SCAN_LIMIT
            })

            signatures_resp = await client.get_signatures_for_address(user_pubkey, limit=TX_SCAN_LIMIT)
            expected_lamports = int(COMMISSION_AMOUNT * 1_000_000_000)

            if signatures_resp.value:
                for sig_info in signatures_resp.value:
                    sig = str(sig_info.signature)

                    existing_user = db.query(User).filter(
                        User.commission_transaction_hash == sig
                    ).first()

                    if existing_user:
                        logger.info("Transaction already used by another user", extra={"signature": sig})
                        continue

                    tx_time = sig_info.block_time
                    if tx_time:
                        current_time = int(datetime.now(timezone.utc).timestamp())
                        time_diff = current_time - tx_time

                        if time_diff > 600:
                            logger.info("Transaction too old", extra={
                                "signature": sig,
                                "age_seconds": time_diff
                            })
                            continue

                    await asyncio.sleep(0.5)

                    try:
                        sig_obj = Signature.from_string(sig)
                        tx_resp = await client.get_transaction(
                            sig_obj,
                            encoding="jsonParsed",
                            max_supported_transaction_version=0
                        )
                    except Exception as tx_error:
                        logger.warning("Failed to get transaction", extra={
                            "signature": sig,
                            "error": str(tx_error)
                        })
                        continue

                    if not tx_resp.value:
                        continue

                    instructions = []
                    try:
                        parsed_msg = tx_resp.value.transaction.transaction.message
                        instructions = getattr(parsed_msg, "instructions", []) or []
                    except Exception:
                        try:
                            instructions = (tx_resp.value.transaction.get("transaction", {}) or {}).get("message",
                                                                                                        {}).get(
                                "instructions", [])
                        except:
                            continue

                    admin_addr = ADMIN_WALLET if isinstance(ADMIN_WALLET, str) else str(ADMIN_WALLET)

                    for ix in instructions:
                        parsed = getattr(ix, "parsed", None) or (ix.get("parsed") if isinstance(ix, dict) else None)
                        if isinstance(parsed, dict) and parsed.get("type") == "transfer":
                            info = parsed.get("info", {})
                            source = info.get("source")
                            destination = info.get("destination")
                            lamports = info.get("lamports", 0)

                            if (source == user.wallet_address and
                                    destination == admin_addr and
                                    int(expected_lamports * 0.98) <= int(lamports) <= int(expected_lamports * 1.02)):
                                user.commission_paid = True
                                user.commission_transaction_hash = sig
                                user.commission_payment_date = datetime.now(timezone.utc)
                                db.commit()

                                await client.close()

                                logger.info("Payment verified and recorded", extra={
                                    "telegram_id": telegram_id,
                                    "signature": sig
                                })
                                return {"success": True, "verified": True, "signature": sig}

            await client.close()
            return {
                "success": False,
                "verified": False,
                "message": "No valid payment transaction found. Please complete payment first."
            }

        except Exception as e:
            await client.close()
            logger.error("Verification error", extra={"error": str(e)}, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("verify_commission_payment error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send_payment_link", response_class=JSONResponse)
async def send_payment_link_endpoint(request: Request, db: Session = Depends(get_db)):
    """
    Send commission payment link to user via Telegram bot
    """
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
                "success": True,
                "message": "Commission already paid"
            }

        success = await send_commission_payment_link(telegram_id, BOT_TOKEN)

        if success:
            logger.info("Payment link sent successfully", extra={
                "telegram_id": telegram_id
            })
            return {
                "success": True,
                "message": "Payment link sent to your Telegram"
            }
        else:
            logger.error("Failed to send payment link", extra={
                "telegram_id": telegram_id
            })
            return {
                "success": False,
                "error": "Failed to send payment link. Please try again."
            }

    except Exception as e:
        logger.error("send_payment_link error", extra={
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan_transaction", response_class=JSONResponse)
async def scan_transaction(request: Request, db: Session = Depends(get_db)):
    """
    Scan recent transactions from wallet to find commission payment
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")

        logger.info("Scanning transactions", extra={"telegram_id": telegram_id})

        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")

        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.commission_paid:
            return {
                "signature": user.commission_transaction_hash,
                "message": "Already paid"
            }

        wallet_address = user.wallet_address

        if not wallet_address:
            raise HTTPException(status_code=400, detail="No wallet address found")

        from solana.rpc.async_api import AsyncClient
        from solders.pubkey import Pubkey

        client = AsyncClient(SOLANA_RPC)

        try:
            # Get recent transactions
            pubkey = Pubkey.from_string(wallet_address)
            signatures = await client.get_signatures_for_address(
                pubkey,
                limit=TX_SCAN_LIMIT
            )

            if not signatures.value:
                await client.close()
                logger.warning("No recent transactions found", extra={"wallet": wallet_address})
                return {
                    "signature": None,
                    "message": "No recent transactions found"
                }

            expected_lamports = int(COMMISSION_AMOUNT * 1_000_000_000)
            admin_addr = ADMIN_WALLET if isinstance(ADMIN_WALLET, str) else str(ADMIN_WALLET)

            logger.info("Checking recent transactions", extra={
                "count": len(signatures.value),
                "expected_lamports": expected_lamports
            })

            # Check each recent transaction
            for sig_info in signatures.value:
                sig_str = str(sig_info.signature)

                logger.info("Checking signature", extra={"signature": sig_str})

                # Skip if already used
                existing = db.query(User).filter(
                    User.commission_transaction_hash == sig_str
                ).first()
                if existing:
                    logger.info("Signature already used", extra={"signature": sig_str})
                    continue

                # Get transaction details
                from solders.signature import Signature as SigObj
                sig_obj = SigObj.from_string(sig_str)

                tx_resp = await client.get_transaction(
                    sig_obj,
                    encoding="jsonParsed",
                    max_supported_transaction_version=0
                )

                if not tx_resp or not tx_resp.value:
                    logger.info("Transaction not found", extra={"signature": sig_str})
                    continue

                # Fix: Check meta attribute properly
                tx_meta = None
                try:
                    tx_meta = getattr(tx_resp.value, 'meta', None)
                except:
                    pass

                # Check if transaction failed
                if tx_meta and hasattr(tx_meta, 'err') and tx_meta.err:
                    logger.info("Transaction failed", extra={"signature": sig_str})
                    continue

                # Parse instructions
                instructions = []
                try:
                    # Try different ways to access instructions
                    if hasattr(tx_resp.value, 'transaction'):
                        tx_data = tx_resp.value.transaction
                        if hasattr(tx_data, 'transaction'):
                            msg = tx_data.transaction.message
                            instructions = getattr(msg, "instructions", []) or []
                        elif hasattr(tx_data, 'message'):
                            instructions = getattr(tx_data.message, "instructions", []) or []
                except Exception as e:
                    logger.error("Failed to parse instructions", extra={"error": str(e)})
                    continue

                logger.info("Found instructions", extra={
                    "signature": sig_str,
                    "instruction_count": len(instructions)
                })

                # Check each instruction
                for ix in instructions:
                    parsed = None
                    try:
                        parsed = getattr(ix, "parsed", None)
                        if not parsed and isinstance(ix, dict):
                            parsed = ix.get("parsed")
                    except:
                        pass

                    if isinstance(parsed, dict) and parsed.get("type") == "transfer":
                        info = parsed.get("info", {})
                        source = info.get("source")
                        destination = info.get("destination")
                        lamports = info.get("lamports", 0)

                        logger.info("Found transfer", extra={
                            "signature": sig_str,
                            "source": source,
                            "destination": destination,
                            "lamports": lamports,
                            "expected_source": wallet_address,
                            "expected_destination": admin_addr,
                            "expected_lamports": expected_lamports
                        })

                        # Verify transfer matches expected payment
                        if (source == wallet_address and
                                destination == admin_addr and
                                int(expected_lamports * 0.98) <= int(lamports) <= int(expected_lamports * 1.02)):
                            await client.close()
                            logger.info("✅ Matching transaction found!", extra={
                                "signature": sig_str,
                                "lamports": lamports
                            })
                            return {
                                "signature": sig_str,
                                "message": "Transaction found"
                            }

            await client.close()
            logger.warning("No matching transaction found")
            return {
                "signature": None,
                "message": "No matching payment found. Please wait a moment and try again."
            }

        except Exception as e:
            await client.close()
            logger.error("Error scanning transactions", extra={"error": str(e)}, exc_info=True)
            return {
                "signature": None,
                "message": f"Scan error: {str(e)}"
            }

    except Exception as e:
        logger.error("scan_transaction error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check_status", response_class=JSONResponse)
async def check_commission_status(telegram_id: str, db: Session = Depends(get_db)):
    """
    Simple status check - just returns current payment status from database
    """
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "commission_paid": user.commission_paid,
            "transaction_hash": user.commission_transaction_hash if user.commission_paid else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("check_status error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


last_sent = {}
lock = threading.Lock()

@router.post("/send_payment_link", response_class=JSONResponse)
async def send_payment_link(request: Request, db: Session = Depends(get_db)):
    """
    Send commission payment link to user's Telegram
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")
        
        with lock:
            now = datetime.now()
            last_time = last_sent.get(telegram_id)
            
            if last_time and (now - last_time).total_seconds() < 5:
                logger.warning("Duplicate request blocked", extra={
                    "telegram_id": telegram_id,
                    "seconds_since_last": (now - last_time).total_seconds()
                })
                return {
                    "success": True,
                    "message": "Link already sent recently"
                }
            
            last_sent[telegram_id] = now
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.commission_paid:
            return {
                "success": False,
                "message": "Commission already paid"
            }
        
        if not user.wallet_address:
            return {
                "success": False,
                "message": "Wallet not connected"
            }
        
        payment_url = f"{request.base_url}commission/browser/pay?telegram_id={telegram_id}"
        
        message = (
            f"💰 *Commission Payment Required*\n\n"
            f"To unlock your airdrop, please pay the commission fee of *{COMMISSION_AMOUNT} SOL*\n\n"
            f"Click the link below to proceed with payment:\n"
            f"{payment_url}\n\n"
            f"⚠️ This link will open in your browser. Complete the payment and return to the app."
        )
        
        success = await send_telegram_message(
            telegram_id,
            message,
            parse_mode="Markdown"
        )
        
        if success:
            logger.info("Payment link sent successfully", extra={
                "telegram_id": telegram_id
            })
            return {
                "success": True,
                "message": "Payment link sent to Telegram"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send Telegram message")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("send_payment_link error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check_status", response_class=JSONResponse)
async def check_commission_status(
        telegram_id: str = Query(...),
        db: Session = Depends(get_db)
):
    """
    Check if user has paid commission
    """
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "commission_paid": user.commission_paid,
        "transaction_hash": user.commission_transaction_hash,
        "payment_date": user.commission_payment_date.isoformat() if user.commission_payment_date else None
    }
