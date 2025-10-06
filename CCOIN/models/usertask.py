from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from CCOIN.database import Base

class UserTask(Base):
    __tablename__ = "user_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    task_id = Column(Integer, ForeignKey("tasks.id"))
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    
    # New fields for attempt tracking
    attempt_count = Column(Integer, default=0)
    last_attempt_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="tasks")
    task = relationship("Task")
