from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.llm_gateway import list_available_models
from app.core.memory_manager import memory_manager
from app.database import get_db
from app.models.chat_record import ChatRecord
from app.models.agent_event import AgentEvent
from app.models.memory_item import MemoryItem
from app.models.session_state import SessionState
from app.schemas.chat import ChatRequest, ChatRecordResponse, ChatSessionSummary, MemoryRecordResponse, AgentEventResponse, ModelInfo, model_info_from_profile
from app.services.chat import stream_chat_reply

# 注册路由，所有接口以 /api/chat 开头
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/models", response_model=list[ModelInfo])
def get_models():
    return [model_info_from_profile(profile) for profile in list_available_models()]


@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    return {
        "sessions": db.query(func.count(func.distinct(ChatRecord.session_id))).scalar() or 0,
        "messages": db.query(func.count(ChatRecord.id)).scalar() or 0,
        "memories": db.query(func.count(MemoryItem.id)).scalar() or 0,
        "events": db.query(func.count(AgentEvent.id)).scalar() or 0,
        "states": db.query(func.count(SessionState.id)).scalar() or 0,
    }


# ── POST /api/chat/stream ─────────────────────────────────
# 流式对话接口：边生成边返回，不等模型全部回答完才响应
@router.post("/stream")
def chat_api_stream(chat_request: ChatRequest):
    return StreamingResponse(
        stream_chat_reply(chat_request, user_id=settings.DEFAULT_USER_ID),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",       # 禁止缓存，保证实时性
            "X-Accel-Buffering": "no"          # 关闭 Nginx 缓冲，避免内容积压
        }
    )


# ── GET /api/chat/history?session_id=xxx ─────────────────
# 获取某个会话的完整聊天记录，按时间正序排列
@router.get("/history", response_model=list[ChatRecordResponse])
def get_chat_history(
    session_id: str = Query(...),       # ... 表示必填参数
    db: Session = Depends(get_db)
):
    records = (
        db.query(ChatRecord)
        .filter(ChatRecord.session_id == session_id)
        .order_by(ChatRecord.created_at.asc(), ChatRecord.id.asc())  # 时间+id双排序，防止同秒乱序
        .all()
    )
    return records


# ── GET /api/chat/sessions ───────────────────────────────
# 获取所有会话列表，每个会话只显示最新一条消息作为预览
@router.get("/sessions", response_model=list[ChatSessionSummary])
def get_chat_sessions(db: Session = Depends(get_db)):

    # 子查询：按 session_id 分组，找出每个会话的最新消息 id 和消息总数
    latest_subquery = (
        db.query(
            ChatRecord.session_id.label("session_id"),
            func.max(ChatRecord.id).label("latest_id"),       # 最新一条消息的 id
            func.count(ChatRecord.id).label("message_count")  # 该会话共有几条消息
        )
        .group_by(ChatRecord.session_id)
        .subquery()
    )

    # 主查询：用子查询结果 JOIN 原表，拿到最新消息的具体内容
    rows = (
        db.query(
            latest_subquery.c.session_id,
            ChatRecord.model,
            ChatRecord.content,
            latest_subquery.c.message_count,
            ChatRecord.created_at
        )
        .join(ChatRecord, ChatRecord.id == latest_subquery.c.latest_id)
        .order_by(ChatRecord.created_at.desc(), ChatRecord.id.desc())  # 最新会话排最前
        .all()
    )

    # 组装返回结构，内容超过 80 字截断加省略号
    return [
        ChatSessionSummary(
            session_id=row.session_id,
            model=row.model,
            preview=(row.content[:80] + "...") if len(row.content) > 80 else row.content,
            message_count=row.message_count
        )
        for row in rows
    ]


@router.get("/memories", response_model=list[MemoryRecordResponse])
def search_memories(
    query: str = Query(...),
    session_id: str | None = Query(None),
    limit: int = Query(settings.MEMORY_SEARCH_LIMIT, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return memory_manager.search_memories(
        db,
        query=query,
        session_id=session_id,
        limit=limit,
    )


@router.get("/state")
def get_session_state(
    session_id: str = Query(...),
    db: Session = Depends(get_db),
):
    state = db.query(SessionState).filter(SessionState.session_id == session_id).first()
    if not state:
        return None

    return {
        "session_id": state.session_id,
        "user_id": state.user_id,
        "running_summary": state.running_summary,
        "current_goal": state.current_goal,
        "task_state_json": state.task_state_json,
        "last_turn_count": state.last_turn_count,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
    }


# ── DELETE /api/chat/session?session_id=xxx ──────────────
# 删除某个会话的全部聊天记录
@router.delete("/session")
def delete_chat_session(
    session_id: str = Query(...),
    db: Session = Depends(get_db)
):
    deleted_count = (
        db.query(ChatRecord)
        .filter(ChatRecord.session_id == session_id)
        .delete()  # 返回实际删除的行数
    )
    db.query(MemoryItem).filter(MemoryItem.session_id == session_id).delete()
    db.query(SessionState).filter(SessionState.session_id == session_id).delete()
    db.commit()
    return {
        "message": f"Session {session_id} 已删除",
        "deleted_count": deleted_count  # 告诉调用方删了几条
    }


@router.get("/events", response_model=list[AgentEventResponse])
def get_agent_events(
    session_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(AgentEvent)
    if session_id:
        query = query.filter(AgentEvent.session_id == session_id)

    rows = query.order_by(AgentEvent.created_at.desc(), AgentEvent.id.desc()).limit(limit).all()
    return rows