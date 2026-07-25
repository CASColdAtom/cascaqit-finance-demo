# Windows 离线包构建与发布报告

## 结果

当前源码已生成 Windows 10/11 x64、CPython 3.11 离线包：

```text
offline/cascaqit-finance-demo-windows-x64-py311.zip
```

ZIP 已作为 `v0.1.1` 的 Windows 离线资产发布：

<https://github.com/CASColdAtom/cascaqit-finance-demo/releases/download/v0.1.1/cascaqit-finance-demo-windows-x64-py311.zip>

`offline/` 仍不进入 Git。发布资产包含可重定位 Python runtime、全部 Windows wheel 和安装脚本；目标机器不需要联网、管理员权限、系统 Python 或 Node.js。构建使用 Finance Demo `v0.1.1` 对应运行代码和 CASCAQit 提交 `44fad22`。

## 制品内容

| 项目 | 当前值 |
|---|---|
| 目标环境 | Windows 10/11 x64 |
| Python | 可重定位 CPython 3.11.9 |
| CASCAQit | `1.0.7a0` |
| Finance Demo | `0.1.1` |
| wheel 数 | 29 |
| manifest 文件数 | 41 |
| ZIP 大小 | `94,600,307` 字节 |
| ZIP SHA256 | `c458c26d4fa48e3c8aee6e6b2f25d86e970613401078cf620e0c5d6adf54dc12` |

wheelhouse 包含 Windows x64 NumPy、SciPy、Bokeh、FastAPI、Uvicorn、Colorama 及完整传递依赖。安装时使用 `--no-index` 和本地 wheelhouse，不访问 Python 包索引。

Finance Demo wheel 已确认包含：

- `scipy>=1.13,<2` 运行时依赖；
- React 静态入口；
- `Views-JNJ1LIwg.js` Problem 映射组件；
- `index--wVDl_FB.js` 应用入口。

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
- ZIP 压缩结构检查通过，GitHub 服务端摘要与本地 SHA256 一致。
- Python 全量测试 134 项通过，React 20 项测试通过。
- Ruff、TypeScript、生产构建和 npm 依赖审计通过。

## 尚未完成

macOS 不能证明 BAT、PowerShell、Windows DLL 加载和本地浏览器启动正常。以下步骤必须在干净 Windows 10/11 x64 实机完成：

1. 完整解压 ZIP，双击 `VERIFY.bat`。
2. 双击 `INSTALL.bat`，确认 runtime 和隔离环境创建成功。
3. 检查安装 smoke test 完成一次真实 settlement 量子执行。
4. 双击 `RUN.bat`，确认服务和浏览器正常启动。
5. 运行投资组合连续优化、Hybrid 交易结算和 Analog 衍生品情景，检查线路、原子、波形、counts 和 Problem 映射。
6. 移动整个目录后再次运行，验证可重定位性和重复安装。

CASCAQit 本地 `main` 仍领先 GitHub 远端，公开 Python 索引也没有对应分发包。本离线包已经包含本次验证使用的精确 wheel，可以独立安装，但不能替代 CASCAQit 源码和公开 Python 分发的后续发布。
