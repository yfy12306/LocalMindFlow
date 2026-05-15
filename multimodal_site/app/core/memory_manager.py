from __future__ import annotations

import json
import re
from datetime import datetime
from hashlib import sha1

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.backend_tasks import build_memory_extraction_messages, resolve_backend_task_model, parse_json_object
from app.core.llm_gateway import chat_completion
from app.models.memory_item import MemoryItem


def _parse_tags(tags: list[str] | str | None) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        return [item.strip() for item in re.split(r"[，,;\s]+", tags) if item.strip()]
    return [item.strip() for item in tags if str(item).strip()]


def _tokenize(query: str) -> list[str]:
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", query.lower())
    return [token for token in tokens if len(token) > 1][:8]


def _serialize_item(item: MemoryItem) -> dict:
    try:
        tags = json.loads(item.tags or "[]")
    except json.JSONDecodeError:
        tags = []

    return {
        "id": item.id,
        "session_id": item.session_id,
        "user_id": item.user_id,
        "role": item.role,
        "memory_type": item.memory_type,
        "content": item.content,
        "tags": tags,
        "importance": item.importance,
        "source_model": item.source_model,
        "created_at": item.created_at.isoformat() if isinstance(item.created_at, datetime) else item.created_at,
    }


def _memory_key(*parts: str) -> str:
    payload = "|".join(part.strip().lower() for part in parts if part)
    return sha1(payload.encode("utf-8", errors="ignore")).hexdigest()


