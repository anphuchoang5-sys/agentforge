// agentClient.ts — 真实后端驱动的 Agent 工作流
// 替换掉 mocks/mockWebSocket.ts：不再模拟数据，接的是 backend/api 真实推送。
// 连不上后端（提交失败 / WebSocket 出错）直接报错给用户看，不做任何兜底假数据。

import { useAppStore, type AgentId, type LogEntry } from '@/store/appStore'
import { submitTask, connectTaskWebSocket } from './api'

type BackendEvent =
  | { type: 'log'; agent: string; message: string; level: LogEntry['level']; timestamp: number }
  | { type: 'node_status'; id: AgentId; status: 'idle' | 'running' | 'success' | 'error' }
  | { type: 'progress'; progress: number }
  | { type: 'done'; result: Record<string, unknown> }
  | { type: 'error'; message: string; detail?: string }

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

export async function startAgentWorkflow(requirement: string): Promise<void> {
  const store = useAppStore.getState()

  if (store.isRunning) {
    store.addLog({
      timestamp: Date.now(),
      agent: 'System',
      message: '已有任务在运行中，请等待完成',
      level: 'warn',
    })
    return
  }

  store.reset()
  store.setUserInput(requirement)
  store.setRunning(true)

  let taskId: string
  try {
    const res = await submitTask(requirement)
    taskId = res.task_id
    store.setCurrentTaskId(taskId)
  } catch (err) {
    store.addLog({
      timestamp: Date.now(),
      agent: 'System',
      message: `无法连接后端: ${errorMessage(err)}`,
      level: 'error',
    })
    store.setRunning(false)
    return
  }

  const ws = connectTaskWebSocket(taskId)

  ws.onmessage = (event) => {
    const data: BackendEvent = JSON.parse(event.data)
    const s = useAppStore.getState()

    switch (data.type) {
      case 'log':
        s.addLog({ timestamp: data.timestamp, agent: data.agent, message: data.message, level: data.level })
        break
      case 'node_status':
        s.updateNodeStatus(data.id, data.status)
        break
      case 'progress':
        s.setProgress(data.progress)
        break
      case 'done':
        s.addLog({ timestamp: Date.now(), agent: 'System', message: '全部任务完成', level: 'success' })
        s.setRunning(false)
        ws.close()
        break
      case 'error':
        s.addLog({ timestamp: Date.now(), agent: 'System', message: `执行出错: ${data.message}`, level: 'error' })
        s.setRunning(false)
        ws.close()
        break
    }
  }

  ws.onerror = () => {
    useAppStore.getState().addLog({
      timestamp: Date.now(),
      agent: 'System',
      message: 'WebSocket 连接失败，无法接收实时进度',
      level: 'error',
    })
    useAppStore.getState().setRunning(false)
  }

  ws.onclose = () => {
    // done/error 分支已经主动关闭过一次；这里兜的是"连接被后端/网络异常中断"的情况，
    // 不是假数据兜底，只是确保 isRunning 不会卡死在 true
    if (useAppStore.getState().isRunning) {
      useAppStore.getState().addLog({
        timestamp: Date.now(),
        agent: 'System',
        message: '连接已断开',
        level: 'error',
      })
      useAppStore.getState().setRunning(false)
    }
  }
}
