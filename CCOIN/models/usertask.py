from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from CCOIN.database import Base

class UserTask(Base):
    __tablename__ = "user_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    platform = Column(String, nullable=False)  # platform name (telegram, instagram, x, youtube)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)

    # New fields for attempt tracking
    attempt_count = Column(Integer, default=0)  # تعداد دفعات کلیک روی دکمه
    last_attempt_at = Column(DateTime, nullable=True)  # آخرین زمان کلیک

    # Relationships
    user = relationship("User", back_populates="tasks")

    def __repr__(self):
        return f"<UserTask(user_id={self.user_id}, platform={self.platform}, completed={self.completed}, attempts={self.attempt_count})>"
