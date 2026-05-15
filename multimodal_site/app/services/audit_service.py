from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.agent_event import AgentEvent


def record_agent_event(
    db: Session,
    *,
    session_id: str,
    user_id: str,
    event_type: str,
    model: str | None = None,
    request_chars: int = 0,
    response_chars: int = 0,
    duration_ms: int = 0,
    success: bool = True,
    error_message: str = "",
    metadata: dict | None = None,
) -> AgentEvent:
    event = AgentEvent(
        session_id=session_id,
        user_id=user_id,
        event_type=event_type,
        model=model,
        request_chars=request_chars,
        response_chars=response_chars,
        duration_ms=duration_ms,
        success=success,
        error_message=error_message,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event