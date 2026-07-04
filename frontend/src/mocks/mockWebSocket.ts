// mockWebSocket.ts — 模拟后端 Validator 推送
// 用于前端独立开发/演示，数据格式严格匹配真实后端接口。
//
// 用法：在 App.tsx 中把 import { startAgentWorkflow } from '@/lib/agentClient'
//       临时改成 import { startAgentWorkflow } from '@/mocks/mockWebSocket'
//       即可用模拟数据跑完整流程。

import { useAppStore, type AgentId, type FailedTest } from '@/store/appStore'

// ============ 模拟 Validator 输出（符合 C 的接口格式） ============

interface MockValidatorResult {
  passed: boolean
  logs: string[]
  screenshot: string   // base64 PNG，实际是空串或真实 base64
  failed_tests: FailedTest[]
  app_path: string
  app_type: string
  iteration: number
}

// 模拟一张 1x1 紫色像素 PNG 的 base64（最小有效 PNG，用于演示截图区）
const MOCK_SCREENSHOT_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPj/HwADBwIAMCbHYQAAAABJRU5ErkJggg=='

// 第 1 轮：有 warning + error，不通过
function mockResultRound1(): MockValidatorResult {
  return {
    passed: false,
    logs: [
      '✅ py_compile: app.py 编译通过',
      '✅ ruff: 代码风格检查通过 (0 issues)',
      '⏭️ pywinauto: 桌面环境未就绪，跳过 UI 交互测试',
      '❌ 功能测试: test_add_task 断言失败 — expected 3, got 0',
      '❌ 功能测试: test_delete_task — 删除按钮未找到',
    ],
    screenshot: MOCK_SCREENSHOT_BASE64,
    failed_tests: [
      { name: 'test_add_task', reason: '断言失败: expected 3, got 0', severity: 'error' },
      { name: 'test_delete_task', reason: '删除按钮未找到', severity: 'error' },
    ],
    app_path: './output/todo_app/app.py',
    app_type: 'tkinter',
    iteration: 1,
  }
}

// 第 2 轮：只剩 warning，通过
function mockResultRound2(): MockValidatorResult {
  return {
    passed: true,
    logs: [
      '✅ py_compile: app.py 编译通过',
      '✅ ruff: 代码风格检查通过 (0 issues)',
      '✅ 功能测试: test_add_task 通过',
      '✅ 功能测试: test_delete_task 通过',
      '✅ 功能测试: test_complete_task 通过',
      '⏭️ pywinauto: 桌面环境未就绪，跳过 UI 交互测试',
    ],
    screenshot: MOCK_SCREENSHOT_BASE64,
    failed_tests: [],
    app_path: './output/todo_app/app.py',
    app_type: 'tkinter',
    iteration: 2,
  }
}

// ============ 模拟工作流 ============

const AGENTS: { id: AgentId; label: string }[] = [
  { id: 'commander', label: 'Commander' },
  { id: 'backend', label: 'BackendExpert' },
  { id: 'frontend', label: 'FrontendExpert' },
  { id: 'test', label: 'TestExpert' },
  { id: 'uivalidator', label: 'UIValidator' },
  { id: 'validator', label: 'Validator' },
]

const MESSAGES: Record<string, string[]> = {
  commander: ['正在分析需求...', '需求拆解完成，生成 5 个子任务', '任务已分配给专家 Agent'],
  frontend: ['生成前端 UI 代码...', 'Tkinter 窗口布局完成', '按钮事件绑定完成'],
  backend: ['生成后端 API 代码...', 'SQLite 数据库初始化完成', 'CRUD 接口实现完成'],
  test: ['生成测试用例...', 'pytest 测试文件生成完成', '运行测试套件...'],
  uivalidator: ['启动桌面自动化验证...', '截图已保存'],
  validator: ['ruff 代码质量检查...', 'py_compile 编译验证...', '验收标准对比...'],
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
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
  store.setCurrentTaskId('mock-task-001')

  // ---- 逐个 Agent 模拟执行 ----
  for (let i = 0; i < AGENTS.length; i++) {
    const agent = AGENTS[i]
    store.updateNodeStatus(agent.id, 'running')
    store.addLog({
      timestamp: Date.now(),
      agent: agent.label,
      message: `${agent.label} 启动`,
      level: 'info',
    })

    for (const msg of MESSAGES[agent.id] || []) {
      await delay(400 + Math.random() * 600)
      store.addLog({ timestamp: Date.now(), agent: agent.label, message: msg, level: 'info' })
    }

    await delay(300)
    store.updateNodeStatus(agent.id, 'success')
    store.setProgress(Math.round(((i + 1) / AGENTS.length) * 90))
  }

  // ---- 第 1 轮验证（不通过） ----
  await delay(500)
  store.setIteration(1)
  store.addLog({ timestamp: Date.now(), agent: 'System', message: '--- 第 1 轮验证 ---', level: 'info' })

  const r1 = mockResultRound1()
  store.setValidationResult({
    passed: r1.passed,
    logs: r1.logs,
    screenshotBase64: r1.screenshot,
    failedTests: r1.failed_tests,
    iteration: r1.iteration,
    appPath: r1.app_path,
    appType: r1.app_type,
  })

  for (const line of r1.logs) {
    const level = line.startsWith('✅') ? 'success' : line.startsWith('❌') ? 'error' : line.startsWith('⏭️') ? 'warn' : 'info'
    store.addLog({ timestamp: Date.now(), agent: 'Validator', message: line, level })
  }

  store.updateNodeStatus('validator', 'error')

  // ---- 模拟一次重试修复 ----
  await delay(1000)
  store.addLog({ timestamp: Date.now(), agent: 'System', message: '验证未通过，触发第 2 轮修复...', level: 'warn' })
  store.updateNodeStatus('validator', 'idle')
  store.updateNodeStatus('backend', 'running')
  store.addLog({ timestamp: Date.now(), agent: 'BackendExpert', message: '根据验证反馈修复 CRUD 逻辑...', level: 'info' })
  await delay(800)
  store.updateNodeStatus('backend', 'success')
  store.updateNodeStatus('test', 'running')
  store.addLog({ timestamp: Date.now(), agent: 'TestExpert', message: '重新运行测试套件...', level: 'info' })
  await delay(600)
  store.updateNodeStatus('test', 'success')
  store.setProgress(95)

  // ---- 第 2 轮验证（通过） ----
  await delay(500)
  store.setIteration(2)
  store.addLog({ timestamp: Date.now(), agent: 'System', message: '--- 第 2 轮验证 ---', level: 'info' })

  const r2 = mockResultRound2()
  store.setValidationResult({
    passed: r2.passed,
    logs: r2.logs,
    screenshotBase64: r2.screenshot,
    failedTests: r2.failed_tests,
    iteration: r2.iteration,
    appPath: r2.app_path,
    appType: r2.app_type,
  })

  for (const line of r2.logs) {
    const level = line.startsWith('✅') ? 'success' : line.startsWith('❌') ? 'error' : line.startsWith('⏭️') ? 'warn' : 'info'
    store.addLog({ timestamp: Date.now(), agent: 'Validator', message: line, level })
  }

  store.updateNodeStatus('validator', 'success')
  store.setProgress(100)

  store.addLog({ timestamp: Date.now(), agent: 'System', message: '全部任务完成', level: 'success' })
  store.setRunning(false)
}
