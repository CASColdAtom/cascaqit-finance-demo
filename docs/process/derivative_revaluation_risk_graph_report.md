# 衍生品重估风险图实现报告

## 结果

衍生品场景不再让四类产品共用固定无权图。当前产品先完成九格压力重估，每个格点保存压力价格、P&L、Delta、Gamma 和 Vega；绝对 P&L 归一化后写入 `MWISProblemIR.node_weights`。四类产品使用相同冲击坐标和近邻边，但权重分布与 Problem hash 各不相同。

权重公式为：

```text
weight = 0.05 + 0.95 x abs(P&L) / max(abs(P&L))
```

`0.05` 下限保证基准格点满足 MWIS 正权重契约，最大权重固定为 `1.0`。若全部 P&L 为零，九个节点使用相同权重。向上敲出期权在压力情景起点已经触及障碍时，价格和局部 Greeks 按零处理。

## 数据边界

`DerivativesScenario.risk_scenarios()` 是九格重估的唯一领域入口。Problem 构建、业务解码、输入表、P&L 热图和业务结果均读取该对象。经典参考价格不读取 counts，量子执行结果也不包含 `reference_price`。

Analog QAA 将节点权重映射到局域失谐，将固定上下左右边映射到 Rydberg interaction。当前迭代没有根据产品动态修改边或原子位置，避免同时改变风险目标和几何保真条件。

## 验证

- 四类产品的九格重估在固定输入和 seed 下可复现。
- 基准格点 P&L 为零，全部 MWIS 权重严格为正且最大值为 `1.0`。
- 四类产品生成四组不同权重和四个不同 Problem hash。
- AHS local detuning addressing 与 MWIS 节点权重逐项一致，Analog 没有 Digital residual。
- API 输入表、P&L 热图、Problem 对角权重和业务结果与同一领域对象一致。
- Analog 执行前后经典参考价格保持不变。
- 四个产品预设按推荐配置各重复运行 3 次，`12/12` 个量子候选通过业务约束复核，展示来源均为 `best_observed`。
- Python 全量测试 `134 passed`，React `20 passed`；Ruff、TypeScript、生产构建和文档风格检查通过。
