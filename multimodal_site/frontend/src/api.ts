import type {
  AgentMode,
  AttachmentRef,
  ModelInfo,
  OverviewResponse,
  RunCreateResponse,
  RunStreamEvent,
  SessionDetail,
  SessionListItem,
  SkillItem,
  WorkspaceFileItem,
  WorkspacePreview,
} from './types'

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  getOverview: () => getJson<OverviewResponse>('/api/overview'),
  getModels: () => getJson<ModelInfo[]>('/api/models'),
  getSessions: () => getJson<SessionListItem[]>('/api/sessions'),
  getSessionDetail: (sessionId: string) =>
    getJson<SessionDetail>(`/api/sessions/${encodeURIComponent(sessionId)}`),
  getSkills: () => getJson<SkillItem[]>('/api/skills'),
  getWorkspaceFiles: (commonOnly = true) =>
    getJson<WorkspaceFileItem[]>(
      `/api/workspace/files?limit=40&common_only=${String(commonOnly)}`,
    ),
  previewWorkspaceFile: (path: string) =>
    getJson<WorkspacePreview>(
      `/api/workspace/file?path=${encodeURIComponent(path)}&start_line=1&end_line=180`,
    ),
  createRun: async (payload: {
    session_id?: string
    input: { type: 'text'; content: string }
    model: string
    attachments: AttachmentRef[]
    skill_names: string[]
    context_files: string[]
    agent_mode: AgentMode
  }) => {
    const response = await fetch('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      throw new Error(`运行创建失败：${response.status}`)
    }

    return (await response.json()) as RunCreateResponse
  },
  streamRun: async (
    streamUrl: string,
    onEvent: (event: RunStreamEvent) => void,
    signal?: AbortSignal,
  ) => {
    const response = await fetch(streamUrl, { signal })
    if (!response.ok || !response.body) {
      throw new Error(`流式响应失败：${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) {
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue
        onEvent(JSON.parse(trimmed) as RunStreamEvent)
      }
    }

    if (buffer.trim()) {
      onEvent(JSON.parse(buffer) as RunStreamEvent)
    }
  },
}
