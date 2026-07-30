# 第十三阶段材料缺陷与吸附构型优化完成报告

## 结论

`MAT-V1-ADSORB-01` 已从分析预览升级为 `available`。场景使用版本化周期表面 fixture，在同一 QUBO 中联合选择缺陷与吸附构型，并通过 CASCAQit 本地模拟执行 Digital 或经过门禁的 Hybrid QAOA。材料 Rydberg 动力学不属于本交付，继续保持纯 Analog Preview。

## 实现范围

- 三个预设：CeO2(111) / CO、TiO2(110) / H2O、MoS2 / H；
- 3 个缺陷变量、8 个吸附构型变量、47 个非零 QUBO 项；
- 形成能、吸附能、缺陷-吸附协同和周期近邻相互作用；
- 缺陷计量、覆盖度、同位点/取向互斥和禁配组合；
- 完整系数贡献账本、周期边界、对称操作和三类坐标身份；
- Digital/Hybrid 共用逻辑 QUBO；Hybrid 为 15 个 Analog 项加 32 个 Digital residual 项；
- 量子 Top-K、经典完整枚举、独立离线参考、可行 shot 比例和稳定审计 hash；
- 材料专用结构、结果、映射、量子、对照和审计视图。

## 科学边界

fixture 的能量系数是无量纲离线教学模型。运行时不执行 DFT，不推导催化活性、反应速率、选择性、稳定性或可合成性。QAOA counts 仅为有限 shots 观测频次。量子未观测到可行构型时返回 `quantum_not_observed`，不会用经典最优构型填充量子结果。

## 校准

默认配置为 Hybrid、QAOA `p=1`、128 shots、`preset` 参数搜索、预算 2。三个预设分别使用 seeds `7/23/41`，九次运行全部观测到至少一个可行构型；可行 shot 比例范围为 2.34%–10.16%。每次编译均保持 15 个 Analog 项、32 个 Digital residual 项。完整 hash 证据见 `docs/process/evidence/materials_defect_adsorption_calibration.json`。

## 验证状态

- Python 全量：`294 passed`；
- 前端全量：11 个测试文件、44 项通过；
- `ruff check src tests`、TypeScript typecheck 和 Vite 生产构建通过；
- wheel `--no-isolation` 构建通过，并确认包含材料 fixture、执行模块、公共 QUBO/审计模块和材料静态 chunk；
- 九组材料校准全部完成；
- Chromium 三视口门禁未通过。当前托管会话在启动 Playwright Chromium 时被 macOS MachPort 拒绝，错误为 `bootstrap_check_in ... Permission denied (1100)`，因此本报告不把截图列为已通过证据。
