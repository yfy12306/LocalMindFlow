from __future__ import annotations

from app.schemas.platform import ArtifactCard


def build_run_artifacts(*, skills: list[str], context_files: list[str]) -> list[ArtifactCard]:
    artifacts: list[ArtifactCard] = []

    if skills:
        artifacts.append(
            ArtifactCard(
                id="skills:selected",
                kind="skills",
                title="已启用技能",
                body=", ".join(skills[:8]),
                tone="accent",
            )
        )

    if context_files:
        artifacts.append(
            ArtifactCard(
                id="files:attached",
                kind="files",
                title="已附加工作区上下文",
                body="\n".join(context_files[:6]),
                tone="neutral",
            )
        )

    return artifacts
