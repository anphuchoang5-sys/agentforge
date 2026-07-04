// agentClient.ts — 真实后端驱动的 Agent 工作流
// 接的是 backend/api（REST + WebSocket），不做假数据兜底。

import { useAppStore, type AgentId, type LogEntry, type FailedTest } from '@/store/appStore'
import { submitTask, connectTaskWebSocket, checkHealth, type HealthStatus } from './api'

// ============ 后端 WebSocket 事件类型 ============

type BackendEvent =
  | { type: 'log'; agent: string; message: string; level: LogEntry['level']; timestamp: number }
  | { type: 'node_status'; id: AgentId; status: 'idle' | 'running' | 'success' | 'error' }
  | { type: 'progress'; progress: number }
  | { type: 'iteration'; iteration: number }
  | { type: 'validator_result'; validation_passed: boolean; validation_logs: string[]; screenshot_path: string; failed_tests: FailedTest[]; app_path: string; app_type: string; iteration: number }
  | { type: 'done'; result: Record<string, unknown> }
  | { type: 'error'; message: string; detail?: string }

// ============ 工具函数 ============

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

// ============ 健康检查（页面初始化时调用） ============

export async function fetchBackendHealth(): Promise<HealthStatus | null> {
  try {
    return await checkHealth()
  } catch {
    return null
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

      case 'iteration':
        s.setIteration(data.iteration)
        break

      case 'validator_result':
        s.setValidationResult({
          passed: data.validation_passed,
          logs: data.validation_logs,
          screenshotBase64: data.screenshot_path,
          failedTests: data.failed_tests,
          iteration: data.iteration,
          appPath: data.app_path,
          appType: data.app_type,
        })
        // 把验证日志逐条写入终端日志
        for (const line of data.validation_logs) {
          // 根据日志行前缀判断级别
          const level: LogEntry['level'] = line.startsWith('✅')
            ? 'success'
            : line.startsWith('❌')
              ? 'error'
              : line.startsWith('⏭️')
                ? 'warn'
                : 'info'
          s.addLog({
            timestamp: Date.now(),
            agent: 'Validator',
            message: line,
            level,
          })
        }
        break

      case 'done':
        s.addLog({ timestamp: Date.now(), agent: 'System', message: '全部任务完成', level: 'success' })
        // done 事件里也可能夹带最后的 validator 结果
        if (data.result) {
          const r = data.result as Record<string, unknown>
          if (typeof r.validation_passed === 'boolean') {
            s.setValidationResult({
              passed: Boolean(r.validation_passed),
              logs: Array.isArray(r.validation_logs) ? r.validation_logs as string[] : [],
              screenshotBase64: typeof r.screenshot_path === 'string' ? r.screenshot_path as string : '',
              failedTests: Array.isArray(r.failed_tests) ? r.failed_tests as FailedTest[] : [],
              iteration: typeof r.iteration === 'number' ? r.iteration as number : s.iteration,
              appPath: typeof r.app_path === 'string' ? r.app_path as string : '',
              appType: typeof r.app_type === 'string' ? r.app_type as string : '',
            })
          }
        }
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
