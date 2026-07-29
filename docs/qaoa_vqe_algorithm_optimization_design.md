# QAOA 与 VQE 算法优化设计

## 1. 结论

本轮只调整金融实验的变分算法使用方式，不修改金融建模、QUBO 罚项、模式选择规则和模拟器实现。

改动分为两条主线：

1. QAOA 不再以两组固定参数作为主要运行方式。Digital 先接入连续优化和自动选层，Hybrid 在 Digital 验收后再开放多层实验。
2. VQE 用于投资组合、抵押品、流动性和授信的 Digital 对照实验。它与 QAOA 使用同一个 Problem、Hamiltonian、变量顺序、解码器和业务约束，不替代 QAOA，也不用于衍生品定价。

CASCAQit 已提供 QAOA、VQE、`optimize_layers()`、`optimize_layers_repeated()` 和层间参数迁移。本轮主要修改金融应用的执行编排、接口、结果证据和页面表达。只有后续研究约束保持 Mixer、金融专用 Ansatz 或新的预算调度方式时，才需要修改 CASCAQit。

## 2. 迭代前的问题

迭代前的执行器把算法写死为：

- Digital、Hybrid 使用 QAOA；
- Analog 使用 QAA；
- Digital 允许 `p=1~3`，Hybrid 被金融应用限制为 `p=1`；
- 投资组合默认使用 COBYLA 连续优化，其余标准场景主要比较两个固定参数点；
- 前端和 API 没有算法选择，也没有 VQE Ansatz 信息；
- `run_repeated()` 只重复完整运行，不负责比较不同层数。

这些限制已经在本轮解除。保留本节是为了说明改动来源，不代表当前实现。

## 3. 范围

本轮完成：

- Digital QAOA 的固定层数和自动选层；
- 连续优化成为正式算法路径，固定参数保留为快速运行和诊断工具；
- 四个 Digital 金融场景的 VQE 执行链与场景级 Ansatz；
- 统一的算法请求、运行计划和结果证据；
- QAOA 层数实验与 QAOA/VQE 对照的自动测试；
- 页面显示实际算法、选中层数、优化成本和 VQE Ansatz。

本轮不做：

- 模拟器、多核 CPU 或 GPU 性能优化；
- 新金融场景或业务页面重做；
- VQE 衍生品定价；
- 约束保持 Mixer、金融专用 Ansatz、噪声模型或真机运行；
- “量子优势”“全局最优”或某算法必然优于另一算法的结论。

## 4. 运行架构

```text
RunRequest
  -> 模式选择：recommended / digital / hybrid / analog
  -> 算法选择：recommended / qaoa / vqe / qaa
  -> AlgorithmPolicy 校验场景、模式和算法组合
  -> ExecutionPlan
       +-> fixed：指定层数，执行一次连续优化或离散参数评估
       +-> adaptive：从 p=1 连续试到 max_layers，按改善幅度早停
  -> CASCAQit ProblemCompiler
       +-> compile() + optimize()
       +-> optimize_layers()
  -> 选中一次 ProblemExecutionResult
  -> 金融解码与业务约束复核
  -> 算法证据、业务结果和采样结果
```

`AlgorithmPolicy` 只决定算法是否允许执行，不修改 Problem。模式和算法的组合规则为：

| 最终模式 | `recommended` 的算法 | 可显式选择 | 当前发布范围 |
|---|---|---|---|
| Digital | QAOA | QAOA；投资组合、抵押品、流动性和授信内部可显式运行 VQE | QAOA 用于全部 Digital 场景；VQE 尚未通过页面发布校准 |
| Hybrid | QAOA | QAOA | 已支持 `p=1~2`，推荐配置仍为 `p=1` |
| Analog | QAA | QAA | 不参与变分层数实验 |

非法组合直接返回稳定错误，不自动改用其他算法。例如 `hybrid + vqe`、`analog + qaoa`、交易结算或反欺诈的 `digital + vqe` 都不能运行。

## 5. 请求与结果

### 5.1 请求字段

保留现有字段并增加：

