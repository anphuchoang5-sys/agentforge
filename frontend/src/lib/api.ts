// api.ts — 后端 REST/WebSocket 客户端
// 对应 backend/api/main.py（POST /api/submit + WS /ws/tasks/{task_id}）

const API_BASE = 'http://localhost:8000'
const WS_BASE = 'ws://localhost:8000'

export interface SubmitResponse {
  task_id: string
}

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
