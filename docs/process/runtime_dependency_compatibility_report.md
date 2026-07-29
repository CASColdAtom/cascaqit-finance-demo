# 运行时依赖兼容性报告

## 2026-07-30 更新

CASCAQit 后续正式发布线采用 `v1.0.5a`，取代本报告早期使用的 `1.0.7a0` 开发版本号。Demo 当前依赖调整为 `>=1.0.5a0,<1.0.6`。发布前从 `v1.0.5a` 标签构建原始 wheel，并在隔离导入路径下运行 50 项生物医药和行业 API 测试，全部通过；Windows 离线构建不再因本地 SDK `1.0.5a0` 与 Demo 元数据冲突而失败。

以下内容保留早期兼容性修复记录，其中 `1.0.7a0` 是当时的开发版本口径，不再是当前发布依赖。

## 修复内容

- 测试打包模块启用延迟类型标注，避免 Python 3.9 在导入 `list[str] | None` 时失败。
- Demo 的 CASCAQit 依赖提升为 `>=1.0.7a0,<1.0.8`。当前 Hybrid 场景依赖该版本系列的 QUBO 完整参考布局，不能继续安装 `1.0.2a1`。
- 打包测试固定最低 SDK 版本，防止后续发布再次生成能安装但无法运行 Hybrid 的 wheel。

## 验证

- Python 3.9 全量后端测试：passed。
- Python 3.11 打包专项：10 passed。
- Python wheel：build passed。
- wheel metadata：`Requires-Dist: cascaqit<1.0.8,>=1.0.7a0`。
- Ruff：passed。

## 边界

仓库中的 Windows 离线包仍是旧构建产物，包含 CASCAQit `1.0.2a1`。发布或交付下一份离线包前必须用当前 SDK 源码重新打包，并在 Windows x64、CPython 3.11 环境重新执行安装、启动和真实场景 smoke test。
