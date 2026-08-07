# CASCAQit 1.0.7a 兼容性报告

## 1. 适配基线

行业量子实验台当前固定使用以下 CASCAQit 发布物：

| 项目 | 值 |
|---|---|
| Python 版本 | `1.0.7a0` |
| Git 标签 | `v1.0.7a` |
| 源码提交 | `2fa67d0c2fdb447995233ab3b65cc92897e81ec5` |
| Wheel | `vendor/cascaqit-1.0.7a0-py3-none-any.whl` |
| SHA-256 | `c6aab02a71e0897d569c3c9f6aebf336b2886daf71be1ed1443a26640defecf6` |
| 依赖范围 | `cascaqit>=1.0.7a0,<1.0.8` |

运行时门禁、CI、Windows 离线包构建和发布校准均使用同一版本范围及 wheel 哈希。

## 2. API 差异与适配

1.0.7a 保留工作台使用的 Pauli Hamiltonian、VQE、QUBO/QAOA、线路、后端、噪声模型、Hybrid 编译和 Analog AHS 公开 API，但移除了旧版 `cascaqit.algorithms.measurement`、`cascaqit.algorithms.readout_mitigation`、`cascaqit.algorithms.vqe_stability` 等模块，`VQE.evaluate_sampled()` 也不再存在。

电子结构和金属活性中心因此改用应用层 `qwc_measurement` 适配器。适配器只调用 1.0.7a 的公开 API，负责：

- 确定性 QWC 分组及稳定计划哈希；
- X/Y Pauli 项的测量基旋转；
- 每个测量组的有限 shots 后端执行；
- Pauli 期望值、Hamiltonian 采样能量和标准误聚合；
- 理想执行与读出噪声执行证据分离。

这项能力登记为应用层 SDK 组合能力 `sdk_application`，不依赖已被删除的私有或旧版高层模块。

## 3. 行为重新校准

SDK 升级后，有限 shots 和优化器轨迹发生了可复现的行为变化，因此发布 seed 不是简单沿用旧版本：

- 抵押品 QAOA 自动选层在 1.0.7a 下选择 `p=2`，`p=3` 的改善置信下界转负并按 `patience_exhausted` 停止；
- 三个标准对接预设分别使用 `1/6/8`、`1/8/11`、`3/6/8`；
- `multi_pose_balanced` 使用 1024 shots、24 次目标评估、单起点和 seeds `0/3/6`；
- 带电竞争小肽使用 seeds `1/6/7`；
- RNA、缺陷吸附和 Analog 场景继续使用固定 seeds `7/23/41`；蛋白路径根据 1.0.7a 的有限 shots 行为按预设使用 `0/5/8`、`0/1/3`、`0/1/3`，每个预设保留两次观测到可行路径和一次未观测到的真实分支。全部审计哈希均由脚本重新生成。

校准器保存实际 SDK 版本、模块路径、运行配置、结果指标和稳定审计字段。聚合门禁覆盖 8 个生物医药与材料场景、84 次固定 seed 运行。

## 4. 验证入口

```bash
python scripts/calibrate_biomedicine_release.py
python scripts/calibrate_v3_discrete_release.py
python scripts/calibrate_materials_analog_release.py
python scripts/validate_v3_release_evidence.py
python -m pytest -q
```

Windows 离线包继续通过 `scripts/build_windows_offline_bundle.py` 构建，构建器会校验固定 wheel 文件名和 SHA-256，安装后的 Python 环境必须解析到 `1.0.7a0`。