```json
{
  "mode": "recommended",
  "algorithm": "recommended",
  "layer_policy": "fixed",
  "layers": 1,
  "max_layers": 3,
  "min_improvement": 0.0,
  "search_strategy": "continuous",
  "parameter_budget": 12,
  "optimizer_starts": 2,
  "shots": 64,
  "seed": 23
}
```

字段规则：

- `algorithm` 取 `recommended | qaoa | vqe | qaa`；
- `layer_policy` 取 `fixed | adaptive`；
- `fixed` 使用 `layers`，忽略 `max_layers` 和 `min_improvement`；
- `adaptive` 只允许连续优化，使用 `max_layers`、`min_improvement` 和早停；
- QAOA 的 `max_layers` 不超过 3；抵押品 VQE 不超过 2，投资组合、流动性和授信 VQE 不超过 1；
- Analog QAA 只能使用固定的一层语义；
- VQE Ansatz 由场景推荐配置决定，不向普通页面开放任意线路编辑。

### 5.2 运行计划

执行器先把请求解析为不可变的 `FinanceAlgorithmPlan`，至少保存：

```text
requested_algorithm
resolved_algorithm
layer_policy
requested_layers / max_layers
optimizer method
per-start evaluation budget
start count
Ansatz definition
Problem hash
```

请求、编译和结果都引用同一个计划。不能由前端根据线路或参数名猜测算法。

### 5.3 结果字段

`FinanceExperimentResult` 仍以选中的 `ProblemExecutionResult` 作为业务解码来源，同时增加结构化算法证据：

```text
algorithm
layer_policy
selected_layers
executed_layers
stop_reason
objective_by_layer
improvement_by_layer
parameter_count
total_evaluation_count
optimizer_starts
ansatz definition / ansatz hash
```

自动选层产生的所有层数结果必须保留，但业务页面只使用选中层的候选进行解码。不得根据单次 counts 中是否出现可行解反向选择层数；选层依据是 CASCAQit 返回的期望目标改善，业务可行性作为独立验收指标。

## 6. QAOA 设计

### 6.1 两种使用方式

现场运行使用经过验收的固定深度：

```text
场景推荐初值 -> 有界 COBYLA -> 末端采样 -> 业务解码
```

算法实验允许自动选层：

```text
p=1 优化
  -> 参数迁移到 p=2
  -> 目标改善达到阈值则保留 p=2
  -> 参数迁移到 p=3
  -> 达到最大层数或连续无明显改善时停止
```

自动选层调用 `ProblemCompiler.optimize_layers()`。发布前的推荐深度校准调用 `optimize_layers_repeated()`，使用配对重复实验和 Student-t 置信区间，避免一次随机种子决定推荐层数。

### 6.2 参数策略

- `continuous` 是正式优化路径；
- `preset` 用作快速运行、回归基准和第一个连续优化初值；
- `grid` 只用于一层 QAOA 参数面观察；
- `seeded_sample` 用于复现和排查优化器问题；
- 页面不能把离散参数点比较描述成连续优化。

默认策略不按算法名称一刀切。三个抵押品预设在 seeds `7/19/23`、64 shots 和单起点 12 次 COBYLA 评估下均得到可行候选，单次约 0.38～0.42 秒，因此抵押品已使用连续优化默认。流动性连续优化仅 `1/3` 可行，单次约 52 秒；授信两个预设分别为 `2/3` 和 `0/3`，单次约 13 秒，因此仍使用已验收的固定参数。连续优化路径对这些场景保持可选，但不能在校准未通过时成为现场默认。

QAOA 有 `2p` 个参数。12 次评估对 `p=3` 只有很有限的搜索空间，因此自动选层不能机械复用最低预算。当前推荐配置来自标准预设的可行率和耗时校准：只有抵押品在现有预算下升级为连续优化默认，流动性和授信保留固定参数。CASCAQit 对每一层使用同一个单起点预算；金融应用不自行复制层间优化逻辑，也不修改 SDK 预算协议。

### 6.3 Hybrid 层数

CASCAQit 和金融执行器均已支持两层 Hybrid QAOA。交易结算和反欺诈的标准输入已完成 `p=2` 验收：

