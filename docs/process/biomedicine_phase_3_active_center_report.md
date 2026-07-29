# 生物医药第三阶段：金属活性中心有效模型实现报告

日期：2026-07-30

## 1. 阶段结论

“金属酶活性中心有效 Hamiltonian”已从结构预览升级为可执行的本地量子演示。场景使用固化的双自旋低能有效模型，CASCAQit 完成 Digital VQE、QWC 分组测量和末端采样；后端从同一绑定 Ansatz 的测量证据返回局域磁化、`XX/YY/ZZ` 两点关联和总磁化扇区占据，并与精确对角化分开展示。

本阶段没有完成全部四个生物医药场景。当前可执行的是电子结构、构象匹配和金属活性中心；小肽能景仍保留预览与后端运行门禁。

## 2. 模型与数据边界

- 数据集：`active-center.bimetal-spin.effective-model`，版本 `1`；
- 模型：两个有效 spin-1/2 位点的各向异性 Heisenberg Hamiltonian；
- 预设：反铁磁耦合、配体场扰动、耦合不平衡；
- 单位：交换耦合、局域场和能量均为 meV；Pauli 期望值无量纲；
- 来源：项目生成的教学有效模型，manifest 对 `domain.json` 与 `pauli.json` 做 SHA-256 校验。

结构图中的金属和配位环境只提供模型语境，不是完整电子轨道，也不是中性原子硬件布局。结果不用于预测催化势垒、反应速率、氧化还原电位或酶活性。

## 3. Hamiltonian 与执行证据

请求解析后的模型为：

```text
H = (Jxy/4)(XX + YY) + (Jz/4)ZZ + (h1/2)Z1 + (h2/2)Z2
```

三个交换项和两个局域场项同时进入 CASCAQit `PauliHamiltonian`。VQE 优化使用一层 hardware-efficient Ansatz；最终 QWC 测量结果的 term expectation 直接生成局域磁化和关联函数，前端不重算观测量。末端计算基采样按声明的 `total_magnetization_z` 聚合扇区占据。

VQE、精确对角化、观测量、比较结果和审计对象共享同一个 Hamiltonian hash。精确对角化只作为小规模经典参考，不替换 VQE 结果。

## 4. 共享层与兼容债务

新增 `pauli_vqe.py` 作为无金融类型依赖的共享工具，电子结构与活性中心共同使用 Hamiltonian 构造和稳定哈希；该模块同时提供小规模精确对角化与扇区聚合。

组合优化的 `ScenarioExecutor` 仍位于金融包并返回 `Finance*` 契约。第三场景未继续扩大这项依赖。直接移动文件只会改名并产生包初始化循环，因此真实类型解耦安排在第四阶段接入小肽 QUBO 前完成。

## 5. 校准与验收

推荐配置为 Digital VQE、`p=1`、512 shots/QWC group、COBYLA 40 次目标评估、单起点，默认 seed 为 `7`。三个预设在固定 seed `1`、`7`、`11` 下，VQE 理想目标相对精确基态的绝对误差均小于 `0.00002 meV`；反铁磁预设的采样标准误约为 `0.008-0.012 meV`。

自动门禁结果：

- Python 3.9：`195 passed`；
- Ruff：通过；
- React：`29 passed`；
- TypeScript：通过；
- Vite 生产构建：通过；
- wheel：通过；
- 浏览器：`1440 x 900`、`1280 x 720`、`390 x 844` 全部通过。

浏览器证据位于 `artifacts/browser-smoke-phase3/`。三视口均无页面级横向溢出、console error 或 page error；活性中心量子页 canvas 非空。结果页截图为 `active-center-result-*.png`，结构化报告为 `report.json`。

## 6. 额外稳定性修正

当前 Python 3.11/SciPy 1.17 环境暴露出既有随机初值 COBYLA 跨版本局部点偏移。H2 fixture 因此固化了已验收的一层 Ansatz warm start，并在审计中声明来源；它只是优化起点，不是预写的采样结果。Python 3.11 下仍有既有金融 `collateral` 固定采样校准偏移，未在本阶段改写金融场景配置。

## 7. 下一步

第四阶段实现小肽离散构象能景：固化 8 至 16 个去重二维自回避构象、构建恰好选择一个构象的 QUBO、接通 Digital QAOA、完整枚举能景与量子观测候选分离，并先完成组合优化执行契约的领域中性类型提取。
