# 生物医药第二阶段：构象匹配实现报告

日期：2026-07-29

## 1. 阶段结论

“靶点口袋与配体候选构象匹配”已从结构预览升级为可执行的本地量子演示。场景从 PDB `1HSG` / Indinavir 的离线派生特征出发，构建带逐系数来源账本的 QUBO；CASCAQit 完成 Hybrid D-A-D QAOA 或 Digital QAOA 编译、参数优化、LocalBackend 模拟和采样。

本阶段没有完成全部四个生物医药场景。当前可执行的是电子结构与构象匹配；金属活性中心和小肽能景仍保持预览和后端运行门禁。

## 2. 数据与许可

- 数据集标识：`docking.1hsg.indinavir.discrete-match`；
- PDB：`1HSG`，配体 component `MK1`，名称 `INDINAVIR`；
- DOI：`10.2210/pdb1hsg/pdb`；
- 原始 mmCIF SHA-256：`d2ba73b5c4be05c45275571bbb4dd042347927f91c6c05038c0df5d1ce23c268`；
- RCSB PDB 政策在 2026-07-29 核对：PDB archive 数据文件使用 CC0-1.0，外部集成注释需遵循各自条款；
- 运行包只保存最小派生数据、原始文件标识和 checksum，不在 API 请求时访问网络。

fixture 固化两个候选 pose、八个候选匹配和四条互不重叠的冲突边。所有冲突都记录规则和几何/占位证据；数据只用于离散匹配演示，不是连续空间对接结果。

## 3. QUBO 与 Hybrid 门禁

业务变量包括八个匹配变量和两个 pose selector，另有一个覆盖 slack 变量。目标包含匹配奖励、距离/角度偏差、关键特征覆盖和构象应变；约束包含单一 pose、match-to-pose 依赖、特征/占位/碰撞冲突和最低覆盖。

四组冲突使用同 pair 内 `6 μm`、单元间 `28 μm` 的确定性布局。当前 Target 的 blockade interaction 图与声明冲突图完全一致：

- 四条冲突贡献全部覆盖；
- 无业务漏边和物理补边；
- 几何来源为 `verified_embedding`；
- Hybrid 同时存在 Analog 项和非空 Digital residual；
- QUBO 贡献账本逐项守恒；
- 生物医药 API 不暴露 `FINANCE_*` 诊断码。

## 4. 领域结果边界

结果对象始终分成：

1. `quantumCandidate`：只来自当前量子 shots 的观测候选；
2. `classicOptimum`：对固化小规模 QUBO 的完整经典枚举；
3. `coCrystalReference`：共晶结构派生的离散相互作用参考。

量子候选不可行时不会被经典结果替换。页面另列 Top-K 已观测可行候选和原始约束复核。评分为无量纲模型目标，不输出结合自由能、Kd、Ki、IC50 或药效判断。

## 5. 校准与验收

推荐配置为 Hybrid QAOA、`p=1`、128 shots、连续 COBYLA、12 次目标评估、单起点。固定 seed `1`、`6`、`7` 均真实观察到量子可行候选；默认 UI seed 为 `7`。Digital QAOA 保留为独立对照路径，不复用 Hybrid counts。

自动门禁覆盖：`187` 项 Python 单元/集成测试、Ruff、TypeScript、`27` 项 React 测试、Vite 生产构建、wheel，以及 `1440 x 900`、`1280 x 720`、`390 x 844` 三视口真实浏览器运行。浏览器检查构象匹配与 H2 两条执行链、canvas 非空像素、结构 SVG、横向溢出、console error 和 page error。

## 6. 当前风险与下一步

最强的架构债务是组合优化执行核心仍位于金融包内。生物医药数据、领域模型、QUBO builder 和贡献类型已经独立，但 `DockingMatchScenario` 通过结构协议复用现有 `ScenarioExecutor`。第三阶段接入金属活性中心前应提取领域中性的共享执行核心，避免继续扩大跨领域命名债务。

下一阶段实现“金属酶活性中心有效 Hamiltonian”：固化有效自旋模型 manifest，接通 Digital VQE、精确对角化和后端计算的单点磁化/两点关联；不输出催化势垒、反应速率或酶活性预测。
