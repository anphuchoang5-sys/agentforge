import { useCallback, useEffect, useRef, useState } from 'react'
import { useAppStore, type AgentStatus } from '@/store/appStore'
import { startAgentWorkflow as realStartAgentWorkflow } from '@/lib/agentClient'
import { startAgentWorkflow as mockStartAgentWorkflow } from '@/mocks/mockWebSocket'
import { fetchTokenMetrics } from '@/lib/api'

// 通过环境变量 VITE_USE_MOCK 控制模式：
//   VITE_USE_MOCK=true  → 使用 Mock 模拟数据（前端独立开发/演示）
//   不设置或设为 false  → 连接真实后端 127.0.0.1:8000
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const startAgentWorkflow = USE_MOCK ? mockStartAgentWorkflow : realStartAgentWorkflow
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LabelList,
} from 'recharts'

// ============ 图标组件 ============

function BotIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <circle cx="9" cy="14" r="1" fill="currentColor" />
      <circle cx="15" cy="14" r="1" fill="currentColor" />
      <path d="M9 17h6" />
    </svg>
  )
}

function SendIcon() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 2L11 13" />
      <path d="M22 2L15 22L11 13L2 9L22 2Z" />
    </svg>
  )
}

function TerminalIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="4,17 10,11 4,5" />
      <line x1="12" y1="19" x2="20" y2="19" />
    </svg>
  )
}

function FlowIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="5" r="2" />
      <circle cx="5" cy="19" r="2" />
      <circle cx="19" cy="19" r="2" />
      <path d="M12 7v4" />
      <path d="M12 15v2" />
      <path d="M7 17l-2 2m0 0l2 2m-2-2h14m0 0l-2-2m2 2l2 2" />
    </svg>
  )
}

function ImageIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <circle cx="8.5" cy="8.5" r="1.5" />
      <path d="M21 15l-5-5L5 21" />
    </svg>
  )
}

function RefreshIcon({ spinning }: { spinning?: boolean }) {
  return (
    <svg
      className={`w-3.5 h-3.5 ${spinning ? 'animate-spin' : ''}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
    >
      <path d="M21 2v6h-6M3 22v-6h6" />
      <path d="M21 8A9 9 0 0 0 4.6 14M3 16a9 9 0 0 0 16.4-6" />
    </svg>
  )
}

// ============ 状态指示灯 ============

function StatusDot({ status }: { status: AgentStatus }) {
  const colors: Record<AgentStatus, string> = {
    idle: 'bg-slate-300 dark:bg-slate-600',
    running: 'bg-blue-500 animate-pulse-node',
    success: 'bg-emerald-500',
    error: 'bg-red-500',
  }
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${colors[status]}`} />
}

// ============ Agent 节点项（流程图侧边栏用） ============

function AgentNodeItem({
  label,
  description,
  status,
  isLast,
}: {
  id: string
  label: string
  description?: string
  status: AgentStatus
  isLast: boolean
}) {
  return (
    <div className="flex items-start gap-3 relative">
      {/* 竖线 */}
      {!isLast && (
        <div className="absolute left-[11px] top-7 bottom-0 w-0.5 bg-slate-200 dark:bg-slate-700" />
      )}
      {/* 圆点 */}
      <div className="relative z-10 mt-1.5 flex-shrink-0">
        <StatusDot status={status} />
      </div>
      {/* 内容 */}
      <div
        className={`flex-1 pb-5 transition-opacity ${
          status === 'idle' ? 'opacity-50' : 'opacity-100'
        }`}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            {label}
          </span>
          {status === 'running' && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 animate-pulse-node">
              执行中
            </span>
          )}
          {status === 'success' && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
              完成
            </span>
          )}
          {status === 'error' && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300">
              失败
            </span>
          )}
        </div>
        {description && (
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            {description}
          </p>
        )}
      </div>
    </div>
  )
}

// ============ 进度条 ============

