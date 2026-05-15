from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class MemoryItem(Base):
    __tablename__ = "memory_items"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True, default="local-user")
    role = Column(String(50), nullable=False)
    memory_type = Column(String(50), nullable=False, default="turn")
    content = Column(Text, nullable=False)
    tags = Column(Text, nullable=False, default="[]")
    importance = Column(Float, nullable=False, default=0.5)
    source_model = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)