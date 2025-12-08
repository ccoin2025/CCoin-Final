import httpx
from CCOIN.config import RECAPTCHA_SECRET_KEY
import structlog

logger = structlog.get_logger()

async def verify_recaptcha(token: str, remote_ip: str) -> bool:
    """Verify reCAPTCHA token"""
    if not RECAPTCHA_SECRET_KEY:
        logger.warning("reCAPTCHA not configured")
        return True  
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://www.google.com/recaptcha/api/siteverify",
                data={
                    "secret": RECAPTCHA_SECRET_KEY,
                    "response": token,
                    "remoteip": remote_ip
                }
            )
            result = response.json()
            
            if result.get("success"):
                logger.info("reCAPTCHA verified", extra={"score": result.get("score")})
                return True
            else:
                logger.warning("reCAPTCHA failed", extra={"errors": result.get("error-codes")})
                return False
    except Exception as e:
        logger.error("reCAPTCHA verification error", extra={"error": str(e)})
        return True  