- 每层仍保持完整 D-A-D 结构；
- Analog core 和 Digital residual 的系数守恒不变；
- 原子布局、逻辑变量顺序和业务解码不变；
- 两个场景都生成 `D-A-D-A-D-M`，包含四个独立 QAOA 参数，counts 完整且 Analog/Digital 系数分配守恒；
- 固定验证参数下，反欺诈候选可行，交易结算候选不可行，因此不修改场景默认层数。

## 7. VQE 场景接入

### 7.1 场景级 Ansatz

VQE 配置由 `FinanceProblemDefinition.vqe_ansatz` 声明，不能由执行器套用全局默认值。当前四个场景都使用单轴 `RY`，先控制参数数量；纠缠拓扑和层数按 Problem 结构设置：

| 场景 | 总变量 | 辅助变量 | Ansatz | 最大层数 | 单层参数 |
|---|---:|---:|---|---:|---:|
| 投资组合 | 12 | 4 | `RY + circular CX` | 1 | 12 |
| 抵押品 | 8 | 0 | `RY + linear CX` | 2 | 8 |
| 流动性 | 16 | 8 | `RY + linear CX` | 1 | 16 |
| 授信 | 14 | 6 | `RY + linear CX` | 1 | 14 |

投资组合的协方差项稠密，闭环纠缠让逻辑顺序首尾都进入纠缠边。其他选择类场景保留线性纠缠。当前连续优化每起点最多 24 次评估；除抵押品外，`p=2` 的参数数量加最小探索余量已经超过预算，因此策略层直接拒绝第二层。

第一组 Ansatz 固定为：

```python
HardwareEfficientAnsatz(
    rotation_axes=("ry",),
    entanglement="linear",
)
```

该配置每层有 `8` 个旋转参数。CASCAQit 默认的 `RY/RZ` 配置每层有 `16` 个参数，在现有评估预算下不适合作为首个试点。

### 7.2 对照原则

QAOA 与 VQE 必须共享：

- 同一业务输入和 `FinanceProblemDefinition`；
- 同一 Canonical QUBO、Hamiltonian 和 logical order；
- 同一 shots、seed 集合和总目标函数评估上限；
- 同一业务解码器和约束复核；
- 同一经典基线，但经典结果不替代量子候选。

对照结果显示目标值、业务可行率、最佳业务方案、参数数量、实际评估次数、运行耗时和 counts。结果只说明在当前 Problem、Ansatz、预算和执行环境下的表现。

### 7.3 开放条件

VQE 先作为内部可执行能力。单个场景满足以下条件后，才在客户页面提供选择：

- 该场景全部标准预设均能完成编译、优化、采样和解码；
- 每个预设至少使用 3 个固定 seed 重复运行，量子候选全部通过业务约束；
- 不依赖经典结果替换不可行量子候选；
- API、页面和导出证据明确显示 `algorithm=vqe` 和实际 Ansatz；
- 结果没有被错误展示成 QAOA 逻辑层；
- 运行时长满足现场演示要求，否则只保留内部对照入口。

### 7.4 当前校准结论

三个抵押品预设使用相同 Problem、`p=1`、64 shots、12 次目标评估和 seeds `7/19/23` 完成 QAOA/VQE 配对运行。QAOA 的量子候选 `9/9` 可行，VQE 为 `3/9`，三个预设都只有 seed `23` 得到可行候选。VQE 的 Problem hash、Ansatz、参数历史和 counts 均来自真实执行，失败原因是当前 Ansatz 与预算下的采样稳定性，不是接口未接通。

新增场景使用 64 shots 和 seeds `7/19/23` 校准。投资组合单起点、14 次评估得到 `11/12` 可行；提高到 24 次仍为 `11/12`，改为两个起点后降为 `8/12`。授信使用 16 次评估得到 `1/6`，单次约 16.7 秒；流动性使用 18 次评估得到 `1/3`，单次约 78 秒。多起点投资组合中，优化器会选择期望能量更低但有限 shots 候选不可行的起点，因此不能按最低期望能量直接宣称发布稳定。

当前四个场景都使用两级声明：`digital_algorithms` 保留后端显式 VQE，`published_digital_algorithms` 只发布 QAOA。API 为 VQE 提供独立的 shots、层数、连续优化预算和起点默认值；VQE 不出现在客户页面，也不使用经典基线替换失败候选。

