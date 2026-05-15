from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.skill_manager import get_skill, list_skills
from app.core.workspace_tools import list_common_files, list_workspace_files, read_text_file
from app.schemas.tools import FileReadResponse, SkillDetail, SkillSummary, WorkspaceFileEntry


router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("/files", response_model=list[WorkspaceFileEntry])
def get_files(
    pattern: str = Query("**/*"),
    limit: int = Query(100, ge=1, le=500),
):
    return list_workspace_files(pattern=pattern, limit=limit)


@router.get("/common-files", response_model=list[WorkspaceFileEntry])
def get_common_files():
    return list_common_files()


@router.get("/file", response_model=FileReadResponse)
def read_file(
    path: str = Query(...),
    start_line: int = Query(1, ge=1),
    end_line: int = Query(200, ge=1),
):
    payload = read_text_file(path=path, start_line=start_line, end_line=end_line)
    return payload


@router.get("/skills", response_model=list[SkillSummary])
def get_skills():
    return list_skills()


@router.get("/skills/{skill_name}", response_model=SkillDetail)
def get_skill_detail(skill_name: str):
    skill = get_skill(skill_name)
    if not skill:
        return {
            "name": skill_name,
            "description": "",
            "path": "",
            "source": "",
            "frontmatter": {},
            "content": "",
        }
    return skill