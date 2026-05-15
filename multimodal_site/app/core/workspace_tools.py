from __future__ import annotations

from pathlib import Path

from app.core.config import settings


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMMON_PATTERNS = [
    "AGENTS.md",
    "README.md",
    "app/**/*.py",
    "templates/**/*.html",
    ".github/**/*.md",
    "*.md",
]


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = (WORKSPACE_ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()

    root = WORKSPACE_ROOT.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("Path is outside the workspace root")

    return candidate


def list_workspace_files(pattern: str = "**/*", limit: int = 100) -> list[dict]:
    matched: list[dict] = []
    seen: set[str] = set()
    for file_path in sorted(WORKSPACE_ROOT.glob(pattern)):
        if not file_path.is_file():
            continue
        try:
            relative = file_path.relative_to(WORKSPACE_ROOT).as_posix()
        except ValueError:
            continue
        if relative in seen:
            continue
        seen.add(relative)
        matched.append({"path": relative, "size_bytes": file_path.stat().st_size})
        if len(matched) >= limit:
            break
    return matched


def list_common_files() -> list[dict]:
    files: list[dict] = []
    seen: set[str] = set()
    for pattern in DEFAULT_COMMON_PATTERNS:
        for item in list_workspace_files(pattern, limit=200):
            if item["path"] in seen:
                continue
            seen.add(item["path"])
            files.append(item)
    return files


def read_text_file(path: str, start_line: int = 1, end_line: int = 200, max_chars: int = 20000) -> dict:
    target = _resolve_path(path)
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    text = target.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    total_lines = len(lines)
    start = max(1, start_line)
    end = min(max(end_line, start), total_lines)
    excerpt = "\n".join(lines[start - 1 : end])
    truncated = len(excerpt) > max_chars
    if truncated:
        excerpt = excerpt[: max_chars - 3].rstrip() + "..."

    return {
        "path": target.relative_to(WORKSPACE_ROOT).as_posix(),
        "start_line": start,
        "end_line": end,
        "total_lines": total_lines,
        "truncated": truncated,
        "content": excerpt,
    }


def read_files(paths: list[str], max_chars_each: int = 12000) -> list[dict]:
    result: list[dict] = []
    for path in paths:
        try:
            result.append(read_text_file(path, 1, 9999, max_chars=max_chars_each))
        except Exception as exc:
            result.append({"path": path, "error": str(exc)})
    return result
