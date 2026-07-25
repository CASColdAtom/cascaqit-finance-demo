# 前后端分离金融工作台实现报告

## 范围

金融 Demo 已使用 FastAPI + React 重构公开工作台。后端负责七个场景、Problem 分析、模式判断、量子执行和业务解码；前端只消费结构化结果并渲染业务、量子和审计视图。

本阶段不接入真实金融系统、量子云服务或真实硬件，也不修改 CASCAQit 的 Problem 编译语义。

## 应用结构

```text
React / TypeScript / ECharts
  -> FastAPI
       -> Scenario Catalog
       -> ScenarioExecutor
            -> FinanceProblemDefinition
            -> ProblemCompiler.analyze()
            -> FinanceModeAdvisor
            -> ProblemCompiler.compile()
            -> LocalBackend
            -> ProblemExecutionResult
            -> 业务解码与约束复核
       -> Presenter
  <- Analysis / Business / Quantum / Audit payloads
```

公开接口包括：

- `GET /api/health`
- `GET /api/scenarios`
- `POST /api/scenarios/{case_id}/analyze`
- `POST /api/scenarios/{case_id}/run`

FastAPI 会托管 `frontend/dist`，生产形态只需访问 `http://127.0.0.1:8000`。开发时 Vite 在 `127.0.0.1:5173` 独立运行，并把 `/api` 代理到 FastAPI。

## 已实现界面

页面采用全宽量子金融指挥台布局：

- 顶部显示“中科酷原金融量子实验台”、服务状态、合成数据和审计状态；
- 左侧切换七个金融场景；
- 中间调整预设、业务参数、模式、shots、seed、QAOA 层数、搜索方式和评估预算；
- 右侧显示业务结果、场景态势、Problem 映射、量子实验和审计证据。

页面支持中英文切换，并记住用户选择。七个场景的标题、说明、预设、参数和主要分析结论均有英文文本。审计摘要显示 mode、seed、shots 和耗时；Backend、Target、硬件、云端和网络事实保留在结构化审计载荷中。

业务图、网络图、Hamiltonian 矩阵、原子阵列、合并波形、counts 和参数历史使用 ECharts。量子实验只展示从实际编译结果提取的 QAOA 逻辑层，不在客户界面展开通用门分解。

“场景态势”不再复用通用散点图。后端 `scenarioVisual` 根据业务输入返回场景专属数据，前端不解析展示字符串：

- 投资组合显示由协方差和波动率计算的资产相关性矩阵；
- 交易结算显示冲突边与前置依赖；
- 反欺诈显示告警与关键实体的二部关系；
- 抵押品显示候选资产到保证金需求桶的分配流；
- 流动性显示日内动作和分币种累计覆盖曲线；
- 授信额度显示资本成本、风险调整价值和资本占用；
- 衍生品显示经典定价链在 `3 x 3` 压力情景下的价格变化，运行后高亮 Analog 选中的代表情景。

场景图在 analyze 完成后即可显示。量子执行完成后只叠加入选状态，不会改变基础业务数据。

场景态势是默认首屏。首次加载、切换场景、切换预设或修改业务参数后，页面都会停留在对应场景图，并显示业务对象数、结构规模、Problem 变量数和推荐链路。实验完成后自动进入业务结果，避免在尚未运行时展示空结果页。

业务结果图也使用场景自己的坐标和单位。结算显示流动性占用与名义金额，反欺诈显示涉案金额与风险分，流动性使用真实日内时点，授信显示资本成本与风险调整价值。抵押品显示完整候选名称。衍生品结果同时显示经典参考价格、Delta、Gamma、Vega 和 Analog 代表情景，量子 counts 仍不参与定价。

Hybrid 量子实验同时显示 D-A-D block、原子布局、Rabi/Detuning/Phase、Digital residual 线路和末端 counts。Analog 不显示数字线路。所有图形读取后端执行上下文，前端不推断或生成量子事实。

三种控制波形绘制在同一张共享时间轴图中，并使用三条独立通道轨道。轨道偏移只用于避免恒零曲线互相覆盖，悬浮提示显示后端返回的原始值。Analog 和 Hybrid 返回的 Rabi、Detuning、Phase 均至少包含起止端点；缺省或恒零控制量不会被伪造成非零波形。

页面已为桌面、平板和移动端设置断点。宽屏使用三栏固定工作区；平板把场景导航放到顶部；手机使用单行横向场景任务带，并把参数区默认收为“参数与执行”工具条。用户展开后仍可访问全部业务参数、模式和运行设置。表格和数字线路只在自身容器内横向滚动，不产生页面级横向溢出。

## 状态管理

