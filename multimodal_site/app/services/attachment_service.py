from __future__ import annotations

from app.schemas.platform import ArtifactCard, AttachmentRef


def normalize_attachments(attachments: list[AttachmentRef] | None) -> list[AttachmentRef]:
    normalized: list[AttachmentRef] = []
    for item in attachments or []:
        status = item.status or "ready"
        if item.kind in {"image", "audio"}:
            status = "not_implemented"
        normalized.append(item.model_copy(update={"status": status}))
    return normalized


def build_attachment_artifacts(attachments: list[AttachmentRef] | None) -> list[ArtifactCard]:
    artifacts: list[ArtifactCard] = []
    for item in attachments or []:
        if item.kind == "image":
            body = "图片附件入口已经就绪，后端多模态推理会在下一阶段接入。"
        elif item.kind == "audio":
            body = "音频附件入口已经注册，流式转写与音频理解尚未实现。"
        else:
            body = f"文件附件已可用于上下文注入：{item.name}"

        artifacts.append(
            ArtifactCard(
                id=f"attachment:{item.id}",
                kind="attachment",
                title=item.name,
                body=body,
                tone="warning" if item.status == "not_implemented" else "neutral",
            )
        )
    return artifacts
