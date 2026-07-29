# 生物医药第五阶段发布验收报告

日期：2026-07-30

## 1. 发布结论

“中科酷原行业量子实验台”的四个生物医药场景已完成发布前校准和构建侧验收：小分子电子结构、靶点口袋与配体构象匹配、金属活性中心有效模型、小肽离散构象能景均可在 CASCAQit `1.0.5a` 本地模拟器上运行。12 个标准预设共执行 36 次固定 seed 校准，结果为 `36/36 passed`。

本次验收支持客户演示和离线交付准备，不代表 Windows 实机验收完成。所有结果来自 `LocalBackend`，不是中性原子量子硬件或云端任务；报告不宣称量子优势，也不输出药物、临床、催化活性或真实蛋白折叠结论。

## 2. 发布范围

| 场景 | 预设数 | 当前量子路径 | 可展示结果 |
|---|---:|---|---|
| 小分子电子结构 | 3 | Digital VQE | H2 三点键长趋势，LiH/H2O 活性空间，QWC 测量、读出噪声与精确对照 |
| 构象匹配 | 3 | Hybrid D-A-D QAOA | 1HSG/Indinavir 离散特征匹配、几何门禁、量子候选与经典参考 |
| 金属活性中心 | 3 | Digital VQE | 双自旋有效模型、磁化与关联观测量、精确对角化对照 |
| 小肽能景 | 3 | Digital QAOA | 10 个二维自回避构象、one-hot QUBO、量子候选与完整经典能景 |

前端继续使用金融与生物医药共用的行业工作台外壳，通过行业导航切换目录、参数和结果视图。四个生物医药结果页统一显示来源、支持的解释、限制和稳定审计链。

## 3. 固定 seed 校准

校准证据保存在 `docs/process/evidence/biomedicine_release_calibration.json`。校准环境为 macOS arm64、Python `3.9.6`、CASCAQit 和 Demo 本地源码；运行不访问网络。

| 检查 | 发布条件 | 实际结果 |
|---|---:|---:|
| 场景、预设和运行数 | 4 场景、12 预设、36 次运行 | 4、12、36 |
| 分析时间 | 每次小于 2 秒 | 最大约 `0.0164 s` |
| 运行时间 | 每次小于 30 秒 | 最大约 `2.6015 s` |
| H2 平衡键长绝对误差 | 不大于 `0.0016 Ha` | 约 `4.73e-7 Ha` |
| 金属活性中心绝对误差 | 小于 `0.02 meV` | 最大约 `4.48e-5 meV` |
| 构象匹配 | 每次观察到可行量子候选 | 9/9 通过，最少 1 个可行候选 |
| 小肽能景 | 每次候选达到最低或次低能级 | 9/9 通过 |

LiH 和 H2O 的 VQE 绝对误差分别约为 `0.000238 Ha` 和 `0.001153 Ha`，只做误差报告，不沿用 H2 平衡键长的精度声明。H2O 的理想模式与读出噪声模式保留独立 QWC 证据，不能把噪声结果解释为硬件结果。

同一场景在相同配置和 seed 下重复运行时，`backendHash`、`configurationHash`、`outcomeHash` 和 `reportHash` 保持稳定，四场景专项测试为 `4 passed`。这些字段用于核对后端、配置、结果和报告是否被改变，不证明科学结论或硬件真实性。

## 4. 数据来源复核

发布包包含 8 组生物医药 fixture：5 组项目生成的 H2、LiH、H2O 电子结构数据，1 组由 RCSB PDB `1HSG` 派生的构象匹配数据，1 组项目生成的双自旋有效模型，1 组项目生成的小肽构象库。

- `1HSG` 原始结构按 RCSB PDB 的 CC0-1.0 政策使用，manifest 保存 DOI、原始 mmCIF checksum 和许可证复核日期；
- 项目生成数据均标记为 `project_generated`，并登记生成参数、工具版本、checksum、允许说法和限制；
- 五组电子结构 fixture 由 PySCF `2.10.0`、OpenFermion `1.7.1` 和 OpenFermion-PySCF `0.5` 固定生成；
- 运行时不依赖上述生成工具，也不读取患者、临床试验受试者、内部化合物或未公开研发项目数据。

