# 生物医药第四阶段：小肽离散构象能景实现报告

日期：2026-07-30

## 1. 阶段结论

“小肽离散构象与折叠能景采样”已从结构预览升级为可执行的本地量子演示。至此四个生物医药场景均已接通 CASCAQit 本地模拟执行链，但仍严格保持各自的科学边界，不声称量子优势或真实药物、催化、蛋白结构结论。

## 2. 构象库与能量模型

- 数据集：`peptide.six-residue.square-lattice`，版本 `1`；
- 10 个六残基二维方格构象；
- 每个构象通过链连续、自回避和接触图重算校验；
- 构象按平移、旋转和镜像对称归一化，覆盖 0、1、2 个非键接触；
- 三个预设：疏水核心、带电竞争、接触受限；
- 能量为无量纲教学接触分数，不是自由能。

运行时不枚举连续结构，也不依赖 RDKit、分子动力学或网络服务。fixture manifest 固化生成规则、单位、SHA-256 和限制。

## 3. QUBO 与量子结果

每个业务变量表示选择一个固化构象。目标写入对应粗粒化接触能，`2.0 (sum x - 1)^2` 强制恰好选择一个构象；逐系数贡献账本与最终 QUBO 完整守恒。

CASCAQit Digital QAOA 负责参数优化与末端采样。量子候选只从当前 counts 的 one-hot 可行态产生；没有可行态时明确返回空候选，不用经典结果替代。完整经典能景、全部最低能简并构象和量子观测 Top-K 分开保存。

## 4. 校准

推荐配置为 Digital QAOA、`p=1`、256 shots、连续 COBYLA、24 次目标评估、单起点，默认 seed 为 `7`。三个预设在固定 seed `1`、`6`、`7` 下均观察到 one-hot 可行候选；默认 seed `7` 均观察到经典最低能集合中的构象。

## 5. 架构边界

小肽场景直接使用 CASCAQit `QAOA` 和生物医药自有 `OptimizationProblemDefinition`、QUBO builder、TermGroup 与贡献账本，没有依赖 `Finance*` 领域模型。构象匹配的 Hybrid 证据适配器仍复用金融包内执行器，这是兼容债务，但没有扩展到新场景。

## 6. 验收

最终门禁覆盖 Python、Ruff、React、TypeScript、Vite build、wheel，以及 `1440 x 900`、`1280 x 720`、`390 x 844` 三视口浏览器。浏览器实际执行电子结构、构象匹配、金属活性中心和小肽能景，检查无横向溢出、console/page error、空白 canvas 或量子/经典结果混淆。

- Python 3.9 全量测试：`200 passed in 233.56s`；
- Ruff：通过；
- React 全量测试：`29 passed`；
- TypeScript 与 Vite 生产构建：通过；
- wheel：包含 `peptide_landscape.py`、两个 fixture JSON、生产 `index.html` 和最新 `BiomedicineViews` chunk；
- 三个浏览器视口：页面级横向溢出均为 `false`，console errors 与 page errors 均为空，小肽量子页 canvas 均有非空绘制像素。

证据位于 `artifacts/browser-smoke-phase4/`，其中 `peptide-result-*.png` 为小肽结果页，`report.json` 为结构化验收报告。

## 7. 剩余风险

二维六残基构象库刻意保持小规模，适合解释 QUBO 与采样行为，不代表对真实蛋白折叠问题的规模或精度覆盖。后续若扩展构象库，必须重新评估量子位数、one-hot 编码成本、QAOA 可行率和经典基线规模。
