# 文档

- [客户演示技术讲解手册](customer_demo_technical_guide.md)：面向金融和量子计算初学者，解释业务建模、QUBO、Digital/Hybrid/Analog 原理、七个场景、页面解读、演示话术和当前限制。
- [金融 Demo 架构设计](finance_problem_api_architecture.md)：说明七个金融场景如何按业务结构选择 Digital、Hybrid、Analog 或经典计算，以及统一执行、结果、可视化和验收边界。
- [金融 Demo 场景与界面设计](finance_demo_design.md)：当前七个场景的输入、结果、页面内容、运行方式和解释边界。

当前实现记录：

- [前后端分离金融工作台实现报告](process/problem_api_workbench_implementation_report.md)：记录 FastAPI + React 结构、七场景执行、状态隔离、自动验证和人工验收缺口。
- [Hybrid 映射证据实现报告](process/hybrid_mapping_evidence_implementation_report.md)：记录完整 core group、QUBO 参考布局、漏边/补边检查和前端证据字段。
- [逐系数业务证据账本实现报告](process/coefficient_ledger_implementation_report.md)：记录业务规则、QUBO contribution、Canonical term 和 Analog/Digital 实现的守恒链路。
- [参数优化与重复统计实现报告](process/parameter_optimization_and_repeated_statistics_report.md)：记录连续 COBYLA、多起点、量子候选统计和 19 个标准预设的三次独立运行结果。
- [Windows 离线包重建报告](process/windows_offline_bundle_rebuild_report.md)：记录当前源码离线包、依赖闭包、完整性检查、Python 3.9 构建兼容修复和待完成的 Windows 实机验收。
- [运行时依赖兼容性报告](process/runtime_dependency_compatibility_report.md)：记录 Python 3.9 收集修复、CASCAQit 最低版本和离线包重建边界。
- [当前实现复盘与迭代优先级](process/current_implementation_review_and_iteration_priorities.md)：汇总七场景链路、默认与全预设执行结果、关键缺口和后续顺序。

历史实现记录：

- [投资组合实现阶段报告](process/portfolio_implementation_report.md)：旧 QAOA runner 阶段的实现记录，不代表当前公开入口。
- [交易结算实现阶段报告](process/settlement_implementation_report.md)：旧手工 Hybrid 阶段的实现记录，不代表当前统一 Problem 执行方式。
