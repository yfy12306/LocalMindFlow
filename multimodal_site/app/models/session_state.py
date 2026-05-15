from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class SessionState(Base):
    """对话会话状态表，持久化保存每个会话的上下文"""

    __tablename__ = "session_state"  # 数据库表名

    # ── 主键 & 标识 ──────────────────────────────
    id = Column(Integer, primary_key=True, index=True)                        # 自增主键
    session_id = Column(String, unique=True, index=True, nullable=False)      # 会话唯一ID，不可重复
    user_id = Column(String, index=True, nullable=False, default="local-user")# 所属用户，默认本地用户

    # ── 对话上下文 ───────────────────────────────
    running_summary = Column(Text, default="")      # 滚动摘要：对话历史过长时压缩存这里
    current_goal = Column(Text, default="")         # 当前对话目标 / 用户意图
    task_state_json = Column(Text, default="{}")    # 任务状态，JSON 字符串格式存储
    last_turn_count = Column(Integer, default=0)    # 上次处理到第几轮对话

    # ── 时间戳 ───────────────────────────────────
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()   # 创建时由数据库自动填入当前时间
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),  # 创建时自动填入
        onupdate=func.now()         # 每次记录被修改时自动刷新为当前时间
    )