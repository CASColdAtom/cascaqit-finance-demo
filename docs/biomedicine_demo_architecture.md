# 中科酷原行业量子实验台 - 生物医药领域架构设计

## 1. 架构结论

对外统一产品名称为“中科酷原行业量子实验台”。金融和生物医药作为产品内的一级领域，`CASCAQit` 仅表示底层量子编程 SDK 和执行引擎。

生物医药领域沿用金融 Demo 已验证的离线 FastAPI、React 工作台、CASCAQit 本地执行和审计报告结构，但不复用金融领域类型和命名。

四个场景分成两条执行链：

| 执行链 | 场景 | CASCAQit 入口 |
|---|---|---|
| Pauli/VQE | 小分子电子结构、金属活性中心有效模型 | `PauliHamiltonian`、`VQE`、`LocalBackend` |
| 组合优化 | 分子对接、小肽离散构象能景 | `QUBOProblemIR`、`QAOA` / `ProblemCompiler`、`LocalBackend` |

Pauli Hamiltonian 不是 QUBO。应用不能为了统一接口把电子结构问题改写成没有化学意义的 Ising 优化，也不能把分子对接的经典评分解释成电子能量。两条链在应用服务层共享输入签名、运行配置、结果摘要和审计记录，不在领域建模层强行合并。

本版本不修改 CASCAQit 的化学能力边界。分子积分、活性空间和费米子映射由离线化学适配器（Chemistry Adapter）或经过校验的固化实验数据（fixture）提供；CASCAQit 从 Pauli Hamiltonian 开始负责 VQE。真实硬件提交不在当前架构范围内。

## 2. 设计原则

### 2.1 领域事实与量子执行分开

- 领域模块负责解释分子、口袋、相互作用、自旋和构象；
- 适配器负责生成 Pauli Hamiltonian 或 QUBO，并保存来源；
- CASCAQit 负责验证、编译、优化、模拟和结果记录；
- 解码器使用原始领域输入复核结果；
- 前端只展示后端返回的结构化事实，不重新计算能量和约束。

### 2.2 经典计算边界公开

经典预处理、经典基线和量子执行分别保存：

```text
source data
  -> classical preprocessing fixture
  -> domain model
  -> Pauli Hamiltonian / QUBO
  -> CASCAQit execution
  -> quantum candidate
  -> domain validation
  -> classic comparison
```

经典预处理可以生成轨道积分、候选构象和离散能景，但不得预先写入量子采样结果。经典基线用于校验和比较，不参与量子候选成功率，也不在采样失败时替换量子结果。

### 2.3 模式由结构决定

- Digital VQE：通用 Pauli Hamiltonian、非对角 `X/Y` 项、QWC 测量；
- Digital QAOA：稠密、全局、方向或带辅助变量的组合约束；
- Hybrid QAOA：完整局域冲突组可由 Rydberg interaction 表达，同时存在真实 Digital residual；
- Analog QAA：完整 Hamiltonian 可由目标和布局表达，不存在隐藏数字项。

默认模式来自编译可行性和领域门禁。编译成功不等于领域适合，原子布局也不能只为得到 Hybrid 图形而删除或补充业务边。

## 3. 总体结构

```mermaid
flowchart LR
    UI[React Industry Quantum Workbench]
    API[FastAPI]
    REG[Scenario Registry]
    SVC[Experiment Service]
    DATA[Fixture Store + Manifest]
    CHEM[Chemistry Adapter]
    OPT[Optimization Adapter]
    VQE[Pauli VQE Executor]
    PROB[Problem Executor]
    SDK[CASCAQit LocalBackend]
    DEC[Domain Decoder and Validator]
    REP[Presenter and Audit Report]

    UI --> API --> REG --> SVC
    SVC --> DATA
    DATA --> CHEM --> VQE
    DATA --> OPT --> PROB
    VQE --> SDK
    PROB --> SDK
    SDK --> DEC --> REP --> API --> UI
```

## 4. 代码布局

生物医药领域代码使用独立包，避免继续扩大金融领域模型的职责。第一阶段采用统一行业 API 外壳，领域目录、路由和缓存签名显式携带 `domain_id`；金融兼容 API 保留在原包内：

```text
src/
  cascaqit_biomedicine_demo/
    catalog.py
    active_center.py
    docking.py
    electronic_structure.py
    fixtures.py
    pauli_vqe.py
    peptide_landscape.py
    problem_model.py
    data/
      docking_match/
      electronic_structure/
      active_center/
      peptide_landscape/
  cascaqit_industry_demo/
    problem_api.py             # 领域中性的 Problem 执行协议
    problem_executor.py        # QAOA / Hybrid 编译、优化和解码编排
  cascaqit_finance_demo/
    api/app.py                 # 统一行业 API 外壳与金融兼容入口
    quantum/problem_executor.py # 对中性执行器的金融兼容重导出
    static/                    # 统一 React 生产构建
```

`cascaqit_finance_demo` 在生物医药建设期间保持可运行，不直接重命名已有 `FinanceProblemDefinition`、`FinanceModeAdvisor` 或旧 API。生物医药的 fixture、QUBO builder、贡献账本、TermGroup、GeometryEvidence、ProblemDefinition 和解码结果均为独立类型，不依赖 `Finance*` 领域类型。

