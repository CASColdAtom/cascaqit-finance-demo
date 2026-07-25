# Windows 离线包重建报告

## 结果

当前源码已生成 Windows 10/11 x64、CPython 3.11 离线包：

```text
offline/cascaqit-finance-demo-windows-x64-py311.zip
```

`offline/` 不进入 Git。该文件是本机交付制品，不是 GitHub Release。构建使用本地 CASCAQit 源码；SDK 尚未形成公开 Python 分发包，因此当前结果不能替代公开安装链。

该 ZIP 生成于 Problem 映射入口禁缓存修改之前。包内已经包含旧响应字段兜底，但不包含本次新增的 `Cache-Control: no-store` 中间件；下次 Windows 交付前需要重新构建并重做实机验收。

## 制品内容

| 项目 | 当前值 |
|---|---|
| 目标环境 | Windows 10/11 x64 |
| Python | 可重定位 CPython 3.11.9 |
| CASCAQit | `1.0.7a0` |
| Finance Demo | `0.1.1` |
| wheel 数 | 29 |
| manifest 文件数 | 41 |
| ZIP 大小 | 约 90 MB |
| ZIP SHA256 | `e4b73dbb78565c57eea8a911445fa30f18514749c6f98ac08576539d13ef1514` |

wheelhouse 包含 Windows x64 NumPy、SciPy、Bokeh、FastAPI、Uvicorn、Colorama 及完整传递依赖。安装时使用 `--no-index` 和本地 wheelhouse，不访问 Python 包索引。

Finance Demo wheel 已确认包含：

- `scipy>=1.13,<2` 运行时依赖；
- React 静态入口；
- `Views-C4OLICMT.js` Problem 映射组件；
- `index-kgOKk-O-.js` 应用入口。

## 构建修复

首次重建在 Python 3.9 失败。脚本直接调用 `tarfile.extractall(filter="data")`，但 Python 3.9 没有 `filter` 参数。

构建器现在先在所有 Python 版本检查归档成员，只允许目标目录内的普通文件和目录，拒绝绝对路径、`..`、符号链接、硬链接和设备文件。较新 Python 在预校验后继续使用标准 `data_filter`，Python 3.9 使用兼容解包。单元测试覆盖正常 runtime 文件、绝对路径和目录穿越。

## 已完成检查

- Windows 条件依赖按目标 marker 审计，`colorama` 已进入闭包。
- 29 个 wheel 的 `Requires-Dist` 均能由 wheelhouse 满足。
- Python runtime 上游归档 SHA256 与脚本固定值一致。
- runtime ZIP 包含 `python/python.exe` 和 `python/python311.dll`。
- 41 条 manifest 逐文件重新计算，0 条失败。
- BAT 为 ASCII + CRLF，并使用进程级 `ExecutionPolicy Bypass` 调用 PowerShell。
- PowerShell 模板为 UTF-8 BOM + CRLF。
- Demo wheel 不包含 source map，静态资源与当前生产构建一致。
- Python 全量测试 123 项通过，Ruff 检查通过。

## 尚未完成

macOS 不能证明 BAT、PowerShell、Windows DLL 加载和本地浏览器启动正常。以下步骤必须在干净 Windows 10/11 x64 实机完成：

1. 完整解压 ZIP，双击 `VERIFY.bat`。
2. 双击 `INSTALL.bat`，确认 runtime 和隔离环境创建成功。
3. 检查安装 smoke test 完成一次真实 settlement 量子执行。
4. 双击 `RUN.bat`，确认服务和浏览器正常启动。
5. 运行投资组合连续优化、Hybrid 交易结算和 Analog 衍生品情景，检查线路、原子、波形、counts 和 Problem 映射。
6. 移动整个目录后再次运行，验证可重定位性和重复安装。

CASCAQit 本地 `main` 还领先 GitHub 远端，公开 Python 索引也没有对应分发包。推送 SDK、建立发行制品和调整 Demo 的公开安装说明属于发布动作，不能由本次本机构建结果代替。
