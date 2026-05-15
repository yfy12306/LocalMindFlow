from __future__ import annotations

import json
import os

from pydantic import BaseModel


DEFAULT_SYSTEM_PROMPT = """你是这个工作台里的本地智能体助手，不要声称自己“认识用户”或知道用户姓名，除非当前对话或明确记忆里直接给出。
要求：
1. 回答准确、直接、清楚
2. 对不确定的信息明确说明不知道
3. 只使用与当前问题直接相关的摘要、长期记忆和近期上下文
4. 不要重复模板化自我介绍，不要输出“我是一个大型语言模型，由 Google 训练”这类泛化开场
5. 产出尽量结构化，便于后续工具调用和自动化处理
6. 如果用户在问“你认识我吗 / 你知道我是谁吗 / 我说谁”，优先回答你只能基于当前会话与明确记忆判断；没有明确证据时就直接说不认识或不知道
"""


class ModelProfile(BaseModel):
    name: str
    provider: str = "ollama"
    label: str | None = None
    description: str = ""
    enabled: bool = True

    @property
    def display_name(self) -> str:
        return self.label or self.name


class Settings(BaseModel):
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gemma3:1b")
    DEFAULT_PROVIDER: str = os.getenv("DEFAULT_PROVIDER", "ollama")
    DEFAULT_USER_ID: str = os.getenv("DEFAULT_USER_ID", "local-user")
    RECENT_TURNS: int = int(os.getenv("RECENT_TURNS", "6"))
    MEMORY_SEARCH_LIMIT: int = int(os.getenv("MEMORY_SEARCH_LIMIT", "6"))
    MEMORY_CONTEXT_LIMIT: int = int(os.getenv("MEMORY_CONTEXT_LIMIT", "5"))
    SUMMARY_TRIGGER_TURNS: int = int(os.getenv("SUMMARY_TRIGGER_TURNS", "8"))
    MAX_SUMMARY_CHARS: int = int(os.getenv("MAX_SUMMARY_CHARS", "1200"))
    ENABLE_REFLECTION: bool = os.getenv("ENABLE_REFLECTION", "true").lower() in {"1", "true", "yes", "on"}
    ENABLE_MEMORY_EXTRACTION: bool = os.getenv("ENABLE_MEMORY_EXTRACTION", "true").lower() in {"1", "true", "yes", "on"}
    REFLECTION_MODEL: str = os.getenv("REFLECTION_MODEL", "")
    MEMORY_EXTRACTION_MODEL: str = os.getenv("MEMORY_EXTRACTION_MODEL", "")
    BACKEND_TASK_MODEL: str = os.getenv("BACKEND_TASK_MODEL", "")
    MODEL_CATALOG_RAW: str = os.getenv("MODEL_CATALOG_JSON", "")
    APP_TITLE: str = os.getenv("APP_TITLE", "多模态 Agent 工作台")
    APP_SUBTITLE: str = os.getenv(
        "APP_SUBTITLE",
        "持久记忆 / 多模型路由 / 可持续演进的本地智能体底座",
    )
    SYSTEM_PROMPT: str = os.getenv("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)


def _default_model_catalog() -> list[ModelProfile]:
    return [
        ModelProfile(name="deepseek-r1:1.5b", provider="ollama", label="DeepSeek R1 1.5B", description="轻量推理模型"),
        ModelProfile(name="gemma3:1b", provider="ollama", label="Gemma 3 1B", description="轻量多模态模型"),
        ModelProfile(name="qwen3:1.7b", provider="ollama", label="Qwen 3 1.7B", description="通用中文对话模型"),
    ]


def get_model_catalog() -> list[ModelProfile]:
    raw = (settings.MODEL_CATALOG_RAW or "").strip()
    if not raw:
        return _default_model_catalog()

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        profiles: list[ModelProfile] = []
        for item in raw.split(","):
            model_name = item.strip()
            if not model_name:
                continue
            profiles.append(ModelProfile(name=model_name, provider=settings.DEFAULT_PROVIDER, label=model_name))
        return profiles or _default_model_catalog()

    profiles: list[ModelProfile] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, str):
                profiles.append(ModelProfile(name=item, provider=settings.DEFAULT_PROVIDER, label=item))
                continue
            if isinstance(item, dict) and item.get("name"):
                profiles.append(ModelProfile(**item))

    return profiles or _default_model_catalog()


settings = Settings()