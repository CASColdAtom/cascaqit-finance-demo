# 生物医药第六阶段完成度报告

日期：2026-07-30

## 1. 范围与结论口径

本阶段针对 `biomedicine_demo_prd.md` 和 `biomedicine_demo_architecture.md` 做完成度收口，不把第五阶段的固定 seed 发布校准直接等同于全部设计完成。产品名称统一为“中科酷原行业量子实验台”，金融和生物医药继续作为同一工作台中的两个一级领域。

四个生物医药场景仍全部使用 CASCAQit `LocalBackend` 本地模拟：小分子电子结构、构象匹配、金属活性中心有效模型和小肽离散能景。本阶段没有引入硬件或云任务，也不扩大量子优势、药物、临床、催化活性或真实蛋白折叠结论。

## 2. PRD 与架构缺口收口

| 检查项 | 实现与证据 |
|---|---|
| 金融与生物医药融合 | 共用品牌头、领域切换、三栏工作台和执行控件；领域目录、分析、运行结果和缓存彼此隔离 |
| 常驻运行边界 | 全局品牌头持续显示 `LOCAL SIMULATION`、`NO HARDWARE EXECUTION`、`RESEARCH DEMONSTRATION` |
| 六类结果视图 | 生物医药增加独立“对照分析”；金融保持原有五视图，不出现空标签页 |
| 四场景对照 | 电子结构展示 HF/VQE/理想与带噪 QWC/精确能量；构象匹配分开量子、枚举和共晶参考；活性中心核对能量、Hamiltonian hash 和关联；小肽核对量子候选、经典最低能集合和完整能景位置 |
| 专业缩写 | VQE、QWC、QAOA 等首次关键展示使用中文 `abbr` tooltip |
| 领域解耦 | `cascaqit_industry_demo` 提供领域中性 Problem 协议和执行器；生物医药包禁止导入金融包；金融执行器改为兼容重导出 |
| 缓存身份 | 签名包含领域、场景、完整运行请求、dataset version、manifest hash 和 execution family |
| 长运行提示 | 场景目录保存固定 seed 校准的本机耗时基线；按当前工作量估算超过 30 秒时在运行前提示，不阻断执行 |
| API 契约 | 分析与运行响应顶层返回 dataset/analysis；生物医药 422 使用 code/message/stage，未知 500 返回不透明 error_id |
| 报告持久化 | 每次生物医药运行把 `biomedicine.execution-report.v1` 写入配置的用户数据目录，文件名只使用后端 case ID 和 report hash |
| 可观测性 | audit 返回 preflight、execution、report 和 total 时间；报告文件和 API audit 内容一致 |
| 安全边界 | 未知异常不向响应泄漏本机路径或 traceback；报告路径不由用户输入拼接 |

## 3. 自动化与运行证据

最终全量门禁、浏览器三视口、wheel 内容和安装 smoke 在本阶段结束前重新执行，结果记录在本节。第五阶段的 `218 passed`、React `32 passed` 和旧截图只作为历史基线，不替代本阶段验证。

| 门禁 | 本阶段最终结果 |
|---|---|
| Python 全量测试 | `221 passed in 219.91s` |
| Ruff / diff check | 通过 |
| React 测试 | 9 个文件，`37 passed` |
| TypeScript / Vite | 类型检查和生产构建通过；最终静态资源写入 Python 包 |
| npm audit | `0 vulnerabilities` |
| 浏览器验收 | `1440 x 900`、`1280 x 720`、`390 x 844` 全部通过；四场景运行、四个对照视图、三条常驻边界、canvas 像素和横向溢出均实际检查，console/page error 为 0 |
| 浏览器证据 | `artifacts/browser-smoke-phase6/report.json` 及同目录截图；本地验收制品不提交 Git |
| 普通 wheel | `582,002` bytes；SHA-256 `303913736f1b79df81c7ebb49f4f85b7d7059ec5931419f7e6d9f37e1df1254b` |
| wheel 内容 | 3 个 `cascaqit_industry_demo` 文件、8 个 manifest、10 个静态文件；临时目录安装后的 health、分析 API、中性执行器和静态入口 smoke 通过 |
| Windows 构建侧 | `13 passed`；29 个 wheel，Python 3.11.9，安装时无需网络 |
| Windows ZIP | `94,859,337` bytes；SHA-256 `68e0ff192a5b0f8e3877bfe996e356148d918f85d9b853277940fd21ad383390` |

浏览器验收服务使用当前源码和最终生产静态资源运行在 `http://127.0.0.1:8138/`。上述性能时间只描述本机验收过程，不构成跨平台基准。

## 4. 剩余限制

- Windows 离线包可以在当前 macOS 构建侧验证依赖闭包、包内容和启动脚本，但尚未在干净 Windows 10/11 x64 实机执行 `VERIFY.bat`、`INSTALL.bat`、`RUN.bat`、浏览器启动和四场景运行。因此 Windows 实机验收仍未完成。
- 耗时估算来自当前 macOS 固定 seed 校准，只用于提示本地等待量级，不是服务等级、硬件性能或跨平台基准。
- 四个场景仍是教学规模固定模型；完成 PRD 演示链不表示具备通用电子结构、完整分子对接、真实金属酶催化预测或蛋白质折叠能力。