第三阶段已提取不依赖金融类型的 `pauli_vqe.py`，由电子结构与金属活性中心共同复用 Hamiltonian 构造、稳定哈希、精确对角化和自旋扇区聚合。金属活性中心没有继续扩展金融执行器依赖。

小肽场景直接使用 CASCAQit `QAOA`、生物医药自有 `OptimizationProblemDefinition` 和贡献账本。构象匹配使用 `cascaqit_industry_demo.problem_executor.ScenarioExecutor` 获取 Digital/Hybrid 编译与执行证据；该包只依赖领域中性 Protocol 和 dataclass，不导入金融包。原金融 `problem_executor.py` 保留兼容重导出，使既有金融 API 与测试继续使用 `FinanceAlgorithmPolicy`、`FinanceModeAdvisor` 和 `ScenarioExecutor` 名称，但真实实现只有一份。架构测试阻止生物医药包重新引用 `cascaqit_finance_demo`。

前端沿用当前 `frontend/` 工程和构建方式，统一展示“中科酷原行业量子实验台”品牌，并增加金融/生物医药领域切换、领域场景目录和领域视图。生产构建继续复制到现有 `cascaqit_finance_demo/static/`，由统一 FastAPI 应用托管。Python 项目新增 `cascaqit-industry-api` 和 `cascaqit-industry-demo` 入口，金融入口继续保留以兼容已有部署。

## 5. 公共领域接口

四个场景实现统一的应用接口，但返回各自的领域结果：

```python
class BiomedicineScenario(Protocol):
    case_id: str
    title: str
    execution_family: Literal["pauli_vqe", "problem"]

    def default_input(self) -> Any: ...
    def validate(self, case_input: Any) -> tuple[DomainIssue, ...]: ...
    def analyze(self, case_input: Any) -> ScenarioDefinition: ...
    def decode(self, case_input: Any, execution: Any) -> Any: ...
    def classic_reference(self, case_input: Any) -> Any: ...
```

`ScenarioDefinition` 是应用层联合类型：

```python
from typing import Union

ScenarioDefinition = Union[
    PauliExperimentDefinition,
    OptimizationProblemDefinition,
]
```

### 5.1 PauliExperimentDefinition

用于电子结构和有效自旋模型：

```text
case_id
dataset_id / manifest_hash
hamiltonian: PauliHamiltonian
logical_order
initial_state
ansatz_definition
observable_definitions
reference_energy
reference_method
metadata
```

### 5.2 OptimizationProblemDefinition

用于分子对接和小肽能景：

```text
case_id
dataset_id / manifest_hash
problem: QUBOProblemIR
business_variables
auxiliary_variables
term_groups
coefficient_contributions
analog_candidate_group_ids
geometry_evidence
metadata
```

该结构沿用金融 Demo 的系数账本和模式证据思想，但名称、字段说明和诊断码使用领域中性或生物医药语义，不依赖 `Finance*` 类型。

## 6. 数据与固化实验数据

### 6.1 目录规则

每个预设使用一个版本目录：

```text
data/<scenario>/<dataset>/<version>/
  manifest.json
  domain.json
  pauli.json          # Pauli 场景
  qubo-input.json     # QUBO 场景
  reference.json
  preview.png
```

原始 PDB、SDF 或量子化学输出只有在许可证允许且发布确有需要时进入 Python 包。默认优先保存经过复核的最小派生数据和来源 checksum，避免让运行包携带无法解释的大型原始文件。

### 6.2 manifest

```json
{
  "dataset_id": "electronic.h2.bond-scan",
  "version": "1",
  "source": {
    "kind": "generated",
    "uri": null,
    "license": "project_generated"
  },
  "generation": {
    "tool": "pyscf",
    "tool_version": "to_be_pinned",
    "script_hash": "...",
    "parameters": {}
  },
  "units": {},
  "logical_order": [],
  "artifacts": [],
  "reference": {},
  "limitations": []
}
```

加载器验证数据结构、checksum、逻辑顺序、单位和交叉引用。任一数据不一致都必须在分析前失败，不允许后端用部分数据继续执行。

当前十四组 fixture 在各自领域加载器读取 artifact 前统一调用 `validate_manifest_contract()`。公共契约强制检查来源 checksum 状态、生成工具版本和参数、单位、坐标系、变量顺序、经典参考方法与软件版本、标准预设参考结果、允许说法和限制；领域加载器继续复核 Pauli logical order、对接 QUBO 变量顺序和小肽构象顺序。

### 6.3 fixture 生成

生成脚本与运行时分离：

- 生成环境可以使用 PySCF、OpenFermion、RDKit 或其他经典工具；
- 运行时默认不依赖这些大型工具；
- 脚本输出经过 schema 校验和参考计算后才进入仓库；
- CI 读取 fixture 做一致性检查，不要求重新生成所有化学数据；
- 发布前在受控环境执行一次可重复生成审计。

## 7. Pauli/VQE 执行链

### 7.1 分析

`PauliVQEExecutor.analyze()` 完成：

1. 校验 fixture 和领域输入；
2. 构造或选择 `PauliHamiltonian`；
3. 校验 logical order、初态和 Ansatz 参数数量；
4. 生成 QWC 测量计划和资源估算；
5. 计算输入、Hamiltonian、Ansatz 和分析 hash；
6. 返回经典参考摘要，但不执行优化。

### 7.2 执行

