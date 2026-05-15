import {
  CaretLeft,
  CaretRight,
  ArrowsClockwise,
  Brain,
  ChatCircleText,
  CircleNotch,
  FileCode,
  FileText,
  FolderOpen,
  ImageSquare,
  MicrophoneStage,
  PaperPlaneTilt,
  Plus,
  Sparkle,
  SquaresFour,
  Stack,
  Waveform,
} from '@phosphor-icons/react'
import { useGSAP } from '@gsap/react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import {
  startTransition,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from './api'
import './index.css'
import type {
  AgentMode,
  ArtifactCard,
  AttachmentRef,
  MessageRecord,
  ModelInfo,
  OverviewResponse,
  RunStreamEvent,
  SessionDetail,
  SessionListItem,
  SkillItem,
  WorkspaceFileItem,
  WorkspacePreview,
} from './types'

gsap.registerPlugin(ScrollTrigger, useGSAP)

const MODES: AgentMode[] = ['chat', 'analyze', 'build', 'research']
const MODE_LABELS: Record<AgentMode, string> = {
  chat: '对话',
  analyze: '分析',
  build: '构建',
  research: '研究',
}
const CENTER_TABS = ['对话', '产物', '总览'] as const
const INSPECTOR_TABS = ['摘要', '技能', '文件', '事件', '记忆'] as const
const SESSION_PAGE_SIZE = 6
const FILE_PAGE_SIZE = 8

const ATTACHMENT_TEMPLATES: Record<'image' | 'audio' | 'file', Omit<AttachmentRef, 'id'>> = {
  image: {
    kind: 'image',
    name: 'interface-shot.png',
    mime_type: 'image/png',
    size_bytes: 340_000,
    preview_url: 'https://picsum.photos/seed/interface-shot/320/200',
  },
  audio: {
    kind: 'audio',
    name: 'standup-note.wav',
    mime_type: 'audio/wav',
    size_bytes: 1_620_000,
  },
  file: {
    kind: 'file',
    name: 'agent_brief.md',
    mime_type: 'text/markdown',
    size_bytes: 24_000,
    local_path: 'README.md',
  },
}

const formatter = new Intl.DateTimeFormat('zh-CN', {
  hour: '2-digit',
  minute: '2-digit',
  month: 'short',
  day: 'numeric',
})

function createLocalAttachment(kind: 'image' | 'audio' | 'file'): AttachmentRef {
  return {
    id: `${kind}-${crypto.randomUUID()}`,
    ...ATTACHMENT_TEMPLATES[kind],
  }
}

function capabilityLabel(capability: string) {
  switch (capability) {
    case 'vision':
      return '视觉'
    case 'reasoning':
      return '推理'
    case 'fast':
      return '快速'
    case 'local':
      return '本地'
    default:
      return capability
  }
}

function formatTime(value: string | null) {
  if (!value) return '暂无'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '暂无' : formatter.format(date)
}

function latencyTierLabel(value: string) {
  switch (value) {
    case 'fast':
      return '快速'
    case 'balanced':
      return '均衡'
    case 'deliberate':
      return '深度'
    default:
      return value
  }
}

function artifactKindLabel(value: string) {
  switch (value) {
    case 'attachment':
      return '附件'
    case 'skills':
      return '技能'
    case 'files':
      return '文件'
    default:
      return value
  }
}

function messageTone(role: MessageRecord['role']) {
  if (role === 'user') return 'message user'
  if (role === 'system') return 'message system'
  return 'message assistant'
}

