from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.backend_tasks import build_session_reflection_messages, resolve_backend_task_model
from app.core.llm_gateway import chat_completion
from app.core.memory_manager import memory_manager
from app.models.session_state import SessionState


def _load_task_state(state: SessionState) -> dict:
    try:
        payload = json.loads(state.task_state_json or "{}")
    except json.JSONDecodeError:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _truncate(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _recent_history_excerpt(history: list[dict] | None, limit: int = 4) -> str:
    if not history:
        return ""

    items = history[-limit:]
    rendered: list[str] = []
    for item in items:
        role = item.get("role", "user")
        content = (item.get("content") or "").strip().replace("\n", " ")
        if content:
            rendered.append(f"{role}: {content[:140]}")
    return " | ".join(rendered)


def _infer_goal(user_message: str, current_goal: str = "") -> str:
    if not user_message.strip():
        return current_goal

    task_markers = ["帮我", "请", "实现", "改造", "设计", "总结", "生成", "优化", "排查", "分析"]
    if any(marker in user_message for marker in task_markers):
        return _truncate(user_message, 220)

    return current_goal or _truncate(user_message, 180)


def _clean_summary_text(summary: str) -> str:
    value = (summary or "").strip()
    if not value:
        return ""

    if any(phrase in value for phrase in ["我是一个大型语言模型", "由 Google 训练", "我记住了你的名字", "请提供更多上下文"]):
        return ""

    return value


def get_or_create_session_state(
    db: Session,
    session_id: str,
    user_id: str = settings.DEFAULT_USER_ID,
) -> SessionState:
    state = db.query(SessionState).filter(SessionState.session_id == session_id).first()
    if state:
        return state

    state = SessionState(
        session_id=session_id,
        user_id=user_id,
        running_summary="",
        current_goal="",
        task_state_json=json.dumps({}, ensure_ascii=False),
        last_turn_count=0,
    )

    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def update_session_state(
    db: Session,
    session_id: str,
    running_summary: str | None = None,
    current_goal: str | None = None,
    task_state: dict | None = None,
    last_turn_count: int | None = None,
    user_id: str = settings.DEFAULT_USER_ID,
) -> SessionState:
    state = get_or_create_session_state(db, session_id, user_id=user_id)

    if running_summary is not None:
        state.running_summary = running_summary

    if current_goal is not None:
        state.current_goal = current_goal

    if task_state is not None:
        state.task_state_json = json.dumps(task_state, ensure_ascii=False)

    if last_turn_count is not None:
        state.last_turn_count = last_turn_count

    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def reflect_session_state(
    *,
    session_state: SessionState,
    user_message: str,
    assistant_message: str,
    history: list[dict] | None = None,
    memory_hits: list[dict] | None = None,
    model: str = "",
) -> dict:
    if not settings.ENABLE_REFLECTION:
        return {}

    if session_state.last_turn_count + 1 < settings.SUMMARY_TRIGGER_TURNS:
        return {}

    reflection_model = resolve_backend_task_model(settings.REFLECTION_MODEL or model)
    prompt = build_session_reflection_messages(
        running_summary=session_state.running_summary,
        current_goal=session_state.current_goal,
        history=history,
        user_message=user_message,
        assistant_message=assistant_message,
        memory_hits=memory_hits,
    )

    try:
        response_text = chat_completion(prompt, reflection_model)
    except Exception:
        return {}

    content = response_text.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE | re.DOTALL).strip()

    if "{" in content and "}" in content:
        content = content[content.find("{") : content.rfind("}") + 1]

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return {}

    return payload if isinstance(payload, dict) else {}


def update_after_turn(
    db: Session,
    *,
    session_id: str,
    user_message: str,
    assistant_message: str,
    model: str,
    history: list[dict] | None = None,
    memory_hits: list[dict] | None = None,
    selected_skills: list[dict] | None = None,
    attached_files: list[dict] | None = None,
    user_id: str = settings.DEFAULT_USER_ID,
) -> SessionState:
    state = get_or_create_session_state(db, session_id, user_id=user_id)
    task_state = _load_task_state(state)

    task_state.update(
        {
            "last_model": model,
            "last_user_message": _truncate(user_message, 240),
            "last_assistant_preview": _truncate(assistant_message, 240),
            "memory_hits": [hit.get("content", "")[:160] for hit in (memory_hits or [])[: settings.MEMORY_CONTEXT_LIMIT]],
            "active_skills": [item.get("name") for item in (selected_skills or [])],
            "attached_files": [item.get("path") for item in (attached_files or []) if item.get("path")],
        }
    )

    reflected = reflect_session_state(
        session_state=state,
        user_message=user_message,
        assistant_message=assistant_message,
        history=history,
        memory_hits=memory_hits,
        model=model,
    )

    running_summary = reflected.get("running_summary")
    current_goal = reflected.get("current_goal")

    if not running_summary:
        recent_excerpt = _recent_history_excerpt(history)
        summary_parts = [state.running_summary.strip()]
        if recent_excerpt:
            summary_parts.append(f"最近对话: {recent_excerpt}")
        if assistant_message.strip() and not any(phrase in assistant_message for phrase in ["我是一个大型语言模型", "由 Google 训练", "我记住了你的名字"]):
            summary_parts.append(f"最新回复: {_truncate(assistant_message, 220)}")
        if memory_hits:
            memory_excerpt = " | ".join(_truncate(item.get("content", ""), 120) for item in memory_hits[: settings.MEMORY_CONTEXT_LIMIT])
            if memory_excerpt:
                summary_parts.append(f"相关记忆: {memory_excerpt}")
        running_summary = _truncate("。".join(part for part in summary_parts if part), settings.MAX_SUMMARY_CHARS)

    if not current_goal:
        current_goal = _infer_goal(user_message, state.current_goal)

    running_summary = _clean_summary_text(running_summary)

    if running_summary or current_goal:
        memory_manager.add_candidate_memory(
            db,
            session_id=session_id,
            user_id=user_id,
            role="system",
            content=_truncate(f"会话摘要: {running_summary or '无'} | 当前目标: {current_goal or '无'}", 480),
            memory_type="summary",
            tags=["summary", "session-state"],
            importance=0.7,
            source_model=model,
        )

    if isinstance(reflected.get("task_state"), dict):
        task_state.update(reflected["task_state"])

    task_state.update(
        {
            "last_reflection": reflected,
            "recent_history": _recent_history_excerpt(history, limit=6),
            "memory_hits_count": len(memory_hits or []),
        }
    )

    return update_session_state(
        db,
        session_id,
        running_summary=running_summary,
        current_goal=current_goal,
        task_state=task_state,
        last_turn_count=state.last_turn_count + 1,
        user_id=user_id,
    )