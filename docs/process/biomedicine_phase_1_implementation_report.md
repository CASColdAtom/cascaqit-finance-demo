# 生物医药第一阶段实现报告

日期：2026-07-29

## 1. 阶段结论

第一阶段已经完成统一行业工作台骨架和生物医药四场景目录。小分子电子结构已接通真实 CASCAQit Digital VQE 执行；构象匹配、金属活性中心和小肽能景当前为结构预览，运行入口在前后端同时关闭。

本阶段不满足四场景全部发布条件，不应描述为完整生物医药求解产品。当前可对外演示的量子执行能力是 H2 活性空间基态能量估计，其余三个入口用于说明后续问题建模、数据和算法边界。

## 2. 已实现范围

- 对外产品名称统一为“中科酷原行业量子实验台”；CASCAQit 只表示底层 SDK 和执行引擎。
- 顶部提供金融与生物医药一级领域切换，领域内场景导航和结果状态彼此隔离。
- URL 使用 `/{domain_id}/{case_id}`，API 使用 `/api/domains/{domain_id}/scenarios/...`，运行缓存签名包含 `domainId`。
- 原 `/api/scenarios`、`cascaqit-finance-api` 和 `cascaqit-finance-demo` 保持兼容。
- 生物医药代码、fixture 和目录位于独立 `cascaqit_biomedicine_demo` 包，不依赖金融领域模型。
- 四个场景均有领域结构视图、问题映射边界和研究演示限制。

## 3. H2 执行链

电子结构预设使用两量子位 H2 STO-3G 活性空间 Pauli Hamiltonian：

```text
fixture + manifest + checksum
  -> Pauli Hamiltonian
  -> CASCAQit VQE Ansatz
  -> 理想态矢量目标优化
  -> QWC 分组
  -> LocalBackend 有限 shots 确认
  -> 精确对角化对照
  -> 审计 hash 链
```

优化目标、末端采样和精确参考分开保存。页面不把最高频 bitstring 解释为基态能量，也不把经典参考替换成量子结果。推荐配置在当前固定 seed 下达到 1.6 mHa 以内误差，并实际执行两个 QWC 测量组。

## 4. 结构预览边界

| 场景 | 当前提供 | 当前不提供 |
|---|---|---|
| 构象匹配 | 离散配体特征、口袋特征和候选关系 | QUBO、Hybrid 编译、counts、结合自由能 |
| 金属活性中心 | 双金属低能有效自旋网络 | Pauli VQE、关联函数、催化或酶活性结论 |
| 小肽能景 | 二维粗粒化构象和接触关系 | QUBO、QAOA、真实蛋白结构预测 |

前端运行按钮对预览场景禁用；后端运行接口返回 `BIOMEDICINE_EXECUTOR_NOT_IMPLEMENTED`，避免调用方绕过页面触发不存在的能力。

## 5. 验收结果

已通过以下门禁：

- Python 全量测试；
- Ruff 全量检查；
- TypeScript 类型检查；
- React 测试 25 项；
- Vite 生产构建；
- 金融 7 场景兼容目录和生物医药 4 场景领域目录；
- `1440 x 900`、`1280 x 720`、`390 x 844` 浏览器验收；
- 四场景切换、预览运行门禁和 H2 真实运行；
- 页面级横向溢出、结构 SVG、量子图表 canvas 实绘像素和浏览器 console/page error 检查。

浏览器门禁由 `node scripts/browser-smoke.mjs` 执行，证据默认写入被 Git 忽略的 `artifacts/browser-smoke/`。

## 6. 当前风险

H2 Hamiltonian 系数已经通过 manifest、文件 checksum、Hamiltonian hash、数值参考和项目测试固化，可用于当前项目 benchmark。manifest 同时明确标记：对外科学发布前还需在受控化学工具链中完成独立来源复核和可重复生成审计。

其余三个场景当前使用合成结构预览，不应被描述为已经完成量子求解。所有执行仍来自 `LocalBackend`，不是中性原子硬件或云端任务，不声称量子优势。

## 7. 后续顺序

1. 构象匹配：完成离线数据 manifest、QUBO 贡献账本、领域解码和 Hybrid 几何门禁。
2. 金属活性中心：接入有效自旋 Pauli Hamiltonian、VQE 和后端计算的关联函数。
3. 小肽能景：完成自回避构象库、QUBO、Digital QAOA 和完整枚举对照。
4. 对四场景执行固定 seed 校准、离线包构建、来源审计和最终发布验收。
