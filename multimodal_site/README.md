# 面向个人知识与任务流的本地智能体系统

一个围绕个人知识管理、任务推进与多模型协作构建的本地智能体工作台。

本项目提供一套本地优先的智能体操作系统体验：你可以在统一界面中发起多轮对话、组织上下文、调用技能、管理工作区文件、沉淀长期记忆，并通过运行事件流持续跟踪智能体的推理与执行过程。系统以本地会话、记忆召回、模型编排和任务流推进为核心，适合个人研发、知识整理、原型验证与本地 AI 助手场景。

## 项目概览

系统采用三栏式智能体控制台设计：

- 左侧聚焦会话归档与模型编排
- 中间聚焦对话、产物与系统总览
- 右侧聚焦上下文检查器，包括摘要、技能、文件、事件与记忆

在交互层面，项目支持：

- 多模型切换与能力标签展示
- 多轮连续对话与流式输出
- 会话级目标、摘要与状态维护
- 长期记忆召回与任务上下文注入
- 技能选择与工作区文件附加
- 运行事件流与产物卡片展示
- 图片、音频、文件等多模态入口

## 界面预览

### 主对话工作台

![主对话工作台](docs/images/dashboard-chat.png)

### 总览与会话控制区

![总览与会话控制区](docs/images/dashboard-overview.png)

## 技术栈

### 前端

- React 19
- Vite
- TypeScript
- GSAP
- React Markdown
- Phosphor Icons

### 后端

- FastAPI
- SQLAlchemy
- SQLite
- LangGraph
- LiteLLM

### 数据与状态

- `chat_records`：对话消息
- `session_state`：会话摘要、目标与任务状态
- `memory_items`：长期记忆与偏好信息
- `agent_events`：运行事件与审计数据

## 部署与运行

### 1. 获取项目

```powershell
cd D:\code\ai\multimodal_site
```

### 2. 安装前端依赖

```powershell
cd frontend
npm install
cd ..
```

### 3. 构建前端

```powershell
cd frontend
npm run build
cd ..
```

### 4. 启动后端服务

如果使用当前项目约定的 Anaconda 环境：

```powershell
D:/software/anaconda/Scripts/conda.exe run -p D:\software\anaconda\envs\langgraph_study --no-capture-output python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir D:\code\ai\multimodal_site
```

如果你已经激活自己的 Python 环境：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir D:\code\ai\multimodal_site
```

### 5. 打开系统

```text
http://127.0.0.1:8000/pages/
```

## 开发模式

### 前端开发

```powershell
cd frontend
npm run dev
```

Vite 已配置开发代理，默认将 `/api` 与 `/pages` 指向本地 FastAPI 服务。

### 常用检查命令

```powershell
cd frontend
npm run lint
npm run build
```

```powershell
cd ..
python -m compileall app
```

## 核心接口

### 页面入口

- `GET /pages/`

### 模型与系统总览

- `GET /api/models`
- `GET /api/overview`

### 会话与详情

- `GET /api/sessions`
- `GET /api/sessions/{session_id}`

### 智能体运行

- `POST /api/runs`
- `GET /api/runs/{run_id}/stream`

### 技能与工作区

- `GET /api/skills`
- `GET /api/workspace/files`
- `GET /api/workspace/file`

## 项目实现边界

当前版本已经完整打通本地智能体工作台的核心产品，包括前端控制台、普通多轮对话、会话状态维护、记忆召回链路、模型目录、技能目录、文件上下文注入、运行事件流与产物展示。

目前的边界主要在以下几类能力：

- 多模态入口已完成，但图片与音频的底层推理仍以扩展位为主
- 工具调用与复杂任务编排仍以智能体壳层和状态展示为核心，后续可继续深化
- 前端已具备完整产品界面，但仍可以进一步做组件拆分与更细的交互打磨

## 未来扩展方向

- 接入真实图片理解、音频转写与多模态推理链路
- 为记忆系统补充独立管理面板、筛选与编辑能力
- 增强 artifact 面板，支持代码草稿、文件草稿与任务计划卡
- 扩展工具调用、任务编排和执行反馈能力
- 引入更丰富的本地模型注册、切换与策略路由机制
