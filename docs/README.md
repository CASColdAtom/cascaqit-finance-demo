# 文档

- [客户演示技术讲解手册](customer_demo_technical_guide.md)：面向金融和量子计算初学者，解释业务建模、QUBO、Digital/Hybrid/Analog 原理、七个场景、页面解读、演示话术和当前限制。
- [金融 Demo 架构设计](finance_problem_api_architecture.md)：说明七个金融场景如何按业务结构选择 Digital、Hybrid、Analog 或经典计算，以及统一执行、结果、可视化和验收边界。
- [金融 Demo 场景与界面设计](finance_demo_design.md)：当前七个场景的输入、结果、页面内容、运行方式和解释边界。

当前实现记录：

- [前后端分离金融工作台实现报告](process/problem_api_workbench_implementation_report.md)：记录 FastAPI + React 结构、七场景执行、状态隔离、自动验证和人工验收缺口。
- [Hybrid 映射证据实现报告](process/hybrid_mapping_evidence_implementation_report.md)：记录完整 core group、QUBO 参考布局、漏边/补边检查和前端证据字段。

历史实现记录：

- [投资组合实现阶段报告](process/portfolio_implementation_report.md)：旧 QAOA runner 阶段的实现记录，不代表当前公开入口。
- [交易结算实现阶段报告](process/settlement_implementation_report.md)：旧手工 Hybrid 阶段的实现记录，不代表当前统一 Problem 执行方式。