```text
PauliHamiltonian
  -> VQE(operator, ansatz, layers)
  -> exact or sampled objective
  -> SPSA / Adam / accepted deterministic optimizer
  -> optional candidate confirmation
  -> final sampling
  -> observables
  -> domain result
```

电子结构和有效自旋模型可以使用不同初态、Ansatz 和观测量，但共用执行、测量和审计实现。

### 7.3 结果

`PauliRunResult` 至少保存：

- 最低评估、最终优化点和末端采样的区别；
- 每次目标评估和参数；
- 测量组、shots、方差和标准误；
- 理想或噪声执行事实；
- 能量和声明观测量；
- 经典参考及误差；
- Hamiltonian、Ansatz、Backend 和结果 hash。

## 8. 组合优化执行链

### 8.1 分析

`BiomedProblemExecutor.analyze()` 完成：

1. 校验领域输入；
2. 构造 QUBO 和逐系数贡献账本；
3. 调用 `ProblemCompiler.analyze()`；
4. 检查编译可行性；
5. 检查 Analog core 完整性和几何保真；
6. 给出 Digital、Hybrid、Analog 的结构化判断。

### 8.2 执行

构象匹配需要 Hybrid 编译证据，通过领域适配器进入 `ProblemCompiler` 和现有场景执行器：

```text
QUBOProblemIR
  -> ProblemCompiler.compile(mode, algorithm, target)
  -> QAOA / Hybrid D-A-D QAOA
  -> parameter optimization
  -> final sampling
  -> candidate decoding
  -> original-domain validation
  -> bounded classic comparison
```

小肽场景只开放 Digital QAOA，不需要构造 Analog core 或 Hybrid residual，直接把领域中性 `QUBOProblemIR` 交给 CASCAQit `QAOA`：

```text
QUBOProblemIR
  -> CASCAQit QAOA
  -> parameter optimization
  -> final sampling
  -> one-hot feasible candidate decoding
  -> complete finite classic landscape comparison
```

### 8.3 系数账本

每个 QUBO 贡献包含：

```text
contribution_id
group_id
source_rule
targets
coefficient
role
term_kind
```

应用检查领域贡献之和等于 Canonical QUBO 系数，并在编译后检查 Analog 与 Digital 系数之和等于逻辑 Hamiltonian 系数。对接场景的每条 Analog 二体项必须对应空间碰撞或占位冲突。

## 9. 四场景映射

| 场景 | 领域输入 | IR / Hamiltonian | 默认算法 | 经典对照 |
|---|---|---|---|---|
| 小分子电子结构 | 几何、活性空间、Pauli fixture | `PauliHamiltonian` | Digital VQE | 精确对角化、HF |
| 分子对接 | 构象、口袋特征、匹配和冲突 | `QUBOProblemIR` | Hybrid QAOA | 有界枚举、共晶参考 |
| 金属活性中心 | 交换耦合、局域场、有效模型 | `PauliHamiltonian` | Digital VQE | 精确对角化 |
| 小肽能景 | 序列、离散构象、接触能 | `QUBOProblemIR` | Digital QAOA | 完整离散能景 |

## 10. API

统一行业应用使用领域化请求路径，同时保留旧金融路径：

```text
GET  /api/health
GET  /api/domains
GET  /api/domains/{domain_id}/scenarios
POST /api/domains/{domain_id}/scenarios/{case_id}/analyze
POST /api/domains/{domain_id}/scenarios/{case_id}/run

# 金融兼容入口
GET  /api/scenarios
POST /api/scenarios/{case_id}/analyze
POST /api/scenarios/{case_id}/run
```

第一阶段尚未开放独立 dataset manifest HTTP 接口；manifest 通过分析和审计响应返回必要摘要，完整文件随 Python 包安装。

### 10.1 分析请求

```json
{
  "preset": "reference",
  "values": {}
}
```

### 10.2 运行请求

```json
{
  "preset": "reference",
  "values": {},
  "mode": "recommended",
  "algorithm": "recommended",
  "layers": 1,
  "shots": 64,
  "seed": 23,
  "optimizer": {
    "method": "recommended",
    "budget": 12,
    "starts": 1
  }
}
```

API 对不适用组合返回 422 和结构化诊断。例如 Pauli/VQE 场景请求 `hybrid`、对接场景请求 `vqe`、缺失 fixture 或 checksum 不一致都必须在执行前失败。

生物医药路径的业务校验错误和 FastAPI/Pydantic 请求 schema 错误统一返回 `detail.code/message/stage`；未知预设使用 `BIOMEDICINE_PRESET_UNKNOWN`，请求字段错误使用 `BIOMEDICINE_REQUEST_INVALID`，阶段均为 `preflight`。金融兼容路径保留原有 FastAPI 校验响应。

### 10.3 响应外层

```text
scenario
dataset
analysis
run
  domain
  quantum
  comparison
  audit
```

`domain` 根据场景使用联合类型；`quantum` 根据 VQE、Digital QAOA 或 Hybrid QAOA 使用可辨识联合类型。前端按 `kind` 渲染，不通过字段是否存在猜测响应类型。

## 11. 前端

### 11.1 场景组件

```text
ElectronicStructureView
DockingView
ActiveCenterView
PeptideLandscapeView
```

金融与生物医药共用品牌头、领域切换、场景导航、参数控制和结果工作区。金融域保持五个既有结果标签；生物医药域显示领域结果、场景结构、Problem 映射、量子实验、对照分析和审计证据六个标签。对照分析是独立视图，按场景分别展示量子观测、精确对角化、经典全枚举或共晶派生参考，不能用领域结果页中的摘要代替。

