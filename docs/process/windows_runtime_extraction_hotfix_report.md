# Windows runtime 解压热修复报告

## 问题

Windows 10/11 x64 实机连续暴露两个 runtime 解压故障：

1. Windows PowerShell 5.1 的 `Expand-Archive` 处理显式目录项时重复清理 `python\DLLs\`，抛出 `ItemNotFoundException`。
2. 改用 .NET `ZipFile` 后，包内 `runtime\python-extract-<guid>` 临时层把 pip 深层文件推到默认 `MAX_PATH` 之外，抛出 `DirectoryNotFoundException`。

第二个异常中的最终 runtime 路径约 214 个字符；临时目录增加约 55 个字符后超过 260。故障发生在 Python 启动之前，与 wheel 依赖、金融场景或中文脚本编码无关。

## 修复

`install.ps1` 保留 .NET `System.IO.Compression.ZipFile`，但直接把带顶层 `python` 的归档解压到 `runtime`：

- 不使用 `Expand-Archive`；
- 不创建包内 GUID 临时目录；
- 不执行目录移动；
- 解压前删除失效的 `runtime\python`；
- 解压后校验 CPython 3.11.9 x64；
- 失败时清理不完整的 Python 目录。

回归测试检查安装脚本不再出现旧归档 API、`python-extract-` 或 `Move-Item`，并确认直接目标为 `$Runtime`。

## 修复包

修复包已覆盖 `v0.1.1` 的同名 Windows Release 资产：

<https://github.com/CASColdAtom/cascaqit-finance-demo/releases/download/v0.1.1/cascaqit-finance-demo-windows-x64-py311.zip>

| 项目 | 结果 |
|---|---|
| 大小 | `94,600,625` 字节 |
| SHA256 | `4deb45cdd37b07034512aec89d5f7402152ebbdff8382fecff738bbbd593198a` |
| manifest | 41 项全部通过 |
| wheel 闭包 | 29 项全部满足 Windows CPython 3.11 x64 条件 |
| Python 测试 | `134 passed` |
| React 测试 | `20 passed` |
| 其他检查 | Ruff、TypeScript、生产构建和 ZIP 结构通过 |

GitHub 返回的资产大小和 SHA256 与本地文件一致。

## 实机重试

必须删除旧 ZIP 和旧解压目录后重新下载。建议解压到 `D:\CQFinance` 这类短路径，再依次运行 `VERIFY.bat`、`INSTALL.bat` 和 `RUN.bat`。当前修复已经通过构建侧门禁，但只有实机完成安装 smoke、服务启动和三个代表场景运行后，Windows 验收才算结束。
