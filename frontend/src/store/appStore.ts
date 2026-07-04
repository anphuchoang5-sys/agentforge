import { create } from 'zustand'

// ============ 类型定义 ============

export type AgentStatus = 'idle' | 'running' | 'success' | 'error'

export interface NodeStatus {
  id: string
  label: string
  status: AgentStatus
  description?: string
}

export interface LogEntry {
  id: number
  timestamp: number
  agent: string
  message: string
  level: 'info' | 'warn' | 'error' | 'success'
}

export interface FailedTest {
  name: string
  reason: string
  severity: 'error' | 'warning'
}

export interface ValidationResult {
  passed: boolean
  logs: string[]
  screenshotBase64: string
  failedTests: FailedTest[]
  iteration: number
  appPath: string
  appType: string
}

export type AgentId =
  | 'commander'
  | 'backend'
  | 'frontend'
  | 'test'
  | 'uivalidator'
  | 'validator'

// ============ 初始节点状态 ============

const initialNodes: NodeStatus[] = [
  { id: 'commander', label: 'Commander', description: '需求分析与任务拆解', status: 'idle' },
  { id: 'frontend', label: 'FrontendExpert', description: '前端 UI 代码生成', status: 'idle' },
  { id: 'backend', label: 'BackendExpert', description: '后端 API / 数据库实现', status: 'idle' },
  { id: 'test', label: 'TestExpert', description: '测试用例生成与执行', status: 'idle' },
  { id: 'uivalidator', label: 'UIValidator', description: '桌面 / Web UI 自动化验证', status: 'idle' },
  { id: 'validator', label: 'Validator', description: '代码质量审计与验收', status: 'idle' },
]

// ============ Store 接口 ============

interface AppState {
  // 用户输入的原始需求
  userInput: string

  // 整体进度 0-100
  progress: number

  // 日志列表
  logs: LogEntry[]

  // Agent 节点状态
  nodeStatus: NodeStatus[]

  // 是否正在执行任务
  isRunning: boolean

  // 当前任务 ID
  currentTaskId: string | null

  // ===== Validator 结果 =====

  // 是否通过验证
  validationPassed: boolean

  // 验证日志（逐条展示）
  validationLogs: string[]

  // 截图 base64 PNG（空串 = 暂无截图）
  screenshotBase64: string

  // 失败测试明细
  failedTests: FailedTest[]

  // 当前迭代轮次（1-5）
  iteration: number

  // 应用路径 & 类型
  appPath: string
  appType: string

  // ===== 后端健康状态 =====
  backendHealthy: boolean | null  // null = 探测中 / 未探测
  healthDetails: Record<string, boolean>  // 各组件可用状态

  // ===== 动作 =====
  setUserInput: (input: string) => void
  setProgress: (progress: number) => void
  addLog: (entry: Omit<LogEntry, 'id'>) => void
  updateNodeStatus: (id: AgentId, status: AgentStatus) => void
  setRunning: (running: boolean) => void
  setCurrentTaskId: (id: string | null) => void

  // Validator 相关
  setValidationResult: (result: ValidationResult) => void
  setIteration: (iteration: number) => void
  setScreenshot: (base64: string) => void

  // 健康检查
  setBackendHealth: (healthy: boolean | null, details: Record<string, boolean>) => void

  reset: () => void
}

// ============ Store 实现 ============

let logIdCounter = 0

export const useAppStore = create<AppState>((set) => ({
  userInput: '',
  progress: 0,
  logs: [],
  nodeStatus: initialNodes,
  isRunning: false,
  currentTaskId: null,

  // Validator 结果初始值
  validationPassed: false,
  validationLogs: [],
  screenshotBase64: '',
  failedTests: [],
  iteration: 0,
  appPath: '',
  appType: '',

  // 健康检查初始值
  backendHealthy: null,
  healthDetails: {},

  setUserInput: (input) => set({ userInput: input }),

  setProgress: (progress) => set({ progress: Math.min(100, Math.max(0, progress)) }),

  addLog: (entry) =>
    set((state) => ({
      logs: [
        ...state.logs,
        { ...entry, id: ++logIdCounter },
      ],
    })),

  updateNodeStatus: (id, status) =>
    set((state) => ({
      nodeStatus: state.nodeStatus.map((n) =>
        n.id === id ? { ...n, status } : n
      ),
    })),

  setRunning: (running) => set({ isRunning: running }),

  setCurrentTaskId: (id) => set({ currentTaskId: id }),

  // Validator 相关 actions
  setValidationResult: (result) =>
    set({
      validationPassed: result.passed,
      validationLogs: result.logs,
      screenshotBase64: result.screenshotBase64,
      failedTests: result.failedTests,
      iteration: result.iteration,
      appPath: result.appPath,
      appType: result.appType,
    }),

  setIteration: (iteration) => set({ iteration }),

  setScreenshot: (base64) => set({ screenshotBase64: base64 }),

  // 健康检查
  setBackendHealth: (healthy, details) =>
    set({ backendHealthy: healthy, healthDetails: details }),

  reset: () => {
    logIdCounter = 0
    set({
      userInput: '',
      progress: 0,
      logs: [],
      nodeStatus: initialNodes.map((n) => ({ ...n, status: 'idle' as AgentStatus })),
      isRunning: false,
      currentTaskId: null,
      validationPassed: false,
      validationLogs: [],
      screenshotBase64: '',
      failedTests: [],
      iteration: 0,
      appPath: '',
      appType: '',
    })
  },
}))