公共组件包括执行参数、模式判断、线路、原子布局、波形、测量分组、参数历史、counts、审计载荷和错误状态。品牌头常驻显示 `LOCAL SIMULATION`、`NO HARDWARE EXECUTION` 和 `RESEARCH DEMONSTRATION`；专业缩写首次出现时使用中文 tooltip 解释。

### 11.2 可视化来源

- 分子和口袋图读取后端提供的稳定节点、键、坐标和标签；
- 前端可以做投影、缩放和布局，但不能改变领域关系；
- 量子线路、原子位置、interaction、波形和 counts 全部来自 CASCAQit 执行上下文；
- 预览图属于数据资产，必须在 manifest 中登记；
- 后续若引入 3D，使用独立的结构查看组件，不把量子原子阵列与分子三维坐标混为一图。

### 11.3 状态隔离

运行缓存签名包含：

```text
case_id
dataset_version / manifest_hash
domain_input_hash
execution_family
mode / algorithm / ansatz
layers / shots / seed
optimizer config
noise config
```

任一字段变化后，旧结果只能作为历史记录显示，不能进入当前结果视图。

当前前端签名直接序列化 `domain_id`、`case_id`、完整运行请求，以及分析响应中的 `dataset.version`、`dataset.manifestHash` 和 `executionFamily`。领域输入、模式、算法、层数、shots、seed、优化器和噪声参数均属于完整运行请求。manifest 或执行族变化会立即使旧缓存失效。

## 12. 审计与安全

### 12.1 hash 链

```text
source checksum
  -> manifest hash
  -> domain input hash
  -> Hamiltonian / Problem hash
  -> analysis hash
  -> compile / Ansatz hash
  -> Backend Job / result hash
  -> report hash
```

### 12.2 输入边界

- 首期 API 只允许目录中已登记的数据集；
- 不接受浏览器上传任意 Python、Hamiltonian 表达式或可执行脚本；
- 数值输入检查范围、有限性和单位；
- 报告文件名由后端生成，不使用用户输入拼接路径；
- 报告写入配置的用户数据目录，API 返回 `reportPath`，不写入安装目录；
- 错误响应不返回本机绝对路径或完整异常栈。

未配置环境变量时，用户数据根目录按平台解析为 macOS `~/Library/Application Support/CASColdAtom/IndustryQuantumWorkbench`、Windows `%LOCALAPPDATA%\CASColdAtom\IndustryQuantumWorkbench`、Linux `${XDG_DATA_HOME:-~/.local/share}/CASColdAtom/IndustryQuantumWorkbench`。`CASCAQIT_INDUSTRY_DATA_DIR` 可覆盖根目录；便携 Windows 离线包显式把它设置为解压目录。旧 `CASCAQIT_FINANCE_DATA_DIR` 仅作为兼容回退。

### 12.3 数据边界

- 不保存患者或临床个体数据；
- 不将公开数据库访问凭据写入 fixture；
- 来源和许可证未确认的数据不进入发布包；
- 合成数据在页面和 manifest 中明确标记。

## 13. 测试策略

### 13.1 数据测试

- manifest schema 和 checksum；
- 单位、逻辑顺序和交叉引用；
- Pauli 项 Hermitian 与变量唯一性；
- 构象、碰撞、接触和参考结果一致性；
- fixture 可重复生成审计。

### 13.2 领域测试

- 输入正向、负向和边界；
- QUBO 系数和贡献账本守恒；
- 电子结构参考能量；
- 自旋模型参考关联；
- 对接冲突和构象一致性；
- 小肽构象去重、自回避和能量。

### 13.3 执行测试

- Pauli VQE 完成真实目标评估、测量和末端采样；
- QAOA 完成编译、优化、counts 和领域解码；
- Hybrid 的 Analog core、Digital residual、D-A-D block 和系数守恒；
- 固定 seed 可重复性；
- 量子候选与经典对照严格分离；
- 报告生成不触发二次执行。

### 13.4 API 和前端测试

- 四场景目录和预设数量；
- 不适用模式和损坏 fixture 的 422；
- 前端四个核心用户流程；
- 中英文领域术语；
- 运行缓存签名；
- `1440 x 900`、`1280 x 720`、`390 x 844` 截图；
- canvas/SVG 非空、无重叠和无页面级横向溢出。

## 14. 可观测性和失败处理

每次分析和执行记录：

- `case_id`、`dataset_id` 和 `error_id`；
- API 层 `preflight`、领域执行、报告生成和总耗时；算法内部通过目标评估数、Backend 执行数、shots、参数历史和测量组保留可观测证据；
- 逻辑量子位、Pauli 项、测量组、QUBO 项和辅助变量数量；
- Backend 执行次数、shots 和模拟方法；
- 失败阶段和稳定诊断码。

领域数据错误返回 422；未支持能力返回 CASCAQit `CapabilityError` 的结构化信息；未知内部错误返回 500 和 `error_id`，详细异常只写入本地日志。

四个推荐配置在场景目录中保存基于固定 seed 校准的本机耗时基线。前端按 shots、预算、优化起点、重复次数和层数估算当前研究配置；估算超过 30 秒时在执行按钮前显示提示。该数字只用于本地等待量级，不是硬件或跨平台性能承诺。

