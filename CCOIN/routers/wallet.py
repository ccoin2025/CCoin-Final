from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
from datetime import datetime, timezone
from CCOIN.database import get_db
from CCOIN.models.user import User
from CCOIN.config import SOLANA_RPC, ADMIN_WALLET, BOT_USERNAME, APP_DOMAIN
import structlog
import json
import base58
import nacl.utils
import nacl.public

logger = structlog.get_logger()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

in_memory_keypairs = {}

@router.get("/browser/connect", response_class=HTMLResponse)
@limiter.limit("20/minute")
async def wallet_browser_connect(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    phantom_encryption_public_key: str = Query(None),
    nonce: str = Query(None),
    data: str = Query(None),
    errorCode: str = Query(None),
    errorMessage: str = Query(None),
    db: Session = Depends(get_db)
):
    """Wallet connection page in browser with Phantom deeplink support"""
    
    try:
        logger.info("Wallet connect request", extra={"telegram_id": telegram_id})
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            logger.error("User not found", extra={"telegram_id": telegram_id})
            raise HTTPException(status_code=404, detail="User not found")
        
        if errorCode or errorMessage:
            error_msg = errorMessage or f"Connection error: {errorCode}"
            logger.warning("Phantom connection error", extra={
                "telegram_id": telegram_id,
                "error_code": errorCode,
                "error_message": errorMessage
            })
            
            return RedirectResponse(
                url=f"/airdrop?wallet_error={error_msg}",
                status_code=302
            )
        
        if phantom_encryption_public_key and nonce and data:
            try:
                logger.info("Processing Phantom redirect", extra={"telegram_id": telegram_id})
                
                dapp_keypair_json = in_memory_keypairs.get(telegram_id)
                
                if not dapp_keypair_json:
                    logger.error("dApp keypair not found in memory", extra={"telegram_id": telegram_id})
                    return RedirectResponse(
                        url=f"/airdrop?wallet_error=Session expired. Please reconnect.",
                        status_code=302
                    )
                
                dapp_keypair = json.loads(dapp_keypair_json)
                
                logger.info("Decrypting Phantom response", extra={"telegram_id": telegram_id})
                
                encrypted_data = base58.b58decode(data)
                nonce_bytes = base58.b58decode(nonce)
                phantom_public_key_bytes = base58.b58decode(phantom_encryption_public_key)
                
                dapp_secret_key = nacl.public.PrivateKey(bytes(dapp_keypair['secretKey']))
                phantom_public_key_obj = nacl.public.PublicKey(phantom_public_key_bytes)
                
                box = nacl.public.Box(dapp_secret_key, phantom_public_key_obj)
                
                decrypted_data = box.decrypt(encrypted_data, nonce_bytes)
                response_data = json.loads(decrypted_data.decode('utf-8'))
                
                logger.info("Decryption successful", extra={"telegram_id": telegram_id})
                
                wallet_address = response_data.get('public_key')
                
                if not wallet_address:
                    raise ValueError("No public_key in response")
                
                logger.info("Wallet address extracted", extra={
                    "telegram_id": telegram_id,
                    "wallet_address": wallet_address
                })
                
                existing_user = db.query(User).filter(
                    User.wallet_address == wallet_address,
                    User.id != user.id
                ).first()
                
                if existing_user:
                    logger.warning("Duplicate wallet attempt", extra={
                        "telegram_id": telegram_id,
                        "wallet": wallet_address
                    })
                    in_memory_keypairs.pop(telegram_id, None)
                    return RedirectResponse(
                        url=f"/airdrop?wallet_error=Wallet already connected to another account",
                        status_code=302
                    )
                
                user.wallet_address = wallet_address
                user.wallet_connected = True
                user.wallet_connection_date = datetime.now(timezone.utc)
                user.updated_at = datetime.now(timezone.utc)
                db.commit()
                
                logger.info("Wallet connected successfully", extra={
                    "telegram_id": telegram_id,
                    "wallet_address": wallet_address
                })
                
                in_memory_keypairs.pop(telegram_id, None)
                
                return RedirectResponse(
                    url=f"/airdrop?wallet_connected=success",
                    status_code=302
                )
                
            except Exception as e:
                logger.error("Failed to process Phantom response", extra={
                    "telegram_id": telegram_id,
                    "error": str(e)
                }, exc_info=True)
                
                in_memory_keypairs.pop(telegram_id, None)
                
                error_message = "Failed to decrypt response from Phantom. Please try again."
                
                return RedirectResponse(
                    url=f"/airdrop?wallet_error={error_message}",
                    status_code=302
                )
        
        else:
            dapp_keypair = nacl.public.PrivateKey.generate()
            
            dapp_keypair_dict = {
                'publicKey': list(bytes(dapp_keypair.public_key)),
                'secretKey': list(bytes(dapp_keypair))
            }
            
            in_memory_keypairs[telegram_id] = json.dumps(dapp_keypair_dict)
            
            logger.info("dApp keypair saved to memory", extra={"telegram_id": telegram_id})
            
            dapp_public_key_base58 = base58.b58encode(bytes(dapp_keypair.public_key)).decode('utf-8')
            
            redirect_url = f"{APP_DOMAIN}/wallet/browser/connect?telegram_id={telegram_id}"
            
            app_url = APP_DOMAIN
            
            return templates.TemplateResponse("wallet_browser_connect.html", {
                "request": request,
                "telegram_id": telegram_id,
                "dapp_public_key": dapp_public_key_base58,
                "redirect_url": redirect_url,
                "app_url": app_url,
                "cluster": "mainnet-beta",
                "bot_username": BOT_USERNAME
            })
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Wallet browser connect error", extra={
            "telegram_id": telegram_id,
            "error": str(e)
        }, exc_info=True)
        
        return RedirectResponse(
            url=f"/airdrop?wallet_error=Internal server error.",
            status_code=302
        )

