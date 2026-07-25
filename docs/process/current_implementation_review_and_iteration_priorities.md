# 金融 Demo 当前实现复盘与迭代优先级

复盘基于当前源码、CASCAQit PRD v0.10、Native SDK Architecture v2.2，以及七个场景的实际分析和执行结果。所有执行均为固定 seed 的本地数值模拟，不代表真机性能或量子优势。

## 结论

Demo 已接通从金融输入、统一 Problem、模式分析、Digital/Hybrid/Analog 编译、本地执行、业务解码到 React 可视化和 HTML 报告的完整链路。六个 QUBO 场景还提供逐系数来源账本，可从业务规则追到 Canonical QUBO、逻辑 Hamiltonian 和当前 Analog/Digital 分配。七个默认场景和全部 21 个标准预设都能按推荐模式得到 `best_observed` 可行候选，不依赖经典基线补齐演示结果。

“日终压力”和“行业集中压降”在当前浅层 QAOA 与固定参数下返回不可行候选。增加到 256 shots、切换多个 seed、提高到 `p=3` 或进行 8 点网格扫描均未解决，因此这两个预设已从标准演示删除。经典基线仍用于审计和自定义输入失败诊断，但不会作为标准预设的量子结果展示；恢复更严格预设前，应先改进参数优化或约束感知 Ansatz。

## 已完成链路

| 范围 | 当前实现 |
|---|---|
| 业务建模 | 七个场景、21 个合成预设；目标、冲突、依赖、容量、分组和 slack 进入 QUBO 或图 Problem；解码后按原始规则复核 |
| 模式选择 | Digital、Hybrid、Analog 分别检查编译可行性和业务适配；无可执行模式时返回稳定能力错误 |
| Hybrid 证据 | 交易结算与反欺诈各有 3/3 core 冲突覆盖；使用 `provided` 参考布局；漏边、补边和异常 Analog 二体项均为 0 |
| 系数证据 | 六个 QUBO 场景记录目标与罚项的原始贡献；校验 QUBO 聚合、QUBO 到 Ising 变换及 Analog/Digital 分配守恒；Graph 场景不伪造 QUBO 账本 |
| Analog 场景 | 衍生品 `3 x 3` 风险图完整编译为 QAA/AHS；经典定价与量子情景选择分离 |
| 变分执行 | Digital 支持 QAOA `p=1~3`、预设、网格和固定 seed 采样；Hybrid/Analog 使用受限预设点 |
| 执行配置 | 后端目录提供场景推荐配置；API 省略字段时使用同一配置；UI 标出推荐或自定义状态 |
| 结果与审计 | 保留量子候选、经典基线、实际展示来源、counts、参数历史、四段 hash、Target、Backend、seed、shots 和执行边界 |
| 前端 | 中英文切换、五个结果视图、业务原生图、Digital 线路、D-A-D、原子阵列、合并波形、counts 和响应式布局 |
| 交付 | Python wheel 内置 React 静态资源；Windows 可重定位 Python、离线依赖闭包、BAT/PS1 入口和 smoke test 已有构建脚本 |

## 默认场景验收

| 场景 | 推荐模式 | 推荐执行配置 | 采样候选 | 展示来源 |
|---|---|---|---|---|
| 投资组合 | Digital | 32 shots，`p=1`，2 个预设点 | 可行 | `best_observed` |
| 交易结算 | Hybrid | 32 shots，1 层，2 个预设点 | 可行 | `best_observed` |
| 调查编排 | Hybrid | 32 shots，1 层，2 个预设点 | 可行 | `best_observed` |
| 抵押品 | Digital | 64 shots，`p=1`，2 个预设点 | 可行 | `best_observed` |
| 流动性 | Digital | 128 shots，`p=1`，2 个预设点 | 可行 | `best_observed` |
| 授信额度 | Digital | 128 shots，`p=2`，2 个预设点 | 可行 | `best_observed` |
| 衍生品风险情景 | Analog | 32 shots，1 层，2 个预设点 | 可行 | `best_observed` |

运行时间受 Python 版本、CPU 负载和模拟器设置影响，本轮单次观测约为 `0.1~11.4s`，只用于确认现场等待量级，不作为性能基准。

## 本阶段验证

- 21 个标准预设逐一执行：`21 passed, 0 failed`，全部展示 `best_observed`。
- Python 全量测试：`110 passed`。
- Ruff：`src`、`tests`、`scripts` 全部通过。
- React：TypeScript 检查通过，`16 tests passed`，生产构建通过。
- Python wheel：构建通过，内置静态资源已同步。
- 文档风格检查：12 个文件，0 warnings。

浏览器三视口截图和 Windows 实机安装没有在本机完成，分别保留在 P2 和 P0，不计入本阶段通过项。

## 关键缺口

### P0

1. **提高严格约束下的量子候选可行率。** 接入 CASCAQit 已有的连续优化、多起点和 repeated runs，按统一评估预算选择层数与参数；必要时增加保持可行子空间的 mixer。更严格的压力预设只有在采样候选本身通过验收后才能恢复，不能以经典回退通过。
2. **重建 Windows 离线包。** 仓库忽略目录中的旧 ZIP 仍包含 CASCAQit `1.0.2a1`，而当前 Demo 要求 `>=1.0.7a0,<1.0.8`。需重新生成 wheelhouse，并在干净 Windows 10/11 x64 上执行 `VERIFY.bat`、`INSTALL.bat`、`RUN.bat` 和真实场景 smoke。
3. **打通可安装发布链。** CASCAQit 本地分支领先远端且没有可供普通用户安装的对应分发包；在 SDK 推送和发布完成前，GitHub 用户无法只靠公开依赖安装 Demo。

### P1

1. **让衍生品风险图读取产品结果。** 当前四类产品共用固定 `3 x 3` 图，产品输入只影响经典价格。应根据情景重估 P&L、Greeks 变化或覆盖贡献构图，同时保持定价与情景选择两条链分离。
2. **展开逐业务边映射。** 页面和导出报告增加业务 pair、两端原子坐标、距离、参考 interaction、mapped term 和覆盖状态，避免只看汇总卡。
3. **把金融映射证据写入 CASCAQit 标准 HTML。** 当前完整证据主要在 React 页面，导出报告还缺金融 term group、几何来源和拒绝原因。
4. **增加统计可信度。** 对推荐配置执行重复运行，展示均值、方差、置信区间、可行率和额外运行成本；VQE 只在有合适 Ansatz 和对照价值的场景使用，不作为统一替换方案。
5. **增加 ideal/noisy 对照。** 用于展示采样质量与噪声敏感性，并持续明确这是本地模型，不是真机噪声测量。

### P2

1. 增加多客户端限流、任务取消、进度和超时恢复。
2. 用浏览器自动验收 `1440 x 900`、`1280 x 720`、`390 x 844`，检查 canvas 非空、页面无横向溢出、元素无重叠。
3. 拆分约 669 kB 的 ECharts chunk。当前 Demo 离线运行，优先级低于算法、证据和交付闭环。

## 下一阶段建议

下一阶段把 CASCAQit 已实现的连续优化、多起点和 repeated runs 接入 Demo，形成严格约束下的统计验收。完成后再决定是否恢复压力预设；无法稳定产生量子可行候选的预设继续保持删除，不回退到经典结果。随后重建 Windows 包和公开发布，衍生品风险图联动放在后续阶段。
