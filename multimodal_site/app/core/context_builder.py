from app.core.config import settings

# ── 系统提示词：定义 AI 角色和回答规范 ───────────────────
SYSTEM_PROMPT = settings.SYSTEM_PROMPT


def _format_memory_block(memories: list[dict] | None) -> str:
    if not memories:
        return ""

    lines: list[str] = []
    for index, item in enumerate(memories[: settings.MEMORY_CONTEXT_LIMIT], start=1):
        content = _sanitize_context_text((item.get("content") or "").strip().replace("\n", " "))
        if not content:
            continue
        role = item.get("role", "memory")
        memory_type = item.get("memory_type", "turn")
        lines.append(f"{index}. [{memory_type}/{role}] {content[:240]}")

    return "\n".join(lines)


def _sanitize_context_text(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return ""

    banned_phrases = [
        "我是一个大型语言模型",
        "由 Google 训练",
        "我并没有“认识”你",
        "我记住了你的名字",
        "请提供更多上下文",
    ]
    if any(phrase in value for phrase in banned_phrases):
        return ""

    return value


def _format_skill_block(skills: list[dict] | None) -> str:
    if not skills:
        return ""

    lines: list[str] = []
    for index, item in enumerate(skills, start=1):
        name = (item.get("name") or "skill").strip()
        description = (item.get("description") or "").strip().replace("\n", " ")
        lines.append(f"{index}. {name}: {description}" if description else f"{index}. {name}")

    return "\n".join(lines)


def _format_file_block(files: list[dict] | None) -> str:
    if not files:
        return ""

    lines: list[str] = []
    for index, item in enumerate(files, start=1):
        if item.get("error"):
            lines.append(f"{index}. {item.get('path')}: {item.get('error')}")
            continue
        path = item.get("path", "")
        start_line = item.get("start_line", 1)
        end_line = item.get("end_line", 1)
        content = (item.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{index}. {path} [{start_line}-{end_line}]\n{content[:1600]}")

    return "\n\n".join(lines)


def build_context_messages(
    message: str,                    # 用户本次输入
    history: list[dict] | None,      # 完整对话历史
    memories: list[dict] | None = None,
    skills: list[dict] | None = None,
    file_contexts: list[dict] | None = None,
    running_summary: str = "",       # 历史摘要（对话过长时压缩存这里）
    current_goal: str = "",          # 当前会话目标 / 意图
) -> list[dict]:
    """拼装发给 LLM 的 messages 列表：系统提示 + 摘要 + 目标 + 历史 + 新消息"""

    history = history or []  # 防止传入 None 时报错

    # 只取最近 N 轮，避免超出模型上下文长度限制
    recent_history = history[-settings.RECENT_TURNS:]

    # 第一条固定是系统提示词
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    # 有摘要则注入，让模型知道之前聊了什么
    running_summary = _sanitize_context_text(running_summary)
    current_goal = _sanitize_context_text(current_goal)

    if running_summary:
        messages.append({
            "role": "system",
            "content": f"当前会话摘要：{running_summary}"
        })

    # 有目标则注入，引导模型聚焦当前任务
    if current_goal:
        messages.append({
            "role": "system",
            "content": f"当前目标：{current_goal}"
        })

    memory_block = _format_memory_block(memories)
    if memory_block:
        messages.append({
            "role": "system",
            "content": "相关长期记忆：\n" + memory_block,
        })

    skill_block = _format_skill_block(skills)
    if skill_block:
        messages.append({
            "role": "system",
            "content": "当前启用技能：\n" + skill_block,
        })

    file_block = _format_file_block(file_contexts)
    if file_block:
        messages.append({
            "role": "system",
            "content": "已读取文件上下文：\n" + file_block,
        })

    # 角色名映射表：统一成 LLM 认识的标准格式
    role_map = {
        "Y": "user",           # 非标准写法，兼容处理
        "user": "user",
        "assistant": "assistant",
        "model": "assistant",  # Gemini 等模型用 "model" 表示 assistant
        "system": "system",
    }

    # 插入最近几轮真实对话记录
    for item in recent_history:
        role = role_map.get(item.get("role", "user"), "user")  # 未知角色默认当 user
        content = (item.get("content") or "").strip()
        if not content:
            continue  # 跳过空消息，防止发送无效内容
        messages.append({
            "role": role,
            "content": content
        })

    # 最后追加用户本次输入
    messages.append({
        "role": "user",
        "content": message
    })

    return messages