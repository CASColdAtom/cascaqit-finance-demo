# 生物医药与材料第十六阶段：V3 总体验收审计

日期：2026-07-31

## 1. 审计结论

本阶段从 PRD 第 16 节和架构第 19 节重新提取要求，不以“场景显示 available”替代发布完成证据。六个生物医药场景、两个材料场景、三领域导航、客户手册、校准聚合、wheel、Windows 离线包构建侧和 Chromium 三视口均已形成直接证据。

V3 状态为 `COMPLETED`。实现基线 `0d5383e5e61c8638d93b162938d59227c8ac0b0a` 已通过 GitHub Actions run `30601093858`：Chromium `151.0.7922.34` 在 `1440x900`、`1280x720`、`390x844` 三个视口执行八场景主 smoke 和独立材料 smoke，27 张主截图与 9 张材料截图均通过证据校验。所有视口无页面级横向溢出，console error 和 page error 均为 0。

## 2. 需求完成矩阵

| 需求 | 当前实现 | 直接证据 | 判定 |
|---|---|---|---|
| `IND-V3-DOMAIN-01` | 金融、生物医药、材料科学一级领域与 API 显式分派 | 目录 API 返回 7/6/2 个 `available` 场景；领域与 App 回归测试 | 通过 |
| `BIO-V3-RNA-01` | 配对 QUBO、Digital QAOA、Top-K、枚举/DP/参考分离 | fixture、模型/API/React 测试、9 次校准、三视口截图 | 通过 |
| `BIO-V3-PROTEIN-DYN-01` | 状态网络、连接保持活动子图、路径 QUBO、Dijkstra 对照 | fixture、路径约束/失败分支测试、9 次校准、三视口截图 | 通过 |
| `MAT-V1-ADSORB-01` | 缺陷-吸附联合 QUBO、Digital/Hybrid、经典与离线参考 | fixture、完整项账本、9 次校准、主与独立材料截图 | 通过 |
| `MAT-V1-AHS-01` | Pure Analog 前缀 AHS、显式初态、时序观测、DOP853 对照 | AHS 契约/数值/API/React 测试、9 次校准、主与独立材料截图 | 通过 |
| `IND-V3-REL-01` | 八场景兼容、校准、wheel、Windows 包、科学边界与客户手册 | 84 次聚合证据、328 项 Python 基线、51 项 React 基线、当前 wheel/Windows 包和浏览器制品 | 通过 |

## 3. 八场景校准聚合

新增 `scripts/validate_v3_release_evidence.py`，机器复核五份已有固定 seed 证据，不重新解释失败为成功：

- V2 四场景：使用 CASCAQit `v1.0.5a` 固定 wheel 重跑 48 次，全部满足各场景发布阈值；证据绑定 SDK tag、源码提交和 wheel SHA-256；
- RNA：3 预设 × 3 seeds，9 次均为真实量子观测可行结构；
- 蛋白路径：9 次中 6 次观测到可行路径、3 次 `quantum_not_observed`，经典回填为 `false`；
- 材料构型：9 次均观测到可行构型，保持每次 15 个 Analog 项和 32 个 Digital residual 项；
- 材料 AHS：9 次全部通过，Digital gate/residual 与 Hybrid block 均为 0。

聚合结果为 8 个场景、84 次运行、8/8 场景通过。证据位于 `docs/process/evidence/industry_v3_release_acceptance.json`，当前文件 SHA-256 为 `3d2d91867aa72c9ec6e0e0eff25657661dbf04a5d872e687ef472cb6d1a8766b`。聚合器记录每份源 JSON 的 SHA-256，并拒绝缺少固定 SDK provenance 的 V2 证据；同时保留篡改蛋白经典回填状态的负向测试。

## 4. 客户演示材料

`docs/biomedicine_customer_demo_guide.md` 已由四场景升级为八场景：

- 演示前检查改为生物医药 6 个、材料科学 2 个场景；
- 新增 RNA、蛋白构象路径、材料缺陷-吸附和材料 Pure Analog AHS 的任务、操作顺序、可说与不可说结论；
- 明确 Hybrid 门禁失败不会静默降级后仍标记 Hybrid；
- 明确蛋白 Digital 路径搜索与材料 Analog 有效模型演化不能互相外推。
- 在 UI、PRD、架构和客户问答中统一增加前沿探索口径：当前不替代成熟经典流程，但可以验证问题映射、量子-经典协同和中性原子执行路线，并沉淀未来硬件可复用基线。

## 5. Windows 离线包构建侧

