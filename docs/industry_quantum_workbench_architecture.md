# 中科酷原行业量子实验台总体架构

## 1. 架构目标

系统是一个跨领域量子实验工作台，不是金融应用与若干附属页面的组合。架构需要同时支持领域隔离、统一体验、量子执行复用、可审计数据和可重复离线发布。

项目级工程名称为 `cascaqit-industry-workbench`。`cascaqit_finance_demo` 保留为金融领域实现包和兼容边界；统一执行能力位于 `cascaqit_industry_demo`，生物医药与材料分别位于独立包。

## 2. 系统分层

```text
React Industry Workbench
  -> FastAPI unified domain routes
     -> finance adapters
     -> biomedicine adapters
     -> materials adapters
        -> domain-neutral problem executor / audit services
           -> CASCAQit compiler and algorithms
              -> packaged execution backend
```

| 层 | 职责 |
|---|---|
| React 工作台 | 领域导航、参数控制、结构图、结果、量子实验和审计展示 |
| FastAPI 外壳 | 领域目录、分析、执行、任务、报告和静态资源托管 |
| 领域包 | 输入校验、数据解释、Hamiltonian/QUBO 构造、结果解码和经典对照 |
| 行业公共层 | Problem protocol、模式顾问、算法策略、执行器和稳定哈希 |
| CASCAQit | Pauli/QUBO/AHS 表达、编译、VQE/QAOA/QAA 和后端执行 |
| 发布层 | Python wheel、Windows runtime、wheelhouse、安装器和完整性清单 |

## 3. 代码所有权

### 3.1 `cascaqit_industry_demo`

持有领域中性的 Problem 模型、执行器、审计 helper 和主启动入口。该包不能导入某一领域的数据模型；入口模块可以延迟加载统一 FastAPI 应用，以保留现有部署兼容性。

### 3.2 `cascaqit_finance_demo`

持有七个金融场景、金融输入模型、QUBO 账本、金融解码器和当前统一 FastAPI 应用实现。包名是历史兼容边界，不是产品名称。新公共能力不得继续沉入该包。

### 3.3 `cascaqit_biomedicine_demo`

持有电子结构、构象匹配、金属活性中心、小肽、RNA 和蛋白路径的领域模型、fixture、执行适配器与对照分析。不得导入金融领域模型。

### 3.4 `cascaqit_materials_demo`

持有缺陷吸附 QUBO 与 Rydberg 动力学 AHS。只依赖领域中性层和 CASCAQit，不依赖金融或生物医药模型。

## 4. API 架构

统一领域路由是项目级正式契约：

```text
GET  /api/domains
GET  /api/domains/{domain_id}/scenarios
POST /api/domains/{domain_id}/scenarios/{case_id}/analyze
POST /api/domains/{domain_id}/scenarios/{case_id}/run
POST /api/domains/{domain_id}/scenarios/{case_id}/jobs
GET  /api/jobs/{job_id}
POST /api/jobs/{job_id}/cancel
```

原金融 `/api/scenarios` 等路由继续兼容。新领域功能只能进入带 `domain_id` 的统一路由，避免继续扩大历史金融 API 的语义。

## 5. 执行架构

| 执行族 | 场景类型 | 核心证据 |
|---|---|---|
| Digital VQE | Pauli 电子结构、有效自旋 Hamiltonian | Pauli 项、QWC 分组、Ansatz、参数历史和期望值 |
| Digital QAOA | 稠密或全局约束的组合优化 | QUBO 账本、逻辑线路、参数搜索、counts 和解码 |
| Hybrid D-A-D | 局域冲突可映射且仍有数字 residual | 原子布局、Analog 波形、Digital residual 和项覆盖率 |
| Pure Analog AHS | 完整有效 Hamiltonian 可由原子与控制表达 | 初态、原子阵列、时间波形、逐时点观测和终态 counts |
| Classic comparison | 小规模校验和独立参考 | 算法身份、输入一致性、结果差异和耗时 |

模式选择由编译事实和领域门禁共同决定。编译成功不等于业务适合；Hybrid 必须覆盖完整局域业务组，Pure Analog 不能隐藏数字残差。

## 6. 数据与可重复性

fixture 目录遵循：

```text
data/{scenario}/{dataset}/{version}/
  manifest.json
  domain.json
  pauli.json | reference.json | other artifacts
```

manifest 声明数据来源、版本、生成方法和 artifact SHA-256。Git 固定 JSON 为 LF，避免 Windows checkout 改变字节哈希。发布构建在 wheel 生成后再次读取 wheel 内容并校验全部 artifact，从而覆盖源码、构建工具和平台换行三类漂移。

## 7. 前端架构

React 应用只有一个顶层壳：

- 顶部领域导航负责一级上下文；
- 左侧场景目录由领域 catalog 驱动；
- 中栏参数面板根据领域 schema 渲染；
- 右侧复用结果、结构、Problem、量子实验、对照和审计视图；
- 生物医药与材料使用各自视图模块，金融视图保持领域专用组件；
- 缓存键必须包含领域、场景、输入和全部执行配置。

生产构建暂由统一 FastAPI 应用从 `cascaqit_finance_demo/static` 托管。该路径属于兼容实现，后续只有在迁移成本可控且能保持旧 wheel 升级时才移动到中性包。

## 8. 分发与兼容

### 8.1 正式身份

- Python distribution：`cascaqit-industry-workbench`。
- 主命令：`cascaqit-industry-api`、`cascaqit-industry-demo`。
- Windows bundle：`cascaqit-industry-workbench-windows-x64-py311`。

### 8.2 兼容身份

- `cascaqit-finance-api`、`cascaqit-finance-demo` 继续作为 CLI 别名。
- `cascaqit_finance_demo` 继续作为金融领域导入路径。
- Windows 缓存构建同时排除新旧 distribution wheel，确保不会把旧项目 wheel 混入新包。

## 9. Windows 发布架构

```text
source checkout (JSON forced LF)
  -> React production build
  -> workbench wheel + CASCAQit pinned wheel
  -> fixture checksum audit
  -> Windows dependency closure
  -> portable CPython runtime
  -> templates + bundle-info + SHA256 manifest
  -> ZIP
  -> Windows VERIFY / INSTALL / RUN acceptance
  -> GitHub Release asset
```

`bundle-info.json` 是安装器的版本事实源。安装器读取 `industry_workbench` 精确 requirement，避免版本同时散落在 Python、PowerShell 和 CI 中。构建流程和发布检查见 [Windows 离线发布手册](process/windows_offline_release_playbook.md)。

## 10. 质量门禁

- 领域单元测试与 API 集成测试；
- 行业公共层依赖方向测试；
- fixture manifest 与 wheel artifact 哈希测试；
- React 类型、组件和生产构建；
- 三视口 Chromium 八场景验收；
- Windows 10/11 x64 离线安装与启动验收；
- Release 资产服务端 SHA-256 复核。

任何门禁失败都不能用旧 revision 的证据替代。仅修改文档时可以复用相同二进制基线，但报告必须明确制品对应的构建提交。
