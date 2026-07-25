# 金融 Demo 架构设计

## 1. 设计结论

金融 Demo 不把七个场景统一包装成 Hybrid。每次输入变化后，系统先判断问题是否值得进入量子链路，再根据业务结构和 `ProblemCompiler.analyze()` 的结果选择 Digital、Analog 或 Hybrid。Hybrid 自身通过完整门禁，并且相对其他可用路径同等或更适配时，优先选择 Hybrid。

目标场景分配如下：

| 主链 | 场景 | 选择依据 |
|---|---|---|
| Digital QAOA | 多资产投资组合、抵押品分配、日内流动性调度、企业授信额度配置 | 稠密或带符号耦合、全局容量、方向依赖和辅助变量占主导 |
| Analog QAA/AHS | 衍生品风险情景压缩 | 风险情景可以形成带二维位置的局域冗余图，完整子问题可由 AHS 表达 |
| Hybrid D-A-D QAOA | 交易结算批次、反欺诈调查编排 | 局域冲突是问题主体之一，同时存在必须保留的全局、方向或资源约束 |
| Classic | 衍生品估值 | 定价和 Greeks 继续使用成熟经典算法，量子 counts 不参与价格计算 |

这里展示的是中性原子程序模型的适配性：原子几何和 Rydberg interaction 直接承担局域冲突，AHS 展示连续控制，D-A-D 在同一量子态中组合原生相互作用与通用门。Demo 不声明量子加速、量子优势、全局最优或真实硬件可执行性。

## 2. 路径选择原则

### 2.1 四类计算方式

`classic` 属于金融应用层，不是 CASCAQit `ProblemCompiler.compile()` 的 `mode`。量子编译只接受三种明确组合：

| mode | algorithm | 产物 | 最适合的问题 |
|---|---|---|---|
| `digital` | `qaoa` | `Circuit` | 任意稠密或带符号 QUBO、全局约束、方向依赖 |
| `analog` | `qaa` | `AHSProgram` | 完整 Hamiltonian 可由二维布局、Rydberg interaction 和局域控制表达的问题 |
| `hybrid` | `qaoa` | `HybridProgram` | 可验证的局域子 Hamiltonian，加具有独立业务含义的 Digital residual |

Digital、Analog 和 Hybrid 共用 Canonical Problem、logical order、Hamiltonian、mapping plan 和 decoder。D-A-D 是 Hybrid 的 block 拓扑，AHS 是 Analog 的程序模型，都不是算法名称。

### 2.2 编译可行不等于业务适配

每种模式必须依次通过两道门禁：

1. **编译门禁**：Target 支持所需能力；所有 Hamiltonian term 都有实现；布局、控制、误差和资源检查通过。
2. **业务门禁**：term assignment 保留原始业务含义；几何没有删边或补边；解码后仍能按原始约束复核。

`ProblemCompiler.analyze()` 负责第一道门禁。金融层的 `FinanceModeAdvisor` 负责第二道门禁。罚项刚好能映射到相邻原子，不构成中性原子适配证据。

### 2.3 三种模式的硬条件

Digital 满足以下条件即可进入候选：

- 完整 Hamiltonian 进入数字 cost unitary；
- logical order、参数和 decoder 与共享 analysis 一致；
- Target 的通用门能力满足当前线路。

Analog 必须同时满足：

- 完整 Hamiltonian 由 AHS 表达，不存在 Digital residual；
- 所有业务边与物理 interaction 一致，既不漏边也不产生未声明的有效边；
- 位置来自业务坐标，或来自经过图保真校验的计算嵌入；
- 系数、局域 detuning 和控制范围在声明误差内可实现。

Hybrid 必须同时满足：

- 至少一个标记为 `core` 的完整业务 term group 由 Analog 承担；
- 该 group 的全部 contribution 都映射成功，不能只命中一条边；
- Digital residual 非空，并承载目标权重、容量、依赖、方向或其他真实规则；
- Analog contribution 与 Digital residual 逐项守恒，合并后等于原 Hamiltonian；
- D-A-D block 共用 logical order、Parameter、寄存器映射、连续 SimulationState 和 decoder。

