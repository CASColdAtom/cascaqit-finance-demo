# 中科酷原行业量子实验台 Windows 离线包

## 适用环境

- Windows 10 或 Windows 11，x64 处理器
- 不需要联网
- 不需要管理员权限
- 包内附带可重定位的 CPython 3.11.9 x64 runtime，不使用系统 Python

不支持 Windows ARM64、32 位 Windows、Windows 7，也不要使用 Microsoft Store 的受限 Python 环境代替包内解释器。

## 安装和启动

1. 将整个目录复制到本机磁盘并完整解压，不要直接在压缩包内运行。
2. 双击 `INSTALL.bat`。安装会解压包内 Python 并创建本目录下的 `runtime`，不会写注册表、修改系统环境变量或安装系统组件。
3. 双击 `RUN.bat`。服务就绪后会自动打开默认浏览器。
4. 关闭运行窗口或按 `Ctrl+C` 停止服务。

默认地址为 `http://127.0.0.1:8000`。实验报告保存在 `artifacts/reports`。

请只通过三个 `.bat` 入口操作，不要直接双击或右键运行 `.ps1`。BAT 会为当前 PowerShell 进程传入 `ExecutionPolicy Bypass`，不会修改系统、当前用户或企业执行策略。

## 文件完整性

拷贝到新机器后可以先双击 `VERIFY.bat`。它会根据 `manifest-sha256.txt` 校验可重定位 Python runtime、全部 wheel 和启动脚本。任何文件缺失或损坏都会停止安装。

## 常见问题

- 端口被占用：关闭占用 8000 端口的程序，或在 PowerShell 中先执行 `$env:CASCAQIT_INDUSTRY_PORT="8010"`，再运行 `run.ps1`。旧的 `CASCAQIT_FINANCE_PORT` 仍可兼容使用。
- 安全软件扫描较慢：首次运行会解压 Python、NumPy 和 SciPy，并执行一次 16 shots 的 settlement 自检，等待完成即可。
- 页面没有自动打开：手动访问运行窗口显示的本地地址。
- PowerShell 提示禁止运行脚本：确认运行的是 `INSTALL.bat`、`RUN.bat` 或 `VERIFY.bat`，而不是直接运行 `.ps1`。如果 BAT 仍被企业组策略拦截，请联系管理员使用签名脚本版本；不要自行修改全局执行策略。
- 重复安装：再次运行 `INSTALL.bat` 会复用有效环境，只补齐缺失或版本不符的包。
- 强制重装：在 PowerShell 中执行 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -ForceReinstall`。
- 移动目录：可以移动整个解压目录；再次运行 `RUN.bat` 时会自动重建因旧绝对路径失效的隔离环境。

## 离线边界

安装和运行过程中不会访问 Python 包索引。服务默认只监听本机回环地址，运行时生成的数据也只写入当前离线包目录。
