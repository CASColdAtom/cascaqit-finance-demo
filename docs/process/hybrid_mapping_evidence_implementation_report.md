# Hybrid 映射证据实现报告

## 目标

修正金融模式裁决：Hybrid 不能因为一条业务冲突偶然落入 blockade 半径就被推荐，必须证明完整 core group 已映射，原子几何没有漏边或补边，且 Analog 二体项都有业务来源。

## 实现

- 删除 `preferred_mode`，推荐结果只由编译可行性、业务分组、几何和 term assignment 推导。
- `QUBOProblemIR` 使用完整参考坐标。交易结算和反欺诈把互不重叠的冲突 pair 放入独立 28 μm 单元，pair 内距离为 6 μm，单元间最近距离为 22 μm。
- `FinanceModeAdvisor` 逐条生成 core contribution 标识，并返回 covered group、missing contribution、unexpected Analog term、unexpected physical interaction、geometry source/status 和 layout policy。
- Hybrid 要求完整 core group、`provided` 布局、无漏边和补边、无异常二体项，并同时保留非空 Digital residual。Analog 还要求完整 Hamiltonian 不含 Digital residual。
- Problem 映射页显示 core 覆盖率、几何状态、漏项和异常数量；Python wheel 内的静态前端已同步更新。

## 默认场景结果

| 场景 | 推荐模式 | core 覆盖 | 几何 | 漏项 / 异常项 / 补边 |
|---|---|---:|---|---:|
| 交易结算 | Hybrid | 3 / 3 | verified embedding | 0 / 0 / 0 |
| 反欺诈调查编排 | Hybrid | 3 / 3 | verified embedding | 0 / 0 / 0 |
| 衍生品风险情景 | Analog | 12 / 12 | business native | 0 / 0 / 0 |

## 验证

- 模式与 API 专项测试：28 passed。
- 结算实际 Hybrid 执行与应用 smoke：8 passed。
- 前端：TypeScript passed，15 tests passed，production build passed。
- 完整后端回归：Python 3.11，93 passed。
- Python wheel：build passed。
- Ruff：passed。
- 文档风格：10 files，0 warnings。

## 保留项

当前 contribution 标识证明业务 pair 是否完整进入映射，但还没有拆解同一聚合 QUBO term 内各业务规则的系数来源。下一步应在 QUBO Builder 增加 coefficient-level ledger，并将业务规则、系数贡献、Canonical term 和最终 Analog/Digital implementation 串成一条可展开的证据链。