## 15. 分阶段实施

### 第一阶段：公共骨架和 Pauli VQE

- 新建生物医药包、API、目录和 manifest 加载器；
- 定义应用层联合结果结构；
- 完成 H2 fixture、Pauli VQE 执行和经典对照；
- 建立审计 hash 链。

### 第二阶段：分子对接旗舰场景

- 完成离线结构派生数据；
- 构造 QUBO、系数账本和领域解码；
- 完成 Hybrid 几何门禁；
- 完成相互作用网络和量子实验页面。

### 第三阶段：有效自旋模型

- 复用 Pauli VQE 链接入有效自旋模型；
- 后端返回局域磁化、两点关联和声明扇区占据；
- 使用相同 Hamiltonian hash 完成精确对角化对照。

### 第四阶段：小肽能景

- 使用生物医药自有 QUBO 契约直接接入 CASCAQit QAOA；
- 构造离散小肽能景和 Digital QAOA；
- 完成四场景统一导航、结果和审计体验。

### 第五阶段：校准和发布

- 标准预设固定 seed 校准；
- 全量质量门禁和浏览器验收；
- 离线包和启动脚本；
- 客户讲解文档、数据来源清单和已知限制。

### 第六阶段：设计完成度收口

- 提取领域中性 Problem 执行器并保留金融兼容层；
- 增加常驻运行边界和独立对照分析视图；
- 补齐数据集与执行族缓存身份、研究配置成本提示；
- 统一结构化错误、用户目录报告和 API 阶段耗时；
- 逐条复核 PRD、架构、浏览器、wheel 和离线包构建证据。

### 第七阶段：最终契约审计

- 强制执行 V1 八组 manifest 的公共溯源和标准参考契约；
- 统一全部生物医药 422 请求错误，并证明长运行不阻塞健康检查；
- 将默认报告位置切换为平台用户数据目录；
- 统一 Web、Windows 离线入口、旧金融界面和当前讲解文档的产品名；
- 重跑 36 次固定 seed 校准、三视口浏览器验收、全量测试和发布包构建。

## 16. 关键风险

| 风险 | 影响 | 处理 |
|---|---|---|
| 化学 fixture 来源不完整 | 无法解释 Hamiltonian | manifest、checksum、生成脚本和经典参考同时入库 |
| 把离散匹配说成完整对接 | 客户形成错误预期 | 产品命名、结果字段和限制统一使用“候选构象匹配” |
| 有效模型被误解为真实金属酶 | 科学可信度受损 | 页面固定显示模型层级、来源和省略项 |
| 小肽构象库使问题过于简单 | 演示价值有限 | 展示完整能景和采样行为，不声明计算优势 |
| Hybrid 几何产生补边 | 业务映射失真 | 完整 interaction 图门禁，失败时降为 Digital |
| VQE 有低能但末端采样不稳定 | 结果解释混乱 | 分开显示能量估计、参数选择和末端采样 |
| 四场景同时开发扩大范围 | 延迟发布 | 按执行链分阶段，共用骨架但逐场景通过发布条件 |

## 17. 架构验收

架构实现完成时应满足：

- Pauli/VQE 与 QUBO/Problem 两条执行链边界清楚；
- 四个领域模块不依赖 React 或 FastAPI；
- fixture 可以独立验证，运行时不需要化学工具或网络；
- 前端不生成量子事实；
- 所有推荐模式来自编译和领域门禁；
- 经典参考不能替换量子候选；
- 现有金融 Demo 在生物医药开发期间仍可运行和回归；
- 文档、API、测试和页面使用一致的场景名称与限制。

## 18. V2 高级实验模式架构

### 18.1 状态与兼容策略

本节是高级实验模式的目标架构，当前状态为 `IN_PROGRESS`。第八阶段已经实现 `CapabilityRegistry`、`ComplexityProfileRegistry` 和 `ExperimentPlanner`；第九至第十一阶段继续接入高级数据、批量执行、长任务和页面。第 1～17 节描述的 V1 结构仍是已实现基线。V2 采用增量扩展，不替换现有四场景、同步运行接口或金融兼容入口。

每个场景同时声明两个实验级别：

```text
standard
  -> 已验收固定预设
  -> 单次同步执行
  -> 30 秒目标

advanced
  -> 更大领域数据和有限参数扫描
  -> 完整问题到量子子问题的显式规划
  -> 配置对照、重复 seed 和长任务编排
```

高级模式不建立第二套量子执行器。它在领域适配器之前增加实验规划，在现有 Pauli/VQE 或 QUBO/Problem 执行链之外增加批量编排和结果聚合。

### 18.2 组件结构

```mermaid
flowchart LR
    UI[Advanced Experiment UI]
    API[Industry API]
    CAP[Capability Registry]
    PROF[Complexity Profile Registry]
    PLAN[Experiment Planner]
    DATA[Versioned Dataset Bundle]
    REDUCE[Deterministic Subproblem Selector]
    JOB[Local Job Manager]
    PAULI[Pauli VQE Executor]
    QUBO[Problem Executor]
    SDK[CASCAQit LocalBackend]
    AGG[Result Aggregator]
    AUDIT[Audit Report Store]

    UI --> API --> PLAN
    PLAN --> CAP
    PLAN --> PROF
    PLAN --> DATA
    PLAN --> REDUCE
    PLAN --> JOB
    JOB --> PAULI --> SDK
    JOB --> QUBO --> SDK
    SDK --> AGG --> AUDIT --> API --> UI
```