@router.post("/connect", response_class=JSONResponse)
@limiter.limit("10/minute")
async def connect_wallet_api(
    request: Request,
    db: Session = Depends(get_db)
):
    """API endpoint for wallet connection"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        wallet_address = body.get("wallet_address")
        
        if not telegram_id or not wallet_address:
            raise HTTPException(status_code=400, detail="Missing telegram_id or wallet_address")
        
        logger.info("Wallet connect API request", extra={
            "telegram_id": telegram_id,
            "wallet_address": wallet_address
        })
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        existing_user = db.query(User).filter(
            User.wallet_address == wallet_address,
            User.id != user.id
        ).first()
        
        if existing_user:
            logger.warning("Duplicate wallet attempt", extra={
                "telegram_id": telegram_id,
                "wallet": wallet_address
            })
            raise HTTPException(status_code=400, detail="Wallet already connected to another account")
        
        user.wallet_address = wallet_address
        user.wallet_connected = True
        user.wallet_connection_date = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)
        db.commit()
        
        logger.info("Wallet connected successfully via API", extra={
            "telegram_id": telegram_id,
            "wallet_address": wallet_address
        })
        
        return {
            "success": True,
            "message": "Wallet connected successfully",
            "wallet_address": wallet_address
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Wallet connect API error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to connect wallet: {str(e)}")

@router.post("/disconnect", response_class=JSONResponse)
@limiter.limit("10/minute")
async def disconnect_wallet_api(
    request: Request,
    db: Session = Depends(get_db)
):
    """API endpoint for wallet disconnection"""
    try:
        body = await request.json()
        telegram_id = body.get("telegram_id")
        
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Missing telegram_id")
        
        logger.info("Wallet disconnect request", extra={"telegram_id": telegram_id})
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.wallet_address = None
        user.wallet_connected = False
        user.updated_at = datetime.now(timezone.utc)
        db.commit()
        
        logger.info("Wallet disconnected successfully", extra={"telegram_id": telegram_id})
        
        return {
            "success": True,
            "message": "Wallet disconnected successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Wallet disconnect error", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to disconnect wallet: {str(e)}")

@router.get("/status", response_class=JSONResponse)
@limiter.limit("30/minute")
async def wallet_status(
    request: Request,
    telegram_id: str = Query(..., description="Telegram user ID"),
    db: Session = Depends(get_db)
):
    """Check wallet connection status"""
    logger.info("Wallet status check", extra={"telegram_id": telegram_id})
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "wallet_connected": user.wallet_connected,
        "wallet_address": user.wallet_address,
        "connection_date": user.wallet_connection_date.isoformat() if user.wallet_connection_date else None
    }