如果 Analog block 只是装饰，或者 Digital residual 是为了凑出 D-A-D 而人工制造，Hybrid 判为 `unsuitable`。

### 2.4 裁决顺序

```text
业务输入
  -> 输入校验与 Classic / Quantum 边界判断
  -> FinanceProblemDefinition
  -> ProblemCompiler.analyze(problem, target)
  -> 编译门禁
  -> 业务 term、几何和贡献守恒门禁
  -> suitable modes
  -> Hybrid > Analog > Digital
  -> recommended / comparable / unsuitable
```

优先级只作用于已经通过全部门禁的模式：

- 完整问题天然适合 AHS，Hybrid 没有真实 residual：选择 Analog。
- Analog 只能承担零散辅助罚项：选择 Digital。
- 局域冲突和全局约束都是问题主体：选择 Hybrid。
- 经典算法已经直接解决业务问题，量子链路没有独立任务：保留 Classic。

## 3. 总体架构

```text
React Workbench
  -> FastAPI
       -> Scenario Registry / Input Validation
       -> Finance Experiment Service
            +-> Classic Pipeline
            |
            +-> Finance Problem Factory
                 -> FinanceProblemDefinition
                 -> ProblemCompiler.analyze()
                 -> FinanceModeAdvisor
                 -> ProblemCompiler.compile(mode, algorithm, target)
                      +-> Digital QAOA -> Circuit
                      +-> Hybrid QAOA  -> HybridProgram / D-A-D
                      +-> Analog QAA   -> AHSProgram
                 -> LocalBackend
                 -> ProblemExecutionResult
                 -> Business Decoder / Constraint Check
       -> Result Presenter / Report Export
  <- Business / Scenario / Mapping / Experiment / Audit views
```

职责边界：

| 层 | 职责 | 不负责 |
|---|---|---|
| React | 收集输入、展示建议、运行状态和真实结果 | 重建 Hamiltonian、推断 term assignment、生成伪线路或伪波形 |
| FastAPI | 校验请求、调度分析与运行、隔离运行签名 | 保存前端状态或替代业务解码 |
| Finance domain | 构造业务 Problem、记录 term 来源、判断业务适配、复核约束 | 修改 CASCAQit 编译语义 |
| CASCAQit Problem API | 规范化、Target-aware mapping、三模式编译、执行和解码 | 判断金融场景是否值得使用某种模式 |
| LocalBackend | 离线数值执行 Digital、Analog 和 Hybrid 程序 | 声称真实硬件性能 |

后端是量子事实的唯一来源。前端所有线路、原子、interaction、波形、参数历史和 counts 都读取 analysis 或 execution context。

## 4. 金融 Problem 契约

### 4.1 场景接口

每个场景实现同一组职责：

```python
default_input()
validate(case_input)
run_classic(case_input)       # 仅在场景需要时实现
build_definition(case_input)
decode(case_input, definition, candidate)
```

`FinanceProblemDefinition` 不再保存会提前决定结果的 `preferred_mode`，而是保存模式裁决所需的业务事实：

| 字段 | 含义 |
|---|---|
| `problem`、`problem_kind` | `QUBOProblemIR`、`GraphProblemIR` 或 `IsingModelIR` |
| `business_variables` | 可直接解释和解码的业务变量 |
| `auxiliary_variables` | slack 等编码变量 |
| `term_groups` | 目标、局域冲突、全局约束、依赖和辅助罚项 |
| `analog_candidate_group_ids` | 允许 Analog 承担的完整 `core` 分组 |
| `geometry_evidence` | 坐标来源、变换、期望边、禁用边和图保真检查 |
| `metadata` | 业务边界与结果解释信息 |