新增应用层职责：

| 组件 | 职责 | 不负责 |
|---|---|---|
| `CapabilityRegistry` | 按 CASCAQit 版本和已验证测试声明 VQE、QAOA、Hybrid、激发态、混合算子和取消能力 | 不根据导入成功猜测算法可用 |
| `ComplexityProfileRegistry` | 声明各预设的量子位、变量、项、shots、预算和时限上限 | 不动态扩大到未校准规模 |
| `ExperimentPlanner` | 展开扫描点、配置和 seed，估算成本并选择同步或长任务 | 不执行量子算法 |
| `SubproblemSelector` | 从完整领域问题确定性选择量子活动子问题，生成覆盖和排除证据 | 不修改原始评分或隐藏变量 |
| `LocalJobManager` | 限制并发、持久化状态、调度独立运行和恢复可查询结果 | 不替代 CASCAQit Backend |
| `ResultAggregator` | 聚合独立运行的成功率、分布和对照指标 | 不合并不同配置的 counts 或 hash |

### 18.3 核心数据契约

高级分析在现有 `ScenarioDefinition` 外增加规划结构：

```python
@dataclass(frozen=True)
class ComplexityProfile:
    profile_id: str
    level: Literal["standard", "advanced_live", "research"]
    max_logical_qubits: int
    max_problem_variables: int
    max_operator_terms: int
    max_measurement_groups: int
    max_shots: int
    max_objective_evaluations: int
    max_estimated_seconds: float


@dataclass(frozen=True)
class ExperimentPlan:
    plan_id: str
    case_id: str
    dataset_id: str
    dataset_manifest_hash: str
    complete_domain_problem_hash: str
    quantum_subproblem_hash: str
    profile: ComplexityProfile
    sweep_points: tuple[dict[str, object], ...]
    configurations: tuple[dict[str, object], ...]
    seeds: tuple[int, ...]
    run_count: int
    estimated_seconds: float
    execution_policy: Literal["sync", "job", "rejected"]
    diagnostics: tuple[DomainIssue, ...]
```

`run_count` 必须等于扫描点数、配置数和 seed 数的乘积。列表展开顺序固定为扫描点、配置、seed；聚合器依靠运行单元 ID，而不是数组位置关联结果。

优化场景额外保存：

```text
complete_variable_ledger
selected_variable_ids
excluded_variables[{id, reason, score, constraint_coverage}]
subproblem_coverage
selection_rule_version
selection_hash
```

Pauli 扫描额外保存模板 Hamiltonian hash、每个参数点的实例 Hamiltonian hash、Ansatz hash 和 QWC 计划 hash。聚合报告只引用各独立运行的 report hash，不复制或重写底层量子事实。

### 18.4 四场景高级数据流

#### 18.4.1 电子结构

```text
versioned geometry series
  -> Hamiltonian fixture per geometry
  -> profile and capability validation
  -> Cartesian product of geometry x configuration x seed
  -> existing PauliVQEExecutor
  -> per-point result
  -> potential-curve and stability aggregation
```

运行时仍不计算分子积分或费米子映射。一个几何系列 manifest 引用多个经过独立 checksum 校验的 Pauli fixture；缺失任一点时整个计划在执行前失败。研究档 6～8 量子位只有在发布机完成资源校准后开放。

#### 18.4.2 构象匹配

```text
complete pose-feature graph
  -> domain validation
  -> deterministic candidate ranking
  -> key-feature and conflict coverage guard
  -> 10-16 active business variables
  -> QUBO ledger and Hybrid feasibility analysis
  -> existing Problem Executor
  -> Top-K feasible candidates and sensitivity aggregation
```

裁剪发生在 QUBO 构造前，但完整问题和被排除候选必须进入审计。裁剪器先为每个强制关键特征保留局部评分最高的候选，再按局部评分、约束覆盖数和候选 ID 稳定排序填满剩余名额。排序规则和权重写入 profile 并单独版本化；不能根据某次量子或经典最优答案反向选择变量。Digital 与 Hybrid 配置必须复用同一个裁剪后 QUBO hash。

#### 18.4.3 多中心有效自旋

```text
Hamiltonian template + bounded parameter grid
  -> instantiate Pauli terms
  -> Hermitian and capability validation
  -> QWC measurement plan
  -> existing PauliVQEExecutor
  -> energy and correlation matrix
  -> parameter-series aggregation
```

有效模型模板允许 `X/Y/Z` Pauli 字符串，但每种新项类型必须进入能力测试。V1 的精确对角化继续提供基态和激发态参考；没有 VQD 或子空间算法时，量子响应 schema 不出现 `quantumExcitedState` 字段。

#### 18.4.4 小肽能景

```text
32-64 conformation library
  -> full classic landscape and basin labels
  -> diversity + energy-window + constraint coverage selection
  -> 10-16 active conformations
  -> one-hot QUBO
  -> existing Digital QAOA executor
  -> active-window samples
  -> full-landscape coverage aggregation
```

离线生成器按接触图汉明距离和 manifest 中固定的阈值生成盆地标签；构象 ID 用于距离和能量相同时的稳定排序。选择器先保留每个主要盆地的最低能代表，再按能量窗、结构多样性和约束覆盖填满活动窗口，避免只包含同一结构族。完整经典能景和量子活动窗口使用不同字段。转向/接触（turn/contact）编码属于独立研究适配器，只有 `CapabilityRegistry` 确认约束保持混合算子后才可注册为正式配置。

