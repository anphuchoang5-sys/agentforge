import { useAppStore, type AgentId, type LogEntry } from '@/store/appStore'

// ============ 模拟延迟 ============

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function rand(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

// ============ 日志 / 节点辅助 ============

function log(agent: string, message: string, level: LogEntry['level'] = 'info') {
  useAppStore.getState().addLog({
    timestamp: Date.now(),
    agent,
    message,
    level,
  })
}

function setNode(id: AgentId, status: 'idle' | 'running' | 'success' | 'error') {
  useAppStore.getState().updateNodeStatus(id, status)
}

// ============ 各阶段模拟 ============

async function runCommander(requirement: string) {
  setNode('commander', 'running')
  log('Commander', `📋 收到需求：「${requirement}」`)
  await delay(rand(600, 1000))
  log('Commander', '🔍 正在分析需求意图...')
  await delay(rand(800, 1500))
  log('Commander', '📐 拆解为结构化子任务 (TaskDecomposition DAG)')
  await delay(rand(400, 800))

  const tasks = [
    { id: 'fe-1', type: 'frontend', desc: 'TodoApp 界面 (Tkinter / Web)' },
    { id: 'be-1', type: 'backend', desc: 'SQLite CRUD 数据层' },
    { id: 'test-1', type: 'test', desc: 'pytest 单元测试 + 集成测试' },
    { id: 'ui-1', type: 'ui_validate', desc: 'UI 元素存在性 + 截图验证' },
  ]
  log('Commander', `✅ 生成 ${tasks.length} 个子任务: ${tasks.map((t) => t.id).join(', ')}`, 'success')
  log('Commander', `📊 预估迭代次数: 2-3 轮`)
  useAppStore.getState().setProgress(15)
  setNode('commander', 'success')
  return tasks
}

async function runBackendExpert() {
  setNode('backend', 'running')
  log('BackendExpert', '🔄 开始实现 SQLite 数据层...')
  await delay(rand(500, 1000))
  log('BackendExpert', '📝 创建 todo_db.py — 定义 Task 表模型')
  await delay(rand(600, 1200))
  log('BackendExpert', '🔧 实现 CRUD 操作: create_task / get_tasks / update_task / delete_task')
  await delay(rand(800, 1400))
  log('BackendExpert', '✅ 后端代码生成完毕，写入文件系统', 'success')
  useAppStore.getState().setProgress(
    Math.min(100, useAppStore.getState().progress + 20)
  )
  setNode('backend', 'success')
}

async function runFrontendExpert() {
  setNode('frontend', 'running')
  log('FrontendExpert', '🎨 开始生成前端 UI 代码...')
  await delay(rand(500, 1000))
  log('FrontendExpert', '📝 创建 todo_app.py — Tkinter 主窗口')
  await delay(rand(600, 1000))
  log('FrontendExpert', '🖼️  设计布局: 输入框 + 任务列表 + 操作按钮')
  await delay(rand(700, 1300))
  log('FrontendExpert', '🎯 绑定事件: 添加 / 完成 / 删除')
  await delay(rand(400, 800))
  log('FrontendExpert', '✅ 前端代码生成完毕，写入文件系统', 'success')
  useAppStore.getState().setProgress(
    Math.min(100, useAppStore.getState().progress + 20)
  )
  setNode('frontend', 'success')
}

async function runTestExpert() {
  setNode('test', 'running')
  log('TestExpert', '🧪 开始生成测试用例...')
  await delay(rand(400, 800))
  log('TestExpert', '📝 创建 test_todo.py — pytest 测试文件')
  await delay(rand(500, 1000))
  log('TestExpert', '✅ 测试用例: test_create_task / test_complete_task / test_delete_task')
  await delay(rand(300, 600))
  log('TestExpert', '⚙️  执行 pytest...')
  await delay(rand(600, 1200))
  log('TestExpert', '📊 测试结果: 4 passed, 1 failed (边界条件)', 'warn')
  log('TestExpert', '🔄 修复失败用例并重新运行...')
  await delay(rand(400, 800))
  log('TestExpert', '✅ 全部测试通过: 5 passed', 'success')
  useAppStore.getState().setProgress(
    Math.min(100, useAppStore.getState().progress + 15)
  )
  setNode('test', 'success')
}

async function runUIValidator() {
  setNode('uivalidator', 'running')
  log('UIValidator', '🖥️  启动桌面 UI 自动化验证...')
  await delay(rand(500, 1000))
  log('UIValidator', '🔍 检查窗口标题 "待办事项" ...')
  await delay(rand(300, 600))
  log('UIValidator', '✅ 窗口标题正确')
  log('UIValidator', '🔍 检查输入框元素存在性...')
  await delay(rand(300, 500))
  log('UIValidator', '✅ 输入框 (Entry) 存在')
  log('UIValidator', '🔍 检查按钮: "添加" / "完成" / "删除" ...')
  await delay(rand(400, 700))
  log('UIValidator', '✅ 三个按钮均已渲染')
  await delay(rand(200, 400))
  log('UIValidator', '📸 截图存档 → screenshots/todo_app_v1.png')
  log('UIValidator', '✅ UI 验证完成，所有元素符合预期', 'success')
  useAppStore.getState().setProgress(
    Math.min(100, useAppStore.getState().progress + 10)
  )
  setNode('uivalidator', 'success')
}

async function runValidator(iteration: number) {
  setNode('validator', 'running')
  log('Validator', `🔎 第 ${iteration} 轮代码质量审计开始...`)
  await delay(rand(400, 800))
  log('Validator', '📏 运行 ruff 代码检查...')
  await delay(rand(500, 1000))

  if (iteration === 1) {
    log('Validator', '⚠️  发现 2 个问题: 未使用的导入, 行过长', 'warn')
    log('Validator', '🔄 触发修复闭环 → 返回 BackendExpert / FrontendExpert 修复', 'warn')
    setNode('validator', 'running') // 保持 running 等待下一轮
    return false // 需要修复
  }

  log('Validator', '✅ ruff 检查通过，0 个问题')
  log('Validator', '📋 对照验收标准逐条检查...')
  await delay(rand(400, 800))
  log('Validator', '✅ 添加任务功能 — 通过')
  log('Validator', '✅ 完成任务功能 — 通过')
  log('Validator', '✅ 删除任务功能 — 通过')
  await delay(rand(200, 400))
  log('Validator', '🎉 所有验收标准通过！代码质量合格', 'success')
  useAppStore.getState().setProgress(100)
  setNode('validator', 'success')
  return true // 通过
}

// ============ 修复闭环 ============

async function runFixIteration(iteration: number) {
  log('Commander', `🔄 第 ${iteration} 轮修复开始...`)

  // 并行修复后端和前端
  await Promise.all([
    (async () => {
      setNode('backend', 'running')
      log('BackendExpert', '🔧 修复: 清理未使用的导入...')
      await delay(rand(400, 800))
      log('BackendExpert', '✅ 修复完成', 'success')
      setNode('backend', 'success')
    })(),
    (async () => {
      setNode('frontend', 'running')
      log('FrontendExpert', '🔧 修复: 格式化长行代码...')
      await delay(rand(400, 800))
      log('FrontendExpert', '✅ 修复完成', 'success')
      setNode('frontend', 'success')
    })(),
  ])

  useAppStore.getState().setProgress(
    Math.min(100, useAppStore.getState().progress + 10)
  )
}

// ============ 主流程入口 ============

export async function startAgentWorkflow(requirement: string) {
  const store = useAppStore.getState()

  if (store.isRunning) {
    log('System', '⚠️  已有任务在运行中，请等待完成', 'warn')
    return
  }

  store.reset()
  store.setUserInput(requirement)
  store.setRunning(true)
  store.setCurrentTaskId(`task-${Date.now()}`)

  const startTime = Date.now()
  log('System', `🚀 AgentForge 协作平台启动`)
  log('System', `📝 输入需求: 「${requirement}」`)

  try {
    // Stage 1: Commander 拆解任务
    await runCommander(requirement)

    // Stage 2: Backend + Frontend 并行
    log('System', '⚡ BackendExpert 和 FrontendExpert 并行启动...')
    await Promise.all([runBackendExpert(), runFrontendExpert()])

    // Stage 3: TestExpert
    await runTestExpert()

    // Stage 4: UIValidator
    await runUIValidator()

    // Stage 5: Validator — 最多 5 轮闭环
    let passed = false
    for (let iteration = 1; iteration <= 5; iteration++) {
      passed = await runValidator(iteration)
      if (passed) break

      // 修复闭环
      log('System', `🔄 进入第 ${iteration} 轮修复闭环...`, 'warn')
      await runFixIteration(iteration)
    }

    if (!passed) {
      log('System', '⚠️  达到最大迭代次数 (5轮)，强制终止', 'error')
      useAppStore.getState().setProgress(100)
    }

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)
    log('System', `✅ 全部任务完成！总耗时 ${elapsed}s`, 'success')
  } catch (err) {
    log('System', `❌ 执行异常: ${String(err)}`, 'error')
  } finally {
    store.setRunning(false)
  }
}

// ============ WebSocket Mock（可选：供真实 WebSocket 替换） ============

export function createMockWebSocket() {
  return {
    connect: () => {
      log('System', '🔌 Mock WebSocket 已连接（模拟模式）')
    },
    disconnect: () => {
      log('System', '🔌 Mock WebSocket 已断开')
    },
    send: (data: unknown) => {
      log('MockWS', `📤 发送: ${JSON.stringify(data)}`)
    },
  }
}