当前实现按 `group_id:left:right` 生成 Analog core contribution 标识，逐条报告 declared、covered 和 missing。后续若要解释同一 QUBO term 内部聚合的多个业务系数，还需要增加 coefficient-level term ledger：

```text
contribution_id
group_id
source_rule
targets
coefficient
role: core | supporting
normalized_term_ids
```

该 ledger 属于后续增强，不是当前完整覆盖门禁的前提。当前门禁已经要求 core pair 全覆盖、物理 interaction 图无漏边和补边、Analog 二体项都有业务依据；无法归因的 term 只能执行 Digital 对照。

### 4.2 几何证据

`geometry_evidence` 支持两种来源：

- `business_native`：坐标本身来自时间、风险因子或其他有明确业务含义的二维空间；
- `verified_embedding`：从业务冲突图计算二维布局，并验证物理 interaction graph 与目标子图一致。

证据至少包含 logical variable 到 site 的映射、坐标单位与缩放、blockade 阈值、期望 interaction、禁止 interaction、漏边和补边。仅使用 `deterministic_grid` 且未验证图保真时，Analog 和 Hybrid 不能被推荐。

`GraphProblemIR` 和 `QUBOProblemIR` 都可以携带完整参考位置。QUBO 的 `positions` 经 `variable_positions` 和 canonical `layout_hints` 进入映射规划器，结果必须显示 `layout_policy="provided"`。未提供完整坐标时虽可生成确定性网格，但该网格不能通过金融层的 Analog/Hybrid 推荐门禁。

### 4.3 模式证据

`FinanceModeAdvisor` 对每种模式返回结构化判断：

| 字段 | 含义 |
|---|---|
| `compiler_feasible` | CASCAQit 是否可以完整编译 |
| `business_suitable` | 是否通过业务、几何和守恒门禁 |
| `covered_group_ids` | 完整覆盖的业务分组 |
| `missing_contribution_ids` | 应映射但未覆盖的业务贡献 |
| `unexpected_analog_term_ids` | 进入 Analog 但没有业务依据的 term |
| `analog_term_count`、`digital_term_count` | 两部分实际承担的 Hamiltonian term 数量 |
| `geometry_status` | `verified`、`missing` 或 `distorted` |
| `diagnostic_codes` | 编译或适配失败原因 |
| `status` | `recommended`、`comparable` 或 `unsuitable` |

`recommended` 必须由证据推导。`comparable` 表示能够完整运行且适合作为对照，但不是最佳表达。`unsuitable` 禁止执行。

## 5. 七个场景的设计

### 5.1 多资产投资组合：Digital

完整 Problem 是带持仓、行业和防御资产约束的稠密协方差 QUBO。协方差含正负耦合，资产关系没有稳定的二维局域几何，全局约束还会引入辅助变量。Digital 能直接表达完整问题；Analog 只能覆盖零散正耦合，放进 Hybrid 也不足以构成有意义的 Analog core。

页面重点展示风险收益分布、相关性矩阵、选中资产与行业暴露、QUBO term 分组、数字线路、参数历史、counts 和约束复核。

### 5.2 交易结算批次：Hybrid，门禁未满足时退回 Digital

Analog core 只表达共享证券、账户、现金池或结算资源造成的不可并行冲突。交易金额、优先级、方向依赖、币种流动性和批次上限保留为 Digital residual。

目标链路为：

```text
Digital preparation
  -> Analog settlement-conflict evolution
  -> Digital value / dependency / liquidity residual + mixer
  -> measurement
```

默认输入的 3 条交易冲突使用独立 pair 单元布局，三条边均落入 blockade 半径，其他变量彼此隔离。当前门禁结果为 `3/3` 覆盖、0 漏边、0 补边和 0 异常 Analog 二体项，因此推荐 Hybrid；布局或输入变化破坏任一条件时自动退回 Digital。

页面在 Hybrid 可用后展示交易冲突网络、依赖链、流动性占用、业务边到原子 interaction 的逐项映射、D-A-D、Digital residual、波形和 counts。