### 18.5 CASCAQit 能力边界

V2 只依赖当前已经验证的 SDK 核心：`PauliHamiltonian`、`VQE`、`QUBOProblemIR`、`QAOA`、`ProblemCompiler`、Hybrid D-A-D 和 `LocalBackend`。化学与生物领域预处理继续在应用侧离线完成。

| 待增强能力 | 所属层 | 最小接口要求 | 未完成时行为 |
|---|---|---|---|
| 批量扫描和重复 seed | 应用服务 | 独立调用现有 executor 并聚合 report hash | 高级配置不开放 |
| 长任务状态 | 应用服务 | 持久化任务、运行和进度快照 | 超过同步预算的计划被拒绝 |
| 目标评估进度 | SDK + 应用适配 | 优化器回调评估序号、预算和当前最佳值 | 只显示当前独立运行序号 |
| 协作式取消 | SDK + Backend | 在优化迭代和 Backend job 之间检查取消信号 | 只允许取消未开始任务 |
| VQD/子空间激发态 | CASCAQit 算法层 | 明确输入、正交约束、结果和审计契约 | 只显示经典精确能隙 |
| 约束保持混合算子 | CASCAQit QAOA | 混合算子定义、可行子空间初态和编译能力检查 | 使用罚函数 QUBO |

`CapabilityRegistry` 使用显式版本范围和通过的契约测试登记能力。环境中存在同名类、实验分支或未发布本地补丁，均不能自动提升正式能力状态。

### 18.6 API 扩展

现有标准请求保持兼容。高级请求增加可选字段：

```json
{
  "preset": "advanced_reference",
  "experimentLevel": "advanced",
  "complexityProfile": "advanced_live",
  "values": {},
  "configurations": [
    {"mode": "digital", "algorithm": "vqe", "layers": 2}
  ],
  "seeds": [7, 23, 41],
  "sweep": {
    "parameter": "bond_length_angstrom",
    "values": [0.6, 0.735, 0.9]
  }
}
```

分析仍使用现有路径，并在响应中增加 `experimentPlan`：

```text
POST /api/domains/{domain_id}/scenarios/{case_id}/analyze
```

只有 `executionPolicy=sync`、`run_count=1` 的计划可以继续使用现有 `/run`。任何包含多个扫描点、配置或 seed 的计划，以及所有研究计划，都使用新增长任务接口：

```text
POST /api/domains/{domain_id}/scenarios/{case_id}/jobs
GET  /api/jobs/{job_id}
POST /api/jobs/{job_id}/cancel
```

任务创建必须携带最新 `plan_id`；服务端重新计算输入签名并拒绝过期计划。`job_id` 由服务端生成，不接受用户路径。取消能力按 `canCancelPending` 和 `canCancelRunning` 分开返回，前端不能假设运行中的 Backend 一定可中止。

### 18.7 长任务、并发和恢复

任务状态机：

```text
queued -> running -> succeeded
                  -> partially_succeeded
                  -> failed
queued -> cancelled
running -> cancel_requested -> cancelled  # 仅能力支持时
```

- 默认只运行一个重计算任务，队列长度有配置上限；
- 每个扫描点、配置和 seed 是独立运行单元，失败不覆盖已完成证据；
- `partially_succeeded` 必须列出成功、失败、未开始和取消的运行单元；
- 任务元数据和 report hash 写入用户数据目录，进程重启后已完成结果仍可查询；
- 任务状态保存在 `jobs/<job_id>/job.json`，写入时使用同目录临时文件和原子替换；进程内锁保证单服务进程不会并发覆盖状态；
- 进程内执行继续使用线程池，事件循环必须能响应 health、静态资源和任务查询；
- V2 首期不承诺跨进程继续执行正在运行的本地模拟，只恢复终态和把中断任务标记为失败；
- 缓存键增加 `plan_id`、复杂度配置、扫描定义、配置集合和 seed 集合。

### 18.8 前端结构

标准模式保持当前三栏工作台。高级模式在中间控制区增加实验级别、复杂度配置、有限扫描、配置对照和 seed 控件；右侧增加两个领域中性视图：

| 视图 | 内容 |
|---|---|
| 复杂度与成本 | 完整领域规模、量子子问题规模、资源估算、覆盖率、排除原因和能力诊断 |
| 实验矩阵 | 扫描点 × 配置 × seed 状态、聚合指标和独立报告入口 |

固定格式矩阵使用稳定网格尺寸和横向局部滚动，不造成页面级横向溢出。移动端先显示聚合摘要，单个运行通过标签或抽屉查看；不在同一画布叠加全部曲线。任务运行时允许切换结果标签和领域，但当前任务状态按 `job_id` 独立保存。

### 18.9 测试与质量门禁

V2 在现有测试基础上增加：

- 复杂度配置上下界、成本估算和拒绝路径；
- 扫描展开顺序、配置笛卡尔积和 seed 独立性；
- 完整问题到量子子问题的确定性、关键覆盖和排除账本；
- 多点 Pauli fixture、模板 Hamiltonian 和实例 hash；
- 任务状态机、队列上限、部分成功、重启恢复和取消能力差异；
- 单个运行失败不污染其他运行的 counts、报告或聚合统计；
- 标准模式 API 和浏览器回归；
- 高级模式三种视口、实验矩阵、长任务状态和局部滚动；
- 每个高级推荐预设至少三个固定 seed 的发布校准；
- wheel 和 Windows 离线包包含全部高级 fixture、profile 和前端资源。