## 8. 页面调整边界

页面只增加算法实验所需内容，不重做现有业务视图：

- Digital 模式只显示 `推荐 / QAOA`；后端发布列表将来包含 VQE 后，页面无需改协议即可显示；
- 层数提供“固定”和“自动”两个选项；
- VQE 线路显示真实旋转层和线性或闭环纠缠定义，不复用 QAOA 的 Cost/Mixer 表示；
- 结果摘要显示实际算法、选中层数、参数量和目标评估次数；
- 自动选层增加紧凑的“层数—目标值”结果，不展示重复的完整线路卡片；
- 固定参数、网格、随机采样和连续优化使用不同名称，避免把参数评估说成优化。

## 9. 实施结果

### 第一阶段：统一算法配置（已完成）

修改范围：领域模型、`ScenarioExecutor`、FastAPI 请求、场景目录、TypeScript 类型。

结果：

- `recommended/qaoa/vqe/qaa` 能解析为唯一算法；
- 所有非法模式与算法组合返回稳定错误；
- 现有请求不传新字段时仍按当前推荐算法运行；
- 执行结果和 API 返回实际算法，而不是前端推断值。

### 第二阶段：Digital QAOA 自动选层（已完成）

修改范围：执行器、算法证据、API presenter、单元测试和集成测试。

结果：

- 固定层数继续调用 `compile().optimize()`；
- 自动选层调用 CASCAQit `optimize_layers()`；
- `p=1~3` 的参数迁移、早停和选中结果可以从响应复核；
- 所有业务解码只读取选中层执行结果；
- 连续优化历史、实际评估次数和停止原因完整保留。

### 第三阶段：VQE 场景接入（执行链完成，页面发布未通过）

修改范围：算法策略、VQE Ansatz 配置、对照运行测试和结果转换。

结果：

- 投资组合、抵押品、流动性和授信可以显式执行 Digital VQE；
- 每个场景由自身 Problem 定义声明 Ansatz、层数上限和算法专属执行配置；
- 实际编译结果为 `algorithm=vqe`；
- Ansatz、参数数量、优化历史和 counts 来自真实执行结果；
- QAOA/VQE 使用同一 Problem hash 和业务解码器；
- 各场景标准预设完成固定 seed 的重复验收并记录结果。

### 第四阶段：Hybrid 深度验证与页面接入（已完成）

修改范围：Hybrid 层数限制、React 控件、QAOA/VQE 线路、层数结果和中英文文案。

结果：

- 交易结算和反欺诈完成 `p=1~2` 验证，未验收配置不成为默认值；
- VQE 不显示 QAOA 线路；
- 页面所有算法、层数、预算和结果值与 API 一致；
- TypeScript 检查、前端测试和生产构建通过。

### 第五阶段：发布前校准（已完成）

本轮校准执行：

- 抵押品三个预设完成 QAOA `p=1~3` 的重复层数实验；
- 交易结算和反欺诈完成 Hybrid `p=2` 结构与业务候选检查；
- 抵押品完成 QAOA/VQE 配对运行；
- 投资组合、流动性和授信完成 VQE 固定 seed 校准，均未通过页面开放条件；
- 抵押品、流动性和授信完成默认连续优化校准，只有抵押品通过可行率和等待时间门槛；
- 19 个标准预设按最终推荐配置各执行 3 次，`57/57` 个量子候选通过业务约束复核；
- VQE 未通过开放条件时不出现在客户页面；
- 所有展示候选来自量子执行，不使用经典结果替换；
- Python 测试、Ruff、前端测试和构建全部通过；
- 更新架构、讲解和当前限制文档。

## 10. 风险与停止条件

最大风险不是 VQE 接口能否接通，而是参数维度增加后，当前预算无法产生稳定、可解释的结果。遇到以下情况时停止扩大范围：

- 更深 QAOA 在重复实验中没有稳定改善；
- VQE 需要明显超出现场时间的预算才能得到可行候选；
- Hybrid 多层导致演示等待时间不可接受；
- 为改善结果需要改变原 QUBO 罚项或用经典结果替换量子候选。

这时保留已验证的固定深度配置，记录实验结论，不把未通过验收的算法选项交给客户。
