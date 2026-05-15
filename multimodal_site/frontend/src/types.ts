export type AgentMode = 'chat' | 'analyze' | 'build' | 'research'

export type AttachmentKind = 'image' | 'audio' | 'file'

export type Capability =
  | 'chat'
  | 'vision'
  | 'reasoning'
  | 'fast'
  | 'local'

export interface ModelInfo {
  name: string
  provider: string
  label: string
  description: string
  enabled: boolean
  capabilities: Capability[]
  latency_tier: string
  context_window: string
}

export interface SessionListItem {
  session_id: string
  title: string
  preview: string
  model: string | null
  last_active_at: string | null
  run_status: string
  message_count: number
}

export interface MessageRecord {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  model: string | null
  created_at: string
}

export interface MemoryItem {
  id: number
  memory_type: string
  content: string
  tags: string[]
  importance: number
  created_at: string | null
}

export interface EventItem {
  id: number
  event_type: string
  model: string | null
  duration_ms: number
  success: boolean
  error_message: string
  metadata_json: string
  created_at: string
}

export interface ArtifactCard {
  id: string
  kind: string
  title: string
  body: string
  tone: string
}

export interface SessionDetail {
  session_id: string
  title: string
  model: string | null
  run_status: string
  message_count: number
  messages: MessageRecord[]
  memories: MemoryItem[]
  recent_events: EventItem[]
  attached_context: string[]
  active_skills: string[]
  state: {
    running_summary: string
    current_goal: string
    task_state_json: string
    updated_at: string | null
  }
  artifacts: ArtifactCard[]
}

export interface OverviewMetric {
  label: string
  value: string
  detail: string
}

export interface OverviewPane {
  title: string
  body: string
  tone: string
}

export interface OverviewResponse {
  metrics: OverviewMetric[]
  panes: OverviewPane[]
}

export interface SkillItem {
  name: string
  description: string
  path: string
  source: string
  category: string
}

export interface WorkspaceFileItem {
  path: string
  size_bytes: number
  extension: string
  group: string
}

export interface WorkspacePreview {
  path: string
  start_line: number
  end_line: number
  total_lines: number
  truncated: boolean
  content: string
}

export interface AttachmentRef {
  id: string
  kind: AttachmentKind
  name: string
  mime_type: string
  size_bytes: number
  local_path?: string | null
  preview_url?: string | null
  status?: string
}

export interface RunCreateResponse {
  run_id: string
  session_id: string
  stream_url: string
  status: string
}

export interface RunStreamEvent {
  type: 'message_delta' | 'run_status' | 'tool_event' | 'artifact' | 'error'
  run_id: string
  session_id: string
  timestamp: string
  delta: string
  status: string | null
  message: string
  artifact: ArtifactCard | null
  meta: Record<string, unknown>
}