function App() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null)
  const [models, setModels] = useState<ModelInfo[]>([])
  const [sessions, setSessions] = useState<SessionListItem[]>([])
  const [skills, setSkills] = useState<SkillItem[]>([])
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFileItem[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [sessionDetail, setSessionDetail] = useState<SessionDetail | null>(null)
  const [composerValue, setComposerValue] = useState('')
  const [selectedModel, setSelectedModel] = useState('')
  const [selectedMode, setSelectedMode] = useState<AgentMode>('chat')
  const [selectedSkills, setSelectedSkills] = useState<string[]>([])
  const [selectedFiles, setSelectedFiles] = useState<string[]>([])
  const [attachments, setAttachments] = useState<AttachmentRef[]>([])
  const [preview, setPreview] = useState<WorkspacePreview | null>(null)
  const [messages, setMessages] = useState<MessageRecord[]>([])
  const [artifacts, setArtifacts] = useState<ArtifactCard[]>([])
  const [statusText, setStatusText] = useState('准备开始新的本地运行。')
  const [statusTone, setStatusTone] = useState<'idle' | 'live' | 'error'>('idle')
  const [isBooting, setIsBooting] = useState(true)
  const [isSending, setIsSending] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [sessionSearch, setSessionSearch] = useState('')
  const [centerTab, setCenterTab] = useState<(typeof CENTER_TABS)[number]>('对话')
  const [inspectorTab, setInspectorTab] = useState<(typeof INSPECTOR_TABS)[number]>('摘要')
  const [sessionPage, setSessionPage] = useState(1)
  const [filePage, setFilePage] = useState(1)
  const canvasRef = useRef<HTMLDivElement | null>(null)
  const welcomeRef = useRef<HTMLDivElement | null>(null)
  const overviewRef = useRef<HTMLDivElement | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const deferredSearchQuery = useDeferredValue(searchQuery)
  const deferredSessionSearch = useDeferredValue(sessionSearch)

  const filteredFiles = useMemo(() => {
    const query = deferredSearchQuery.trim().toLowerCase()
    if (!query) return workspaceFiles
    return workspaceFiles.filter((item) => item.path.toLowerCase().includes(query))
  }, [deferredSearchQuery, workspaceFiles])

  const filteredSessions = useMemo(() => {
    const query = deferredSessionSearch.trim().toLowerCase()
    if (!query) return sessions
    return sessions.filter(
      (item) =>
        item.title.toLowerCase().includes(query) ||
        item.preview.toLowerCase().includes(query),
    )
  }, [deferredSessionSearch, sessions])

  const sessionPageCount = Math.max(1, Math.ceil(filteredSessions.length / SESSION_PAGE_SIZE))
  const filePageCount = Math.max(1, Math.ceil(filteredFiles.length / FILE_PAGE_SIZE))
  const effectiveSessionPage = Math.min(sessionPage, sessionPageCount)
  const effectiveFilePage = Math.min(filePage, filePageCount)

  const pagedSessions = useMemo(() => {
    const start = (effectiveSessionPage - 1) * SESSION_PAGE_SIZE
    return filteredSessions.slice(start, start + SESSION_PAGE_SIZE)
  }, [effectiveSessionPage, filteredSessions])

  const pagedFiles = useMemo(() => {
    const start = (effectiveFilePage - 1) * FILE_PAGE_SIZE
    return filteredFiles.slice(start, start + FILE_PAGE_SIZE)
  }, [effectiveFilePage, filteredFiles])

  const groupedModels = useMemo(() => {
    return models.reduce<Record<string, ModelInfo[]>>((accumulator, item) => {
      accumulator[item.provider] ??= []
      accumulator[item.provider].push(item)
      return accumulator
    }, {})
  }, [models])

  useGSAP(
    () => {
      if (!canvasRef.current || !welcomeRef.current) return

      gsap.fromTo(
        welcomeRef.current.querySelectorAll('[data-reveal]'),
        { opacity: 0, y: 26 },
        {
          opacity: 1,
          y: 0,
          duration: 1.1,
          ease: 'power3.out',
          stagger: 0.08,
        },
      )

      if (overviewRef.current) {
        const words = overviewRef.current.querySelectorAll('.insight-words span')
        gsap.fromTo(
          words,
          { opacity: 0.16 },
          {
            opacity: 1,
            ease: 'none',
            stagger: 0.05,
            scrollTrigger: {
              trigger: overviewRef.current,
              scroller: canvasRef.current,
              scrub: true,
              start: 'top 72%',
              end: 'bottom 38%',
            },
          },
        )

        const heading = overviewRef.current.querySelector('.overview-heading')
        if (heading) {
          ScrollTrigger.create({
            trigger: overviewRef.current,
            scroller: canvasRef.current,
            start: 'top top+=96',
            end: '+=220',
            pin: heading,
            pinSpacing: false,
          })
        }
      }
    },
    { scope: canvasRef, dependencies: [overview] },
  )

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const [overviewData, modelData, sessionData, skillData, fileData] =
          await Promise.all([
            api.getOverview(),
            api.getModels(),
            api.getSessions(),
            api.getSkills(),
            api.getWorkspaceFiles(true),
          ])

        setOverview(overviewData)
        setModels(modelData)
        setSelectedModel(modelData[0]?.name ?? '')
        setSessions(sessionData)
        setSkills(skillData)
        setWorkspaceFiles(fileData)

        if (sessionData[0]?.session_id) {
          setSelectedSessionId(sessionData[0].session_id)
        }
      } catch (error) {
        setStatusTone('error')
        setStatusText(error instanceof Error ? error.message : '初始化失败。')
      } finally {
        setIsBooting(false)
      }
    }

    void bootstrap()
  }, [])

  useEffect(() => {
    if (!selectedSessionId) {
      return
    }

    startTransition(() => {
      void api
        .getSessionDetail(selectedSessionId)
        .then((detail) => {
          setSessionDetail(detail)
          setMessages(detail.messages)
          setArtifacts(detail.artifacts)
          if (detail.model) {
            setSelectedModel(detail.model)
          }
        })
        .catch((error: unknown) => {
          setStatusTone('error')
          setStatusText(error instanceof Error ? error.message : '会话加载失败。')
        })
    })
  }, [selectedSessionId])

  useEffect(() => {
    if (!preview && filteredFiles[0]) {
      void handlePreviewFile(filteredFiles[0].path)
    }
  }, [filteredFiles, preview])

  async function refreshShell(targetSessionId?: string) {
    const [overviewData, sessionData] = await Promise.all([
      api.getOverview(),
      api.getSessions(),
    ])
    setOverview(overviewData)
    setSessions(sessionData)

    const nextSessionId = targetSessionId ?? selectedSessionId ?? sessionData[0]?.session_id
    if (nextSessionId) {
      const detail = await api.getSessionDetail(nextSessionId)
      setSelectedSessionId(nextSessionId)
      setSessionDetail(detail)
      setMessages(detail.messages)
      setArtifacts(detail.artifacts)
    }
  }

  async function handlePreviewFile(path: string) {
    try {
      const payload = await api.previewWorkspaceFile(path)
      setPreview(payload)
    } catch (error) {
      setStatusTone('error')
      setStatusText(error instanceof Error ? error.message : '文件预览失败。')
    }
  }

  function toggleSkill(name: string) {
    setSelectedSkills((current) =>
      current.includes(name) ? current.filter((item) => item !== name) : [...current, name],
    )
  }

  function toggleFile(path: string) {
    setSelectedFiles((current) =>
      current.includes(path) ? current.filter((item) => item !== path) : [...current, path],
    )
  }

  function resetComposer() {
    setComposerValue('')
    setAttachments([])
    setSelectedFiles([])
  }

  async function sendRun() {
    const content = composerValue.trim()
    if (!content || !selectedModel || isSending) return

    const optimisticUser: MessageRecord = {
      id: Date.now(),
      role: 'user',
      content,
      model: selectedModel,
      created_at: new Date().toISOString(),
    }

    const optimisticAssistant: MessageRecord = {
      id: Date.now() + 1,
      role: 'assistant',
      content: '',
      model: selectedModel,
      created_at: new Date().toISOString(),
    }

    setIsSending(true)
    setStatusTone('live')
    setStatusText('正在运行，本地输出与产物会持续流式更新。')
    setMessages((current) => [...current, optimisticUser, optimisticAssistant])

    try {
      const run = await api.createRun({
        session_id: selectedSessionId ?? undefined,
        input: { type: 'text', content },
        model: selectedModel,
        attachments,
        skill_names: selectedSkills,
        context_files: selectedFiles,
        agent_mode: selectedMode,
      })

      setSelectedSessionId(run.session_id)
      abortRef.current = new AbortController()

      await api.streamRun(
        run.stream_url,
        (event: RunStreamEvent) => {
          if (event.type === 'message_delta') {
            setMessages((current) =>
              current.map((item, index) =>
                index === current.length - 1
                  ? { ...item, content: `${item.content}${event.delta}` }
                  : item,
              ),
            )
          }

          if (event.type === 'artifact' && event.artifact) {
            setArtifacts((current) => [...current, event.artifact!])
          }

          if (event.type === 'tool_event') {
            setStatusTone('live')
            setStatusText(event.message)
          }

          if (event.type === 'error') {
            setStatusTone('error')
            setStatusText(event.message || 'Run failed.')
          }

          if (event.type === 'run_status' && event.status === 'completed') {
            setStatusTone('idle')
            setStatusText('运行完成，上下文与记忆已更新。')
          }
        },
        abortRef.current.signal,
      )

      await refreshShell(run.session_id)
      resetComposer()
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        setStatusTone('idle')
        setStatusText('已在前端停止流式显示，后端任务可能仍在后台结束。')
      } else {
        setStatusTone('error')
        setStatusText(error instanceof Error ? error.message : '运行失败。')
      }
    } finally {
      setIsSending(false)
      abortRef.current = null
    }
  }

  function stopRun() {
    abortRef.current?.abort()
    setStatusTone('idle')
    setStatusText('已在前端停止流式显示，后端任务可能仍在后台结束。')
    setIsSending(false)
  }

  const showWelcome = messages.length === 0

  return (
    <main className="app-shell overflow-x-hidden w-full max-w-full">
      <header className="command-bar">
        <div className="brand-lockup">
          <div className="brand-mark">
            <SquaresFour size={22} weight="fill" />
          </div>
          <div>
            <p className="eyebrow">本地智能体控制台</p>
            <h1>面向个人知识与任务流的本地智能体系统</h1>
          </div>
        </div>

        <div className="command-actions">
          <button
            type="button"
            className="surface-button"
            onClick={() => {
              setSelectedSessionId(null)
              setSessionDetail(null)
              setMessages([])
              setArtifacts([])
              setStatusTone('idle')
              setStatusText('新的空白会话已就绪。')
            }}
          >
            <Plus size={18} />
            新建会话
          </button>
          <button type="button" className="surface-button" onClick={() => void refreshShell()}>
            <ArrowsClockwise size={18} />
            刷新
          </button>
          <div className={`status-pill ${statusTone}`}>
            <Waveform size={16} />
            <span>{statusText}</span>
          </div>
        </div>
      </header>

      <section className="control-layout">
        <aside className="workspace-rail">
          <section className="rail-panel brand-panel">
            <p className="eyebrow">控制中心</p>
            <h2>面向研究、构建与分析的本地优先智能体系统</h2>
            <p className="panel-copy">
              以高质感控制台体验为核心，围绕现有 FastAPI、记忆层和 LangGraph
              底座重新组织，让主界面更聚焦、更适合长期使用。
            </p>
          </section>

          <section className="rail-panel">
            <div className="panel-heading">
              <span>会话归档</span>
              <ChatCircleText size={18} />
            </div>
            <input
              className="ghost-input"
              placeholder="筛选会话"
              value={sessionSearch}
              onChange={(event) => {
                setSessionSearch(event.target.value)
                setSessionPage(1)
              }}
            />
            <div className="session-list">
              {pagedSessions.length === 0 ? (
                <div className="empty-card">
                  <p>还没有会话记录。</p>
                  <span>首次运行后会出现在这里。</span>
                </div>
              ) : (
                pagedSessions.map((session) => (
                  <button
                    type="button"
                    key={session.session_id}
                    className={`session-card ${selectedSessionId === session.session_id ? 'active' : ''}`}
                    onClick={() => setSelectedSessionId(session.session_id)}
                  >
                    <div className="session-card-top">
                      <strong>{session.title}</strong>
                      <span>{session.message_count}</span>
                    </div>
                    <p>{session.preview}</p>
                    <div className="session-card-meta">
                      <span>{session.model ?? '未指定模型'}</span>
                      <span>{formatTime(session.last_active_at)}</span>
                    </div>
                  </button>
                ))
              )}
            </div>
            <div className="pager-row">
              <button
                type="button"
                className="pager-button"
                disabled={sessionPage <= 1}
                onClick={() => setSessionPage((value) => Math.max(1, value - 1))}
              >
                <CaretLeft size={16} />
              </button>
              <span className="pager-label">
                第 {effectiveSessionPage} / {sessionPageCount} 页
              </span>
              <button
                type="button"
                className="pager-button"
                disabled={effectiveSessionPage >= sessionPageCount}
                onClick={() => setSessionPage((value) => Math.min(sessionPageCount, value + 1))}
              >
                <CaretRight size={16} />
              </button>
            </div>
          </section>

          <section className="rail-panel">
            <div className="panel-heading">
              <span>模型编排</span>
              <Stack size={18} />
            </div>
            <div className="model-groups">
              {Object.entries(groupedModels).map(([provider, items]) => (
                <div key={provider} className="model-group">
                  <p className="mini-label">{provider}</p>
                  {items.map((item) => (
                    <button
                      key={item.name}
                      type="button"
                      className={`model-card ${selectedModel === item.name ? 'selected' : ''}`}
                      onClick={() => setSelectedModel(item.name)}
                    >
                      <div className="model-card-top">
                        <strong>{item.label}</strong>
                        <span>{latencyTierLabel(item.latency_tier)}</span>
                      </div>
                      <p>{item.description || '本地模型路由壳层'}</p>
                      <div className="capability-row">
                        {item.capabilities.map((capability) => (
                          <span key={capability} className="capability-chip">
                            {capabilityLabel(capability)}
                          </span>
                        ))}
                      </div>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </section>
        </aside>

        <section className="conversation-column">
          <div ref={canvasRef} className="conversation-scroll">
            <section ref={welcomeRef} className="hero-stage">
              <nav className="floating-nav" data-reveal>
                <span>工作区</span>
                <span>对话</span>
                <span>上下文</span>
              </nav>

              <div className="dialogue-hero" data-reveal>
                <div className="dialogue-hero-copy">
                  <p className="eyebrow">对话区域</p>
                  <h2>在这里发起你的任务、整理知识，并持续推进当前工作流。</h2>
                  <p className="hero-subtitle">
                    选择模型、附加技能或文件上下文后，直接在下方输入框开始新一轮对话。
                  </p>
                </div>
                <div className="dialogue-hero-meta">
                  <span className="hero-meta-chip">当前模式：{MODE_LABELS[selectedMode]}</span>
                  <span className="hero-meta-chip">当前模型：{selectedModel || '未选择'}</span>
                </div>
              </div>
            </section>

            <section className="content-switcher">
              <div className="tab-row">
                {CENTER_TABS.map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    className={`tab-chip ${centerTab === tab ? 'active' : ''}`}
                    onClick={() => setCenterTab(tab)}
                  >
                    {tab}
                  </button>
                ))}
              </div>

              {centerTab === '总览' ? (
                <section ref={overviewRef} className="overview-section compact-section">
                  <div className="overview-heading">
                    <p className="eyebrow">系统状态</p>
                    <div className="insight-words">
                      {'本地优先的智能体壳层，把前端体验放在最前面，同时保留后端能力继续演进的空间。'
                        .split(' ')
                        .map((word, index) => (
                          <span key={`${word}-${index}`}>{word} </span>
                        ))}
                    </div>
                  </div>

                  <div className="overview-grid">
                    {overview?.metrics.map((metric) => (
                      <article key={metric.label} className="metric-card">
                        <span>{metric.label}</span>
                        <strong>{metric.value}</strong>
                        <p>{metric.detail}</p>
                      </article>
                    ))}
                    {overview?.panes.map((pane) => (
                      <article key={pane.title} className={`pane-card ${pane.tone}`}>
                        <h3>{pane.title}</h3>
                        <p>{pane.body}</p>
                      </article>
                    ))}
                  </div>
                </section>
              ) : null}

              {centerTab === '对话' ? (
                <section className="messages-section compact-section">
                  {showWelcome ? (
                    <div className="empty-conversation">
                      <Sparkle size={28} />
                      <h3>还没有对话内容</h3>
                      <p>选择模型、附加上下文并发起任务后，这里会展示流式输出。</p>
                    </div>
                  ) : (
                    messages.map((message) => (
                      <article key={message.id} className={messageTone(message.role)}>
                        <div className="message-meta">
                          <span>{message.role === 'user' ? '用户' : message.role === 'assistant' ? '智能体' : '系统'}</span>
                          <span>{message.model ?? '本地智能体'}</span>
                          <span>{formatTime(message.created_at)}</span>
                        </div>
                        <div className="message-bubble">
                          {message.role === 'assistant' ? (
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {message.content || '正在接收流式输出...'}
                            </ReactMarkdown>
                          ) : (
                            <p>{message.content}</p>
                          )}
                        </div>
                      </article>
                    ))
                  )}
                </section>
              ) : null}

              {centerTab === '产物' ? (
                <section className="artifact-strip compact-section">
                  <div className="panel-heading">
                    <span>产物与工具壳层</span>
                    <Sparkle size={18} />
                  </div>
                  <div className="artifact-grid">
                    {artifacts.length === 0 ? (
                      <div className="empty-card">
                        <p>还没有产物输出。</p>
                        <span>附件、文件注入和技能壳层会显示在这里。</span>
                      </div>
                    ) : (
                      artifacts.map((artifact) => (
                        <article key={artifact.id} className={`artifact-card ${artifact.tone}`}>
                          <p>{artifactKindLabel(artifact.kind)}</p>
                          <h3>{artifact.title}</h3>
                          <pre>{artifact.body}</pre>
                        </article>
                      ))
                    )}
                  </div>
                </section>
              ) : null}
            </section>
          </div>

          <footer className="composer-shell">
            <div className="composer-top">
              <div className="mode-row">
                {MODES.map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    className={`mode-chip ${selectedMode === mode ? 'active' : ''}`}
                    onClick={() => setSelectedMode(mode)}
                  >
                    {MODE_LABELS[mode]}
                  </button>
                ))}
              </div>

              <div className="attachment-row">
                <button
                  type="button"
                  className="icon-button"
                  onClick={() => setAttachments((current) => [...current, createLocalAttachment('image')])}
                >
                  <ImageSquare size={18} />
                  图片占位
                </button>
                <button
                  type="button"
                  className="icon-button"
                  onClick={() => setAttachments((current) => [...current, createLocalAttachment('audio')])}
                >
                  <MicrophoneStage size={18} />
                  音频占位
                </button>
                <button
                  type="button"
                  className="icon-button"
                  onClick={() => setAttachments((current) => [...current, createLocalAttachment('file')])}
                >
                  <FileCode size={18} />
                  文件占位
                </button>
              </div>
            </div>

            <textarea
              className="composer-input"
              value={composerValue}
              onChange={(event) => setComposerValue(event.target.value)}
              placeholder="输入任务目标、代码修改需求，或要求基于附加工作区上下文进行分析。"
            />

            <div className="composer-bottom">
              <div className="context-pills">
                {selectedSkills.map((skill) => (
                  <span key={skill} className="context-pill">
                    <Brain size={14} />
                    {skill}
                  </span>
                ))}
                {selectedFiles.map((file) => (
                  <span key={file} className="context-pill">
                    <FolderOpen size={14} />
                    {file}
                  </span>
                ))}
                {attachments.map((attachment) => (
                  <span key={attachment.id} className="context-pill">
                    <FileText size={14} />
                    {attachment.name}
                  </span>
                ))}
              </div>

              <div className="composer-actions">
                <select
                  className="model-select"
                  value={selectedModel}
                  onChange={(event) => setSelectedModel(event.target.value)}
                >
                  {models.map((model) => (
                    <option key={model.name} value={model.name}>
                      {model.label}
                    </option>
                  ))}
                </select>

                {isSending ? (
                  <button type="button" className="secondary-button compact" onClick={stopRun}>
                    停止流式输出
                  </button>
                ) : null}

                <button
                  type="button"
                  className="primary-button compact"
                  disabled={!composerValue.trim() || !selectedModel || isSending}
                  onClick={() => void sendRun()}
                >
                  {isSending ? <CircleNotch size={18} className="spin" /> : <PaperPlaneTilt size={18} />}
                  运行智能体
                </button>
              </div>
            </div>
          </footer>
        </section>

        <aside className="context-inspector">
          <section className="inspector-panel inspector-shell">
            <div className="panel-heading">
              <span>上下文检查器</span>
              <Brain size={18} />
            </div>
            <div className="tab-row inspector-tabs">
              {INSPECTOR_TABS.map((tab) => (
                <button
                  key={tab}
                  type="button"
                  className={`tab-chip ${inspectorTab === tab ? 'active' : ''}`}
                  onClick={() => setInspectorTab(tab)}
                >
                  {tab}
                </button>
              ))}
            </div>

            {inspectorTab === '摘要' ? (
              <div className="summary-card">
                <h3>{sessionDetail?.state.current_goal || '当前还没有明确目标'}</h3>
                <p>
                  {sessionDetail?.state.running_summary || '系统在完成一轮运行并反思后，会在这里生成滚动摘要。'}
                </p>
              </div>
            ) : null}

            {inspectorTab === '技能' ? (
              <div className="skill-grid">
                {skills.slice(0, 8).map((skill) => (
                  <button
                    key={skill.name}
                    type="button"
                    className={`skill-card ${selectedSkills.includes(skill.name) ? 'selected' : ''}`}
                    onClick={() => toggleSkill(skill.name)}
                  >
                    <strong>{skill.name}</strong>
                    <p>{skill.description || skill.category}</p>
                  </button>
                ))}
              </div>
            ) : null}

            {inspectorTab === '文件' ? (
              <>
                <input
                  className="ghost-input"
                  placeholder="筛选文件"
                  value={searchQuery}
                  onChange={(event) => {
                    setSearchQuery(event.target.value)
                    setFilePage(1)
                  }}
                />
                <div className="file-list">
                  {pagedFiles.map((file) => (
                    <button
                      key={file.path}
                      type="button"
                      className={`file-card ${selectedFiles.includes(file.path) ? 'selected' : ''}`}
                      onClick={() => {
                        toggleFile(file.path)
                        void handlePreviewFile(file.path)
                      }}
                    >
                      <div className="file-card-top">
                        <strong>{file.path}</strong>
                        <span>{file.extension || '文件'}</span>
                      </div>
                      <p>{Math.round(file.size_bytes / 1024)} KB</p>
                    </button>
                  ))}
                </div>
                <div className="pager-row">
                  <button
                    type="button"
                    className="pager-button"
                    disabled={filePage <= 1}
                    onClick={() => setFilePage((value) => Math.max(1, value - 1))}
                  >
                    <CaretLeft size={16} />
                  </button>
                  <span className="pager-label">
                    第 {effectiveFilePage} / {filePageCount} 页
                  </span>
                  <button
                    type="button"
                    className="pager-button"
                    disabled={effectiveFilePage >= filePageCount}
                    onClick={() => setFilePage((value) => Math.min(filePageCount, value + 1))}
                  >
                    <CaretRight size={16} />
                  </button>
                </div>
                <div className="preview-card">
                  <div className="panel-heading tight">
                    <span>文件预览</span>
                    <FileText size={16} />
                  </div>
                  {preview ? (
                    <>
                      <strong>{preview.path}</strong>
                      <pre>{preview.content}</pre>
                    </>
                  ) : (
                    <p className="muted-copy">选择一个文件后，这里会展示前几行内容。</p>
                  )}
                </div>
              </>
            ) : null}

            {inspectorTab === '事件' ? (
              <div className="event-list">
                {sessionDetail?.recent_events.length ? (
                  sessionDetail.recent_events.map((event) => (
                    <article key={event.id} className="event-card">
                      <div className="event-card-top">
                        <strong>{event.event_type}</strong>
                        <span>{event.duration_ms} ms</span>
                      </div>
                      <p>{event.model ?? '系统'}</p>
                      <div className="event-card-meta">
                        <span>{event.success ? '成功' : '失败'}</span>
                        <span>{formatTime(event.created_at)}</span>
                      </div>
                    </article>
                  ))
                ) : (
                  <div className="empty-card">
                    <p>还没有事件记录。</p>
                    <span>运行过程中的时间线会显示在这里。</span>
                  </div>
                )}
              </div>
            ) : null}

            {inspectorTab === '记忆' ? (
              <div className="memory-list">
                {sessionDetail?.memories.length ? (
                  sessionDetail.memories.map((memory) => (
                    <article key={memory.id} className="memory-card">
                      <div className="memory-card-top">
                        <strong>{memory.memory_type}</strong>
                        <span>{memory.importance.toFixed(2)}</span>
                      </div>
                      <p>{memory.content}</p>
                    </article>
                  ))
                ) : (
                  <div className="empty-card">
                    <p>还没有长期记忆。</p>
                    <span>反思摘要和历史记忆会逐步沉淀在这里。</span>
                  </div>
                )}
              </div>
            ) : null}
          </section>
        </aside>
      </section>

      {isBooting ? (
        <div className="boot-overlay">
          <CircleNotch size={24} className="spin" />
          <span>正在启动本地控制台</span>
        </div>
      ) : null}
    </main>
  )
}

export default App
