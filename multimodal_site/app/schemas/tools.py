from pydantic import BaseModel, Field


class SkillSummary(BaseModel):
    name: str
    description: str = ""
    path: str
    source: str = ""


class SkillDetail(SkillSummary):
    frontmatter: dict[str, str] = Field(default_factory=dict)
    content: str


class FileReadRequest(BaseModel):
    path: str
    start_line: int = 1
    end_line: int = 200


class FileReadResponse(BaseModel):
    path: str
    start_line: int
    end_line: int
    total_lines: int
    truncated: bool
    content: str


class WorkspaceFileEntry(BaseModel):
    path: str
    size_bytes: int = 0
