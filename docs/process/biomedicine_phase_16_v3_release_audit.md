# 生物医药与材料第十六阶段：V3 总体验收审计

日期：2026-07-30

## 1. 审计结论

本阶段从 PRD 第 16 节和架构第 19 节重新提取要求，不以“场景显示 available”替代发布完成证据。六个生物医药场景、两个材料场景、三领域导航、客户手册、校准聚合、wheel 和 Windows 离线包构建侧均已形成当前源码的直接证据。

V3 仍不标记为 `COMPLETED`。PRD 明确要求 `1440x900`、`1280x720`、`390x844` 三视口真实浏览器截图；当前托管 macOS 环境在 Chromium Mach 服务注册阶段返回 `Permission denied (1100)`。组件测试、DOM 断言、脚本语法和历史截图均不能替代本次 V3 页面截图。

## 2. 需求完成矩阵

| 需求 | 当前实现 | 直接证据 | 判定 |
|---|---|---|---|
| `IND-V3-DOMAIN-01` | 金融、生物医药、材料科学一级领域与 API 显式分派 | 目录 API 返回 7/6/2 个 `available` 场景；领域与 App 回归测试 | 通过 |
| `BIO-V3-RNA-01` | 配对 QUBO、Digital QAOA、Top-K、枚举/DP/参考分离 | fixture、模型/API/React 测试、9 次校准 | 实现通过；V3 截图待验 |
| `BIO-V3-PROTEIN-DYN-01` | 状态网络、连接保持活动子图、路径 QUBO、Dijkstra 对照 | fixture、路径约束/失败分支测试、9 次校准 | 实现通过；V3 截图待验 |
| `MAT-V1-ADSORB-01` | 缺陷-吸附联合 QUBO、Digital/Hybrid、经典与离线参考 | fixture、完整项账本、9 次校准 | 实现通过；V3 截图待验 |
| `MAT-V1-AHS-01` | Pure Analog 前缀 AHS、显式初态、时序观测、DOP853 对照 | AHS 契约/数值/API/React 测试、9 次校准 | 实现通过；V3 截图待验 |
| `IND-V3-REL-01` | 八场景兼容、校准、wheel、Windows 包、科学边界与客户手册 | 84 次聚合证据、326 项 Python 基线、50 项 React 基线、当前 wheel/Windows 包 | 浏览器门禁未完成 |

## 3. 八场景校准聚合

新增 `scripts/validate_v3_release_evidence.py`，机器复核五份已有固定 seed 证据，不重新解释失败为成功：

- V2 四场景：48 次运行，全部满足各场景发布阈值；
- RNA：3 预设 × 3 seeds，9 次均为真实量子观测可行结构；
- 蛋白路径：9 次中 6 次观测到可行路径、3 次 `quantum_not_observed`，经典回填为 `false`；
- 材料构型：9 次均观测到可行构型，保持每次 15 个 Analog 项和 32 个 Digital residual 项；
- 材料 AHS：9 次全部通过，Digital gate/residual 与 Hybrid block 均为 0。

聚合结果为 8 个场景、84 次运行、8/8 场景通过。证据位于 `docs/process/evidence/industry_v3_release_acceptance.json`，文件 SHA-256 为 `6d777d5a75af9ae528bb552e231593e06f98b44fe5a88e888849f648396ebc4f`。聚合器记录每份源 JSON 的 SHA-256，并有篡改蛋白经典回填状态的负向测试。

## 4. 客户演示材料

`docs/biomedicine_customer_demo_guide.md` 已由四场景升级为八场景：

- 演示前检查改为生物医药 6 个、材料科学 2 个场景；
- 新增 RNA、蛋白构象路径、材料缺陷-吸附和材料 Pure Analog AHS 的任务、操作顺序、可说与不可说结论；
- 明确 Hybrid 门禁失败不会静默降级后仍标记 Hybrid；
- 明确蛋白 Digital 路径搜索与材料 Analog 有效模型演化不能互相外推。
- 在 UI、PRD、架构和客户问答中统一增加前沿探索口径：当前不替代成熟经典流程，但可以验证问题映射、量子-经典协同和中性原子执行路线，并沉淀未来硬件可复用基线。

## 5. Windows 离线包构建侧

原构建器硬编码 `uv build`，在受限 macOS 初始化系统配置时崩溃。本阶段改用标准 `python -m build --wheel --no-isolation`，并增加 `--cache-root`：

- 只复用上一份已验收包的第三方 Windows wheel 和已验签 Python runtime；
- 旧 CASCAQit/Demo wheel 被过滤，当前两个 wheel 始终从源码重建；
- runtime 的版本、release、源归档 SHA 和派生 ZIP SHA 全部匹配才允许复用；
- 缓存与输出为同一目录时先暂存上一版，构建失败则恢复完整旧目录，支持安全重试；
- 复用后重新执行 29-wheel 依赖闭包、包清单和 41 个文件的 SHA-256 清单。

当前构建产物：

```text
/tmp/cascaqit-phase16-offline/cascaqit-finance-demo-windows-x64-py311.zip
size:   94,962,279 bytes
sha256: a4e4e60dac1ce71ae74a1dba2b725b73f65c0ac2cd5c74c701f1d203b009d2a8
```

包内 CASCAQit 为 `1.0.5a0`，没有旧 `1.0.7a0`；Demo wheel 包含 RNA、蛋白路径、材料构型、材料 AHS 四个模块及其 fixture，并包含最新 `BiomedicineViews`、`MaterialsViews` 和“前沿探索价值”双语静态资源。manifest 41/41 校验通过。该结果是 macOS 构建侧证据，不等于干净 Windows 10/11 x64 实机运行通过。

## 6. 自动化质量门禁

- `CASCAQIT_INDUSTRY_DATA_DIR=/tmp/... python -m pytest -q`：`326 passed`；
- Windows 包装与 V3 聚合定向回归：`20 passed`；
- `ruff check src tests scripts`：通过；
- React：11 个测试文件、50 项测试通过；TypeScript 和 Vite 生产构建通过；
- V3 聚合复核：8 个场景、84 次运行、8/8 场景通过。

第一次在未覆盖数据目录时运行全量测试，有 13 项因当前沙箱禁止写入 macOS `~/Library/Application Support` 而失败；显式使用产品支持的 `CASCAQIT_INDUSTRY_DATA_DIR` 后 13 项全部通过。该记录属于宿主写权限差异，不被隐藏为算法成功或失败。

## 7. 剩余发布门禁

唯一阻止 V3 总目标标记完成的明确发布条件是当前版本的真实浏览器证据：

```bash
cd frontend
npm run browser-smoke
npm run browser-smoke:materials
```

需要归档三个视口的截图和结构化报告，并证明：无页面级横向溢出、结构 SVG 有实际图元、量子 canvas 非空、console/page error 为 0、量子/经典/参考结果分离、材料 Analog 不显示数字线路。宿主权限放行前继续保持 `FINAL ACCEPTANCE / BROWSER PENDING`。

仓库已增加 `.github/workflows/v3-browser-acceptance.yml` 作为宿主受限时的真实 Chromium 验收路径。工作流使用 CASCAQit `v1.0.5a`、生产 FastAPI 和 Ubuntu Chromium，运行八场景主 smoke 与独立材料 smoke；主报告记录提交 SHA、Chromium 版本和生成时间，`scripts/validate_browser_evidence.mjs` 复核三个视口、八场景、27 张截图、canvas 像素、横向溢出、浏览器错误和前沿探索文案。该工作流代码提交不等于门禁通过，只有远端运行成功、制品下载并完成 revision/SHA 一致性复核后才能更新本节结论。
