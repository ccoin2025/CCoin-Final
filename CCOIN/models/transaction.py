from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from CCOIN.database import Base

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    signature = Column(String, unique=True, nullable=False, index=True)
    wallet_address = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    recipient = Column(String, nullable=False)
    status = Column(String, default="pending", index=True)  # pending, verified, failed
    transaction_type = Column(String, default="commission", index=True)  # commission, airdrop, etc.
    
    # Security fields
    telegram_id = Column(String, nullable=False, index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationship
    user = relationship("User", back_populates="transactions")
    
    __table_args__ = (
        Index('idx_transaction_user_status', 'user_id', 'status'),
        Index('idx_transaction_telegram_signature', 'telegram_id', 'signature'),
        UniqueConstraint('signature', name='uq_transaction_signature'),
    )
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, user_id={self.user_id}, signature={self.signature[:8]}..., status={self.status})>"
