# 多模态 Agent 工作台

一个面向本地开发与原型验证的 FastAPI 智能体工作台。当前版本不再只是聊天 demo，而是一个可继续扩展的 agent 底座，已经接入：

- 流式对话
- 多模型路由
- 持久会话状态
- 长期记忆检索
- 会话审计事件
- 工作区文件读取
- Skills 加载与上下文注入
- 运营概览接口

## 项目定位

这个项目的目标不是做一个“能聊天的页面”，而是提供一个可以继续演进为商用 agent 的本地工作台：

- 让模型选择变成后端驱动，而不是前端写死
- 让记忆可以跨会话回召，不只停留在当前聊天记录
- 让技能和文件上下文可以按需附加到对话中
- 让所有关键操作都可审计、可回放、可扩展

## 核心能力

### 1. 对话与会话

- 支持流式输出
- 支持会话历史回放
- 支持删除会话
- 支持当前会话状态持久化

### 2. 多模型

后端通过模型目录统一管理可用模型，前端从接口动态加载，不再硬编码。

### 3. 长期记忆

系统会把对话内容写入 SQLite，并基于当前问题和会话上下文做记忆召回。

### 4. Skills

项目支持从 `.github/skills/` 加载 `SKILL.md`。

当前内置技能包括：

- `agent-memory`
- `file-reader`
- `workspace-inspector`

### 5. 文件读取

支持读取工作区内文件，并将文件内容附加到聊天上下文中。

### 6. 审计与运营

提供事件记录与概览接口，便于查看：

- 会话数
- 消息数
- 记忆数
- 事件数
- 状态数

## 页面效果

前端已经改成更克制的工作台风格：

- 左侧为会话与工具区
- 中间为主对话区
- 底部为输入与模型选择
- 技能、文件读取都以收起式面板呈现，避免干扰主流程

## 技术栈

- FastAPI
- SQLAlchemy
- SQLite
- Jinja2
- LangGraph
- LiteLLM
- Vanilla JavaScript

## 目录结构

```text
multimodal_site/
├── app/
│   ├── core/
│   │   ├── config.py
│   │   ├── context_builder.py
│   │   ├── llm_gateway.py
│   │   ├── memory_manager.py
│   │   ├── skill_manager.py
│   │   └── workspace_tools.py
│   ├── graphs/
│   │   └── chat_graph.py
│   ├── models/
│   │   ├── agent_event.py
│   │   ├── chat_record.py
│   │   ├── memory_item.py
│   │   └── session_state.py
│   ├── routers/
│   │   ├── api_chat.py
│   │   ├── base.py
│   │   ├── history.py
│   │   ├── pages.py
│   │   └── tools.py
│   ├── schemas/
│   │   ├── chat.py
│   │   └── tools.py
│   ├── services/
│   │   ├── audit_service.py
│   │   ├── chat.py
│   │   └── session_state_service.py
│   └── main.py
├── templates/
│   └── index.html
└── README.md
```

## 本地启动

项目要求在 Anaconda 环境中运行。当前约定环境名为：`butterfly-collectiondsf`。

### 1. 进入项目目录

```bash
cd d:\code\ai\multimodal_site
```

### 2. 启动服务

```bash
D:/software/anaconda/Scripts/conda.exe run -p D:\software\anaconda\envs\langgraph_study --no-capture-output python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir d:\code\ai\multimodal_site
```

如果你本机已经有 `butterfly-collectiondsf` 环境，可以改成对应环境路径启动。

### 3. 打开页面

```text
http://127.0.0.1:8000/pages/
```

## 常用接口

### 页面

- `GET /pages/`：前端工作台

### 聊天

- `GET /api/chat/models`：模型目录
- `POST /api/chat/stream`：流式聊天
- `GET /api/chat/history?session_id=...`：会话历史
- `GET /api/chat/sessions`：会话列表
- `GET /api/chat/state?session_id=...`：会话状态
- `GET /api/chat/memories?query=...`：记忆检索
- `GET /api/chat/events`：审计事件
- `GET /api/chat/overview`：运行概览
- `DELETE /api/chat/session?session_id=...`：删除会话

### 工具

- `GET /api/tools/skills`：列出可用 skills
- `GET /api/tools/skills/{skill_name}`：读取 skill 详情
- `GET /api/tools/files?pattern=...`：列出工作区文件
- `GET /api/tools/common-files`：列出常用文件
- `GET /api/tools/file?path=...&start_line=1&end_line=200`：读取文件片段

## Skills 使用方式

在网页左侧可以直接勾选技能，当前请求会把选中的 skills 注入对话上下文。

内置 skills 的位置：

```text
.github/skills/<skill-name>/SKILL.md
```

如果你要新增 skill，只要按这个格式放进去：

```md
---
name: your-skill-name
description: 一句话说明它适合什么场景，越具体越好
---

# Skill Title

...workflow...
```

## 文件读取使用方式

在左侧文件读取面板中输入工作区内相对路径，例如：

```text
app/main.py
app/core/config.py
templates/index.html
```

读取后可以：

- 直接查看文件内容
- 附加到当前聊天上下文
- 配合 skill 一起分析和修改项目

## 记忆机制说明

系统当前不是单纯保存聊天记录，而是把信息拆成几层：

- `chat_records`：原始聊天消息
- `session_state`：当前会话的摘要、目标和状态
- `memory_items`：可召回的长期记忆
- `agent_events`：审计事件和运行指标

其中长期记忆会优先召回偏好、约束和重复出现的重要信息。

## 现在的改造方向

当前底座已经能工作，但如果你继续把它做成真正的商用 agent，下一步通常是：

1. 增加工具调用编排
2. 接入向量数据库做语义记忆
3. 把记忆反思拆成后台任务
4. 加入鉴权、用户系统和审计面板
5. 做模型供应商注册与切换
6. 把 skills 做成可配置工作流

## 备注

如果浏览器里看起来还有旧内容，先确认后端进程是最新启动的，再刷新页面。
