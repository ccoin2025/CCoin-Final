from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from CCOIN.database import Base

class UserTask(Base):
    __tablename__ = "user_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    platform = Column(String, nullable=False) 
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)

    attempt_count = Column(Integer, default=0)  
    last_attempt_at = Column(DateTime, nullable=True) 
    
    user = relationship("User", back_populates="tasks")

    def __repr__(self):
        return f"<UserTask(user_id={self.user_id}, platform={self.platform}, completed={self.completed}, attempts={self.attempt_count})>"