class MemoryManager:
    def _dedupe_exists(
        self,
        db: Session,
        *,
        session_id: str,
        user_id: str,
        role: str,
        memory_type: str,
        content: str,
    ) -> bool:
        content_key = _memory_key(session_id, user_id, role, memory_type, content)
        rows = (
            db.query(MemoryItem)
            .filter(MemoryItem.session_id == session_id)
            .filter(MemoryItem.user_id == user_id)
            .filter(MemoryItem.role == role)
            .filter(MemoryItem.memory_type == memory_type)
            .order_by(MemoryItem.id.desc())
            .limit(20)
            .all()
        )
        for row in rows:
            if _memory_key(row.session_id, row.user_id, row.role, row.memory_type, row.content) == content_key:
                return True
        return False

    def add_candidate_memory(
        self,
        db: Session,
        *,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        memory_type: str = "turn",
        tags: list[str] | str | None = None,
        importance: float = 0.5,
        source_model: str | None = None,
    ) -> MemoryItem:
        if self._dedupe_exists(
            db,
            session_id=session_id,
            user_id=user_id,
            role=role,
            memory_type=memory_type,
            content=content,
        ):
            existing = (
                db.query(MemoryItem)
                .filter(MemoryItem.session_id == session_id)
                .filter(MemoryItem.user_id == user_id)
                .filter(MemoryItem.role == role)
                .filter(MemoryItem.memory_type == memory_type)
                .filter(MemoryItem.content == content)
                .order_by(MemoryItem.id.desc())
                .first()
            )
            if existing:
                return existing

        item = MemoryItem(
            session_id=session_id,
            user_id=user_id,
            role=role,
            memory_type=memory_type,
            content=content,
            tags=json.dumps(_parse_tags(tags), ensure_ascii=False),
            importance=importance,
            source_model=source_model,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def record_turn(
        self,
        db: Session,
        *,
        session_id: str,
        user_id: str,
        model: str,
        user_message: str,
        assistant_message: str,
        tags: list[str] | str | None = None,
        importance: float = 0.6,
    ) -> list[MemoryItem]:
        written: list[MemoryItem] = []
        preference_markers = ["记住", "偏好", "以后", "请以后", "我喜欢", "不要", "always", "记一下"]
        preference_flag = any(marker in user_message for marker in preference_markers) or any(
            marker in assistant_message for marker in ["你更喜欢", "你偏好", "建议长期", "以后应当"]
        )

        if not settings.ENABLE_MEMORY_EXTRACTION:
            if preference_flag:
                written.append(
                    self.add_candidate_memory(
                        db,
                        session_id=session_id,
                        user_id=user_id,
                        role="system",
                        content=f"用户偏好/约束: {user_message[:180]} | 回复摘要: {assistant_message[:180]}",
                        memory_type="preference",
                        tags=["preference", "persistent"],
                        importance=0.95,
                        source_model=model,
                    )
                )
            return written

        existing_memories = self.search_memories(
            db,
            query=user_message,
            session_id=session_id,
            user_id=user_id,
            limit=3,
        )
        prompt = build_memory_extraction_messages(
            user_message=user_message,
            assistant_message=assistant_message,
            history=[],
            existing_memories=existing_memories,
        )
        extraction_model = resolve_backend_task_model(settings.MEMORY_EXTRACTION_MODEL or model)

        payload = {}
        try:
            payload = parse_json_object(chat_completion(prompt, extraction_model))
        except Exception:
            payload = {}

        if preference_flag:
            fallback_content = user_message.strip()[:180]
            if fallback_content.startswith("请记住"):
                fallback_content = fallback_content.replace("请记住", "", 1).strip()
            if fallback_content.startswith("记住"):
                fallback_content = fallback_content.replace("记住", "", 1).strip()
            if fallback_content.startswith("请"):
                fallback_content = fallback_content[1:].strip()
            payload = {
                "store": True,
                "memory_type": "preference",
                "content": f"用户偏好/约束: {fallback_content or user_message[:180]}",
                "importance": 0.95,
                "tags": ["preference", "persistent"],
                "reason": "explicit preference request",
            }

        if not payload or not payload.get("store"):
            return written

        content = str(payload.get("content", "")).strip()
        if not content:
            return written

        memory_type = str(payload.get("memory_type", "preference")).strip() or "preference"
        if memory_type not in {"preference", "fact", "goal", "summary"}:
            memory_type = "preference"

        importance = payload.get("importance", 0.85)
        try:
            importance_value = float(importance)
        except (TypeError, ValueError):
            importance_value = 0.85

        tags = payload.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        written.append(
            self.add_candidate_memory(
                db,
                session_id=session_id,
                user_id=user_id,
                role="system",
                content=content[:480],
                memory_type=memory_type,
                tags=tags,
                importance=max(0.0, min(1.0, importance_value)),
                source_model=model,
            )
        )
        return written

    def search_memories(
        self,
        db: Session,
        query: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        effective_limit = limit or settings.MEMORY_SEARCH_LIMIT
        q = db.query(MemoryItem)
        if user_id:
            q = q.filter(MemoryItem.user_id == user_id)
        q = q.filter(MemoryItem.memory_type.in_(["preference", "summary", "fact", "goal"]))

        rows = q.order_by(MemoryItem.created_at.desc(), MemoryItem.id.desc()).limit(max(effective_limit * 6, 24)).all()
        if not rows:
            return []

        tokens = _tokenize(query)
        ranked: list[tuple[float, MemoryItem]] = []
        for row in rows:
            score = float(row.importance or 0.0)
            haystack = f"{row.content} {row.tags} {row.role} {row.memory_type}".lower()
            if tokens:
                score += sum(2.0 for token in tokens if token in haystack)
            if session_id and row.session_id == session_id:
                score += 0.75
            if row.memory_type == "preference":
                score += 1.0
            if row.memory_type == "summary":
                score += 0.35
            ranked.append((score, row))

        ranked.sort(key=lambda item: (item[0], item[1].created_at or datetime.min), reverse=True)
        return [_serialize_item(item) for _, item in ranked[:effective_limit]]

    def delete_memory(self, db: Session, memory_id: int) -> bool:
        deleted = db.query(MemoryItem).filter(MemoryItem.id == memory_id).delete()
        db.commit()
        return deleted > 0


memory_manager = MemoryManager()