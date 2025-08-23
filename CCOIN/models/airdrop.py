from sqlalchemy import Column, Integer, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from ..database import Base

class Airdrop(Base):
    __tablename__ = "airdrops"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    eligible = Column(Boolean, default=False)
    amount = Column(Float, default=0.0)

    user = relationship("User", back_populates="airdrop")