# 交易结算正式应用实现报告

## 实现范围

交易结算案例已经从固定原型接入两条真实本地计算链路：10 条合成指令进入 QUBO 和数字 QAOA；其中 6 条依赖闭合的指令映射到 2×3 中性原子阵列，执行 Digital-Analog-Digital Hybrid 实验。两条链路的结果、counts、报告和执行证据分别保存。

## 业务与 QUBO

- 输入包含名义金额、业务等级、合成流动性占用、前置依赖和交易冲突。
- 目标函数平衡归一化结算金额与业务等级。
- 硬约束包含 CNY、USD、HKD 三个额度桶、批次上限、前置依赖和冲突关系。
- 不等式额度使用有界二进制 slack 展开为平方等式罚项。
- 默认批次上限已被三币种额度严格蕴含，不重复增加 batch slack，因此默认模型为 16 个变量；更紧的批次上限会显式加入 slack，模型仍限制在 20 个变量以内。
- 所有候选都用原始交易输入重新检查，不根据低 energy 直接判定可行。

## 数字与 Hybrid 结果

数字链路通过 CASCAQit `QAOA` 和 `LocalBackend` 返回最佳观测候选、精确枚举基线、objective history 和最终 sampling counts。候选不可行时，业务页展示精确基线，并保留原候选供审计。

Hybrid 链路包含 `prepare` Digital、`evolve` Analog、`decode` Digital 和末端测量。Analog block 使用 2×3 等间距阵列以及 Rabi、Detuning、Phase 控制；结果保留三次连续状态交接和末端 counts。页面只计算 Hybrid 可行样本率和最佳可行样本，不把它写成结算最优解。

默认 128 shots 实验在本机得到：

```text
QUBO variables: 16
QAOA counts total: 128
Displayed source: qaoa_best_observed
Selected trades: T-001, T-004, T-008, T-009, T-010
Settled notional: 9.7 M
Hybrid counts total: 128
Hybrid feasible sample rate: 0.328125
State transitions: 3
Combined runtime: about 4 seconds
```

这些数值只对应当前合成输入、参数和本机环境，不是性能承诺。

## 页面与报告

正式页面增加“交易结算”案例，保留业务结果、场景分析、模型与求解、量子实验、审计证据五个页签。量子页并列展示同刻度原子阵列和合并控制波形，并分别展示数字 QAOA counts 与 Hybrid counts。

运行结果保存在：

- `artifacts/reports/settlement-qaoa.html`
- `artifacts/reports/settlement-hybrid.html`

审计页显示两条链路的 Backend、execution kind、result hash、counts total、报告路径和 Hybrid 状态连续性。当前 `hardware_execution`、`cloud_execution` 和 `network_accessed` 均为 `false`。

## 验证与限制

结算专项测试覆盖输入校验、变量规模、依赖、冲突、额度、QAOA counts、精确基线、Hybrid counts、状态连续性和两份标准报告。阶段结束时完整测试为 `21 passed in 4.89s`，Ruff 检查和 wheel 构建通过，Bokeh 页面返回 HTTP 200。

当前流动性占用使用合成整数额度单位，不等同于交易名义金额或生产现金头寸。页面没有真实行情、结算网络、硬件或云端接入；自动化环境也没有可用浏览器实例，因此最终桌面和移动端视觉复核仍需人工完成。
