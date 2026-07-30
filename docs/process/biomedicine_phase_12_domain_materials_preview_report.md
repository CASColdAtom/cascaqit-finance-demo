# 生物医药第十二阶段：统一领域与材料 Analog 预览报告

## 1. 阶段结论

第十二阶段完成 `IND-V3-DOMAIN-01` 的代码落地，并建立 `BIO-V3-RNA-01`、`BIO-V3-PROTEIN-DYN-01`、`MAT-V1-QUBO-01` 和 `MAT-V1-AHS-01` 的分析预览入口。产品现以“中科酷原行业量子实验台”统一承载金融、生物医药和材料科学三个一级领域。

本阶段没有宣称新增场景已执行量子算法。RNA、蛋白转变路径和两个材料场景保持 `preview`；材料运行接口返回结构化 `422 / MATERIALS_EXECUTOR_NOT_IMPLEMENTED`。

## 2. 已实现范围

- 统一领域 API 增加材料科学目录，前端支持三领域切换和各领域最近场景记忆。
- 生物医药目录增加 RNA 二级结构集合和蛋白构象转变路径两个预览场景。
- 材料科学目录增加缺陷-吸附构型优化和缺陷晶格 Rydberg 动力学两个预览场景。
- 材料 UI 分开展示材料晶格坐标、有效模型位点和 Rydberg 编译坐标。
- 原生 AHS 预览提供 Hamiltonian、Rabi/Detuning 脉冲和采样时刻定义，不生成伪造的时间序列。
- 纯 Analog UI 只显示 Analog 模式，不显示 Digital/Hybrid 分段、数字线路、QUBO 或 Digital residual。
- 纯 Analog 机器审计载荷保留 `digitalGateCount = 0`、`digitalResidualCount = 0`、`hybridBlockCount = 0`，资源规模使用 `analogSites` 而不是 `logicalQubits`。
- 预览场景不生成 `experimentPlan`，运行按钮禁用。
- 新增离线材料浏览器验收脚本，可用真实 FastAPI 分析载荷和生产构建完成三视口检查，无需监听本地端口。

## 3. 科学与执行边界

- 材料 Rydberg 场景模拟的是材料问题派生的有效多体晶格，不是材料全电子动力学。
- 当前 CASCAQit 发布包、模块来源、可编程初态、时分辨采样和超过 4 原子的本地模拟能力尚未全部通过门禁，因此不实例化 `AnalogExecutor`。
- 缺陷-吸附场景只把 Digital 标记为可比较、Hybrid 标记为推荐；在没有可验证 AHS 映射时，Analog 明确为不适用。
- 经典参考和量子结果保持独立；预览页面不会用经典计算结果填充量子结果。

## 4. 验证证据

通过：

```text
ruff check ...
All checks passed!

pytest -q tests/integration/test_industry_domain_api.py \
  tests/unit/test_biomedicine_electronic_structure.py
50 passed

npm test -- --run
10 test files / 40 tests passed

npm run typecheck
passed

npm run build
passed; MaterialsViews 独立 chunk 约 10.07 kB

python3 -m build --wheel --no-isolation
passed; wheel 包含 cascaqit_materials_demo、MaterialsViews chunk 和 static/index.html

全量 Python（排除已确认的金融抵押品既有失败）
272 passed, 1 deselected
```

全量 Python 唯一既有失败为 `collateral / haircut` 推荐 Digital 配置未采样到可行业务候选。本阶段未修改金融场景、推荐配置或 `ScenarioExecutor`，该问题单独保留，不纳入材料域提交修复。

浏览器验收命令：

```bash
cd frontend
npm run browser-smoke:materials
```

当前受限 macOS 执行容器在 Chromium 注册 Mach port 时返回 `Permission denied (1100)`，并同时禁止 API/Vite 监听本地端口。因此本阶段没有把截图列为已通过证据。脚本的真实 FastAPI fixture 生成和 Node 语法检查已通过；在允许 Chromium 子进程的环境中仍需补跑 `1440x900`、`1280x720` 和 `390x844` 三个视口。

## 5. 下一阶段

第十三阶段按 PRD 保持原范围：

1. 固化 RNA 候选配对、能量参数、贡献账本和经典动态规划对照，接入可执行 QUBO。
2. 固化材料周期晶格、对称归一、缺陷/吸附能量 fixture 和经典枚举对照，接入 Digital/Hybrid 共用逻辑 QUBO。
3. 完成 CASCAQit AHS 发布 wheel、版本来源、初态、时间采样和规模门禁；门禁未通过时 `MAT-V1-AHS-01` 继续保持预览。
4. 在可启动 Chromium 的环境补齐三视口截图并归档 `report.json`。
