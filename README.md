# 中科酷原行业量子实验台

这是一个基于 CASCAQit 的离线行业量子计算演示平台。产品在统一工作台内按一级领域组织场景，当前包含金融和生物医药两个领域；`CASCAQit` 是底层量子编程 SDK 与本地执行引擎，不作为对外产品名称。

金融领域保留七个成熟场景。生物医药领域首阶段提供四个独立场景入口，其中小分子电子结构已经接通真实 CASCAQit Digital VQE 与 QWC 有限 shots 测量，另外三个场景当前只开放结构预览，不生成虚构的量子结果。

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
cascaqit-industry-api
```

打开 <http://127.0.0.1:8000>，先在顶部切换金融或生物医药领域，再选择场景。金融场景继续使用原有推荐执行配置；生物医药电子结构场景使用独立的 VQE 配置。执行全部来自本地模拟器，不访问网络。

原命令 `cascaqit-finance-api` 和 `cascaqit-finance-demo` 继续保留，用于兼容已有离线包和自动化脚本。

前端开发时可以让 Vite 独立运行，`/api` 会代理到 FastAPI：

```bash
cd frontend
npm run dev
```

开发地址为 <http://127.0.0.1:5173>，API 地址仍为 <http://127.0.0.1:8000>。

## 当前场景

### 金融

| 场景 | 默认方式 | 当前计算内容 |
|---|---|---|
| 多资产投资组合 | Digital QAOA | 资产收益、协方差、持仓数量、行业上限和防御资产下限 |
| 交易结算 | Hybrid D-A-D QAOA | Analog 表达可映射的交易冲突；Digital 保留金额、优先级、依赖和流动性约束 |
| 反欺诈调查编排 | Hybrid D-A-D QAOA | Analog 表达共享实体冲突；Digital 保留风险权重、席位和工时约束 |
| 抵押品分配 | Digital QAOA | 资格、保证金需求、批次互斥、融资成本和抵押品价值 |
| 日内流动性调度 | Digital QAOA | 融资动作、币种分组、覆盖下限、时序依赖和渠道冲突 |
| 企业授信额度配置 | Digital QAOA | 已准入额度档位、资本上限、行业集中度和风险调整价值 |
| 衍生品估值与风险情景 | Classic + Analog QAA | 经典方法重估 `3 x 3` 压力情景；绝对 P&L 生成 MWIS 权重并进入 Analog 局域失谐 |

场景共包含 19 个标准预设。每个预设都已按推荐配置完成 3 次独立运行，并由量子采样候选直接通过业务约束复核。修改业务输入后，应用会重新构造并分析 Problem，再更新模式建议；技术上可以编译但缺少业务映射意义的模式不会作为主结果运行。

当前默认参数策略按场景校准：投资组合和抵押品使用有界 COBYLA 连续优化；交易结算、调查编排、流动性、授信额度和衍生品风险情景继续使用已验收的固定参数。连续优化不是统一默认值，只有在标准预设的可行率和等待时间同时通过验收后才会替换固定参数。

### 生物医药

| 场景 | 当前状态 | 中性原子量子路径 | 当前展示内容 |
|---|---|---|---|
| 小分子活性空间基态能量估计 | 可执行 | Digital VQE | H2 Pauli Hamiltonian、QWC 测量组、收敛历史、有限 shots 确认和精确对照 |
| 靶点口袋与配体候选构象匹配 | 结构预览 | Hybrid QAOA（规划） | 离散候选相互作用、匹配和碰撞关系；运行入口禁用 |
| 金属酶活性中心有效 Hamiltonian | 结构预览 | Digital VQE（规划） | 双金属低能有效自旋网络；运行入口禁用 |
| 小肽离散构象与折叠能景采样 | 结构预览 | Digital QAOA（规划） | 二维粗粒化离散构象和接触关系；运行入口禁用 |

H2 使用仓库内带 manifest 和 checksum 的固化实验数据。当前数据可用于项目内 benchmark 和演示，但在对外科学发布前仍需完成独立来源复核。页面不输出药效、临床、催化活性或真实蛋白折叠结论，也不声称量子优势。

## 页面内容

React 工作台使用统一三栏布局：左侧只展示当前领域的场景，中间展示领域参数和执行配置，右侧展示结果。金融和生物医药通过顶部一级领域切换，不在同一结果视图中直接比较业务指标。结果分为五个视图：

- 业务结果：当前选择、核心指标、约束和未选原因。
- 场景态势：合成输入、候选空间、冲突网络或依赖关系。
- Problem 映射：Canonical Problem、Hamiltonian、模式判断、资源估算和 term mapping。
- 量子实验：Digital 线路、Hybrid D-A-D、原子排列、合并控制波形、参数历史、counts 和独立重复运行统计。
- 模式证据：完整 core contribution 覆盖率、几何来源、布局策略、漏项、异常 Analog term 和物理补边。
- 审计证据：Problem、analysis、compile、execution hash，以及 mode、seed、shots 和耗时；完整 Target、Backend 和执行边界保留在结构化审计载荷中。

Digital 当前公开 QAOA，并展示实际变分逻辑层。投资组合、抵押品、流动性和授信的 VQE 已接通显式 API，每个场景都有独立的 Ansatz 和执行默认值；固定 seed 校准仍未达到页面发布门槛，因此客户界面不显示 VQE。Hybrid 同时显示 D-A-D block、原子阵列、波形和 Digital residual 逻辑层。Analog 只显示原子阵列、波形和采样结果，不伪造数字线路。

同一业务输入下，各执行配置的结果分别缓存。只有场景、输入、mode、algorithm、层数策略、shots、seed、搜索方式、评估预算、优化起点数和重复次数完全一致时才会恢复旧结果；修改任一字段后，旧的 counts、线路、波形和审计证据不会混入当前页面。

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

- 生物医药首阶段只有 H2 电子结构接通真实执行；构象匹配、金属活性中心和小肽能景仍是明确标记的结构预览。
- 生物医药 fixture、结构与参数全部为公开来源待审计数据或合成数据，不是内部药物研发和临床数据。
- 输入全部为合成数据，不读取市场、账户、客户或交易生产数据。
- 执行来自 `LocalBackend`，不是量子硬件或云端结果。
- Hybrid 支持 `p=1~2`，当前推荐配置仍为 `p=1`；两层链路已通过结构和系数守恒验收，但交易结算在固定验证参数下没有稳定得到可行业务候选。
- 自动选层按期望目标改善选择深度，不保证更深层数一定更好。抵押品三个预设的最新配对校准均选择 `p=1`；更深线路在当前预算下没有获得正的 95% 改善置信下界。
- VQE 当前属于内部对照能力。投资组合、流动性和授信受 12～16 个参数及辅助位约束，只开放 `p=1`；抵押品最多允许 `p=2`。显式 API 会自动使用算法专属连续优化预算，但当前结果不能作为稳定业务方案。
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
cd ..
node scripts/browser-smoke.mjs
curl http://127.0.0.1:8000/api/health
```

浏览器验收脚本覆盖 `1440 x 900`、`1280 x 720` 和 `390 x 844`，检查四个生物医药场景切换、预览执行门禁、H2 运行、页面级横向溢出、结构 SVG 和量子图表 canvas 实绘像素。执行前需先启动 API 和 Vite 开发服务。

设计说明见[文档索引](docs/README.md)。
