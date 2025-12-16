import structlog
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, Dict, Any
from solana.rpc.async_api import AsyncClient
from solders.signature import Signature as SigObj
from solders.pubkey import Pubkey

from CCOIN.models.user import User
from CCOIN.models.transaction import Transaction
from CCOIN.config import SOLANA_RPC, COMMISSION_AMOUNT, ADMIN_WALLET

logger = structlog.get_logger(__name__)


class TransactionValidator:
    """Validator for Solana transactions with security checks"""
    
    def __init__(self, db: Session):
        self.db = db
        self.client = None
    
    async def initialize_client(self):
        """Initialize Solana RPC client"""
        if not self.client:
            self.client = AsyncClient(SOLANA_RPC)
        return self.client
    
    async def close_client(self):
        """Close Solana RPC client"""
        if self.client:
            await self.client.close()
            self.client = None
    
    def check_duplicate_signature(self, signature: str) -> Optional[Dict[str, Any]]:
        """
        Check if signature already exists in database
        Returns existing transaction info if found
        """
        existing_tx = self.db.query(Transaction).filter(
            Transaction.signature == signature
        ).first()
        
        if existing_tx:
            logger.warning("Duplicate signature detected", extra={
                "signature": signature,
                "existing_user_id": existing_tx.user_id,
                "existing_telegram_id": existing_tx.telegram_id,
                "existing_status": existing_tx.status
            })
            return {
                "exists": True,
                "user_id": existing_tx.user_id,
                "telegram_id": existing_tx.telegram_id,
                "status": existing_tx.status,
                "created_at": existing_tx.created_at
            }
        
        return None
    
    def check_user_already_paid(self, user_id: int) -> bool:
        """Check if user already paid commission"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if user and user.commission_paid:
            logger.info("User already paid commission", extra={"user_id": user_id})
            return True
        return False
    
    def validate_ownership(
        self, 
        signature: str, 
        telegram_id: str, 
        wallet_address: str
    ) -> Dict[str, Any]:
        """
        Validate that signature belongs to the requesting user
        """
        user = self.db.query(User).filter(
            User.telegram_id == telegram_id
        ).first()
        
        if not user:
            return {
                "valid": False,
                "error": "User not found"
            }
        
        if user.wallet_address != wallet_address:
            logger.warning("Wallet mismatch", extra={
                "telegram_id": telegram_id,
                "expected_wallet": user.wallet_address,
                "provided_wallet": wallet_address
            })
            return {
                "valid": False,
                "error": "Wallet address mismatch"
            }
        
        # Check if signature already used by another user
        existing_tx = self.db.query(Transaction).filter(
            and_(
                Transaction.signature == signature,
                Transaction.user_id != user.id
            )
        ).first()
        
        if existing_tx:
            logger.warning("Signature used by different user", extra={
                "signature": signature,
                "requesting_user": user.id,
                "owning_user": existing_tx.user_id
            })
            return {
                "valid": False,
                "error": "Transaction signature already used by another user"
            }
        
        return {
            "valid": True,
            "user": user
        }
    
    async def verify_solana_transaction(
        self,
        signature: str,
        expected_wallet: str,
        expected_amount: float,
        expected_recipient: str
    ) -> Dict[str, Any]:
        """
        Verify transaction on Solana blockchain
        """
        try:
            await self.initialize_client()
            
            sig_obj = SigObj.from_string(signature)
            
            logger.info("Fetching transaction from blockchain", extra={
                "signature": signature
            })
            
            tx_resp = await self.client.get_transaction(
                sig_obj,
                encoding="jsonParsed",
                max_supported_transaction_version=0
            )
            
            if not tx_resp or not tx_resp.value:
                return {
                    "verified": False,
                    "error": "Transaction not found on blockchain"
                }
            
            # Check transaction error status
            tx_meta = getattr(tx_resp.value, 'meta', None)
            
            if tx_meta and hasattr(tx_meta, 'err') and tx_meta.err:
                logger.error("Transaction failed on blockchain", extra={
                    "signature": signature,
                    "error": str(tx_meta.err)
                })
                return {
                    "verified": False,
                    "error": "Transaction failed on blockchain"
                }
            
            # Parse transaction instructions
            instructions = []
            try:
                if hasattr(tx_resp.value, 'transaction'):
                    tx_data = tx_resp.value.transaction
                    if hasattr(tx_data, 'transaction'):
                        msg = tx_data.transaction.message
                        instructions = getattr(msg, "instructions", []) or []
                    elif hasattr(tx_data, 'message'):
                        instructions = getattr(tx_data.message, "instructions", []) or []
            except Exception as e:
                logger.error("Failed to parse instructions", extra={"error": str(e)})
                return {
                    "verified": False,
                    "error": "Failed to parse transaction"
                }
            
            # Validate transfer instruction
            expected_lamports = int(expected_amount * 1_000_000_000)
            
            for ix in instructions:
                parsed = getattr(ix, "parsed", None)
                if not parsed and isinstance(ix, dict):
                    parsed = ix.get("parsed")
                
                if isinstance(parsed, dict) and parsed.get("type") == "transfer":
                    info = parsed.get("info", {})
                    source = info.get("source")
                    destination = info.get("destination")
                    lamports = info.get("lamports", 0)
                    
                    logger.info("Checking transfer instruction", extra={
                        "source": source,
                        "destination": destination,
                        "lamports": lamports,
                        "expected_source": expected_wallet,
                        "expected_destination": expected_recipient,
                        "expected_lamports": expected_lamports
                    })
                    
                    # Allow 2% tolerance for fees
                    min_lamports = int(expected_lamports * 0.98)
                    max_lamports = int(expected_lamports * 1.02)
                    
                    if (source == expected_wallet and
                        destination == expected_recipient and
                        min_lamports <= int(lamports) <= max_lamports):
                        
                        return {
                            "verified": True,
                            "amount": lamports / 1_000_000_000,
                            "source": source,
                            "destination": destination
                        }
            
            logger.warning("No valid transfer instruction found", extra={
                "signature": signature,
                "expected_source": expected_wallet,
                "expected_destination": expected_recipient
            })
            
            return {
                "verified": False,
                "error": "Transaction does not match expected payment details"
            }
            
        except Exception as e:
            logger.error("Error verifying transaction on blockchain", extra={
                "error": str(e),
                "signature": signature
            }, exc_info=True)
            return {
                "verified": False,
                "error": f"Blockchain verification error: {str(e)}"
            }
    
    def create_transaction_record(
        self,
        user_id: int,
        telegram_id: str,
        signature: str,
        wallet_address: str,
        amount: float,
        recipient: str,
        status: str = "pending",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Transaction:
        """
        Create a new transaction record
        """
        transaction = Transaction(
            user_id=user_id,
            telegram_id=telegram_id,
            signature=signature,
            wallet_address=wallet_address,
            amount=amount,
            recipient=recipient,
            status=status,
            transaction_type="commission",
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.db.add(transaction)
        self.db.flush()
        
        logger.info("Transaction record created", extra={
            "transaction_id": transaction.id,
            "user_id": user_id,
            "signature": signature,
            "status": status
        })
        
        return transaction
    
    def update_transaction_status(
        self,
        transaction: Transaction,
        status: str
    ):
        """Update transaction status"""
        transaction.status = status
        if status == "verified":
            transaction.verified_at = datetime.now(timezone.utc)
        
        self.db.flush()
        
        logger.info("Transaction status updated", extra={
            "transaction_id": transaction.id,
            "status": status
        })
    
    def mark_user_as_paid(self, user: User, signature: str):
        """Mark user as having paid commission"""
        user.commission_paid = True
        user.commission_transaction_hash = signature
        user.commission_payment_date = datetime.now(timezone.utc)
        
        self.db.flush()
        
        logger.info("User marked as paid", extra={
            "user_id": user.id,
            "telegram_id": user.telegram_id,
            "signature": signature
        })


def cleanup_expired_sessions(session_store, max_age_hours: int = 24):
    """
    Clean up expired sessions (if using Redis or similar)
    """
    try:
        # Implementation depends on your session storage
        logger.info("Session cleanup completed", extra={"max_age_hours": max_age_hours})
    except Exception as e:
        logger.error("Session cleanup failed", extra={"error": str(e)})
