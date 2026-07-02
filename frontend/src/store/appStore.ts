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

  // 动作
  setUserInput: (input: string) => void
  setProgress: (progress: number) => void
  addLog: (entry: Omit<LogEntry, 'id'>) => void
  updateNodeStatus: (id: AgentId, status: AgentStatus) => void
  setRunning: (running: boolean) => void
  setCurrentTaskId: (id: string | null) => void
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

  reset: () => {
    logIdCounter = 0
    set({
      userInput: '',
      progress: 0,
      logs: [],
      nodeStatus: initialNodes.map((n) => ({ ...n, status: 'idle' as AgentStatus })),
      isRunning: false,
      currentTaskId: null,
    })
  },
}))
