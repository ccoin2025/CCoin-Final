from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from CCOIN.database import Base

class UserTask(Base):
    __tablename__ = "usertasks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    platform = Column(String)  # telegram, instagram, x, youtube
    completed = Column(Boolean, default=False)

    user = relationship("User", back_populates="tasks")