### 5.3 反欺诈调查编排：Hybrid，按输入动态退化

本场景只安排已经生成的告警，不判断交易是否欺诈。共享账户、设备或收款方形成局域冲突组；风险分、涉案金额、时效、席位和工时属于 Digital residual。

默认输入的 3 条共享实体冲突使用同一套 verified embedding，当前门禁结果为 `3/3` 覆盖、0 漏边、0 补边和 0 异常 Analog 二体项。用户将单实体并行上限改为 2 后，冲突组消失，系统自动退回 Digital。

页面展示告警实体网络、风险与金额覆盖、席位和工时、冲突到 interaction 的映射、D-A-D、波形、counts 及业务约束。

### 5.4 抵押品分配：Digital

资格、需求覆盖、批次唯一性和集中度组成二部匹配与全局约束。两条批次互斥边不足以代表完整问题，不能因为这些边可局域映射就改用 Hybrid。

页面展示抵押品到保证金需求的分配流、覆盖价值、融资成本、HQLA 保留、数字线路、约束贡献和 counts。

### 5.5 日内流动性调度：Digital

现金递推、动作时点、前置依赖、币种容量和渠道约束具有方向与顺序。无向 Rydberg interaction 无法直接表达这些主结构，因此使用 Digital。

页面展示分币种现金曲线、动作时间线、资金缺口、成本、依赖 term、数字线路和 counts。

### 5.6 企业授信额度配置：Digital

场景只为已准入企业配置额度，不执行授信审批。资本预算、额度档位和行业集中度是全局资源约束；单个企业档位互斥不足以支撑 Analog core。

页面展示风险调整收益、资本占用、行业集中度、额度档位、数字线路、约束 term 和 counts。

### 5.7 衍生品估值与风险情景：Classic + Analog

场景拆成两条独立链：

```text
定价输入
  +-> ClassicPricingPipeline -> price / Greeks / standard error
  |
  +-> RiskScenarioPipeline
        -> 场景估值与相似度
        -> 带二维位置的 Graph Problem
        -> Analog QAA/AHS
        -> representative scenarios
```

价格和 Greeks 使用 Black-Scholes、二叉树或固定 seed Monte Carlo。Analog 只做风险情景压缩：节点表示市场冲击，边表示业务定义下的信息冗余，二维位置来自标准化后的风险因子空间。

当前 `3 x 3` 图对所有产品都固定不变，只验证了 Analog 执行链，尚未体现产品对场景重要性的影响。目标设计应先用当前产品重估全部情景，再根据损失、Greeks 变化或覆盖贡献构造图；在现有无权 `GraphProblemIR` 下先做 MIS，需权重时再使用可完整 AHS 表达的 QUBO/Ising，不能在页面层伪造权重。

页面明确分开展示经典价格与 Analog 情景选择，并提供价格与 Greeks、情景损失热图、冗余图、原子阵列、Rabi/Detuning/Phase、counts、覆盖率和冲突违反。

## 6. 执行与结果

`ScenarioExecutor` 是唯一量子运行入口：

```python
analysis = executor.analyze(scenario, case_input)
result = executor.run(
    scenario,
    case_input,
    mode="recommended",
    parameter_sets=parameter_sets,
    shots=64,
    seed=23,
)
```

金融层的 `mode="recommended"` 先执行裁决，再向 CASCAQit 传入显式 `mode + algorithm`。用户显式选择的模式只有在状态不是 `unsuitable` 时才能执行。

统一结果包含：

- 原始业务输入、Problem、Target 和 analysis hash；
- 实际 compile/bind/execution hash；
- 原生程序、term mapping、参数历史和 counts；
- best observed candidate、经典有界基准和展示来源；
- 按原始业务规则重新计算的 objective、feasibility 和 violation；
- 本地模拟、seed、shots、耗时及无硬件执行声明。

