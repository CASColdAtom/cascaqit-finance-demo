# 生物医药与材料第十五阶段：Pure Analog AHS 实现报告

日期：2026-07-30

## 1. 阶段结论

`MAT-V1-AHS-01` 已从 Preview 升级为 `available`。场景覆盖版本化材料有效晶格、四位点活动窗口、声明初态、真实 AHS 前缀程序、逐时点量子观测量、终态采样、独立 DOP853 对照、稳定审计和材料专用页面。

本阶段模拟的是材料问题对应的四位点有效 Rydberg 多体模型，不是材料晶体的全电子或全原子实时演化，也不代表真实硬件执行、材料寿命、输运性质或量子优势。

## 2. 数据与预设

- 数据集：`materials.effective-lattice.rydberg-quench.teaching-v1`，版本 `1`；
- 数据目录：`src/cascaqit_materials_demo/data/rydberg_dynamics/effective_lattice_quench/1`；
- 三个预设：`perfect_lattice`、`single_vacancy`、`multi_defect_impurity`；
- 每个预设固定 4 个活动位点，Hilbert 空间维度为 16；
- 材料晶格、有效模型活动窗口和 Rydberg 编译坐标分别持久化并独立哈希；
- `domain.json` SHA-256：`7972c2cacc57b8c92659c6056b812b4ef0a23f5ece2ba5fe32e4ad904c53a411`。

固定 fixture 只用于教学演示。页面不把 Rydberg 原子阵列描述为真实材料原子排布，也不接受浏览器提交任意 Hamiltonian 脚本。

## 3. CASCAQit 契约与执行语义

运行时硬门禁要求 CASCAQit `>=1.0.5a0,<1.0.6`，并记录模块来源。当前验收解析到相邻源码中的 `1.0.5a`，使用公开 API：

- `AHSProgram`、`AtomRegister`、`Waveform`；
- `validate_program` 与目标快照；
- `SimulationState.from_amplitudes()`；
- `AnalogStateVectorKernel.evolve()`。

高层 `LocalAhsSimulator.run()` 只支持全基态和终态，因此不用于生成时序结果。零时刻返回声明初态；每个非零采样时刻都从同一声明初态出发，独立构造覆盖 `[0,t]` 的完整 AHS 前缀程序并执行。时点之间不插值，不把上一时点终态作为下一时点输入，也不把多次终态拼接成单次硬件轨迹。

Pure Analog 证据要求 Digital gate、Digital residual 和 Hybrid block 均为 0，并验证目标 Hamiltonian 的驱动、失谐和相互作用项无漏项、无补项。任何版本、目标、布局、初态、波形、规模或项账本失败都返回稳定结构化诊断，不切换到 Digital 或经典计算。

## 4. 结果与经典对照

每个时点保存请求时间、实际时间、AHS 程序 hash、状态 hash、结果 hash、solver 信息、逐位点占据、平均激发/磁化和二点关联。终态 counts 只由当前量子态按请求 seed 和 shots 采样。

独立 SciPy `DOP853` 从同一声明初态求解同一有效 Hamiltonian，只进入 `classicReference`。经典曲线不回填 Analog 时间序列、counts 或量子观测字段。

## 5. 发布校准

结构化证据位于 `docs/process/evidence/materials_analog_calibration.json`。配置覆盖 3 个预设与 seeds `7/23/41`，共 9 次运行；每次使用 9 个采样时刻、每时刻 128 shots，终态 RK4 使用 320 个时间步。

校准结果：

- 9/9 通过，失败数为 0；
- 最大逐位点占据绝对误差：`5.112615205249416e-6`；
- 最大二点关联绝对误差：`9.814506272354251e-6`；
- 最小终态保真度：`0.9999999998217326`；
- 单次最长执行时间：`0.560836583` 秒；
- 9 次运行的 Digital gate、Digital residual 和 Hybrid block 均为 0；
- 每次终态 counts 总数均为 128。

门槛分别为占据/关联误差不超过 `1e-3`、状态范数误差不超过 `1e-9`、终态保真度不低于 `0.999`。校准证明当前四位点本地实现与独立数值参考一致，不构成产业规模性能结论。

## 6. API、页面与错误契约

统一端点已接通：

```text
POST /api/domains/materials/scenarios/rydberg_dynamics/analyze
POST /api/domains/materials/scenarios/rydberg_dynamics/run
```

非法输入、非 Analog 模式、非 AHS 算法和执行证据失败分别返回：

```text
MATERIALS_AHS_INPUT_INVALID
MATERIALS_AHS_MODE_UNSUPPORTED
MATERIALS_AHS_ALGORITHM_UNSUPPORTED
MATERIALS_AHS_EXECUTION_INVALID
```

页面提供有效晶格/缺陷/杂质视图、Rydberg 布局、实际逐位点占据时间序列、DOP853 虚线对照、终态 counts、脉冲与项账本、Pure Analog 零 Digital/Hybrid 证据。Analog 结果使用判别联合，不访问 QAOA 参数或数字线路字段。

## 7. 验证状态与剩余风险

阶段定向门禁已通过：后端 45 项定向测试、前端 `MaterialsViews` 5 项、`App` 8 项、TypeScript 类型检查、Ruff 检查和 9 次发布校准。最终自动化门禁结果：

```text
Python 全量测试                         319 passed
前端全量测试                           11 files / 50 passed
TypeScript typecheck                   passed
Ruff（src + tests + calibration）      passed
Vite 生产构建                           passed
CASCAQit 1.0.5a wheel 构建             passed
Demo wheel 构建与解包内容核验            passed
wheel 隔离目录导入、分析与运行 API         passed
```

Demo wheel 已确认包含 `rydberg_dynamics.py`、两个版本化 AHS fixture 文件和本次 Vite 构建的 `MaterialsViews` 静态资源。隔离探针从 `/tmp` wheel 加载 CASCAQit `1.0.5a`，合法五时点请求的 analyze/run 均返回 200，Pure Analog 三个 Digital/Hybrid 计数仍为 0。低于产品下限的 `sample_count=3` 返回 422，证明发布包保留输入门禁。

Chromium 三视口验收尚未通过。当前托管 macOS 环境在 Chromium Mach 服务注册阶段返回 `Permission denied (1100)`；用户已允许启动 Chromium，但会话系统沙箱未提供提升权限入口。组件测试和脚本语法检查不能替代桌面、紧凑桌面与移动端截图证据。

剩余科学与工程边界：

- 本地模拟器上限仍为 4 个活动原子，完整材料晶格不进入 AHS 核心；
- 时序由同初态的独立前缀程序产生，不声称单次连续硬件采样；
- fixture 参数不等于运行时 DFT、实验反演或材料数据库预测；
- 材料有效模型结果不能外推为蛋白全原子动力学；
- 真实硬件、噪声标定、连续采样和超过四位点的规模策略仍未交付。