详细来源、许可证和 checksum 见 `docs/biomedicine_data_source_inventory.md`。

## 5. 代码与页面门禁

| 检查 | 结果 |
|---|---|
| Python 3.9 全量测试 | `218 passed in 230.70s` |
| Ruff | 通过 |
| React 测试 | 9 个文件、`32 passed` |
| TypeScript | 通过 |
| Vite 生产构建 | 通过，产物直接写入 Python static 目录 |
| npm 依赖审计 | 0 vulnerabilities |
| API 异常输入 | 损坏 fixture 和不支持模式均返回 422 |
| CASCAQit 正式标签兼容性 | 在 `v1.0.5a` 隔离 wheel 下运行 50 项生物医药/API 测试，全部通过 |
| 最终 Python wheel | 构建和安装后真实 smoke 通过 |

Python 全量测试使用 `.venv/bin/python -m pytest -q`。直接调用 `.venv/bin/pytest` 不会自动把仓库根目录加入 `sys.path`，会导致既有 `scripts` 测试模块在收集阶段找不到；这不是场景执行失败。

浏览器验收覆盖 `1440 x 900`、`1280 x 720` 和 `390 x 844` 三个视口。每个视口实际运行 H2、LiH、H2O 读出噪声、构象匹配、金属活性中心和小肽能景；所有页面均无横向溢出，console error 和 page error 均为 0，canvas 像素检查非空。截图和结构化报告位于 `artifacts/browser-smoke-phase5/`，该目录是本地验收制品，不进入 Git。

## 6. 依赖与交付制品

Demo 发布依赖固定为 `cascaqit>=1.0.5a0,<1.0.6`。该范围对应已发布标签 `v1.0.5a`；此前文档中的 `1.0.7a0` 是开发版本口径，不再作为本次发布依赖。

最终普通 wheel：

- 文件：`dist/cascaqit_finance_demo-0.1.1-py3-none-any.whl`；
- SHA-256：`1456fb84ee27f7c05cdc061d8e68d59cb110e6fba2f73e03fd9652f4535f0b83`；
- 内容：75 个文件，包含 8 组 manifest、四场景实现和最终 React 静态资源；
- 安装验证：Demo 与 CASCAQit 均从临时 wheel 安装目录加载，CASCAQit 版本为 `1.0.5a`，16 shots 真实运行 smoke 通过。

Windows x64、CPython 3.11 离线包的构建侧结果：

- 文件：`artifacts/biomedicine-windows-offline-phase5-v3/cascaqit-finance-demo-windows-x64-py311.zip`；
- 大小：`94,853,341` bytes；
- SHA-256：`002166e221e45f72bbe0b0479749d8458b33348c7135f5405a00a8f3a1834604`；
- 内容：29 个 wheel，CASCAQit `1.0.5a0`、Demo `0.1.1`、8 组生物医药 manifest 和最终前端资源；
- 构建侧测试：`13 passed`，依赖闭包、manifest、压缩结构和包内容检查通过。

`artifacts/` 和 `dist/` 不提交到 Git；交付时应使用上述 SHA-256 单独核对制品。

## 7. 发布限制

- Windows 离线包尚未在干净的 Windows 10/11 x64 机器执行 `VERIFY.bat`、`INSTALL.bat`、`RUN.bat`、浏览器启动和四场景运行，因此不能标记为 Windows 实机验收通过。
- 四个场景均为教学规模的固定模型，不能外推为任意分子电子结构、通用分子对接、真实金属酶催化预测或真实蛋白质折叠能力。
- 构象匹配只报告离散特征匹配和可行候选，不报告结合自由能、Kd、Ki、IC50、药效或临床结论。
- 金属活性中心参数不是从具体金属酶结构或轨道自动推导的；小肽接触分数不是分子自由能。
- 所有量子结果来自本地模拟器。本次验收没有接入中性原子量子硬件，也不提供量子优势证据。
