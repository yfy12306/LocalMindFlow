from __future__ import annotations

import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent_event import AgentEvent
from app.models.chat_record import ChatRecord
from app.models.memory_item import MemoryItem
from app.models.session_state import SessionState
from app.schemas.platform import (
    ArtifactCard,
    DashboardMetric,
    DashboardPane,
    EventPanelItem,
    MemoryPanelItem,
    MessageRecord,
    OverviewResponse,
    SessionDetailResponse,
    SessionListItem,
    SessionStatePanel,
)
from app.services.artifact_service import build_run_artifacts


def _truncate(value: str | None, limit: int = 120) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _safe_tags(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass
    return []


def list_sessions(db: Session) -> list[SessionListItem]:
    latest_subquery = (
        db.query(
            ChatRecord.session_id.label("session_id"),
            func.max(ChatRecord.id).label("latest_id"),
            func.count(ChatRecord.id).label("message_count"),
        )
        .group_by(ChatRecord.session_id)
        .subquery()
    )

    rows = (
        db.query(
            latest_subquery.c.session_id,
            latest_subquery.c.message_count,
            ChatRecord.content,
            ChatRecord.model,
            ChatRecord.created_at,
        )
        .join(ChatRecord, ChatRecord.id == latest_subquery.c.latest_id)
        .order_by(ChatRecord.created_at.desc(), ChatRecord.id.desc())
        .all()
    )

    items: list[SessionListItem] = []
    for row in rows:
        preview = _truncate(row.content, 110) or "Empty session"
        title = _truncate(row.content, 42) or "Untitled run"
        items.append(
            SessionListItem(
                session_id=row.session_id,
                title=title,
                preview=preview,
                model=row.model,
                last_active_at=row.created_at,
                run_status="idle",
                message_count=row.message_count or 0,
            )
        )
    return items


def get_session_detail(db: Session, session_id: str) -> SessionDetailResponse:
    records = (
        db.query(ChatRecord)
        .filter(ChatRecord.session_id == session_id)
        .order_by(ChatRecord.created_at.asc(), ChatRecord.id.asc())
        .all()
    )
    state = db.query(SessionState).filter(SessionState.session_id == session_id).first()
    memory_rows = (
        db.query(MemoryItem)
        .filter(MemoryItem.session_id == session_id)
        .order_by(MemoryItem.created_at.desc(), MemoryItem.id.desc())
        .limit(8)
        .all()
    )
    event_rows = (
        db.query(AgentEvent)
        .filter(AgentEvent.session_id == session_id)
        .order_by(AgentEvent.created_at.desc(), AgentEvent.id.desc())
        .limit(8)
        .all()
    )

    task_state: dict = {}
    if state and state.task_state_json:
        try:
            parsed = json.loads(state.task_state_json)
            if isinstance(parsed, dict):
                task_state = parsed
        except json.JSONDecodeError:
            task_state = {}

    active_skills = [str(item) for item in task_state.get("active_skills", []) if item]
    attached_context = [str(item) for item in task_state.get("attached_files", []) if item]
    artifacts: list[ArtifactCard] = build_run_artifacts(skills=active_skills, context_files=attached_context)

    title_source = next((item.content for item in records if item.role == "user" and item.content.strip()), "")
    last_model = next((item.model for item in reversed(records) if item.model), None)

    return SessionDetailResponse(
        session_id=session_id,
        title=_truncate(title_source, 42) or "Untitled run",
        model=last_model,
        run_status="idle",
        message_count=len(records),
        messages=[MessageRecord.model_validate(item) for item in records],
        memories=[
            MemoryPanelItem(
                id=item.id,
                memory_type=item.memory_type,
                content=item.content,
                tags=_safe_tags(item.tags),
                importance=item.importance,
                created_at=item.created_at,
            )
            for item in memory_rows
        ],
        recent_events=[EventPanelItem.model_validate(item) for item in event_rows],
        attached_context=attached_context,
        active_skills=active_skills,
        state=SessionStatePanel(
            running_summary=state.running_summary if state else "",
            current_goal=state.current_goal if state else "",
            task_state_json=state.task_state_json if state else "{}",
            updated_at=state.updated_at if state else None,
        ),
        artifacts=artifacts,
    )


def get_overview(db: Session) -> OverviewResponse:
    sessions = db.query(func.count(func.distinct(ChatRecord.session_id))).scalar() or 0
    messages = db.query(func.count(ChatRecord.id)).scalar() or 0
    memories = db.query(func.count(MemoryItem.id)).scalar() or 0
    events = db.query(func.count(AgentEvent.id)).scalar() or 0

    latest_event = db.query(AgentEvent).order_by(AgentEvent.created_at.desc(), AgentEvent.id.desc()).first()
    latest_session = db.query(ChatRecord).order_by(ChatRecord.created_at.desc(), ChatRecord.id.desc()).first()

    return OverviewResponse(
        metrics=[
            DashboardMetric(label="会话数", value=str(sessions), detail="已持久化的本地线程"),
            DashboardMetric(label="消息数", value=str(messages), detail="累计保存的对话轮次"),
            DashboardMetric(label="记忆数", value=str(memories), detail="可供召回的长期记忆"),
            DashboardMetric(label="事件数", value=str(events), detail="运行审计与时序记录"),
        ],
        panes=[
            DashboardPane(
                title="当前状态",
                body="前端已经升级为本地智能体控制台，后端能力保持模块化，便于后续继续补强编排与多模态。",
                tone="accent",
            ),
            DashboardPane(
                title="最近活动",
                body=_truncate(latest_session.content if latest_session else "暂时还没有运行记录。", 180),
                tone="neutral",
            ),
            DashboardPane(
                title="运行备注",
                body=_truncate(latest_event.event_type if latest_event else "暂时还没有智能体事件。", 180),
                tone="muted",
            ),
        ],
    )
