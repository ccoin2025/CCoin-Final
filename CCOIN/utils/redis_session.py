import json
import time
import structlog
from typing import Optional, Dict, Any
import redis
from CCOIN.config import REDIS_URL

logger = structlog.get_logger(__name__)

class RedisSessionStore:
    """Redis-based session storage for payment sessions"""
    
    def __init__(self):
        try:
            self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            self.redis_client.ping()
            logger.info("Redis session store initialized successfully")
        except Exception as e:
            logger.error("Redis connection failed, falling back to memory storage", error=str(e))
            self.redis_client = None
            self._memory_store = {}
    
    def _get_key(self, session_id: str) -> str:
        return f"payment_session:{session_id}"
    
    def set_session(self, session_id: str, data: Dict[str, Any], ttl: int = 600) -> bool:
        """Store session data with TTL"""
        try:
            if self.redis_client:
                session_data = {
                    "data": data,
                    "expires_at": time.time() + ttl
                }
                self.redis_client.setex(
                    self._get_key(session_id),
                    ttl,
                    json.dumps(session_data)
                )
                logger.info("Session stored in Redis", session_id=session_id, ttl=ttl)
                return True
            else:
                self._memory_store[session_id] = {
                    "data": data,
                    "expires_at": time.time() + ttl
                }
                logger.warning("Session stored in memory (Redis unavailable)", session_id=session_id)
                return True
        except Exception as e:
            logger.error("Failed to store session", error=str(e), session_id=session_id)
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data"""
        try:
            if self.redis_client:
                data = self.redis_client.get(self._get_key(session_id))
                if data:
                    session_data = json.loads(data)
                    if time.time() < session_data.get("expires_at", 0):
                        return session_data.get("data")
                    else:
                        self.delete_session(session_id)
                        return None
                return None
            else:
                ent = self._memory_store.get(session_id)
                if not ent:
                    return None
                if time.time() > ent["expires_at"]:
                    self._memory_store.pop(session_id, None)
                    return None
                return ent["data"]
        except Exception as e:
            logger.error("Failed to retrieve session", error=str(e), session_id=session_id)
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session data"""
        try:
            if self.redis_client:
                self.redis_client.delete(self._get_key(session_id))
            else:
                self._memory_store.pop(session_id, None)
            logger.info("Session deleted", session_id=session_id)
            return True
        except Exception as e:
            logger.error("Failed to delete session", error=str(e), session_id=session_id)
            return False

session_store = RedisSessionStore()
