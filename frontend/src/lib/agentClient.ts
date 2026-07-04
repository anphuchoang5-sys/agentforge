// agentClient.ts — 真实后端驱动的 Agent 工作流
// 对接 backend/api（POST /api/submit → WS /ws/tasks/{task_id}）
// 连不上就直接报错，不做假数据兜底。

import { useAppStore, type AgentId, type LogEntry, type FailedTest } from '@/store/appStore'
import { submitTask, connectTaskWebSocket } from './api'

// ============ 后端推送的原始 JSON 格式 ============
// 带 type 字段的：{ type: 'log' | 'node_status' | 'progress' | 'iteration' | 'done' | 'error', ... }
// Validator 结果（无 type 字段，扁平 JSON）：
//   { passed: bool, logs: string[], screenshot: string, failed_tests: [...], iteration: number }

interface RawValidatorPayload {
  passed: boolean
  logs: string[]
  screenshot: string
  failed_tests: FailedTest[]
  app_path?: string
  app_type?: string
  iteration: number
}

type RawEvent =
  | { type: 'log'; agent: string; message: string; level: LogEntry['level']; timestamp: number }
  | { type: 'node_status'; id: AgentId; status: 'idle' | 'running' | 'success' | 'error' }
  | { type: 'progress'; progress: number }
  | { type: 'iteration'; iteration: number }
  | { type: 'done'; result?: Record<string, unknown> }
  | { type: 'error'; message: string; detail?: string }

// ============ 工具函数 ============

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

/** 判断一个 JSON 对象是否是 Validator 结果（无 type 字段，但包含 passed 布尔值） */
function isValidatorPayload(data: Record<string, unknown>): data is RawValidatorPayload {
  return typeof data.passed === 'boolean'
}

/** 把 Validator 结果写入 Zustand store */
function applyValidatorResult(s: ReturnType<typeof useAppStore.getState>, data: RawValidatorPayload): void {
  s.setValidationResult({
    passed: data.passed,
    logs: data.logs,
    screenshotBase64: data.screenshot,
    failedTests: data.failed_tests,
    iteration: data.iteration,
    appPath: data.app_path || '',
    appType: data.app_type || '',
  })

  for (const line of data.logs) {
    const level: LogEntry['level'] = line.startsWith('✅')
      ? 'success'
      : line.startsWith('❌')
        ? 'error'
        : line.startsWith('⏭️')
          ? 'warn'
          : 'info'
    s.addLog({ timestamp: Date.now(), agent: 'Validator', message: line, level })
  }
}

// ============ 主入口 ============

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

  // 1. POST 提交任务
  let taskId: string
  try {
    store.addLog({ timestamp: Date.now(), agent: 'System', message: '正在提交任务到后端...', level: 'info' })
    const res = await submitTask(requirement)
    taskId = res.task_id
    store.setCurrentTaskId(taskId)
    store.addLog({ timestamp: Date.now(), agent: 'System', message: `任务已创建: ${taskId}`, level: 'success' })
  } catch (err) {
    store.addLog({
      timestamp: Date.now(),
      agent: 'System',
      message: `任务提交失败 — ${errorMessage(err)}`,
      level: 'error',
    })
    store.setRunning(false)
    return
  }

  // 2. 建立 WebSocket，带超时保护
  const CONNECTION_TIMEOUT_MS = 8000
  let messageReceived = false
  let connectionTimer: ReturnType<typeof setTimeout> | null = null

  const ws = connectTaskWebSocket(taskId)

  const teardown = () => {
    if (connectionTimer) { clearTimeout(connectionTimer); connectionTimer = null }
  }

  connectionTimer = setTimeout(() => {
    if (!messageReceived) {
      teardown()
      ws.close()
      useAppStore.getState().addLog({
        timestamp: Date.now(),
        agent: 'System',
        message: `WebSocket 连接超时（${CONNECTION_TIMEOUT_MS / 1000}s 未收到任何消息）`,
        level: 'error',
      })
      useAppStore.getState().setRunning(false)
    }
  }, CONNECTION_TIMEOUT_MS)

  // 3. 消息处理
  ws.onmessage = (event) => {
    messageReceived = true
    teardown() // 收到第一条消息就清除超时

    let data: Record<string, unknown>
    try {
      data = JSON.parse(event.data)
    } catch {
      useAppStore.getState().addLog({
        timestamp: Date.now(),
        agent: 'System',
        message: `收到非法 JSON: ${String(event.data).slice(0, 200)}`,
        level: 'warn',
      })
      return
    }

    const s = useAppStore.getState()

    // 判断事件类型：优先看是否有 type 字段；其次看是否是 Validator 扁平结构
    if (typeof data.type === 'string') {
      const typed = data as unknown as RawEvent
      switch (typed.type) {
        case 'log':
          s.addLog({ timestamp: typed.timestamp || Date.now(), agent: typed.agent, message: typed.message, level: typed.level })
          break
        case 'node_status':
          s.updateNodeStatus(typed.id, typed.status)
          break
        case 'progress':
          s.setProgress(typed.progress)
          break
        case 'iteration':
          s.setIteration(typed.iteration)
          break
        case 'done':
          // done 事件可能夹带最后的 validator 结果
          if (typed.result && typeof typed.result === 'object') {
            const r = typed.result as Record<string, unknown>
            if (typeof r.passed === 'boolean') {
              applyValidatorResult(s, r as unknown as RawValidatorPayload)
            }
          }
          s.addLog({ timestamp: Date.now(), agent: 'System', message: '全部任务完成', level: 'success' })
          s.setRunning(false)
          ws.close()
          break
        case 'error':
          s.addLog({ timestamp: Date.now(), agent: 'System', message: `执行出错: ${typed.message}`, level: 'error' })
          s.setRunning(false)
          ws.close()
          break
        default:
          s.addLog({ timestamp: Date.now(), agent: 'System', message: `未知事件类型: ${typed.type}`, level: 'warn' })
      }
    } else if (isValidatorPayload(data)) {
      // 无 type 字段，但包含 passed — Validator 结果（扁平 JSON）
      applyValidatorResult(s, data)
    } else {
      s.addLog({
        timestamp: Date.now(),
        agent: 'System',
        message: `收到无法识别的事件: ${JSON.stringify(data).slice(0, 200)}`,
        level: 'warn',
      })
    }
  }

  // 4. 连接错误
  ws.onerror = () => {
    teardown()
    useAppStore.getState().addLog({
      timestamp: Date.now(),
      agent: 'System',
      message: `WebSocket 连接失败（ws://127.0.0.1:8000/ws/tasks/${taskId}），请确认后端已启动`,
      level: 'error',
    })
    useAppStore.getState().setRunning(false)
  }

  // 5. 连接关闭
  ws.onclose = () => {
    teardown()
    if (useAppStore.getState().isRunning) {
      if (!messageReceived) {
        useAppStore.getState().addLog({
          timestamp: Date.now(),
          agent: 'System',
          message: 'WebSocket 连接在收到任何消息前关闭 — 后端可能拒绝了连接或崩溃',
          level: 'error',
        })
      } else {
        useAppStore.getState().addLog({
          timestamp: Date.now(),
          agent: 'System',
          message: 'WebSocket 连接意外断开',
          level: 'error',
        })
      }
      useAppStore.getState().setRunning(false)
    }
  }
}
