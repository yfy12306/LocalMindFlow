from __future__ import annotations

from app.core.config import ModelProfile, get_model_catalog
from app.schemas.platform import ModelCapabilityInfo


def _infer_capabilities(profile: ModelProfile) -> list[str]:
    name = (profile.name or "").lower()
    capabilities = ["chat"]

    if any(token in name for token in ["vision", "vl", "gemma3", "qwen2.5vl", "qwen-vl"]):
        capabilities.append("vision")
    if any(token in name for token in ["r1", "reason", "coder", "qwen3", "deepseek"]):
        capabilities.append("reasoning")
    if any(token in name for token in ["1b", "1.5b", "3b"]):
        capabilities.append("fast")
    if profile.provider == "ollama":
        capabilities.append("local")

    return capabilities


def _infer_latency_tier(profile: ModelProfile) -> str:
    name = (profile.name or "").lower()
    if any(token in name for token in ["1b", "1.5b", "3b"]):
        return "fast"
    if any(token in name for token in ["70b", "72b", "405b"]):
        return "deliberate"
    return "balanced"


def list_models() -> list[ModelCapabilityInfo]:
    items: list[ModelCapabilityInfo] = []
    for profile in get_model_catalog():
        items.append(
            ModelCapabilityInfo(
                name=profile.name,
                provider=profile.provider,
                label=profile.display_name,
                description=profile.description,
                enabled=profile.enabled,
                capabilities=_infer_capabilities(profile),
                latency_tier=_infer_latency_tier(profile),
                context_window="standard",
            )
        )
    return [item for item in items if item.enabled]
