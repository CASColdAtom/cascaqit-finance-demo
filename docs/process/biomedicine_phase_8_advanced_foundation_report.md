# 生物医药第八阶段高级实验骨架报告

日期：2026-07-30

## 1. 阶段结论

本阶段完成 V2 高级实验模式的公共规划层，不改变四个现有量子执行器。标准模式继续使用原有单次 `/run`；每次生物医药分析新增稳定的 `experimentPlan`，明确记录复杂度档位、领域问题和量子子问题身份、运行数量、估计时间、执行策略、能力快照和拒绝原因。

高级场景数据、批量任务和高级前端尚未在本阶段开放。目录中的 `advanced_live` 和 `research` 均标记为 `planned`，高级请求返回 `rejected` 计划，不用当前标准 fixture 冒充高级实验。

## 2. 已实现内容

| 范围 | 实现 |
|---|---|
| SDK 能力注册 | 显式校验 CASCAQit `>=1.0.5a0,<1.0.6`；分别登记 Pauli/VQE、QWC、Digital QAOA、Hybrid D-A-D、批量执行、取消、激发态和混合算子状态 |
| 复杂度档位 | 四场景各有 `standard`、`advanced_live`、`research`，包含量子位、变量、项、测量组、shots、目标评估和预计时间上限 |
| 实验计划 | 稳定生成 `planId`、完整领域问题 hash、量子子问题 hash、扫描点、配置、seed、运行数量和成本 |
| 成本与能力门禁 | 资源、shots、目标评估、单运行预计时间、SDK 版本、Hybrid 和批量执行均有结构化诊断 |
| 有限扫描 | 高级分析请求可以声明一个已登记控件的 1～9 个值；每个点独立完成领域分析和 problem hash |
| API | 分析请求兼容 V1，并增加 `experimentLevel`、`complexityProfile`、配置、seed 和 sweep；新增 `/api/domains/biomedicine/capabilities` |
| 前端契约 | TypeScript 增加 profile、capability、plan 和高级分析请求类型；标准页面行为不变 |

## 3. 关键不变量

- `runCount = 扫描点数 × 配置数 × seed 数`；
- 同一输入重复分析得到相同 `planId`；
- 标准计划只有一个运行单元且资源未超限时才返回 `sync`；
- 批量能力未开放时，多运行计划必须返回 `rejected`；
- 不受支持的 CASCAQit 版本不能生成可执行计划；
- 高级档位未发布时返回 `COMPLEXITY_PROFILE_NOT_AVAILABLE`；
- 分析失败使用 `analysis` 阶段，计划参数失败使用 `planning` 阶段；
- 经典参考、当前分析结果和未来批量聚合不改变底层量子结果身份。

## 4. 验证结果

| 门禁 | 结果 |
|---|---|
| Python 全量 | `239 passed in 250.61s` |
| 第八阶段专项 | `27 passed` |
| Ruff / diff check | 通过 |
| React | 9 个文件，`38 passed` |
| TypeScript | 通过 |
| Vite 生产构建 | 通过 |
| npm audit | `0 vulnerabilities` |

专项测试覆盖四场景标准计划、目录 profile、能力接口、SDK 版本范围、计划稳定性、运行数量、扫描顺序、超资源和超成本拒绝、未发布高级档位、批量能力缺失、未知扫描参数及规划错误结构。

## 5. 后续边界

- `advanced_live` 与 `research` 仍是规划状态，第九、十阶段接入真实高级 fixture 后才能逐场景改为可用；
- `batch_execution`、任务持久化和运行状态仍未实现，多扫描点、配置或 seed 的计划不能执行；
- 当前量子子问题选择规则是 `identity.v1`。对接和小肽的完整问题裁剪与排除账本属于第十阶段；
- VQD/子空间激发态、约束保持混合算子和运行中协作取消仍无已验证 SDK 能力；
- 本阶段没有新增页面控件，避免在执行链未完成前展示不可用操作。
