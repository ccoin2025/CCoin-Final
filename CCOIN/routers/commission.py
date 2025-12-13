import os
import time
import secrets
import base64
import structlog
import asyncio
from datetime import datetime, timezone

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
#from CCOIN.utils.redis_session import session_store
#from CCOIN.utils.solana_rpc import rpc_client
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
            return JSONResponse({"success": False, "error": "Commission already paid"}, status_code=400)

        if not user.wallet_address:
            raise HTTPException(status_code=400, detail="Wallet not connected")

        session_id = secrets.token_urlsafe(32)

        try:
            blockhash_resp = await rpc_client.get_latest_blockhash()
            recent_blockhash = blockhash_resp.value.blockhash

            from_pubkey = Pubkey.from_string(user.wallet_address)
            to_pubkey = Pubkey.from_string(recipient)
            lamports = int(amount * 1_000_000_000)

            transfer_ix = transfer(
                TransferParams(
                    from_pubkey=from_pubkey,
                    to_pubkey=to_pubkey,
                    lamports=lamports
                )
            )

            message = Message.new_with_blockhash(
                [transfer_ix],
                from_pubkey,
                recent_blockhash
            )

            tx = Transaction.new_unsigned(message)
            tx_bytes = bytes(tx)
            tx_base64 = base64.b64encode(tx_bytes).decode("utf-8")

        except Exception as e:
            logger.error("Transaction creation failed", extra={"error": str(e)}, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")

        session_data = {
            "telegram_id": telegram_id,
            "amount": amount,
            "recipient": recipient,
            "wallet_address": user.wallet_address,
            "created_at": datetime.utcnow().isoformat()
        }
        session_store.set_session(session_id, session_data, ttl=1800)  # 30 minutes

        logger.info("Payment session created", extra={"session_id": session_id, "telegram_id": telegram_id})
        return {"success": True, "session_id": session_id, "transaction": tx_base64, "expires_in": 1800}

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
    Verify commission payment using transaction signature from frontend
    """
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        signature = body.get("signature")
        
        logger.info("Verify signature request", extra={
            "telegram_id": telegram_id,
            "signature": signature
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
        
        existing_user = db.query(User).filter(
            User.commission_transaction_hash == signature
        ).first()
        
        if existing_user:
            logger.warning("Transaction signature already used", extra={
                "signature": signature,
                "used_by": existing_user.telegram_id,
                "attempted_by": telegram_id
            })
            return {
                "verified": False,
                "message": "This transaction has already been used by another user"
            }
        
        from solana.rpc.async_api import AsyncClient
        from solders.signature import Signature as SigObj
        
        client = AsyncClient(SOLANA_RPC)
        
        try:
            logger.info("Waiting for transaction finalization", extra={
                "signature": signature,
                "wait_time": TX_FINALIZATION_WAIT
            })
            await asyncio.sleep(TX_FINALIZATION_WAIT)
            
            sig_obj = SigObj.from_string(signature)
            tx_resp = await client.get_transaction(
                sig_obj,
                encoding="jsonParsed",
                max_supported_transaction_version=0
            )
            
            if not tx_resp.value:
                await client.close()
                logger.warning("Transaction not found or not finalized", extra={
                    "signature": signature
                })
                return {
                    "verified": False,
                    "message": "Transaction not found on blockchain yet. Please wait 30 seconds and try again.",
                    "retry_after": 30
                }
            
            if tx_resp.value.meta and tx_resp.value.meta.err:
                await client.close()
                logger.error("Transaction failed on blockchain", extra={
                    "signature": signature,
                    "error": str(tx_resp.value.meta.err)
                })
                return {
                    "verified": False,
                    "message": "Transaction failed on blockchain"
                }
            
            expected_lamports = int(COMMISSION_AMOUNT * 1_000_000_000)
            instructions = []
            
            try:
                parsed_msg = tx_resp.value.transaction.transaction.message
                instructions = getattr(parsed_msg, "instructions", []) or []
            except Exception as e:
                logger.error("Failed to parse transaction instructions", extra={
                    "error": str(e)
                })
                try:
                    tx_data = tx_resp.value.transaction
                    if isinstance(tx_data, dict):
                        instructions = tx_data.get("transaction", {}).get("message", {}).get("instructions", [])
                except:
                    pass
            
            admin_addr = ADMIN_WALLET if isinstance(ADMIN_WALLET, str) else str(ADMIN_WALLET)
            
            for ix in instructions:
                parsed = getattr(ix, "parsed", None) or (ix.get("parsed") if isinstance(ix, dict) else None)
                
                if isinstance(parsed, dict) and parsed.get("type") == "transfer":
                    info = parsed.get("info", {})
                    source = info.get("source")
                    destination = info.get("destination")
                    lamports = info.get("lamports", 0)
                    
                    logger.info("Checking transfer instruction", extra={
                        "source": source,
                        "destination": destination,
                        "lamports": lamports,
                        "expected_source": user.wallet_address,
                        "expected_destination": admin_addr,
                        "expected_lamports": expected_lamports
                    })
                    
                    if (source == user.wallet_address and 
                        destination == admin_addr and
                        int(expected_lamports * 0.98) <= int(lamports) <= int(expected_lamports * 1.02)):
                        
                        user.commission_paid = True
                        user.commission_transaction_hash = signature
                        user.commission_payment_date = datetime.now(timezone.utc)
                        db.commit()
                        
                        await client.close()
                        
                        logger.info("Commission payment verified successfully", extra={
                            "telegram_id": telegram_id,
                            "signature": signature,
                            "amount": lamports / 1_000_000_000
                        })
                        
                        return {
                            "verified": True,
                            "signature": signature,
                            "message": "Payment verified successfully! You can now return to the app."
                        }
            
            await client.close()
            
            logger.warning("No valid transfer instruction found", extra={
                "signature": signature,
                "telegram_id": telegram_id
            })
            
            return {
                "verified": False,
                "message": "Transaction found but does not match expected payment details"
            }
            
        except Exception as e:
            await client.close()
            logger.error("Error verifying transaction", extra={
                "error": str(e),
                "signature": signature
            }, exc_info=True)
            return {
                "verified": False,
                "message": f"Error verifying transaction: {str(e)}"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("verify_signature error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
                            instructions = (tx_resp.value.transaction.get("transaction", {}) or {}).get("message", {}).get("instructions", [])
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

@router.post("/send_payment_link", response_class=JSONResponse)
async def send_payment_link_to_telegram(request: Request, db: Session = Depends(get_db)):
    """Send payment link to Telegram"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        
        logger.info("send_payment_link called", extra={"telegram_id": telegram_id})
        
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.commission_paid:
            return {"success": False, "message": "Commission already paid"}
        
        success = await send_commission_payment_link(telegram_id, BOT_TOKEN)
        
        if success:
            logger.info("Payment link sent successfully", extra={"telegram_id": telegram_id})
            return {"success": True, "message": "Payment link sent to Telegram"}
        else:
            logger.error("Failed to send payment link", extra={"telegram_id": telegram_id})
            return {"success": False, "message": "Failed to send payment link"}
            
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
