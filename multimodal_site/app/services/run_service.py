from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from uuid import uuid4

from app.core.config import settings
from app.core.memory_manager import memory_manager
from app.core.skill_manager import load_selected_skills
from app.core.workspace_tools import read_files
from app.database import SessionLocal
from app.models.chat_record import ChatRecord
from app.schemas.platform import ArtifactCard, RunCreateRequest, RunStreamEvent
from app.services.artifact_service import build_run_artifacts
from app.services.attachment_service import build_attachment_artifacts, normalize_attachments
from app.services.audit_service import record_agent_event
from app.services.chat import stream_generate_reply
from app.services.session_state_service import get_or_create_session_state, update_after_turn


@dataclass
class PendingRun:
    run_id: str
    session_id: str
    request: RunCreateRequest
    created_at: datetime
    status: str = "queued"


_PENDING_RUNS: dict[str, PendingRun] = {}


def _load_session_history(db, session_id: str) -> list[dict]:
    rows = (
        db.query(ChatRecord)
        .filter(ChatRecord.session_id == session_id)
        .order_by(ChatRecord.created_at.asc(), ChatRecord.id.asc())
        .all()
    )
    return [
        {"role": row.role, "content": row.content, "model": row.model}
        for row in rows
        if row.content
    ]


def create_run(request: RunCreateRequest) -> PendingRun:
    run_id = uuid4().hex
    session_id = request.session_id or uuid4().hex
    pending = PendingRun(
        run_id=run_id,
        session_id=session_id,
        request=request.model_copy(update={"session_id": session_id}),
        created_at=datetime.utcnow(),
        status="queued",
    )
    _PENDING_RUNS[run_id] = pending
    return pending


def get_pending_run(run_id: str) -> PendingRun | None:
    return _PENDING_RUNS.get(run_id)


def pop_pending_run(run_id: str) -> PendingRun | None:
    return _PENDING_RUNS.pop(run_id, None)


def _json_line(event: RunStreamEvent) -> str:
    return event.model_dump_json() + "\n"


def _event(
    *,
    event_type: str,
    run_id: str,
    session_id: str,
    delta: str = "",
    status: str | None = None,
    message: str = "",
    artifact: ArtifactCard | None = None,
    meta: dict | None = None,
) -> str:
    payload = RunStreamEvent(
        type=event_type,
        run_id=run_id,
        session_id=session_id,
        timestamp=datetime.utcnow(),
        delta=delta,
        status=status,
        message=message,
        artifact=artifact,
        meta=meta or {},
    )
    return _json_line(payload)


def stream_run(run_id: str) -> Iterator[str]:
    pending = pop_pending_run(run_id)
    if not pending:
        yield _event(
            event_type="error",
            run_id=run_id,
            session_id="unknown",
            status="missing",
            message="Run not found or already consumed.",
        )
        return

    request = pending.request
    db = SessionLocal()
    start_time = perf_counter()
    normalized_attachments = normalize_attachments(request.attachments)

    try:
        session_id = request.session_id or pending.session_id
        session_state = get_or_create_session_state(db, session_id, user_id=settings.DEFAULT_USER_ID)
        history = _load_session_history(db, session_id)
        selected_skills = load_selected_skills(request.skill_names)
        file_contexts = read_files(request.context_files)
        memory_hits = memory_manager.search_memories(
            db,
            query=request.input.content,
            session_id=session_id,
            user_id=settings.DEFAULT_USER_ID,
            limit=settings.MEMORY_SEARCH_LIMIT,
        )
    except Exception as exc:
        db.close()
        yield _event(
            event_type="error",
            run_id=run_id,
            session_id=request.session_id or pending.session_id,
            status="failed",
            message=str(exc),
        )
        return

    def generator() -> Iterator[str]:
        full_answer = ""
        success = True
        error_message = ""
        session_id = request.session_id or pending.session_id
        artifacts = build_attachment_artifacts(normalized_attachments) + build_run_artifacts(
            skills=request.skill_names,
            context_files=request.context_files,
        )

        yield _event(
            event_type="run_status",
            run_id=run_id,
            session_id=session_id,
            status="started",
            message="Run started",
            meta={"agent_mode": request.agent_mode, "model": request.model},
        )

        for artifact in artifacts:
            yield _event(
                event_type="artifact",
                run_id=run_id,
                session_id=session_id,
                status="artifact",
                artifact=artifact,
                message=artifact.title,
            )

        if normalized_attachments:
            yield _event(
                event_type="tool_event",
                run_id=run_id,
                session_id=session_id,
                status="attachments-registered",
                message="Attachment shell registered",
                meta={"count": len(normalized_attachments)},
            )

        try:
            for piece in stream_generate_reply(
                message=request.input.content,
                model=request.model,
                messages=history,
                skills=selected_skills,
                file_contexts=file_contexts,
                session_id=session_id,
                user_id=settings.DEFAULT_USER_ID,
                running_summary=session_state.running_summary,
                current_goal=session_state.current_goal,
                memories=memory_hits,
            ):
                full_answer += piece
                yield _event(
                    event_type="message_delta",
                    run_id=run_id,
                    session_id=session_id,
                    delta=piece,
                    status="streaming",
                )
        except Exception as exc:
            success = False
            error_message = str(exc)
            yield _event(
                event_type="error",
                run_id=run_id,
                session_id=session_id,
                status="failed",
                message=error_message,
            )
        finally:
            duration_ms = int((perf_counter() - start_time) * 1000)
            try:
                db.add(
                    ChatRecord(
                        session_id=session_id,
                        role="user",
                        content=request.input.content,
                        model=request.model,
                    )
                )
                if full_answer.strip():
                    db.add(
                        ChatRecord(
                            session_id=session_id,
                            role="assistant",
                            content=full_answer.strip(),
                            model=request.model,
                        )
                    )
                db.commit()

                memory_manager.record_turn(
                    db,
                    session_id=session_id,
                    user_id=settings.DEFAULT_USER_ID,
                    model=request.model,
                    user_message=request.input.content,
                    assistant_message=full_answer.strip(),
                    tags=["run", request.model, request.agent_mode],
                )

                update_after_turn(
                    db,
                    session_id=session_id,
                    user_message=request.input.content,
                    assistant_message=full_answer.strip(),
                    model=request.model,
                    history=history
                    + [{"role": "user", "content": request.input.content}]
                    + (
                        [{"role": "assistant", "content": full_answer.strip()}]
                        if full_answer.strip()
                        else []
                    ),
                    memory_hits=memory_hits,
                    selected_skills=selected_skills,
                    attached_files=file_contexts,
                    user_id=settings.DEFAULT_USER_ID,
                )

                record_agent_event(
                    db,
                    session_id=session_id,
                    user_id=settings.DEFAULT_USER_ID,
                    event_type=f"run:{request.agent_mode}",
                    model=request.model,
                    request_chars=len(request.input.content or ""),
                    response_chars=len(full_answer),
                    duration_ms=duration_ms,
                    success=success,
                    error_message=error_message,
                    metadata={
                        "run_id": run_id,
                        "attachments": [item.model_dump() for item in normalized_attachments],
                        "skills": request.skill_names,
                        "files": request.context_files,
                    },
                )
            finally:
                db.close()

            yield _event(
                event_type="run_status",
                run_id=run_id,
                session_id=session_id,
                status="completed" if success else "failed",
                message="Run completed" if success else "Run failed",
                meta={"duration_ms": duration_ms},
            )

    yield from generator()
