# 文档

产品总册：

- [中科酷原行业量子实验台 PRD](industry_quantum_workbench_prd.md)：定义三个领域、15 个场景、统一用户流程、产品标识、交付要求和发布条件。
- [中科酷原行业量子实验台总体架构](industry_quantum_workbench_architecture.md)：说明统一工作台、领域包、执行族、API、数据审计、兼容边界和 Windows 发布架构。
- [Windows 离线包构建与发布手册](process/windows_offline_release_playbook.md)：固化版本、构建、Windows 安装验收、Release、故障和回滚流程。
- [CASCAQit 1.0.7a 兼容性报告](process/cascaqit_1_0_7a_compatibility_report.md)：记录发布 wheel 身份、API 差异、QWC 应用层适配、重新校准和验证入口。

领域规格与演示资料：

- [行业量子实验台产品知识手册](market_demo_product_guide.md)：面向市场、销售和售前人员，说明三个领域 15 个场景解决的问题、原理、算法、求解过程、52 个预设、全部参数和结果页面含义。
- [生物医药与材料领域需求](biomedicine_demo_prd.md)：定义八个正式场景、用户流程、数据要求、展示边界和发布条件。
- [生物医药与材料领域架构](biomedicine_demo_architecture.md)：说明 Pauli/VQE、组合优化和 Pure Analog AHS 三条执行链及其数据、API、前端、审计和测试结构。
- [生物医药与材料客户演示手册](biomedicine_customer_demo_guide.md)：说明三个一级领域如何共用工作台、八场景讲解顺序、可解释结论和禁止外推内容。
- [生物医药与材料数据来源清单](biomedicine_data_source_inventory.md)：登记 20 组 fixture 的来源、许可证、生成工具、checksum、允许说法和离线发布检查。
- [客户演示技术讲解手册](customer_demo_technical_guide.md)：面向金融和量子计算初学者，解释业务建模、QUBO、Digital/Hybrid/Analog 原理、七个场景、页面解读、演示话术和当前限制。
- [逐场景讲解与页面解读](scenario_presentation_guide.md)：逐项说明七个场景的业务问题、输入、输出、建模、算法选择、页面元素，并结合实际运行截图讲解固定配置结果。
- [金融领域架构设计](finance_problem_api_architecture.md)：说明七个金融场景如何按业务结构选择 Digital、Hybrid、Analog 或经典计算，以及统一执行、结果、可视化和验收边界。
- [QAOA 与 VQE 算法优化设计](qaoa_vqe_algorithm_optimization_design.md)：说明 QAOA 自动选层、连续优化、四个 Digital 场景的 VQE 契约和发布门槛。
- [金融领域场景与界面设计](finance_demo_design.md)：当前七个场景的输入、结果、页面内容、运行方式和解释边界。

当前实现记录：

