# CASCAQit Finance Demo

这是一个基于 CASCAQit Unified Problem API 的本地金融量子实验台。七个场景按问题结构选择 Digital、Hybrid、Analog 或经典计算，页面展示业务结果、Problem 映射、原生量子程序、counts 和运行证据。

## 启动

先安装同级 CASCAQit 源码和 Demo：

```bash
python3 -m pip install -e ../cascaqit-new/CASCAQit -e .
```

Demo 需要 CASCAQit `1.0.7a0` 系列提供的 QUBO 完整参考布局契约；旧版 SDK 不能运行当前 Hybrid 场景。

构建 React 前端：

```bash
cd frontend
npm install
npm run build
cd ..
```

启动 FastAPI：

```bash
cascaqit-finance-api
```

打开 <http://127.0.0.1:8000>。选择场景和预设，调整业务参数后运行。工作台会加载按场景验收的 shots、QAOA 层数和参数搜索配置，修改任一执行参数后标记为自定义配置。Digital QAOA 可选择 `p=1~3`、预设参数、二维网格、固定 seed 采样或连续优化；Hybrid 和 Analog 支持一层预设参数或连续优化。执行来自本地模拟器，不访问网络。

前端开发时可以让 Vite 独立运行，`/api` 会代理到 FastAPI：

```bash
cd frontend
npm run dev
```

开发地址为 <http://127.0.0.1:5173>，API 地址仍为 <http://127.0.0.1:8000>。

## 当前场景

| 场景 | 默认方式 | 当前计算内容 |
|---|---|---|
| 多资产投资组合 | Digital QAOA | 资产收益、协方差、持仓数量、行业上限和防御资产下限 |
| 交易结算 | Hybrid D-A-D QAOA | Analog 表达可映射的交易冲突；Digital 保留金额、优先级、依赖和流动性约束 |
| 反欺诈调查编排 | Hybrid D-A-D QAOA | Analog 表达共享实体冲突；Digital 保留风险权重、席位和工时约束 |
| 抵押品分配 | Digital QAOA | 资格、保证金需求、批次互斥、融资成本和抵押品价值 |
| 日内流动性调度 | Digital QAOA | 融资动作、币种分组、覆盖下限、时序依赖和渠道冲突 |
| 企业授信额度配置 | Digital QAOA | 已准入额度档位、资本上限、行业集中度和风险调整价值 |
| 衍生品估值与风险情景 | Classic + Analog QAA | 经典方法重估 `3 x 3` 压力情景；绝对 P&L 生成 MWIS 权重并进入 Analog 局域失谐 |

场景共包含 19 个演示预设。每个预设都已按推荐配置完成 3 次独立运行，并由量子采样候选直接通过业务约束复核。修改业务输入后，应用会重新构造并分析 Problem，再更新模式建议；技术上可以编译但缺少业务映射意义的模式不会作为主结果运行。

## 页面内容

React 工作台使用三栏布局：场景导航、参数控制和结果工作区。结果分为五个视图：

- 业务结果：当前选择、核心指标、约束和未选原因。
- 场景态势：合成输入、候选空间、冲突网络或依赖关系。
- Problem 映射：Canonical Problem、Hamiltonian、模式判断、资源估算和 term mapping。
- 量子实验：Digital 线路、Hybrid D-A-D、原子排列、合并控制波形、参数历史、counts 和独立重复运行统计。
- 模式证据：完整 core contribution 覆盖率、几何来源、布局策略、漏项、异常 Analog term 和物理补边。
- 审计证据：Problem、analysis、compile、execution hash，以及 mode、seed、shots 和耗时；完整 Target、Backend 和执行边界保留在结构化审计载荷中。

Digital 只展示 QAOA 逻辑层。Hybrid 同时显示 D-A-D block、原子阵列、波形和 Digital residual 逻辑层。Analog 只显示原子阵列、波形和采样结果，不伪造数字线路。

同一业务输入下，各执行模式的结果分别缓存。只有场景、输入、mode、shots、seed、QAOA 层数、搜索方式、评估预算、优化起点数和重复次数完全一致时才会恢复旧结果；修改任一字段后，旧的 counts、线路、波形和审计证据不会混入当前页面。

## Problem API

应用通过统一执行器运行量子场景：

```python
from cascaqit_finance_demo import PortfolioScenario, ScenarioExecutor

scenario = PortfolioScenario()
executor = ScenarioExecutor()

analysis = executor.analyze(scenario, scenario.default_input())
result = executor.run(
    scenario,
    scenario.default_input(),
    mode="recommended",
    layers=1,
    search_strategy="continuous",
    parameter_budget=12,
    optimizer_starts=2,
    shots=32,
    seed=23,
)

print(analysis.mode_decision.recommended_mode)
print(result.execution.result.counts)
```

执行结果包含 `ProblemExecutionResult`、业务候选、经典有界基准、模式分析和运行证据。业务解码会根据原始输入重新检查约束；QUBO energy 较低不等于业务方案可行。每次 UI 运行还会把 CASCAQit 标准 Problem 报告保存到 `artifacts/reports/`。

## 当前限制

- 输入全部为合成数据，不读取市场、账户、客户或交易生产数据。
- 执行来自 `LocalBackend`，不是量子硬件或云端结果。
- Hybrid 只使用当前 Problem API 支持的一层 D-A-D。
- Analog 要求完整 AHS 可表达性，不会用隐藏数字项补齐失败映射。
- 离散搜索最多比较 24 个参数点。连续搜索使用有界 COBYLA，每个起点最多评估 4～24 次，可配置 1～3 个起点；它不保证找到全局最优参数。
- 独立重复运行当前提供 1、3、5 次选项。可行率和置信区间只统计量子业务候选；最多 5 次只适合演示稳定性，不构成生产统计结论。
- 经典基线只用于小规模校验和自定义输入失败诊断，不计入重复运行成功率，也不作为标准演示预设的结果。
- 经典枚举用于小规模校验，不表示量子优势或生产最优性。
- 衍生品价格与九格重估来自 Black-Scholes、二叉树或固定 seed Monte Carlo；Analog 使用重估权重选择情景，counts 不参与定价。
- 结果不构成投资、清算、风控、授信或定价建议。

## 验证

运行测试前安装开发依赖：

```bash
python3 -m pip install -e ".[dev]"
```

```bash
python3 -m pytest -q
python3 -m ruff check src tests
cd frontend
npm run typecheck
npm test
npm run build
npm audit --audit-level=moderate
curl http://127.0.0.1:8000/api/health
```

浏览器验收覆盖 `1440 x 900`、`1280 x 720` 和 `390 x 844`。每种视口检查页面级横向溢出、控件重叠、canvas 非空、逻辑层、原子比例、波形和 counts。

设计说明见[文档索引](docs/README.md)。