原构建器硬编码 `uv build`，在受限 macOS 初始化系统配置时崩溃。本阶段改用标准 `python -m build --wheel --no-isolation`，并增加 `--cache-root`。第一次尝试复用旧缓存时发现其中的同版本 CASCAQit wheel 缺少 `threadpoolctl` 依赖元数据，因此该缓存未作为发布输入；最终包从精确 SDK tag 源码构建 CASCAQit wheel，并重新联网解析 Windows x64 完整闭包：

- CASCAQit 与 Demo wheel 均从对应源码重建，不复用旧同名 wheel；
- Windows 第三方依赖重新下载，`bundle-info.json` 记录 `build_dependency_source=network`；
- runtime 的版本、release、源归档 SHA 和派生 ZIP SHA 全部匹配才允许复用；
- 安装阶段完全离线，`network_required_at_install=false`；
- 最终包包含 30 个 wheel，并校验 42 个受 manifest 管理的文件。

当前构建产物：

```text
/tmp/cascaqit-phase16-final-online/cascaqit-finance-demo-windows-x64-py311.zip
size:   95,014,639 bytes
sha256: 9f5a6a364e74bbe0b1bfdd7093bdc160011f6e9caec18c55e73ac19b66067209
```

包内 CASCAQit 为 `1.0.5a0`，没有旧 `1.0.7a0`；CASCAQit 发布输入绑定 tag `v1.0.5a`、commit `6a7df7a2f6f611b1e5f4b3377bc7631a6ff69853` 和 wheel SHA-256 `af665bcd8dc81d7afe1370c1acee656dcc3192b63552429692655dc0159ee97e`。30-wheel 闭包包含 `threadpoolctl-3.6.0`；Demo wheel 包含 RNA、蛋白路径、材料构型、材料 AHS 四个模块及其 fixture，并包含最新 `BiomedicineViews`、`MaterialsViews` 和“前沿探索价值”双语静态资源。manifest 42/42 校验通过。该结果是 macOS 构建侧证据，不等于干净 Windows 10/11 x64 实机运行通过。

## 6. 自动化质量门禁

- `CASCAQIT_INDUSTRY_DATA_DIR=/tmp/... python -m pytest -q`：`328 passed`；
- Windows 包装与 V3 聚合定向回归：`20 passed`；
- `ruff check src tests scripts`：通过；
- React：11 个测试文件、51 项测试通过；TypeScript 和 Vite 生产构建通过；
- V3 聚合复核：8 个场景、84 次运行、8/8 场景通过。
- V2 四场景发布 SDK 重校准：48/48 通过，SDK tag、commit 和 wheel SHA-256 均写入证据；
- wheel 构建、隔离安装 smoke 与 `npm audit --audit-level=moderate` 均通过，npm audit 为 0 vulnerabilities。

第一次在未覆盖数据目录时运行全量测试，有 13 项因当前沙箱禁止写入 macOS `~/Library/Application Support` 而失败；显式使用产品支持的 `CASCAQIT_INDUSTRY_DATA_DIR` 后 13 项全部通过。该记录属于宿主写权限差异，不被隐藏为算法成功或失败。

## 7. 浏览器发布证据

本地 Chromium 主 smoke 与 GitHub Actions 远端 smoke 均已完成。标准复核命令仍为：

```bash
cd frontend
npm run browser-smoke
npm run browser-smoke:materials
```

归档证据覆盖三个视口、八个场景、27 张主截图和 9 张独立材料截图，并证明：无页面级横向溢出、结构 SVG 有实际图元、量子 canvas 非空、console/page error 为 0、量子/经典/参考结果分离、材料 Analog 不显示数字线路。

`.github/workflows/v3-browser-acceptance.yml` 使用固定 CASCAQit wheel、生产 FastAPI 和 Ubuntu Chromium，运行八场景主 smoke 与独立材料 smoke；主报告记录提交 SHA、Chromium 版本和生成时间。run `30601093858` 的制品已下载并由 `scripts/validate_browser_evidence.mjs` 复核通过，报告 revision 与实现基线 `0d5383e5e61c8638d93b162938d59227c8ac0b0a` 一致。此后任何代码或发布文档提交仍必须让最终分支 HEAD 取得 revision 一致的成功工作流，旧制品不能替代新提交证据。

## 8. 科学与发布边界

- 当前演示用于前沿探索、问题映射验证、量子-经典协同路线评估和未来硬件基线沉淀，不表示量子计算已经能够替代成熟经典计算流程；
- 所有执行仍是本地模拟，不声明真实中性原子硬件运行或量子优势；
- 不从 QAOA counts 推导药效、临床效果、结合自由能、蛋白真实动力学、催化活性或材料真实性能；
- 材料 Analog 结果是四位点有效 Rydberg 模型的时间演化，不能外推为材料全电子、全原子或蛋白全原子动力学；
- Windows ZIP 已完成构建侧闭包和 manifest 校验，但尚未形成干净 Windows 10/11 x64 实机启动证据。
