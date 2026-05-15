from __future__ import annotations

from collections.abc import Iterator
from time import perf_counter

from app.core.config import settings
from app.core.skill_manager import load_selected_skills
from app.core.memory_manager import memory_manager
from app.core.workspace_tools import read_files
from app.database import SessionLocal
from app.graphs.chat_graph import chat_graph
from app.models.chat_record import ChatRecord
from app.schemas.chat import ChatRequest
from app.services.audit_service import record_agent_event
from app.services.session_state_service import get_or_create_session_state, update_after_turn


def _extract_token_from_chunk(chunk):
    if isinstance(chunk, dict):
        if chunk.get("type") == "token":
            return chunk.get("content", "")

        if chunk.get("type") == "custom":
            data = chunk.get("data", {})
            if isinstance(data, dict) and data.get("type") == "token":
                return data.get("content", "")

    return ""


def _normalize_messages(messages) -> list[dict]:
    normalized: list[dict] = []
    for item in messages or []:
        if hasattr(item, "role") and hasattr(item, "content"):
            normalized.append({"role": item.role, "content": item.content})
        else:
            normalized.append({"role": item.get("role", "user"), "content": item.get("content", "")})
    return normalized


def stream_generate_reply(
    message: str,
    model: str,
    messages=None,
    skills=None,
    file_contexts=None,
    session_id: str = "",
    user_id: str = settings.DEFAULT_USER_ID,
    running_summary: str = "",
    current_goal: str = "",
    memories: list[dict] | None = None,
):
    history = _normalize_messages(messages)
    selected_skills = skills or []
    selected_file_contexts = file_contexts or []

    for chunk in chat_graph.stream(
        {
            "session_id": session_id or "temp-session",
            "user_id": user_id,
            "model": model,
            "message": message,
            "history": history,
            "memories": memories or [],
            "skills": selected_skills,
            "file_contexts": selected_file_contexts,
            "running_summary": running_summary,
            "current_goal": current_goal,
            "llm_messages": [],
            "answer": "",
        },
        stream_mode="custom",
    ):
        piece = _extract_token_from_chunk(chunk)
        if piece:
            yield piece


def _persist_chat_turn(
    db,
    *,
    chat_request: ChatRequest,
    full_answer: str,
    memory_hits: list[dict],
    selected_skills: list[dict],
    file_contexts: list[dict],
    user_id: str,
):
    db.add(
        ChatRecord(
            session_id=chat_request.session_id,
            role="user",
            content=chat_request.message,
            model=chat_request.model,
        )
    )
    if full_answer:
        db.add(
            ChatRecord(
                session_id=chat_request.session_id,
                role="assistant",
                content=full_answer,
                model=chat_request.model,
            )
        )
    db.commit()

    memory_manager.record_turn(
        db,
        session_id=chat_request.session_id,
        user_id=user_id,
        model=chat_request.model,
        user_message=chat_request.message,
        assistant_message=full_answer,
        tags=["chat", chat_request.model],
    )

    update_after_turn(
        db,
        session_id=chat_request.session_id,
        user_message=chat_request.message,
        assistant_message=full_answer,
        model=chat_request.model,
        history=_normalize_messages(chat_request.messages),
        memory_hits=memory_hits,
        selected_skills=selected_skills,
        attached_files=file_contexts,
        user_id=user_id,
    )


def stream_chat_reply(chat_request: ChatRequest, user_id: str = settings.DEFAULT_USER_ID) -> Iterator[str]:
    db = SessionLocal()
    start_time = perf_counter()

    try:
        session_state = get_or_create_session_state(db, chat_request.session_id, user_id=user_id)
        history = _normalize_messages(chat_request.messages)
        selected_skills = load_selected_skills(chat_request.skill_names)
        file_contexts = read_files(chat_request.context_files)
        memory_hits = memory_manager.search_memories(
            db,
            query=chat_request.message,
            session_id=chat_request.session_id,
            user_id=user_id,
            limit=settings.MEMORY_SEARCH_LIMIT,
        )
    except Exception:
        db.close()
        raise

    def generator():
        chunks: list[str] = []
        success = True
        error_message = ""
        try:
            for piece in stream_generate_reply(
                message=chat_request.message,
                model=chat_request.model,
                messages=history,
                skills=selected_skills,
                file_contexts=file_contexts,
                session_id=chat_request.session_id,
                user_id=user_id,
                running_summary=session_state.running_summary,
                current_goal=session_state.current_goal,
                memories=memory_hits,
            ):
                chunks.append(piece)
                yield piece
        except Exception as exc:
            success = False
            error_message = str(exc)
            raise
        finally:
            full_answer = "".join(chunks).strip()
            duration_ms = int((perf_counter() - start_time) * 1000)
            try:
                _persist_chat_turn(
                    db,
                    chat_request=chat_request,
                    full_answer=full_answer,
                    memory_hits=memory_hits,
                    selected_skills=selected_skills,
                    file_contexts=file_contexts,
                    user_id=user_id,
                )
                record_agent_event(
                    db,
                    session_id=chat_request.session_id,
                    user_id=user_id,
                    event_type="chat_turn",
                    model=chat_request.model,
                    request_chars=len(chat_request.message or ""),
                    response_chars=len(full_answer),
                    duration_ms=duration_ms,
                    success=success,
                    error_message=error_message,
                    metadata={
                        "memory_hits": len(memory_hits),
                        "skills": [item.get("name") for item in selected_skills],
                        "files": [item.get("path") for item in file_contexts],
                        "summary_present": bool(session_state.running_summary),
                        "goal_present": bool(session_state.current_goal),
                    },
                )
            finally:
                db.close()

    return generator()