`optimize(parameter_sets=...)` 只比较调用方给出的离散参数点，不表示连续优化或全局寻优。Demo 可为 Digital 生成一到三层 QAOA 的预设、二维网格或固定 seed 采样点，最多评估 24 个点；生成策略属于应用编排，不改变 CASCAQit 的 Problem 和 Hamiltonian。若量子候选不可行，页面可以另行展示经典基准，但必须保留原候选并标出 `displayed_source`。

## 7. 界面信息架构

每个场景保留五个稳定视图，但内容按场景变化：

1. **业务结果**：选择了什么、业务指标如何、约束是否满足。
2. **场景态势**：风险收益、冲突网络、依赖链、资金曲线或风险热图。
3. **Problem 映射**：Canonical Problem、term groups、三模式证据、几何和资源估算。
4. **量子实验**：实际线路、D-A-D、原子布局、控制波形、参数历史和 counts。
5. **审计证据**：输入、Problem、analysis、compile、execution hash 及执行边界。

三种实验视图遵循固定规则：

- Digital：通用门线路和 QAOA 逻辑层可切换，线路高度随 qubit 数变化，counts 位于线路下方。
- Analog：原子阵列与合并波形并列，坐标轴等比例，counts 位于下方，不显示数字线路。
- Hybrid：同时展示 D-A-D、完整 Analog 业务组、Digital residual、业务边到 interaction 的映射和末端 counts。

模式建议显示具体证据，不只显示 “recommended”。切换业务输入后立即清空旧结果，并重新分析。缓存键包含场景、完整输入、mode、shots、seed、层数、搜索方式和评估预算。

## 8. 后续顺序

已完成：移除 `preferred_mode`，QUBO 接入完整参考坐标，交易结算和反欺诈使用 verified embedding，Hybrid 按完整 core group 裁决，并公开 missing、unexpected term、补边和几何状态。自动测试覆盖完整覆盖、缺边、补边和 Hybrid -> Digital 退化。

### P0：补齐 coefficient-level term ledger

1. 在 QUBO 建模过程中记录每次目标或罚项展开产生的系数 contribution。
2. 将 contribution 聚合值与 Canonical linear/quadratic term 逐项核对。
3. 在界面展开“业务规则 -> contribution -> Hamiltonian term -> Analog/Digital implementation”。

### P1：让 Analog 场景与产品输入联动

1. 从衍生品定价结果生成风险场景特征和相似度。
2. 验证风险图与原子 interaction graph 一致。
3. 增加情景覆盖、冗余违反和经典选择基准。
4. 保持价格链与量子情景链在类型、接口和页面中分离。

### P2：界面与报告收口

1. 把当前 group coverage、几何状态和拒绝原因加入导出 HTML 报告。
2. 增加业务边到原子 interaction 的逐行距离和参考系数表。
3. 为宽屏、平板和手机完成浏览器截图与溢出验收。

## 9. 验收边界

- 七个场景都能完成输入校验、Problem 分析、推荐模式执行、业务解码和约束复核。
- 推荐 Hybrid 时，至少一个完整 `core` group 进入 Analog，Digital residual 非空且具有业务含义。
- 推荐 Analog 时，完整 Hamiltonian 由 AHS 表达，不存在隐藏 Digital 项。
- 推荐 Digital 时，不把零散可映射罚项解释为中性原子优势。
- Digital、Analog 和 Hybrid 对照共用同一 Problem hash、logical order 和 decoder。
- 经典衍生品价格与量子 counts 在类型、接口、页面和导出中分离。
- 所有线路、原子、interaction、波形、term mapping、参数历史和 counts 来自实际分析或执行上下文。
- counts 总数等于 shots，候选解按原始业务约束重新校验。
- 默认运行离线、固定 seed、不访问云端或真实硬件。

本地精确模拟规模只用于演示，不代表中性原子硬件规模或性能。扩大变量和 site 数前，需要单独记录运行时间、内存、数值精度和失败边界。
