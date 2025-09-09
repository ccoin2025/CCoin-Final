from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from CCOIN.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    tokens = Column(Integer, default=0)
    referral_code = Column(String, unique=True)
    referred_by = Column(Integer, ForeignKey("users.id"))
    wallet_address = Column(String, unique=True, nullable=True)
    first_login = Column(Boolean, default=True)  # اضافه شده
    commission_paid = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    tasks = relationship("UserTask", back_populates="user")
    airdrop = relationship("Airdrop", back_populates="user", uselist=False)
    referrals = relationship("User", foreign_keys=[referred_by])
    commission_paid = Column(Boolean, default=False)
    commission_payment_date = Column(DateTime, nullable=True)
    commission_transaction_hash = Column(String, nullable=True)
