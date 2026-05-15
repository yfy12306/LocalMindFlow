from pydantic import BaseModel, Field
from datetime import datetime

from app.core.config import ModelProfile, settings

class ChatMessage(BaseModel):
    role: str
    content: str 

class ChatResponse(BaseModel):
    session_id: str
    input_message: str
    model: str
    answer: str

class ChatRequest(BaseModel):
    session_id: str
    message: str
    model: str = settings.DEFAULT_MODEL
    messages: list[ChatMessage] = Field(default_factory=list)
    skill_names: list[str] = Field(default_factory=list)
    context_files: list[str] = Field(default_factory=list)

class ChatRecordResponse(BaseModel):
    
    id: int
    session_id: str
    role: str
    content: str 
    model:str| None= None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionSummary(BaseModel):
    session_id: str
    model: str | None = None
    preview: str
    message_count: int


class ModelInfo(BaseModel):
    name: str
    provider: str
    label: str | None = None
    description: str = ""
    enabled: bool = True


class MemoryRecordResponse(BaseModel):
    id: int
    session_id: str
    user_id: str
    role: str
    memory_type: str
    content: str
    tags: list[str] = Field(default_factory=list)
    importance: float = 0.5
    source_model: str | None = None
    created_at: datetime | None = None


class AgentEventResponse(BaseModel):
    id: int
    session_id: str
    user_id: str
    event_type: str
    model: str | None = None
    request_chars: int
    response_chars: int
    duration_ms: int
    success: bool
    error_message: str
    metadata_json: str
    created_at: datetime


def model_info_from_profile(profile: ModelProfile) -> ModelInfo:
    return ModelInfo(**profile.dict())