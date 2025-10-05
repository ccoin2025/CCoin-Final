from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from CCOIN.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, index=True)  # جدید: index اضافه شد
    first_name = Column(String)
    last_name = Column(String)
    tokens = Column(Integer, default=0, index=True)  # جدید: index برای sorting
    referral_code = Column(String, unique=True, index=True)
    referred_by = Column(Integer, ForeignKey("users.id"), index=True)  # جدید: index
    wallet_address = Column(String, unique=True, nullable=True, index=True)  # جدید: index
    first_login = Column(Boolean, default=True)
    
    # Wallet connection tracking (جدید)
    wallet_connected = Column(Boolean, default=False)
    wallet_connection_date = Column(DateTime(timezone=True), nullable=True)
    
    # Commission tracking
    commission_paid = Column(Boolean, default=False, index=True)  # جدید: index
    commission_payment_date = Column(DateTime(timezone=True), nullable=True)
    commission_transaction_hash = Column(String, nullable=True)
    
    # Timestamps با timezone
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    tasks = relationship("UserTask", back_populates="user")
    airdrop = relationship("Airdrop", back_populates="user", uselist=False)
    referrals = relationship("User", foreign_keys=[referred_by])
    
    # Composite indexes برای query های پرتکرار
    __table_args__ = (
        Index('idx_user_tokens_created', 'tokens', 'created_at'),  # برای leaderboard
        Index('idx_user_referral_commission', 'referred_by', 'commission_paid'),  # برای referral queries
    )
    
    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username={self.username})>"
