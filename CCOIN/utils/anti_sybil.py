from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from CCOIN.models.user import User
from solana.rpc.api import Client
from CCOIN.config import SOLANA_RPC
import structlog

logger = structlog.get_logger()
solana_client = Client(SOLANA_RPC)

def check_wallet_age(wallet_address: str) -> bool:
    """بررسی سن کیف پول - جدید بودن مشکوک است"""
    try:
        response = solana_client.get_signatures_for_address(wallet_address, limit=1)
        if not response.value:
            logger.warning("Empty wallet detected", extra={"wallet": wallet_address})
            return False  # کیف پول بدون تراکنش
        
        # بررسی اولین تراکنش
        first_tx_time = response.value[0].block_time
        if first_tx_time:
            wallet_age = datetime.now(timezone.utc) - datetime.fromtimestamp(first_tx_time, tz=timezone.utc)
            if wallet_age < timedelta(days=7):  # کمتر از 7 روز
                logger.warning("New wallet detected", extra={
                    "wallet": wallet_address,
                    "age_days": wallet_age.days
                })
                return False
        return True
    except Exception as e:
        logger.error("Error checking wallet age", extra={"error": str(e)})
        return True  # در صورت خطا، اجازه بده (fail open)

def check_duplicate_pattern(db: Session, telegram_id: str, ip_address: str = None) -> bool:
    """بررسی الگوهای مشکوک - چند اکانت از یک IP"""
    try:
        # بررسی تعداد اکانت‌ها با همان الگو
        recent_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        # اگر IP tracking دارید:
        if ip_address:
            # این نیاز به اضافه کردن فیلد ip_address به مدل User دارد
            suspicious_count = db.query(User).filter(
                User.last_ip == ip_address,
                User.created_at > recent_time
            ).count()
            
            if suspicious_count > 3:  # بیش از 3 اکانت از یک IP در 24 ساعت
                logger.warning("Multiple accounts from same IP", extra={
                    "ip": ip_address,
                    "count": suspicious_count
                })
                return False
        
        return True
    except Exception as e:
        logger.error("Error checking duplicate pattern", extra={"error": str(e)})
        return True

def check_wallet_activity(wallet_address: str) -> dict:
    """بررسی فعالیت کیف پول"""
    try:
        response = solana_client.get_signatures_for_address(wallet_address, limit=100)
        
        if not response.value:
            return {
                "is_active": False,
                "tx_count": 0,
                "risk_score": 100  # بالاترین ریسک
            }
        
        tx_count = len(response.value)
        
        # محاسبه risk score
        if tx_count == 0:
            risk_score = 100
        elif tx_count < 5:
            risk_score = 80
        elif tx_count < 20:
            risk_score = 50
        else:
            risk_score = 20
        
        return {
            "is_active": tx_count > 5,
            "tx_count": tx_count,
            "risk_score": risk_score
        }
    except Exception as e:
        logger.error("Error checking wallet activity", extra={"error": str(e)})
        return {"is_active": True, "tx_count": 0, "risk_score": 50}
