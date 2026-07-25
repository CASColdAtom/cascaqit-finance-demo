# 金融 Demo 当前实现复盘与迭代优先级

复盘基于当前源码、CASCAQit Problem API 契约，以及七个场景的实际分析和执行结果。所有执行均为固定 seed 的本地数值模拟，不代表真机性能或量子优势。

## 结论

Demo 已接通从金融输入、统一 Problem、模式分析、Digital/Hybrid/Analog 编译、本地执行、业务解码到 React 可视化和 HTML 报告的完整链路。六个 QUBO 场景还提供逐系数来源账本，可从业务规则追到 Canonical QUBO、逻辑 Hamiltonian 和当前 Analog/Digital 分配。现存 19 个标准预设各完成 3 次独立运行，57 个量子候选全部通过业务约束复核，不依赖经典基线补齐演示结果。

“日终压力”“行业集中压降”“流动性收紧”和“跨币种短缺”未达到量子候选稳定性要求，因此保持从标准演示删除。后两项在连续优化下分别只有 `2/3` 和 `1/3`；经典基线仍用于审计和自定义输入失败诊断，但不会用于恢复标准预设。

## 已完成链路

| 范围 | 当前实现 |
|---|---|
| 业务建模 | 七个场景、19 个合成预设；目标、冲突、依赖、容量、分组和 slack 进入 QUBO 或图 Problem；解码后按原始规则复核 |
| 模式选择 | Digital、Hybrid、Analog 分别检查编译可行性和业务适配；无可执行模式时返回稳定能力错误 |
| Hybrid 证据 | 交易结算与反欺诈各有 3/3 core 冲突覆盖；使用 `provided` 参考布局；漏边、补边和异常 Analog 二体项均为 0 |
| 系数证据 | 六个 QUBO 场景记录目标与罚项的原始贡献；校验 QUBO 聚合、QUBO 到 Ising 变换及 Analog/Digital 分配守恒；Graph 场景不伪造 QUBO 账本 |
| Analog 场景 | 衍生品 `3 x 3` 风险图完整编译为 QAA/AHS；经典定价与量子情景选择分离 |
| 变分执行 | Digital 支持 QAOA `p=1~3`、离散搜索和连续优化；Hybrid/Analog 支持一层预设参数或连续优化；连续优化支持 1～3 个起点 |
| 执行配置 | 后端目录提供 shots、seed、层数、搜索、预算、起点数和重复次数；API 与 UI 共用同一配置 |
| 重复统计 | 每次重新分析、编译、优化和采样；只统计量子候选可行率、目标分布、95% Student-t 置信区间、评估次数和耗时 |
| 结果与审计 | 保留量子候选、经典基线、实际展示来源、counts、参数历史和四段 hash；摘要显示 mode、seed、shots、耗时，结构化载荷保留完整执行事实 |
| 前端 | 中英文切换、五个结果视图、业务原生图、Digital 线路、D-A-D、原子阵列、合并波形、counts 和响应式布局 |
| 交付 | Python wheel 内置 React 静态资源；Windows 可重定位 Python、离线依赖闭包、BAT/PS1 入口和 smoke test 已有构建脚本 |

## 默认场景验收

| 场景 | 推荐模式 | 推荐执行配置 | 采样候选 | 展示来源 |
|---|---|---|---|---|
| 投资组合 | Digital | 32 shots，`p=1`，COBYLA 每起点 12 次，2 个起点 | `3/3` 可行 | `best_observed` |
| 交易结算 | Hybrid | 32 shots，1 层，2 个预设点 | `3/3` 可行 | `best_observed` |
| 调查编排 | Hybrid | 32 shots，1 层，2 个预设点 | `3/3` 可行 | `best_observed` |
| 抵押品 | Digital | 64 shots，`p=1`，2 个预设点 | `3/3` 可行 | `best_observed` |
| 流动性 | Digital | 128 shots，`p=1`，2 个预设点 | `3/3` 可行 | `best_observed` |
| 授信额度 | Digital | 128 shots，`p=2`，2 个预设点 | `3/3` 可行 | `best_observed` |
| 衍生品风险情景 | Analog | 32 shots，1 层，2 个预设点 | `3/3` 可行 | `best_observed` |

运行时间受 Python、CPU 负载和模拟器设置影响，本轮完整 57 次执行约 165 秒，只用于确认现场等待量级，不作为性能基准。

## 本阶段验证

- 19 个标准预设各执行 3 次：`57 passed, 0 failed`，成功来源均为量子 `business_candidate`。
- Python 全量测试：`123 passed`。
- Ruff：`src`、`tests`、`scripts` 全部通过。
- React：TypeScript 检查通过，`18 tests passed`，生产构建通过。
- Python wheel：构建通过，内置静态资源已同步。
- 文档风格检查：12 个文件，0 warnings。

浏览器三视口截图和 Windows 实机安装没有在本机完成，分别保留在 P2 和 P0，不计入本阶段通过项。

## 关键缺口

### P0

1. **完成 Windows 实机验收。** 当前源码离线包已重建并通过主机侧依赖闭包、runtime、manifest 和 wheel 内容审计；仍需在干净 Windows 10/11 x64 上执行 `VERIFY.bat`、`INSTALL.bat`、`RUN.bat` 和真实场景 smoke。
2. **打通可安装发布链。** Demo 依赖的 CASCAQit 能力尚未形成公开分发包，GitHub 用户仍无法只靠公开依赖安装。

### P1

1. **让衍生品风险图读取产品结果。** 当前四类产品共用固定 `3 x 3` 图，产品输入只影响经典价格。应根据情景重估 P&L、Greeks 变化或覆盖贡献构图，同时保持定价与情景选择两条链分离。
2. **展开逐业务边映射。** 页面和导出报告增加业务 pair、两端原子坐标、距离、参考 interaction、mapped term 和覆盖状态，避免只看汇总卡。
3. **把金融映射证据写入 CASCAQit 标准 HTML。** 当前完整证据主要在 React 页面，导出报告还缺金融 term group、几何来源和拒绝原因。
4. **增加 ideal/noisy 对照。** 用于展示采样质量与噪声敏感性，并持续明确这是本地模型，不是真机噪声测量。
5. **研究约束保持 mixer。** 只用于恢复被删除的严格预设，不以经典回退替代量子候选；VQE 不作为统一替换方案。

### P2

1. 增加多客户端限流、任务取消、进度和超时恢复。
2. 用浏览器自动验收 `1440 x 900`、`1280 x 720`、`390 x 844`，检查 canvas 非空、页面无横向溢出、元素无重叠。
3. 拆分约 669 kB 的 ECharts chunk。当前 Demo 离线运行，优先级低于算法、证据和交付闭环。

## 下一阶段建议

下一阶段先在 Windows 实机验收新离线包，并完成 CASCAQit 公开安装链。完成交付闭环后，让衍生品风险图读取实际产品重估结果，再把金融映射证据写入标准 HTML 报告。被删除的严格预设继续保持删除，直到约束保持量子策略能够稳定产生可行候选。
