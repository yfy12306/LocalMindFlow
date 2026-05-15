from __future__ import annotations

from litellm import completion

from app.core.config import ModelProfile, get_model_catalog, settings
from app.core.backend_tasks import parse_json_object


def list_available_models() -> list[ModelProfile]:
    return [profile for profile in get_model_catalog() if profile.enabled]


def resolve_model_profile(model: str | None) -> ModelProfile:
    requested = (model or "").strip() or settings.DEFAULT_MODEL
    catalog = {profile.name: profile for profile in list_available_models()}

    if requested in catalog:
        return catalog[requested]

    if "/" in requested:
        provider, name = requested.split("/", 1)
        return ModelProfile(name=name, provider=provider, label=name)

    return ModelProfile(name=requested, provider=settings.DEFAULT_PROVIDER, label=requested)


def normalize_model_name(model: str) -> str:
    profile = resolve_model_profile(model)

    if profile.provider and profile.provider != settings.DEFAULT_PROVIDER:
        return f"{profile.provider}/{profile.name}"

    return f"{settings.DEFAULT_PROVIDER}/{profile.name}"


def _completion_kwargs(messages: list[dict], model: str, stream: bool) -> dict:
    profile = resolve_model_profile(model)
    kwargs = {
        "model": normalize_model_name(profile.name if profile.provider == settings.DEFAULT_PROVIDER else f"{profile.provider}/{profile.name}"),
        "messages": messages,
        "stream": stream,
    }

    if profile.provider == "ollama":
        kwargs["api_base"] = settings.OLLAMA_BASE_URL

    return kwargs


def chat_completion(messages: list[dict], model: str) -> str:
    resp = completion(**_completion_kwargs(messages, model, stream=False))
    return resp.choices[0].message.content or ""


def chat_completion_json(messages: list[dict], model: str) -> dict:
    return parse_json_object(chat_completion(messages, model))


def iter_llm_text(messages: list[dict], model: str):
    response = completion(**_completion_kwargs(messages, model, stream=True))

    for part in response:
        piece = ""
        try:
            piece = part.choices[0].delta.content or ""
        except Exception:
            piece = ""

        if piece:
            yield piece