发布报告必须分别记录标准模式和高级模式的最大分析时间、最大单次运行时间、完整任务时间、峰值内存和失败率。模拟器规模数据不能外推为真实硬件性能。

### 18.10 V2 分阶段实施

#### 第八阶段：高级实验公共骨架

- 实现 Capability Registry、Complexity Profile 和 Experiment Plan；
- 实现成本门禁、完整问题/量子子问题身份和分析响应；
- 保持标准模式行为和 API 回归。

状态（2026-07-30）：已完成。当前目录公开标准、高级实时和研究三档 profile；只有标准档标记为 `available`。四场景标准分析均返回单运行 `sync` 计划；高级档、批量执行、量子激发态和约束保持混合算子仍按能力快照明确拒绝，等待后续阶段逐项启用。

#### 第九阶段：高级 Pauli 场景

- 接入多点电子结构 fixture 和配置对照；
- 接入 3～4 位点有效自旋模板与参数扫描；
- 完成批量运行、观测量聚合和经典参考分离。

状态（2026-07-30）：已完成。电子结构已接入 5 点 LiH 势能扫描；活性中心已接入 3 位点受挫网络和 4 位点环形网络；公共运行单元按扫描点、配置、seed 稳定展开并支持部分成功聚合。持久化任务 API 仍属于第十一阶段，因此公开批量能力在该接口完成前继续标记为不可用。

#### 第十阶段：高级组合优化场景

- 接入多构象匹配完整业务图和确定性裁剪；
- 接入更大小肽构象库、盆地识别和活动窗口；
- 完成 Digital/Hybrid 对照及完整领域覆盖报告。

#### 第十一阶段：长任务与发布验收

- 完成长任务状态、并发限制、部分成功和可用的取消语义；
- 完成三视口高级工作流、性能校准和离线包；
- 逐条复核 V2 PRD、能力门禁、架构契约和发布说法。

### 18.11 新增风险

| 风险 | 影响 | 架构处理 |
|---|---|---|
| 本地状态向量模拟随量子位指数增长 | 高级配置无法现场完成 | 校准 profile、执行前成本门禁、量子子问题上限 |
| 领域问题很大但量子子问题较小 | 用户误解为完整求解 | 同屏显示两种规模、裁剪账本和覆盖率 |
| 批量运行放大失败和耗时 | 页面长时间不可用 | 有界队列、独立运行单元、部分成功和异步状态 |
| 参数扫描产生大量近似结果 | 用户只选择最好看的点 | 固定扫描计划、完整点集报告、失败点不删除 |
| 新 SDK 能力只存在本地分支 | 发布包无法复现 | 显式能力注册、版本门禁、禁止未发布补丁 |
| 精确参考被误认为量子激发态 | 科学结论错误 | 响应 schema 和页面明确标记经典来源 |

### 18.12 需求到组件的映射

该映射与 PRD 15.11 的需求编号共同作为第十一阶段验收索引。组件名称是职责边界，不要求每项对应一个同名源文件。

| 需求编号 | 主要组件 | 核心持久化或身份 | 失败时行为 |
|---|---|---|---|
| `BIO-V2-PLAN-01` | `CapabilityRegistry`、`ComplexityProfileRegistry`、`ExperimentPlanner` | capability snapshot、profile ID、`plan_id` | 返回 `rejected` 计划和结构化诊断，不进入执行器 |
| `BIO-V2-ES-01` | 电子结构适配器、Pauli VQE 执行器、结果聚合器 | geometry-series manifest、逐点 Hamiltonian/report hash | 任一 fixture 损坏时整项计划在执行前失败；单个运行失败进入部分成功统计 |
| `BIO-V2-METAL-01` | 有效自旋模板实例化器、Pauli VQE 执行器、观测量聚合器 | template hash、instance hash、QWC plan hash | 不支持的 Pauli 项在能力检查阶段拒绝；经典能隙不写入量子结果字段 |
| `BIO-V2-DOCK-01` | 完整业务图、`SubproblemSelector`、QUBO 适配器、Problem 执行器 | complete-problem hash、selection hash、QUBO hash | 关键特征覆盖不足或 Hybrid 门禁失败时拒绝对应配置；不得补造候选或替换结果 |
| `BIO-V2-PEP-01` | 构象库加载器、盆地标注器、`SubproblemSelector`、QUBO 适配器 | landscape hash、basin-rule version、selection hash | 构象校验或盆地覆盖失败时不生成活动窗口 |
| `BIO-V2-JOB-01` | `LocalJobManager`、运行单元调度器、`ResultAggregator` | `jobs/<job_id>/job.json`、run/report hash | 保留已完成证据，明确区分失败、未开始和取消的运行单元 |
| `BIO-V2-UI-01` | 行业工作台外壳、高级控制区、复杂度视图、实验矩阵 | analysis/plan/job ID | 过期计划不能执行；领域切换不覆盖其他任务状态 |
| `BIO-V2-REL-01` | 校准脚本、测试门禁、打包流程、验收报告 | calibration/report/package checksum | 任一场景或发布包未通过时，高级入口保持研究状态 |
