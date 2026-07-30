# 生物医药第九阶段高级 Pauli 场景报告

日期：2026-07-30

## 1. 阶段结论

第九阶段完成 `BIO-V2-ES-01` 和 `BIO-V2-METAL-01` 的数据、分析、单运行执行与批量聚合基础。电子结构新增 5 点 LiH 势能扫描；金属活性中心新增 3 位点受挫网络和 4 位点环形网络。两类场景继续复用 CASCAQit `PauliHamiltonian`、Digital VQE、QWC 分组测量和 `LocalBackend`，没有引入第二套量子执行器。

持久化任务 API 尚未实现。高级多运行计划会如实返回 `BATCH_EXECUTION_NOT_AVAILABLE`，不会绕过成本门禁同步执行。公共运行单元展开和部分成功聚合已经完成，供第十一阶段的 `LocalJobManager` 调用。

## 2. 电子结构

| 项目 | 实现结果 |
|---|---|
| 高级预设 | `lih_potential_scan` |
| 几何点 | LiH 1.2、1.4、1.6、1.8、2.2 Å |
| 量子规模 | 每点 4 个逻辑量子位，固化 Pauli Hamiltonian |
| 生成工具 | PySCF 2.10.0、OpenFermion 1.7.1、OpenFermion-PySCF 0.5 |
| 分析证据 | 逐点 dataset/manifest/problem hash、资源快照和经典势能参考 |
| 执行边界 | 运行时不计算分子积分或费米子映射；经典精确结果不替换 VQE 结果 |

九组电子结构 fixture 使用同一个生成脚本 hash。5 点扫描在相同输入下生成稳定 `planId`，每个几何点保留独立 analysis hash 和 Hamiltonian hash。

## 3. 多中心有效自旋

| 预设 | 位点 | 交换路径 | Pauli 项 | 用途 |
|---|---:|---:|---:|---|
| `trinuclear_frustrated` | 3 | 3 | 12 | 三角反铁磁受挫与不均匀局域场 |
| `tetranuclear_ligand_field` | 4 | 4 | 16 | 环形不等价交换路径与交错局域场 |

加载器根据预设选择版本化 fixture，并从 `exchange_paths` 和 `fields` 通用展开 Hamiltonian。原双位点预设继续保留 `exchange.xx/yy/zz` 与 `field.m1/m2` term ID。分析和执行分别保存模板 Hamiltonian hash 与参数实例 Hamiltonian hash；结果返回全部位点磁化和带路径、左右位点标识的 `XX/YY/ZZ` 关联。

基态和第一能隙来自同一实例 Hamiltonian 的经典精确对角化。响应使用 `exactFirstGapSource=classical_exact_diagonalization`，没有 `quantumExcitedState` 或 VQD 表述。

## 4. 批量运行基础

`advanced_runner.py` 提供以下应用层能力：

- 按扫描点、配置、seed 的固定顺序展开独立运行单元；
- 使用 `planId`、点/配置索引、analysis/problem hash 和 seed 生成稳定 `runId`；
- 每个运行单元单独保存 report hash 和领域指标，不合并 counts；
- 单元失败只记录异常类型和消息，不生成经典回退指标；
- 聚合成功率、中位数、四分位数、最小值、最大值，以及逐点和逐配置摘要；
- 区分 `succeeded`、`partially_succeeded` 和 `failed`。

公开能力注册仍把 `batch_execution` 标记为不可用。只有第十一阶段完成有界队列、持久化状态和任务 API 后，规划器才允许多运行计划进入 `job` 策略。

## 5. 验证证据

| 门禁 | 结果 |
|---|---|
| Python 全量 | `254 passed in 224.73s` |
| 第九阶段与发布专项 | `75 passed in 11.12s` |
| Ruff | 通过 |
| React | 9 个文件，`38 passed` |
| TypeScript | 通过 |
| Vite 生产构建 | 通过 |
| npm audit | `0 vulnerabilities` |
| wheel | 构建通过，SHA-256 `6f296bb9240fd273a5e71dcf54c8eb25cb03a2fc35d073bddba61b4ceeb0bc24` |
| wheel 内容 | 14 组 manifest、5 点 LiH、高级 3/4 位点模型、`advanced_runner.py` 和最新前端资源均存在 |

专项测试覆盖脚本 hash、manifest checksum、5 点计划、3/4 位点项数、模板/实例 hash、两层 VQE、全部多中心观测量、经典能隙标识、运行单元顺序、聚合统计和部分失败隔离。

## 6. 后续边界

- 第十阶段接入高级构象匹配和小肽能景，并把 `identity.v1` 选择规则替换为带排除账本的确定性活动子问题选择；
- 第十一阶段实现持久化任务、队列上限、任务 API、页面实验矩阵和三视口验收；
- 研究档 6～8 量子位尚未完成发布机校准，继续保持 `planned`；
- 量子激发态、约束保持混合算子和运行中协作取消仍没有已验证 SDK 支持。
