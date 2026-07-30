# 生物医药第十四阶段：蛋白构象转变路径实现报告

日期：2026-07-30

## 1. 阶段结论

`BIO-V3-PROTEIN-DYN-01` 已从结构预览升级为 `available`。场景覆盖版本化构象状态网络、连接保持活动子图、完整路径 QUBO、Digital QAOA、有界 Dijkstra 对照、报告持久化、校准和蛋白路径专用页面。

本阶段实现的是有限状态网络上的离散路径优化，不是全原子蛋白折叠、结构预测、实时动力学或量子分子动力学。材料 Rydberg Pure Analog 场景不属于本阶段，继续保持 Preview。

## 2. 数据与选择

- 数据集：`protein.adenylate-kinase.conformation-network.teaching-v1`，版本 `1`；
- 完整规模：7 个构象状态、15 条有向允许转移；
- 预设：`open_to_closed`、`barrier_shift`、`alternate_basin`；
- 端点标签：RCSB PDB `4AKE` 开放态和 `1AKE` 闭合态；
- 中间态：项目编写的粗粒化教学质心，不冒充实验结构或 MD 轨迹；
- 边权：`structuralCost + barrierWeight * barrierProfile`；
- 单位：`dimensionless_model_cost`，不是时间、速率、驻留时间或自由能。

连接优先选择器先对完整网络执行有界最短路，锁定起点、终点和完整通路，再按前八条候选路径覆盖与盆地多样性补足活动节点。标准活动子图包含 4 个状态、4–5 条边和 2–3 条完整通路；选择前后的网络与 selection 分别保存 hash。若起终点、完整路径或活动子图连通性不能保留，分析阶段拒绝构造 QUBO。

## 3. QUBO 与执行

时间片状态变量在 `maximum_steps=3..4` 时使用 9–12 个逻辑变量。QUBO 分组覆盖：

- 起点：第一时间片必须是起点的声明后继；
- 终点：最后时间片固定为目标态；
- 流守恒与连续：每片恰好一个状态，相邻时间片只允许 manifest 中的有向转移；
- 禁止回路：非目标状态不能在多个时间片重复；
- 最大路径长度：有限时间片定义严格上限，目标态只作吸收填充；
- 目标：声明边权之和。

每个平方罚项和转移代价都进入来源贡献账本，最终 QUBO 通过系数守恒校验。场景只开放 Digital QAOA、`p=1` 和本地状态向量模拟；没有经过验证的 Rydberg 几何，因此 Hybrid 与 Pure Analog 均返回结构化不支持诊断。

`quantumCandidate` 只从本次 counts 中重新通过六项约束的 bitstring 产生。未观测到可行路径时返回 `quantum_not_observed` 和 `null`，失败原因按 shot 统计；完整网络和活动子图的有界 Dijkstra 结果只进入经典字段。

## 4. 校准

发布配置为 Digital QAOA、`p=1`、256 shots、4 次 COBYLA 目标评估、单起点、`maximum_steps=3`、`barrierWeight=1.0`。三个预设分别使用 seeds `7/23/41`，共 9 次运行：

- 6 次观测到可行路径，3 次为 `quantum_not_observed`；
- 可行 shot 比例范围为 0–2.734375%；
- 默认 seed `7` 的三个预设均观测到可行路径；
- 已观测路径代价为 2.10–3.50；
- 与完整网络经典最短路的有向边 Jaccard 重合度为 0%、25% 或 100%；
- 三次未观测运行未回填经典路径，主要失败原因完整保留为 one-hot 连续性、终点、允许转移和重复状态约束。

结构化证据位于 `docs/process/evidence/protein_dynamics_calibration.json`。校准只描述当前本地模拟器、有限 shots 和固定教学网络，不构成量子优势或实际动力学性能声明。

## 5. API、报告与页面

统一端点已接通：

```text
POST /api/domains/biomedicine/scenarios/protein_dynamics/analyze
POST /api/domains/biomedicine/scenarios/protein_dynamics/run
```

分析返回完整网络、活动节点/边、排除账本、约束编码、完整/活动经典路径和 `conformationSetHash`、`transitionNetworkHash`、`selectionHash`、`pathQuboHash`。运行报告继续使用 `biomedicine.execution-report.v1`。

前端增加：

- 完整构象网络与活动子图高亮；
- 起点、终点、边权、来源和排除状态；
- 量子观测路径图，空结果不画经典路径；
- 量子、完整网络 Dijkstra、活动子图 Dijkstra 三方对照；
- 可行 shot 比例、路径代价、路径重合度和失败原因；
- Digital QAOA 线路、counts、参数历史与 hash 审计；
- “counts 不是转移概率，pathCost 不是时间/速率/驻留时间”的科学边界。

## 6. 验证状态

阶段定向门禁已通过：

```text
蛋白模型与三 seed 测试              9 passed
蛋白 API 与领域目录测试             3 passed
蛋白相关 Python 定向回归            12 passed
BiomedicineViews 组件测试           14 passed
TypeScript typecheck                passed
Ruff 定向检查                       passed
九组发布校准                        completed
```

最终质量门禁结果：

```text
Python 全量测试                       305 passed
前端全量测试                          11 files / 47 passed
TypeScript typecheck                 passed
Ruff（src + tests）                  passed
Vite 生产构建                         passed
wheel 构建与解包内容核验               passed
wheel 隔离目录导入、目录 API 与数据加载   passed
browser-smoke 脚本语法                 passed
```

wheel 已确认包含 `protein_dynamics.py`、版本化蛋白数据集及本次 Vite 构建生成的 JS、CSS 和 `index.html`。浏览器三视口仍未列为通过：当前托管 macOS 环境拒绝 FastAPI/Vite 本地端口绑定，并在 Chromium Mach 服务注册阶段返回 `Permission denied (1100)`；组件测试不能替代截图证据。

## 7. 剩余风险

- 9–12 变量规模证明的是端到端演示与审计契约，不代表产业规模加速；
- 低可行 shot 比例使部分 seed 没有量子候选，页面必须继续展示真实失败；
- 中间态和边权是教学数据，不能外推真实蛋白动力学；
- 本阶段没有实时演化、时间关联函数、速率常数、驻留时间、溶剂或全原子自由能；
- 材料 Pure Analog 仍受 CASCAQit 发布 wheel、可编程初态、时分辨采样和规模契约阻塞，不能降级为 Digital 后标记 Analog。
