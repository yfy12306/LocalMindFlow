from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer
from app.core.context_builder import build_context_messages  # 上下文拼装（摘要+历史+新消息）
from app.core.llm_gateway import iter_llm_text               # 流式调用 LLM，逐 token 返回


# ── 图的全局状态结构 ──────────────────────────────────────
class ChatGraphState(TypedDict):
    """流经整个 LangGraph 的全局状态，每个节点都能读写这里的字段"""
    session_id: str          # 会话唯一标识
    user_id: str             # 用户标识
    model: str               # 使用的模型名
    message: str             # 用户本次输入
    history: List[Dict]      # 完整对话历史
    memories: List[Dict]     # 长期记忆检索结果
    skills: List[Dict]       # 选中的技能上下文
    file_contexts: List[Dict] # 读取的文件上下文
    running_summary: str     # 历史摘要（对话过长时压缩存这里）
    current_goal: str        # 当前会话目标 / 意图
    llm_messages: List[Dict] # 拼装好的、准备发给 LLM 的消息列表
    answer: str              # LLM 最终完整回复


# ── 节点1：拼装上下文 ─────────────────────────────────────
def prepare_context(state: ChatGraphState):
    """把历史、摘要、目标、新消息拼装成 LLM 可用的 messages 列表"""
    llm_messages = build_context_messages(
        message=state["message"],
        history=state.get("history", []),
        memories=state.get("memories", []),
        skills=state.get("skills", []),
        file_contexts=state.get("file_contexts", []),
        running_summary=state.get("running_summary", ""),
        current_goal=state.get("current_goal", ""),
    )
    # 只更新 llm_messages，其余字段保持不变
    return {"llm_messages": llm_messages}


# ── 节点2：流式调用模型 ───────────────────────────────────
def call_model_stream(state: ChatGraphState):
    """流式调用模型：边收到 token 边往外写，同时拼完整 answer"""

    # LangGraph 提供的写入器，writer() 的内容会实时推送给外部调用方
    writer = get_stream_writer()

    answer_parts: List[str] = []  # 暂存每个 token，最后拼成完整回复

    for piece in iter_llm_text(
        messages=state["llm_messages"],
        model=state["model"],
    ):
        answer_parts.append(piece)
        # 每个 token 立刻推出去，前端实现打字机效果
        writer({
            "type": "token",
            "content": piece,
        })

    # 返回完整回复，写入 state["answer"]
    return {"answer": "".join(answer_parts)}


# ── 构建并编译图 ──────────────────────────────────────────
graph_builder = StateGraph(ChatGraphState)

# 注册节点
graph_builder.add_node("prepare_context", prepare_context)
graph_builder.add_node("call_model_stream", call_model_stream)

# 串行连边：START → 拼上下文 → 流式调模型 → END
graph_builder.add_edge(START, "prepare_context")
graph_builder.add_edge("prepare_context", "call_model_stream")
graph_builder.add_edge("call_model_stream", END)

# 编译成可执行图，供外部 stream / invoke 调用
chat_graph = graph_builder.compile()