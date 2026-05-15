from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict
from pydantic import BaseModel, Field


AgentMode = Literal["chat", "analyze", "build", "research"]
AttachmentKind = Literal["image", "audio", "file"]
RunEventType = Literal["message_delta", "run_status", "tool_event", "artifact", "error"]


class AttachmentRef(BaseModel):
    id: str
    kind: AttachmentKind
    name: str
    mime_type: str
    size_bytes: int = 0
    local_path: str | None = None
    preview_url: str | None = None
    status: str = "ready"


class RunInput(BaseModel):
    type: Literal["text"] = "text"
    content: str


class RunCreateRequest(BaseModel):
    session_id: str | None = None
    input: RunInput
    model: str
    attachments: list[AttachmentRef] = Field(default_factory=list)
    skill_names: list[str] = Field(default_factory=list)
    context_files: list[str] = Field(default_factory=list)
    agent_mode: AgentMode = "chat"


class RunCreateResponse(BaseModel):
    run_id: str
    session_id: str
    stream_url: str
    status: str


class ModelCapabilityInfo(BaseModel):
    name: str
    provider: str
    label: str
    description: str = ""
    enabled: bool = True
    capabilities: list[str] = Field(default_factory=list)
    latency_tier: str = "balanced"
    context_window: str = "standard"


class SessionListItem(BaseModel):
    session_id: str
    title: str
    preview: str
    model: str | None = None
    last_active_at: datetime | None = None
    run_status: str = "idle"
    message_count: int = 0


class MessageRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    model: str | None = None
    created_at: datetime


class MemoryPanelItem(BaseModel):
    id: int
    memory_type: str
    content: str
    tags: list[str] = Field(default_factory=list)
    importance: float = 0.5
    created_at: datetime | None = None


class EventPanelItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    model: str | None = None
    duration_ms: int
    success: bool
    error_message: str
    metadata_json: str
    created_at: datetime


class SessionStatePanel(BaseModel):
    running_summary: str = ""
    current_goal: str = ""
    task_state_json: str = "{}"
    updated_at: datetime | None = None


class ArtifactCard(BaseModel):
    id: str
    kind: str
    title: str
    body: str
    tone: str = "neutral"


class SessionDetailResponse(BaseModel):
    session_id: str
    title: str
    model: str | None = None
    run_status: str = "idle"
    message_count: int = 0
    messages: list[MessageRecord] = Field(default_factory=list)
    memories: list[MemoryPanelItem] = Field(default_factory=list)
    recent_events: list[EventPanelItem] = Field(default_factory=list)
    attached_context: list[str] = Field(default_factory=list)
    active_skills: list[str] = Field(default_factory=list)
    state: SessionStatePanel = Field(default_factory=SessionStatePanel)
    artifacts: list[ArtifactCard] = Field(default_factory=list)


class DashboardMetric(BaseModel):
    label: str
    value: str
    detail: str


class DashboardPane(BaseModel):
    title: str
    body: str
    tone: str = "neutral"


class OverviewResponse(BaseModel):
    metrics: list[DashboardMetric]
    panes: list[DashboardPane]


class SkillCatalogItem(BaseModel):
    name: str
    description: str = ""
    path: str = ""
    source: str = ""
    category: str = "general"


class WorkspaceFilePanelItem(BaseModel):
    path: str
    size_bytes: int
    extension: str = ""
    group: str = "workspace"


class WorkspaceFileReadResponse(BaseModel):
    path: str
    start_line: int
    end_line: int
    total_lines: int
    truncated: bool
    content: str


class RunStreamEvent(BaseModel):
    type: RunEventType
    run_id: str
    session_id: str
    timestamp: datetime
    delta: str = ""
    status: str | None = None
    message: str = ""
    artifact: ArtifactCard | None = None
    meta: dict = Field(default_factory=dict)
