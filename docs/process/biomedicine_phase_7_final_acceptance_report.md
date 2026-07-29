# 生物医药第七阶段最终验收报告

日期：2026-07-30

## 1. 验收结论

本阶段不沿用“已有测试通过即视为完成”的口径，而是重新从 `biomedicine_demo_prd.md` 和 `biomedicine_demo_architecture.md` 提取交付要求并核对当前源码、API、运行行为、浏览器和发布制品。四个生物医药场景、统一行业工作台、两条执行链、数据溯源、经典/量子结果分离、审计报告、离线运行和发布门禁均有当前状态的直接证据。

产品对外名称统一为“中科酷原行业量子实验台”。所有生物医药结果仍来自 CASCAQit `LocalBackend` 本地模拟器，不代表真实硬件执行，不证明量子优势，也不提供药物、临床、催化活性或真实蛋白结构结论。

## 2. PRD 与架构完成矩阵

| 范围 | 当前实现 | 验收证据 |
|---|---|---|
| 四场景与 12 个预设 | 电子结构、构象匹配、有效自旋、小肽能景均为正式可执行入口 | 目录/API 测试；36/36 固定 seed 校准 |
| 两条量子执行链 | Pauli/VQE 与 QUBO/QAOA/Problem 保持领域边界 | 架构依赖测试；四场景真实执行测试 |
| 金融与生物医药融合 | 共用品牌、领域切换、三栏工作台和执行控件，结果与缓存按领域隔离 | React 测试；三视口浏览器流程 |
| 六类生物医药视图 | 领域结果、结构、映射、量子实验、对照分析、审计证据均可访问 | 浏览器实际切换四个对照页和量子页 |
| 量子/经典/参考分离 | 不用经典结果替换失败的量子候选 | 领域、API、React 和浏览器断言 |
| 数据与许可证 | 8 组 manifest 随包安装；只有 1HSG 是外部 CC0 派生数据 | 统一 manifest 校验；wheel 内容检查 |
| 输入与错误边界 | 目录外数据、未知控件、错误模式和 schema 错误在执行前拒绝 | 结构化 422 与损坏 fixture 测试 |
| 审计与报告 | 保存输入、Problem/Hamiltonian、analysis、compile、Backend、执行、结果和稳定 hash | 四场景可重复 hash；报告落盘与内容一致测试 |
| 离线与响应性 | 运行时无网络；长计算进入线程池，不阻塞 health/static | Backend 审计字段；并发健康检查测试 |
| 可用性 | 常驻三条边界；缩写中文 tooltip；颜色之外使用文字和图标表达状态 | React 38 项；浏览器像素、溢出与错误检查 |
| 品牌与交付入口 | React、Windows 启动器、旧金融界面和当前讲解文档使用统一产品名 | 命名搜索；打包模板测试；离线包内容检查 |

## 3. 本阶段发现并关闭的缺口

1. 默认报告目录从进程工作目录改为 macOS、Windows、Linux 的平台用户数据目录；便携包和环境变量仍可显式覆盖。
2. 生物医药未知预设与 Pydantic 请求错误统一为 `code/message/stage` 结构，不再混用字符串和框架默认数组。
3. 对接、有效自旋和小肽 manifest 补齐原始输入 checksum 状态、坐标系、变量顺序、参考软件版本和三个标准预设的参考值。
4. 八组 manifest 统一经过公共契约校验，领域加载器继续校验 Hamiltonian/QUBO/构象顺序和 artifact checksum。
5. 独立视图中的 HF、VQE、QWC、QAOA、QUBO、D-A-D、QAA、AHS 首次关键展示提供中文解释。
6. Windows 离线入口改用 `cascaqit-industry-demo`、`CASCAQIT_INDUSTRY_DATA_DIR` 和 `CASCAQIT_INDUSTRY_PORT`，旧接口只作兼容回退。

## 4. 最终质量门禁

| 门禁 | 结果 |
|---|---|
| Python 全量 | `226 passed in 220.19s` |
| Ruff / diff check | 通过 |
| React | 9 个文件，`38 passed` |
| TypeScript / Vite | 类型检查和生产构建通过 |
| npm audit | `0 vulnerabilities` |
| 固定 seed 校准 | 4 场景、12 预设、36 次运行，`36/36 passed` |
| 性能校准 | 最大分析约 `0.0121 s`，最大标准运行约 `2.4798 s` |
| 浏览器 | `1440 x 900`、`1280 x 720`、`390 x 844` 全部通过 |
| 浏览器图形 | 每个视口检测到 12 个非空 canvas；横向溢出、console error、page error 均为 0 |
| Windows 构建侧 | `13 passed`；29 个 wheel；PowerShell 模板为 UTF-8 BOM + CRLF |

固定 seed 证据保存在 `docs/process/evidence/biomedicine_release_calibration.json`。浏览器报告与截图保存在本地 `artifacts/browser-smoke-phase7/`，不进入 Git。

## 5. 发布制品

普通 wheel：

- `dist/cascaqit_finance_demo-0.1.1-py3-none-any.whl`；
- `584,721` bytes；
- SHA-256 `75b12f621ed94ffe04b33898967a0cabebf9ea2e45bbc4317046eb75303a0760`；
- 包含 8 个 manifest、10 个静态文件和 3 个 `cascaqit_industry_demo` 文件；
- 隔离目标目录安装后的 health、分析 API、中性执行器导入和前端入口 smoke 通过。

Windows x64 / CPython 3.11 离线包：

- `artifacts/biomedicine-windows-offline-phase7/cascaqit-finance-demo-windows-x64-py311.zip`；
- `94,862,200` bytes；
- SHA-256 `0887e0f4f94a2aadc988e841c59ac26ceb84bf45eeb65882ddf184d6ca694414`；
- 包含 29 个 wheel、CPython 3.11.9 runtime、完整性校验和统一行业启动入口。

## 6. 保留边界

- Windows 包已通过 macOS 构建侧的依赖闭包、内容、编码、换行符和脚本静态测试，但尚未在干净 Windows 10/11 x64 实机执行 `VERIFY.bat`、`INSTALL.bat`、`RUN.bat` 和四场景浏览器运行，因此不能声称 Windows 实机已验收。
- 四个生物医药场景是教学规模的固定模型，不具备任意分子电子结构、连续空间完整对接、真实金属酶催化预测或真实蛋白折叠能力。
- 本机耗时基线只用于运行前等待提示，不是跨平台性能承诺或服务等级。
