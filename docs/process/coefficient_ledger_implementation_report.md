# 逐系数业务证据账本实现报告

## 范围

本阶段补齐六个 QUBO 金融场景的系数来源。目标、冲突、依赖和平方罚项产生的每个 offset、linear、quadratic 贡献都有稳定 ID，并能继续追到 Canonical QUBO、逻辑 Hamiltonian 和当前执行模式的 Analog/Digital 分配。衍生品使用 Graph Problem，继续保留节点、边和几何来源，不生成虚假的 QUBO 账本。

## 数据链

`FinanceCoefficientContribution` 保存 `contribution_id`、`group_id`、`source_rule`、`term_kind`、`targets`、`coefficient` 和 `role`。`QuboBuilder` 在建模时直接记录这些字段；平方等式按实际展开结果生成线性、二次和常数贡献。

`FinanceProblemDefinition` 要求所有 QUBO 场景提供账本，并在编译前拒绝以下输入：

- 重复的 contribution 或 term group ID；
- 引用未知 term group 或 QUBO 变量的贡献；
- 贡献聚合值与最终 QUBO 系数不一致；
- 缺失或格式错误的账本 metadata。

Presenter 使用 CASCAQit `source_term_ids` 建立 Canonical QUBO 与逻辑 Hamiltonian 的多对多关系。页面区分本条业务贡献造成的 Hamiltonian 增量 `Δ`、Hamiltonian 聚合逻辑系数，以及当前模式的 Analog/Digital 系数。后端同时验证：

```text
sum(contribution) = canonical QUBO coefficient
sum(transformed contribution Δ) = logical Hamiltonian coefficient
analog coefficient + digital coefficient = logical Hamiltonian coefficient
```

## 页面

Problem 映射页增加“业务规则与系数溯源”宽表，显示业务分组、规则、贡献 ID、原始系数、Canonical term、聚合系数、Hamiltonian 项、Analog/Digital 分配和守恒状态。表头固定，内容在表格区域内横向和纵向滚动，不扩张页面宽度。运行前显示“待执行模式分配”，运行后替换为本次编译的实际实现。

## 验证

- Python 全量测试：`110 passed`。
- Ruff：`src`、`tests`、`scripts` 通过。
- React：TypeScript 通过，`16 tests passed`，生产构建通过。
- HTTP：交易结算分析返回 73 条贡献且三层守恒；Hybrid 执行后冲突项关联两个局域场和一个 `ZZ` 项，并返回实际 Analog/Digital 分配。
- Python wheel：构建通过，React 静态资源已同步到包内。

浏览器运行时没有可用实例，未完成三视口截图、DOM 溢出和 canvas 像素检查。该项仍需人工或在可用浏览器中验收，不能由 HTTP 和组件测试替代。

## 后续

下一阶段接入连续优化、多起点和 repeated runs，统计严格约束下的候选可行率、目标值分布和运行成本。已删除的两个压力预设只有在量子采样候选稳定通过业务复核后才恢复，不使用经典基线兜底。