- [生物医药第一阶段实现报告](process/biomedicine_phase_1_implementation_report.md)：记录统一行业外壳、四场景目录、H2 Pauli VQE、浏览器验收、当前结构预览边界和后续执行链顺序。
- [生物医药第二阶段实现报告](process/biomedicine_phase_2_docking_report.md)：记录 1HSG 离线派生数据、构象匹配 QUBO、Hybrid 门禁、三类结果分离、固定 seed 校准和浏览器验收。
- [生物医药第三阶段实现报告](process/biomedicine_phase_3_active_center_report.md)：记录双金属有效自旋 fixture、Digital VQE、QWC 观测量、精确对角化、固定 seed 校准和三视口验收。
- [生物医药第四阶段实现报告](process/biomedicine_phase_4_peptide_landscape_report.md)：记录二维自回避构象库、one-hot QUBO、Digital QAOA、完整经典能景和四场景联调验收。
- [生物医药第五阶段发布验收报告](process/biomedicine_phase_5_release_report.md)：记录 12 个预设的固定 seed 校准、数据来源复核、浏览器与打包门禁、CASCAQit 版本验证和 Windows 实机验收限制。
- [生物医药第六阶段完成度报告](process/biomedicine_phase_6_completion_report.md)：逐条记录领域解耦、六视图、运行边界、缓存身份、报告落盘、错误契约、最终门禁和剩余外部验收项。
- [生物医药第七阶段最终验收报告](process/biomedicine_phase_7_final_acceptance_report.md)：记录 PRD/架构逐项审计、manifest 与错误契约收口、平台用户数据目录、品牌统一、重新校准、三视口和最终交付制品证据。
- [生物医药第八阶段高级实验骨架报告](process/biomedicine_phase_8_advanced_foundation_report.md)：记录 CASCAQit 能力注册、复杂度档位、稳定实验计划、成本门禁、分析 API 与标准模式回归。
- [第十二阶段材料领域预览报告](process/biomedicine_phase_12_domain_materials_preview_report.md)：记录材料一级领域、四个 V3 入口和当时的严格 Preview 边界。
- [第十三阶段 RNA 实现报告](process/biomedicine_phase_13_rna_structure_report.md)：记录 RNA 候选配对、Digital QAOA、经典对照和三 seed 校准。
- [第十三阶段材料构型实现报告](process/biomedicine_phase_13_materials_defect_adsorption_report.md)：记录缺陷-吸附联合 QUBO、Hybrid 门禁、经典/离线参考和校准。
- [第十四阶段蛋白路径实现报告](process/biomedicine_phase_14_protein_dynamics_report.md)：记录构象状态网络、路径 QUBO、失败结果和 Dijkstra 对照。
- [第十五阶段材料 Analog 实现报告](process/biomedicine_phase_15_materials_analog_report.md)：记录四位点 Pure Analog AHS、同初态前缀语义、DOP853 对照和校准。
- [第十六阶段 V3 总体验收审计](process/biomedicine_phase_16_v3_release_audit.md)：记录八场景 84 次校准聚合、当前 Windows 离线包和待完成的 Chromium 门禁。
- [前后端分离金融工作台实现报告](process/problem_api_workbench_implementation_report.md)：记录 FastAPI + React 结构、七场景执行、状态隔离、自动验证和人工验收缺口。
- [Hybrid 映射证据实现报告](process/hybrid_mapping_evidence_implementation_report.md)：记录完整 core group、QUBO 参考布局、漏边/补边检查和前端证据字段。
- [逐系数业务证据账本实现报告](process/coefficient_ledger_implementation_report.md)：记录业务规则、QUBO contribution、Canonical term 和 Analog/Digital 实现的守恒链路。
- [参数优化与重复统计实现报告](process/parameter_optimization_and_repeated_statistics_report.md)：记录连续 COBYLA、多起点、量子候选统计和 19 个标准预设的三次独立运行结果。
- [变分算法迭代报告](process/variational_algorithm_iteration_report.md)：记录 QAOA 自动选层、Hybrid 两层验收、四个场景的 VQE 校准和页面发布结论。
- [衍生品重估风险图实现报告](process/derivative_revaluation_risk_graph_report.md)：记录九格压力重估、MWIS 风险权重、Analog 局域失谐映射和四类产品验收结果。
- [Problem 映射旧前端热修复报告](process/problem_mapping_stale_frontend_hotfix_report.md)：记录旧响应字段兜底、入口禁缓存和升级后强制刷新边界。
- [量子实验与审计界面收敛报告](process/quantum_audit_interface_convergence_report.md)：记录 QAOA 逻辑层与执行上下文摘要的展示范围。
- [Windows 离线包发布报告](process/windows_offline_bundle_rebuild_report.md)：记录当前离线制品、依赖闭包、完整性检查、Windows 安装启动验收和 Release 身份。
- [Windows runtime 解压热修复报告](process/windows_runtime_extraction_hotfix_report.md)：记录 PowerShell 5.1 归档缺陷、临时目录触发的长路径失败和当前修复包校验结果。
- [运行时依赖兼容性报告](process/runtime_dependency_compatibility_report.md)：记录 Python 3.9 收集修复、CASCAQit 最低版本和离线包重建边界。
- [当前实现复盘与迭代优先级](process/current_implementation_review_and_iteration_priorities.md)：汇总七场景链路、默认与全预设执行结果、关键缺口和后续顺序。
- [v0.1.1 发布验收报告](process/v0_1_1_release_report.md)：记录功能冻结范围、发布门禁、安装后烟雾验证和已知边界。

历史实现记录：

- [投资组合实现阶段报告](process/portfolio_implementation_report.md)：旧 QAOA runner 阶段的实现记录，不代表当前公开入口。
- [交易结算实现阶段报告](process/settlement_implementation_report.md)：旧手工 Hybrid 阶段的实现记录，不代表当前统一 Problem 执行方式。
