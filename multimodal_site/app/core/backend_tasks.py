from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import settings


def _strip_code_fence(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.IGNORECASE | re.DOTALL).strip()
    return value


def parse_json_object(text: str) -> dict[str, Any]:
    value = _strip_code_fence(text)
    if "{" in value and "}" in value:
        value = value[value.find("{") : value.rfind("}") + 1]

    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_memory_extraction_messages(
    *,
    user_message: str,
    assistant_message: str,
    history: list[dict] | None = None,
    existing_memories: list[dict] | None = None,
) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "你是长期记忆提取器。只输出 JSON，不要输出解释。"
                "任务：判断当前对话是否值得存入长期记忆。优先提取稳定偏好、持续约束、项目目标、明确事实。"
                "不要把普通寒暄、重复自我介绍、模型模板话术当作记忆。"
                "如果没有值得保存的内容，store 必须是 false。"
                "输出字段：store, memory_type, content, importance, tags, reason。"
                "memory_type 只能是 preference / fact / goal / summary。"
                "content 要简洁、可复用、适合未来召回。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "user_message": user_message,
                    "assistant_message": assistant_message,
                    "history": history or [],
                    "existing_memories": existing_memories or [],
                },
                ensure_ascii=False,
            ),
        },
    ]


def build_session_reflection_messages(
    *,
    running_summary: str,
    current_goal: str,
    history: list[dict] | None = None,
    user_message: str,
    assistant_message: str,
    memory_hits: list[dict] | None = None,
) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "你是会话反思器，只返回 JSON，不要输出多余文本。"
                "JSON 字段包括 running_summary, current_goal, task_state, memory_facts, next_actions。"
                "running_summary 要简洁但保留任务上下文。"
                "不要写模板化自我介绍，不要复述无用寒暄。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "running_summary": running_summary,
                    "current_goal": current_goal,
                    "history": history or [],
                    "user_message": user_message,
                    "assistant_message": assistant_message,
                    "memory_hits": memory_hits or [],
                },
                ensure_ascii=False,
            ),
        },
    ]


def build_backend_task_prompt(task_name: str, payload: dict[str, Any]) -> list[dict]:
    if task_name == "memory_extraction":
        return build_memory_extraction_messages(
            user_message=payload.get("user_message", ""),
            assistant_message=payload.get("assistant_message", ""),
            history=payload.get("history", []),
            existing_memories=payload.get("existing_memories", []),
        )
    if task_name == "session_reflection":
        return build_session_reflection_messages(
            running_summary=payload.get("running_summary", ""),
            current_goal=payload.get("current_goal", ""),
            history=payload.get("history", []),
            user_message=payload.get("user_message", ""),
            assistant_message=payload.get("assistant_message", ""),
            memory_hits=payload.get("memory_hits", []),
        )

    return [
        {
            "role": "system",
            "content": f"你是后端任务执行器。请完成任务 {task_name}，只输出 JSON。",
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]


def resolve_backend_task_model(preferred: str | None = None) -> str:
    return (preferred or settings.BACKEND_TASK_MODEL or settings.MEMORY_EXTRACTION_MODEL or settings.REFLECTION_MODEL or settings.DEFAULT_MODEL).strip()