业务输入变化后，前端延迟 180 ms 调用 analyze，并使用 revision 丢弃过期响应。每次执行记录完整签名：

```text
case + preset + values + mode + shots + seed + layers + search_strategy + parameter_budget
```

只有签名完全一致时才恢复缓存结果。运行期间按钮禁用；完成后结果写入对应签名，不覆盖用户已经切换到的其他输入。

用户切换到可比较模式后，场景头部和控制区显示所选模式自己的判断理由，并标记为 `COMPARISON PATH`。Problem 映射中的 Analog / Digital 分配条按当前模式两类 term 的实际数量归一化，不使用展示系数估算比例。

FastAPI 使用线程池执行本地模拟，避免阻塞异步请求循环。当前没有持久化任务队列，页面刷新后运行缓存会丢失。

## 量子执行事实

七个默认场景当前推荐模式为：

| 场景 | 推荐模式 |
|---|---|
| 多资产投资组合 | Digital |
| 交易结算 | Hybrid |
| 反欺诈调查编排 | Hybrid |
| 抵押品分配 | Digital |
| 日内流动性调度 | Digital |
| 企业授信额度配置 | Digital |
| 衍生品风险情景选择 | Analog |

本地联调分别执行了三条代表链：

- Digital：投资组合的 `p=1/2/3` 均通过实际编译、执行和采样，参数数量严格为 `2p`；
- Hybrid：交易结算返回 `digital -> analog -> digital -> measure`、16 sites、波形和 16 shots；
- Analog：衍生品风险情景返回 9 sites、波形和 16 shots，数字门数量为 0。

衍生品参考价格仍由经典算法计算，Analog counts 不参与定价。所有运行均为 `LocalBackend` 本地模拟，未访问网络、云端或真实硬件，最优性声明为 `not_claimed`。

## 模式判断现状

`FinanceModeAdvisor` 不再读取场景预填的 `preferred_mode`。Analog 与 Hybrid 必须使用 `provided` 布局，完整覆盖声明的 core group，且实际物理 interaction 图不能漏边或补边；进入 Analog 的二体 Hamiltonian 项也必须能回到业务 pair。API 返回 covered group、missing contribution、unexpected term、unexpected interaction、geometry source/status 和 layout policy。

默认交易结算和反欺诈均为 `3/3` core contribution 覆盖，衍生品风险图为 `12/12`；三者均为 0 漏项、0 异常二体项、0 补边。分组缺边和物理补边已有负向测试。本报告完成时尚未实现逐系数账本，该项已在后续阶段补齐，见[逐系数业务证据账本实现报告](coefficient_ledger_implementation_report.md)。

## Digital QAOA 参数搜索

Digital 控制区支持 `p=1~3`。预设方式提供两组人工校验参数；二维网格只用于 `p=1`；固定 seed 采样支持全部三种层数，最多评估 24 个离散点。每个点的 `gamma_i`、`beta_i`、目标值和是否入选都进入 API 结果，参数图悬浮提示直接读取这些值。

本报告完成时，Hybrid 和 Analog 只使用一层预设配置，参数搜索通过 `compiled.optimize(parameter_sets=...)` 比较离散点。后续已接入连续优化、多起点和独立重复运行，当前实现见[参数优化与重复统计实现报告](parameter_optimization_and_repeated_statistics_report.md)。

## 验证结果

```text
/opt/homebrew/bin/python3.11 -m pytest -q
91 passed

python3 -m ruff check src tests
All checks passed!

npm run typecheck
passed

npm test
6 files, 15 tests passed

npm run build
passed

```

FastAPI 根页面和 health 返回 HTTP 200。重新加载服务后，七个 analyze 接口分别返回 64 个相关性格点、10 个交易节点、21 个告警/实体节点、11 个抵押品流节点、8 个流动性动作与 3 条币种曲线、8 个授信候选和 9 个衍生品重估情景。

自动浏览器运行时没有可用实例，因此没有完成 `1440 x 900`、`1280 x 720` 和 `390 x 844` 的截图、DOM 溢出及 canvas 像素检查。该项仍需在可用浏览器中人工验收，不能用 HTTP 200、接口数据或组件测试替代。

## 当前限制

- 前端已把应用入口、结果视图和 ECharts 拆开。应用入口为 37.57 kB（gzip 13.96 kB），结果视图为 38.98 kB（gzip 11.37 kB）；ECharts 为延迟加载资源，当前为 668.65 kB（gzip 225.65 kB），构建仍会报告大 chunk 警告。
- 旧 Bokeh 代码仍保留为内部调试路径，不再是公开启动入口。
- 本地精确模拟规模用于现场演示，不代表中性原子硬件规模。
- 合成数据和小规模经典基准不能证明真实业务收益或量子优势。
