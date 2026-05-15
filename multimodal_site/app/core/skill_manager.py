from __future__ import annotations

import re
from pathlib import Path

from app.core.workspace_tools import WORKSPACE_ROOT


SKILL_DIRECTORIES = [
    WORKSPACE_ROOT / ".github" / "skills",
    WORKSPACE_ROOT / ".agents" / "skills",
    WORKSPACE_ROOT / "skills",
]


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, flags=re.DOTALL)
    if not match:
        return {}, text

    frontmatter_text, body = match.groups()
    frontmatter: dict[str, str] = {}
    for line in frontmatter_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip('"').strip("'")
    return frontmatter, body


def _skill_files() -> list[Path]:
    files: list[Path] = []
    for directory in SKILL_DIRECTORIES:
        if not directory.exists():
            continue
        files.extend(sorted(directory.rglob("SKILL.md")))
    return files


def list_skills() -> list[dict]:
    skills: list[dict] = []
    seen: set[str] = set()
    for skill_file in _skill_files():
        try:
            content = skill_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        frontmatter, body = _parse_frontmatter(content)
        name = frontmatter.get("name") or skill_file.parent.name
        if name in seen:
            continue
        seen.add(name)
        skills.append(
            {
                "name": name,
                "description": frontmatter.get("description", ""),
                "path": skill_file.relative_to(WORKSPACE_ROOT).as_posix(),
                "source": skill_file.parent.as_posix(),
            }
        )
    return skills


def get_skill(name: str) -> dict | None:
    target = (name or "").strip().lower()
    for skill_file in _skill_files():
        try:
            content = skill_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        frontmatter, body = _parse_frontmatter(content)
        skill_name = (frontmatter.get("name") or skill_file.parent.name).strip().lower()
        if target and target not in {skill_name, skill_file.parent.name.lower(), skill_file.stem.lower()}:
            continue
        return {
            "name": frontmatter.get("name") or skill_file.parent.name,
            "description": frontmatter.get("description", ""),
            "path": skill_file.relative_to(WORKSPACE_ROOT).as_posix(),
            "source": skill_file.parent.as_posix(),
            "frontmatter": frontmatter,
            "content": body.strip(),
        }
    return None


def load_selected_skills(skill_names: list[str] | None) -> list[dict]:
    selected: list[dict] = []
    for name in skill_names or []:
        skill = get_skill(name)
        if skill:
            selected.append(skill)
    return selected
