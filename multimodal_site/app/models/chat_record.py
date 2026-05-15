from sqlalchemy import Column, Integer, String, Text,DateTime
from app.database import Base
from datetime import datetime

class ChatRecord(Base):
    __tablename__ = "chat_records"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    model = Column(String(100), nullable=True)
    content = Column(Text, nullable=False)
    role = Column(String(50), nullable=False)
    created_at = Column(DateTime,default=datetime.utcnow ,nullable=False,index=True)  # 存储时间戳