function ProgressBar({ progress }: { progress: number }) {
  return (
    <div className="w-full">
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs text-slate-500 dark:text-slate-400">执行进度</span>
        <span className="text-xs font-mono font-semibold text-slate-700 dark:text-slate-300">
          {progress}%
        </span>
      </div>
      <div className="w-full h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full transition-all duration-700 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}

// ============ 日志行（按前缀着色） ============

function LogLine({
  entry,
}: {
  entry: { agent: string; message: string; level: string; timestamp: number }
}) {
  const time = new Date(entry.timestamp).toLocaleTimeString('zh-CN', {
    hour12: false,
  })

  // 按消息前缀 emoji 决定文字颜色
  let textColor = 'text-slate-300 dark:text-slate-300'  // 默认白色
  if (entry.message.startsWith('✅')) {
    textColor = 'text-emerald-400'
  } else if (entry.message.startsWith('❌')) {
    textColor = 'text-red-400'
  } else if (entry.message.startsWith('⏭️')) {
    textColor = 'text-slate-500'
  }

  // 按 level 作为后备着色（无前缀时）
  const levelColors: Record<string, string> = {
    info: 'text-slate-300 dark:text-slate-300',
    warn: 'text-amber-400',
    error: 'text-red-400',
    success: 'text-emerald-400',
  }
  const fallbackColor = levelColors[entry.level] || 'text-slate-300'

  return (
    <div className="flex gap-2 py-0.5 font-mono text-xs leading-relaxed animate-slide-in">
      <span className="text-slate-500 dark:text-slate-600 flex-shrink-0">{time}</span>
      <span className="text-violet-400 dark:text-violet-400 flex-shrink-0 font-semibold">
        [{entry.agent}]
      </span>
      <span className={entry.message.match(/^[✅❌⏭️]/) ? textColor : fallbackColor}>
        {entry.message}
      </span>
    </div>
  )
}

// ============ 提示示例 ============

const EXAMPLE_PROMPTS = [
  '开发一个待办事项桌面应用，支持添加、完成、删除任务',
  '构建一个简单的个人记账应用，支持收入支出记录和月度统计',
  '做一个天气预报查询工具，输入城市名显示天气信息',
]

// ============ Token 消耗 Mock 数据 ============

const TOKEN_DATA = [
  { name: 'Commander', tokens: 1200 },
  { name: 'Backend', tokens: 600 },
  { name: 'Frontend', tokens: 400 },
  { name: 'Test', tokens: 300 },
  { name: 'UIValidator', tokens: 200 },
]

// ============ 主组件 ============

function App() {
  const {
    userInput,
    progress,
    logs,
    nodeStatus,
    isRunning,
    iteration,
    screenshotBase64,
    validationPassed,
    failedTests,
    setUserInput,
  } = useAppStore()

  const logsEndRef = useCallback(
    (el: HTMLDivElement | null) => {
      if (el) el.scrollTop = el.scrollHeight
    },
    [logs.length]
  )

  // Token 消耗数据：初始用静态兜底，任务完成后自动从后端拉取真实数据
  const [tokenData, setTokenData] = useState(TOKEN_DATA)
  const [tokenLoading, setTokenLoading] = useState(false)
  const prevRunning = useRef(isRunning)

  const refreshTokens = useCallback(() => {
    setTokenLoading(true)
    fetchTokenMetrics()
      .then((data) => {
        if (data && data.length > 0) setTokenData(data)
      })
      .catch(() => {
        // 接口失败静默兜底，保留现有数据（可能是 TOKEN_DATA 或上一轮的真实数据）
      })
      .finally(() => setTokenLoading(false))
  }, [])

  // 任务执行完成时（isRunning: true → false）自动刷新
  useEffect(() => {
    if (prevRunning.current && !isRunning) {
      refreshTokens()
    }
    prevRunning.current = isRunning
  }, [isRunning, refreshTokens])

  // 页面首次加载时也拉一次
  useEffect(() => {
    refreshTokens()
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  const handleRun = () => {
    const input = userInput.trim()
    if (!input || isRunning) return
    startAgentWorkflow(input)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleRun()
    }
  }

  const handleExampleClick = (prompt: string) => {
    if (isRunning) return
    setUserInput(prompt)
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      {/* ===== 顶部导航 ===== */}
      <header className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center">
            <BotIcon className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-800 dark:text-slate-100 tracking-tight">
              AgentForge
            </h1>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 -mt-0.5">
              多角色 Agent 协作平台
            </p>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${
                isRunning
                  ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
                  : 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400'
              }`}
            >
              {isRunning ? '⚡ 运行中' : '⏸ 就绪'}
            </span>
          </div>
        </div>
      </header>

      {/* ===== 主内容区 ===== */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* --- 输入区 --- */}
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 mb-5 shadow-sm">
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <input
                type="text"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入需求，例如：开发一个待办事项桌面应用…"
                disabled={isRunning}
                className="w-full h-11 px-4 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm text-slate-800 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-400 disabled:opacity-60 disabled:cursor-not-allowed transition-all"
              />
            </div>
            <button
              onClick={handleRun}
              disabled={!userInput.trim() || isRunning}
              className="h-11 px-5 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white text-sm font-semibold flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-[0.97]"
            >
              <SendIcon />
              开始执行
            </button>
          </div>

          {/* 示例提示 */}
          <div className="flex gap-2 mt-3 flex-wrap">
            {EXAMPLE_PROMPTS.map((p) => (
              <button
                key={p}
                onClick={() => handleExampleClick(p)}
                disabled={isRunning}
                className="text-xs px-2.5 py-1 rounded-full border border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-700 dark:hover:text-slate-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {p.length > 28 ? p.slice(0, 28) + '…' : p}
              </button>
            ))}
          </div>

          {/* 进度条 + 迭代轮次 */}
          <div className="mt-4 flex items-end gap-4">
            <div className="flex-1">
              <ProgressBar progress={progress} />
            </div>
            {iteration > 0 && (
              <div className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800">
                <span className="text-[10px] text-indigo-500 dark:text-indigo-400">🔄</span>
                <span className="text-xs font-semibold text-indigo-700 dark:text-indigo-300">
                  第 {iteration} 轮验证
                </span>
                {validationPassed && iteration > 0 && (
                  <span className="text-[10px] text-emerald-500">✓ 已通过</span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* --- 双栏布局 --- */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* 左栏：Agent 流程图 + 验证结果概要 */}
          <div className="lg:col-span-1 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <FlowIcon />
              <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                Agent 协作流程
              </h2>
            </div>
            <div className="pl-1">
              {nodeStatus.map((node, i) => (
                <AgentNodeItem
                  key={node.id}
                  id={node.id}
                  label={node.label}
                  description={node.description}
                  status={node.status}
                  isLast={i === nodeStatus.length - 1}
                />
              ))}
            </div>
            {/* 图例 */}
            <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center gap-4 text-[10px] text-slate-400">
              <span className="flex items-center gap-1">
                <StatusDot status="idle" /> 等待
              </span>
              <span className="flex items-center gap-1">
                <StatusDot status="running" /> 执行中
              </span>
              <span className="flex items-center gap-1">
                <StatusDot status="success" /> 完成
              </span>
              <span className="flex items-center gap-1">
                <StatusDot status="error" /> 失败
              </span>
            </div>

          </div>

          {/* 右栏：截图 + 终端日志 + 失败测试 */}
          <div className="lg:col-span-2 space-y-4">
            {/* 截图展示区 */}
            {screenshotBase64 && (
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                <div className="flex items-center gap-2 px-4 py-2.5 bg-slate-50 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
                  <ImageIcon />
                  <span className="text-xs text-slate-500 dark:text-slate-400 font-semibold">
                    应用截图
                  </span>
                  <span className="text-[10px] text-slate-400 ml-auto">
                    第 {iteration} 轮
                  </span>
                </div>
                <div className="p-3 bg-slate-100 dark:bg-slate-950">
                  <img
                    src={`data:image/png;base64,${screenshotBase64}`}
                    alt="应用运行截图"
                    className="max-w-full h-auto rounded border border-slate-200 dark:border-slate-700 mx-auto"
                    style={{ maxHeight: 320 }}
                  />
                </div>
              </div>
            )}

            {/* 终端日志 */}
            <div className="bg-slate-900 dark:bg-slate-950 rounded-xl border border-slate-700 dark:border-slate-800 shadow-sm overflow-hidden">
              {/* 标题栏 */}
              <div className="flex items-center gap-2 px-4 py-2.5 bg-slate-800 dark:bg-slate-900 border-b border-slate-700 dark:border-slate-800">
                <div className="flex gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-red-500/80" />
                  <span className="w-3 h-3 rounded-full bg-amber-500/80" />
                  <span className="w-3 h-3 rounded-full bg-emerald-500/80" />
                </div>
                <TerminalIcon />
                <span className="text-xs text-slate-400 font-semibold">终端日志</span>
                <span className="text-[10px] text-slate-600 ml-auto">
                  {logs.length} 条
                </span>
              </div>
              {/* 日志内容 */}
              <div
                ref={logsEndRef}
                className="h-[360px] overflow-y-auto p-4 log-scrollbar"
              >
                {logs.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-slate-600 gap-2 opacity-60">
                    <TerminalIcon />
                    <p className="text-xs">等待任务启动...</p>
                    <p className="text-[10px] text-slate-700">
                      输入需求并点击「开始执行」
                    </p>
                  </div>
                ) : (
                  logs.map((entry) => <LogLine key={entry.id} entry={entry} />)
                )}
              </div>
            </div>

            {/* 失败测试明细 */}
            {failedTests.length > 0 && (
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                <div className="flex items-center gap-2 px-4 py-2.5 bg-red-50 dark:bg-red-950/30 border-b border-red-200 dark:border-red-900">
                  <span className="text-xs font-semibold text-red-700 dark:text-red-400">
                    ❌ 失败测试 ({failedTests.length})
                  </span>
                </div>
                <div className="divide-y divide-slate-100 dark:divide-slate-800">
                  {failedTests.map((ft, i) => (
                    <div
                      key={i}
                      className={`px-4 py-2.5 flex items-start gap-3 ${
                        ft.severity === 'error'
                          ? 'bg-red-50/50 dark:bg-red-950/10'
                          : 'bg-amber-50/50 dark:bg-amber-950/10'
                      }`}
                    >
                      <span
                        className={`mt-0.5 flex-shrink-0 w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold ${
                          ft.severity === 'error'
                            ? 'bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400'
                            : 'bg-amber-100 text-amber-600 dark:bg-amber-900/40 dark:text-amber-400'
                        }`}
                      >
                        {ft.severity === 'error' ? '✕' : '!'}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                            {ft.name}
                          </span>
                          <span
                            className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                              ft.severity === 'error'
                                ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400'
                                : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400'
                            }`}
                          >
                            {ft.severity}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                          {ft.reason}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* --- Token 消耗统计 --- */}
        <div className="mt-5 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              📊 Token 消耗统计
            </h2>
            <button
              onClick={refreshTokens}
              disabled={tokenLoading}
              className="ml-auto flex items-center gap-1 text-[11px] px-2 py-1 rounded-md text-slate-500 hover:text-slate-700 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-slate-800 disabled:opacity-50 transition-colors"
              title="刷新 Token 数据"
            >
              <RefreshIcon spinning={tokenLoading} />
              刷新
            </button>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={tokenData}
              margin={{ top: 20, right: 30, left: 0, bottom: 5 }}
            >
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 12, fill: '#64748b' }}
                  axisLine={{ stroke: '#cbd5e1' }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: '#64748b' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: '8px',
                    border: '1px solid #e2e8f0',
                    fontSize: '13px',
                  }}
                  formatter={(value: number) => [`${value.toLocaleString()} tokens`, '消耗量']}
                />
                <Bar dataKey="tokens" fill="#3b82f6" radius={[4, 4, 0, 0]}>
                  <LabelList
                    dataKey="tokens"
                    position="top"
                    style={{ fontSize: 12, fontWeight: 600, fill: '#3b82f6' }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
        </div>
      </main>

      {/* ===== 底部状态栏 ===== */}
      <footer className="border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <div className="max-w-7xl mx-auto px-4 py-2 flex items-center gap-4 text-[10px] text-slate-400">
          <span>AgentForge v1.0</span>
          <span className="text-slate-300 dark:text-slate-700">|</span>
          <span>Ollama + Qwen2.5-Coder</span>
          <span className="text-slate-300 dark:text-slate-700">|</span>
          <span>LangGraph 编排</span>
          {iteration > 0 && (
            <>
              <span className="text-slate-300 dark:text-slate-700">|</span>
              <span>验证轮次: {iteration}/5</span>
              <span className={validationPassed ? 'text-emerald-500' : 'text-red-400'}>
                {validationPassed ? '✓ 通过' : '✗ 未通过'}
              </span>
            </>
          )}
          {isRunning && (
            <>
              <span className="text-slate-300 dark:text-slate-700">|</span>
              <span className="text-blue-500 animate-pulse-node">⚡ Agent 协作中...</span>
            </>
          )}
        </div>
      </footer>
    </div>
  )
}

export default App
