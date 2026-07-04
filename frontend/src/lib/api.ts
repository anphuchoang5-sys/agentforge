// api.ts — 后端 REST/WebSocket 客户端
// 对应 backend/api/main.py（POST /api/submit + WS /ws/tasks/{task_id}）

const API_BASE = 'http://localhost:8000'
const WS_BASE = 'ws://localhost:8000'

// ============ 类型 ============

export interface SubmitResponse {
  task_id: string
}

export interface TokenMetric {
  name: string
  tokens: number
}

export interface HealthStatus {
  status: string
  pywinauto: boolean
  ruff: boolean
  py_compile: boolean
}

// ============ REST API ============

// 连不上后端就直接抛错，不做任何兜底/降级
export async function submitTask(userInput: string): Promise<SubmitResponse> {
  const resp = await fetch(`${API_BASE}/api/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_input: userInput }),
  })
  if (!resp.ok) {
    throw new Error(`提交失败: HTTP ${resp.status}`)
  }
  return resp.json()
}

export function connectTaskWebSocket(taskId: string): WebSocket {
  return new WebSocket(`${WS_BASE}/ws/tasks/${taskId}`)
}

// 连不上就抛错，调用方决定怎么展示（不做假数据兜底）
export async function fetchTokenMetrics(): Promise<TokenMetric[]> {
  const resp = await fetch(`${API_BASE}/api/metrics/tokens`)
  if (!resp.ok) {
    throw new Error(`获取 Token 统计失败: HTTP ${resp.status}`)
  }
  const data = await resp.json()
  return data.data
}

// 健康检查 — GET http://localhost:8901/health（Validator 专用端口）
// 注意：健康检查端口是 8901，不是 8000
export async function checkHealth(): Promise<HealthStatus> {
  const resp = await fetch('http://localhost:8901/health')
  if (!resp.ok) {
    throw new Error(`健康检查失败: HTTP ${resp.status}`)
  }
  return resp.json()
}
