# 文档

- [生物医药量子实验台 PRD](biomedicine_demo_prd.md)：定义四个正式场景、用户流程、数据要求、展示边界和发布条件。
- [生物医药量子实验台架构设计](biomedicine_demo_architecture.md)：说明 Pauli/VQE 与组合优化两条执行链、数据 manifest、API、前端、审计和测试结构。
- [客户演示技术讲解手册](customer_demo_technical_guide.md)：面向金融和量子计算初学者，解释业务建模、QUBO、Digital/Hybrid/Analog 原理、七个场景、页面解读、演示话术和当前限制。
- [逐场景讲解与页面解读](scenario_presentation_guide.md)：逐项说明七个场景的业务问题、输入、输出、建模、算法选择、页面元素，并结合实际运行截图讲解固定配置结果。
- [金融 Demo 架构设计](finance_problem_api_architecture.md)：说明七个金融场景如何按业务结构选择 Digital、Hybrid、Analog 或经典计算，以及统一执行、结果、可视化和验收边界。
- [QAOA 与 VQE 算法优化设计](qaoa_vqe_algorithm_optimization_design.md)：说明 QAOA 自动选层、连续优化、四个 Digital 场景的 VQE 契约和发布门槛。
- [金融 Demo 场景与界面设计](finance_demo_design.md)：当前七个场景的输入、结果、页面内容、运行方式和解释边界。

当前实现记录：

- [生物医药第一阶段实现报告](process/biomedicine_phase_1_implementation_report.md)：记录统一行业外壳、四场景目录、H2 Pauli VQE、浏览器验收、当前结构预览边界和后续执行链顺序。
- [生物医药第二阶段实现报告](process/biomedicine_phase_2_docking_report.md)：记录 1HSG 离线派生数据、构象匹配 QUBO、Hybrid 门禁、三类结果分离、固定 seed 校准和浏览器验收。
- [前后端分离金融工作台实现报告](process/problem_api_workbench_implementation_report.md)：记录 FastAPI + React 结构、七场景执行、状态隔离、自动验证和人工验收缺口。
- [Hybrid 映射证据实现报告](process/hybrid_mapping_evidence_implementation_report.md)：记录完整 core group、QUBO 参考布局、漏边/补边检查和前端证据字段。
- [逐系数业务证据账本实现报告](process/coefficient_ledger_implementation_report.md)：记录业务规则、QUBO contribution、Canonical term 和 Analog/Digital 实现的守恒链路。
- [参数优化与重复统计实现报告](process/parameter_optimization_and_repeated_statistics_report.md)：记录连续 COBYLA、多起点、量子候选统计和 19 个标准预设的三次独立运行结果。
- [变分算法迭代报告](process/variational_algorithm_iteration_report.md)：记录 QAOA 自动选层、Hybrid 两层验收、四个场景的 VQE 校准和页面发布结论。
- [衍生品重估风险图实现报告](process/derivative_revaluation_risk_graph_report.md)：记录九格压力重估、MWIS 风险权重、Analog 局域失谐映射和四类产品验收结果。
- [Problem 映射旧前端热修复报告](process/problem_mapping_stale_frontend_hotfix_report.md)：记录旧响应字段兜底、入口禁缓存和升级后强制刷新边界。
- [量子实验与审计界面收敛报告](process/quantum_audit_interface_convergence_report.md)：记录 QAOA 逻辑层与执行上下文摘要的展示范围。
- [Windows 离线包重建报告](process/windows_offline_bundle_rebuild_report.md)：记录当前源码离线包、依赖闭包、完整性检查、Python 3.9 构建兼容修复和待完成的 Windows 实机验收。
- [Windows runtime 解压热修复报告](process/windows_runtime_extraction_hotfix_report.md)：记录 PowerShell 5.1 归档缺陷、临时目录触发的长路径失败和当前修复包校验结果。
- [运行时依赖兼容性报告](process/runtime_dependency_compatibility_report.md)：记录 Python 3.9 收集修复、CASCAQit 最低版本和离线包重建边界。
- [当前实现复盘与迭代优先级](process/current_implementation_review_and_iteration_priorities.md)：汇总七场景链路、默认与全预设执行结果、关键缺口和后续顺序。
- [v0.1.1 发布验收报告](process/v0_1_1_release_report.md)：记录功能冻结范围、发布门禁、安装后烟雾验证和已知边界。

历史实现记录：

- [投资组合实现阶段报告](process/portfolio_implementation_report.md)：旧 QAOA runner 阶段的实现记录，不代表当前公开入口。
- [交易结算实现阶段报告](process/settlement_implementation_report.md)：旧手工 Hybrid 阶段的实现记录，不代表当前统一 Problem 执行方式。
