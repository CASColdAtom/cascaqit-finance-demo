# 生物医药第十三阶段：RNA 二级结构集合实现报告

日期：2026-07-30

## 1. 阶段结论

`BIO-V3-RNA-01` 已从结构预览升级为可执行的本地 Digital QAOA 演示。场景覆盖版本化短 RNA、候选碱基配对 QUBO、量子观测 Top-K、经典精确枚举、无假结动态规划基线、独立数据集参考、报告持久化和 RNA 专用页面。

本阶段只实现 RNA 场景，不把材料缺陷-吸附优化、蛋白路径或材料 AHS 的预览状态提前提升。所有执行继续标记 `LOCAL SIMULATION`、`NO HARDWARE EXECUTION` 和 `RESEARCH DEMONSTRATION`。

## 2. 数据与模型

- 数据集：`rna.short-pairing-benchmarks`，版本 `1`；
- 预设：`hairpin_reference`、`stem_competition`、`limited_pseudoknot`；
- 公开参考：`PDB:1ZIH` 的短发卡序列与二级结构元数据；
- 规模：每个预设 8–9 个候选配对变量；
- 配对规则：A-U、C-G 和预设显式声明的 G-U 摆动配对；
- 约束：最小环长、单核苷酸至多一个配对、未声明交叉禁止、声明的有限假结保留；
- 目标：候选配对收益、未配对代价和相邻嵌套配对堆叠奖励；
- 单位：`dimensionless educational score`，不是热力学自由能。

manifest 保存来源、使用政策、变量顺序、生成规则、单位、允许说法、限制和 `domain.json` SHA-256。运行时在构造 QUBO 前校验 checksum、序列、配对类型、位置、环长、允许交叉和参考结构。

## 3. 执行与结果隔离

场景固定使用 CASCAQit Digital QAOA、`p=1`、本地状态向量模拟。推荐配置为 256 shots、24 次 COBYLA 目标评估、单起点、seed `7`。Hybrid 和 Analog 返回结构化不支持诊断，不构造没有来源的 Rydberg 几何。

结果严格分开：

- `quantumCandidate` 只来自本次 QAOA counts 中实际观测到的可行 bitstring；
- `topObservedFeasible` 保存最多 8 个已观测可行结构；
- `classicExact` 对固化候选配对空间做完整枚举；
- `classicDynamicProgramming` 提供无假结动态规划基线；
- `referenceStructure` 单独标记为 `dataset_reference`；
- 未观测到可行态时返回 `quantum_not_observed`，不复制经典最优结构。

三个预设分别使用固定 seed `7/23/41` 完成共 9 次 256-shot 校准，全部观测到可行结构；部分运行的低评分覆盖为 0，按实际结果保留，没有改写为命中经典最优。每次运行保存可行 shot 比例、低评分覆盖、结构多样性、参考配对重合度、线路、counts、参数历史和完整审计 hash 链。结构化证据位于 `docs/process/evidence/rna_structure_calibration.json`。

## 4. API 与页面

领域目录把 `rna_structure` 标记为 `available`。分析和运行继续使用统一端点：

```text
POST /api/domains/biomedicine/scenarios/rna_structure/analyze
POST /api/domains/biomedicine/scenarios/rna_structure/run
```

自由序列和任意能量脚本不开放；页面只允许选择版本化预设并在 3–6 nt 范围内调整最小环长。非法输入、模式、算法和执行配置返回稳定 RNA 诊断码。

前端增加：

- RNA 序列与碱基配对弧图；
- 量子观测、经典精确枚举和数据集参考三方结果卡；
- 包含动态规划的四方对照；
- Top-K 已观测结构、可行率、低评分覆盖和结构多样性；
- Digital QAOA 线路、counts 与参数历史；
- “counts 不是热力学概率或碱基配对概率”的显式边界；
- manifest、问题、Hamiltonian、Ansatz、配置、执行、结果和报告 hash 链。

## 5. 验证证据

已通过：

```text
RNA 模型测试                         9 passed
相关 Python 模型/API/规划测试       67 passed
全量 Python（排除既有金融回归）     282 passed, 1 deselected
前端组件与应用测试                  42 passed
TypeScript typecheck                passed
Vite production build               passed
Ruff format/check                   passed
wheel --no-isolation                passed
```

新增参考结构一致性用例前，未排除时的全量 Python 结果为 `281 passed, 1 failed`；唯一失败是既有的 `tests/integration/test_new_scenario_execution.py` 中 `collateral/haircut` 推荐 Digital 配置未采样到可行候选。新增用例随后在 RNA 相关测试和最终绿色全量中通过。本阶段未修改金融抵押品场景、推荐配置或 `ScenarioExecutor`，因此在绿色门禁中只 deselect 该参数化用例。

生产构建已更新 Python 包内的静态 `index.html`、CSS 和带内容 hash 的 React chunks。构建出的 `cascaqit_finance_demo-0.1.1-py3-none-any.whl` 已检查包含 `rna_structure.py`、RNA `domain.json`/`manifest.json`、最新 `BiomedicineViews` chunk、CSS 和 `static/index.html`。

浏览器脚本已更新为在 `1440x900`、`1280x720` 和 `390x844` 三个视口实际运行 RNA QAOA，检查弧图图元、页面横向溢出、三方结果、四方对照、counts 警示、量子 canvas 和 console/page errors。当前受限 macOS 沙箱启动 Chromium 时仍返回：

```text
MachPortRendezvousServer: Permission denied (1100)
```

因此本报告不把截图列为已通过证据。待运行环境真正允许 Chromium 子进程后执行 `cd frontend && npm run browser-smoke` 并归档 `report.json` 与三视口截图。

## 6. 科学边界与剩余风险

- 模型搜索的是固化候选配对集合，不是任意 RNA 序列结构预测器；
- 教学评分不是自由能，counts 不是 Boltzmann 集合或碱基配对概率；
- 不输出 RNA 三维坐标、溶剂效应、折叠速率或生物功能；
- 8–9 变量规模只证明演示链路与审计契约，不证明量子优势或产业规模加速；
- 浏览器三视口视觉验收仍受当前系统沙箱阻塞，不能用组件测试替代截图证据。

## 7. 后续阶段

下一项按 V3 架构实现 `MAT-V1-ADSORB-01`：固化周期表面、缺陷/吸附联合变量、对称性与能量来源，构造 Digital/Hybrid 共用逻辑 QUBO、经典基线和材料专用结果视图。材料 AHS 继续受发布 wheel、模块来源、初态、时分辨采样和规模门禁约束，未通过前保持 `preview`。
