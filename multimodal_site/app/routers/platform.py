from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.skill_manager import list_skills
from app.core.workspace_tools import list_common_files, list_workspace_files, read_text_file
from app.database import get_db
from app.schemas.platform import (
    OverviewResponse,
    RunCreateRequest,
    RunCreateResponse,
    SessionDetailResponse,
    SessionListItem,
    SkillCatalogItem,
    WorkspaceFilePanelItem,
    WorkspaceFileReadResponse,
)
from app.services.agent_state_service import get_overview, get_session_detail, list_sessions
from app.services.model_registry import list_models
from app.services.run_service import create_run, stream_run


router = APIRouter(prefix="/api", tags=["platform"])


@router.get("/models")
def get_models():
    return list_models()


@router.get("/overview", response_model=OverviewResponse)
def overview(db: Session = Depends(get_db)):
    return get_overview(db)


@router.get("/sessions", response_model=list[SessionListItem])
def sessions(db: Session = Depends(get_db)):
    return list_sessions(db)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def session_detail(session_id: str, db: Session = Depends(get_db)):
    return get_session_detail(db, session_id)


@router.post("/runs", response_model=RunCreateResponse)
def create_run_endpoint(payload: RunCreateRequest):
    pending = create_run(payload)
    return RunCreateResponse(
        run_id=pending.run_id,
        session_id=pending.session_id,
        stream_url=f"/api/runs/{pending.run_id}/stream",
        status=pending.status,
    )


@router.get("/runs/{run_id}/stream")
def stream_run_endpoint(run_id: str):
    return StreamingResponse(
        stream_run(run_id),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/skills", response_model=list[SkillCatalogItem])
def skills():
    items: list[SkillCatalogItem] = []
    for item in list_skills():
        category = "workflow"
        path = item.get("path", "")
        if "design" in path or "frontend" in path:
            category = "design"
        elif "memory" in path:
            category = "memory"
        elif "file" in path or "workspace" in path:
            category = "workspace"
        items.append(SkillCatalogItem(**item, category=category))
    return items


@router.get("/workspace/files", response_model=list[WorkspaceFilePanelItem])
def workspace_files(
    pattern: str = Query("**/*"),
    limit: int = Query(100, ge=1, le=500),
    common_only: bool = Query(False),
):
    rows = list_common_files() if common_only else list_workspace_files(pattern=pattern, limit=limit)
    items: list[WorkspaceFilePanelItem] = []
    for item in rows:
        path = item["path"]
        extension = path.rsplit(".", 1)[1].lower() if "." in path else ""
        group = "code" if extension in {"py", "ts", "tsx", "js", "jsx", "css", "html"} else "docs"
        items.append(
            WorkspaceFilePanelItem(
                path=path,
                size_bytes=item["size_bytes"],
                extension=extension,
                group=group,
            )
        )
    return items


@router.get("/workspace/file", response_model=WorkspaceFileReadResponse)
def workspace_file(
    path: str = Query(...),
    start_line: int = Query(1, ge=1),
    end_line: int = Query(200, ge=1),
):
    return WorkspaceFileReadResponse(**read_text_file(path=path, start_line=start_line, end_line=end_line))
