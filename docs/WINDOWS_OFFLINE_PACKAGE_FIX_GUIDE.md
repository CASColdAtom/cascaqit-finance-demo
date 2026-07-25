# CASCAQit Finance Demo Windows 离线包问题与修复指南

> 本文是旧离线包的故障复盘，文中的 `1.0.2a0`、`1.0.2a1` 和制品哈希只对应当时的测试包，不是当前安装要求。当前源码离线包已经重建，结果见[Windows 离线包重建报告](process/windows_offline_bundle_rebuild_report.md)；Windows 实机验收仍未完成。

## 1. 文档目的

本文整理本次在 Windows x64、CPython 3.11 环境中，对 `cascaqit-finance-demo` 离线安装包进行安装、启动和场景运行验证时发现的全部问题。

目标是指导源码环境完成以下工作：

- 修复 Windows 平台兼容问题；
- 修复 Python runtime 的打包和安装策略；
- 改善安装错误诊断；
- 重新构建 CASCAQit 和 Finance Demo wheel；
- 重新生成完整离线包；
- 在干净 Windows 环境完成离线验收。

本次验证的包信息：

| 项目 | 版本或环境 |
|---|---|
| 操作系统 | Windows 10/11 x64 |
| Python | CPython 3.11.9 x64 |
| CASCAQit | `1.0.2a0` |
| Finance Demo | `0.1.0` |
| 安装方式 | 本地 wheelhouse，禁止联网 |
| 前端 | Finance Demo wheel 内置静态资源 |

---

## 2. 问题总览

| 编号 | 问题 | 严重程度 | 主要修复位置 |
|---|---|---:|---|
| P1 | CPython 安装器在包移动或重复解压后返回成功但未安装解释器 | 阻断 | 离线包构建与 `install.ps1` |
| P2 | Python 安装过程缺少日志和残留注册诊断 | 高 | `install.ps1` |
| P3 | 默认强制重装全部 wheel，重复安装慢且覆盖补丁 | 中 | `install.ps1` |
| P4 | 安装自检未覆盖真实模拟执行 | 高 | 安装 smoke test / CI |
| P5 | Windows 调用 POSIX 专用 `os.sysconf` 导致场景 500 | 阻断 | `cascaqit/simulators/planning.py` |
| P6 | 缺少 Windows 平台单元和端到端测试 | 高 | CASCAQit / Demo 测试与 CI |
| P7 | README 在 Windows PowerShell 5.1 中可能显示乱码 | 中 | 文本编码与构建流程 |
| P8 | Chrome DevTools 探测路径返回 404 | 无需修复 | 可选日志过滤 |
| P9 | 生产包包含 JavaScript source map | 低 | 前端构建配置 |
| P10 | 本地 site-packages 补丁会被重新安装覆盖 | 高 | 版本和 wheel 发布流程 |
| P11 | 后端执行异常直接成为裸 500 | 中 | API 异常映射 |
| P12 | UTF-8、LF-only BAT 被 cmd.exe 错误解析 | 阻断 | INSTALL.bat / RUN.bat / VERIFY.bat |
| P13 | 直接运行 PS1 被默认 PowerShell 执行策略阻止 | 阻断 | BAT 入口与 Windows 使用说明 |
| P14 | runtime 解压受 PowerShell 归档缺陷和默认长路径限制阻断 | 阻断 | `install.ps1` |

---

## 3. P1：CPython 安装器无法支持离线包随意移动

### 3.1 问题现象

运行 `install.ps1` 时：

```text
离线包完整性检查通过，共校验 40 个文件。
未发现 Python 3.11 x64，正在安装到离线包 runtime 目录……
Python 安装完成后仍无法验证解释器。
```

CPython 安装器返回码为 `0`，但目标目录 `runtime\python311` 为空，`python.exe` 不存在。

增加 `/log` 后，安装日志显示：

```text
ActionLikeInstallation = Modify
WixBundleInstalled = 1
execute: None
TargetDir = <当前新包>\runtime\python311
```

注册表中的 Python 路径仍指向已经被删除的旧离线包：

```text
HKCU\Software\Python\PythonCore\3.11\InstallPath
```

### 3.2 根因

`python-3.11.9-amd64.exe` 是带 Windows Installer/Burn 产品注册的系统安装器，不是可重定位 runtime。

当同一台机器曾从旧离线包目录安装过相同版本 Python，随后旧目录被删除时：

1. Python 文件已经不存在；
2. CPython 产品注册和组件状态仍然存在；
3. 新离线包运行同版本安装器时被识别为 `Modify`；
4. 安装器不会根据新的 `TargetDir` 迁移已有产品；
5. 所有组件计划为 `execute: None`；
6. 安装器返回成功，但新目录没有解释器。

因此，不能仅凭安装器退出码 `0` 判断 Python 安装成功。

### 3.3 本次临时恢复方法

本次测试机上的旧解释器文件已经完全不存在，只剩损坏的安装注册。恢复步骤为：

1. 使用同版本 CPython 安装器执行 `/repair`，恢复旧路径组件；
2. 使用同版本安装器执行 `/uninstall`，正常清理产品注册；
3. 再次运行当前离线包的 `install.ps1`；
4. Python 成功安装至当前 `runtime\python311`；
5. 创建 `runtime\venv` 并完成离线 wheel 安装。

不要把自动 repair/uninstall 作为正式安装包的默认逻辑。用户可能有其他程序依赖已安装的 Python 3.11，自动卸载会产生额外影响。

### 3.4 推荐正式方案

首选方案是停止将官方 CPython EXE 作为“随离线包移动的 Python runtime”。

推荐使用可重定位 Python 发行版，例如 `python-build-standalone`：

1. 在打包环境准备 Windows x64 Python 3.11 runtime；
2. 将 runtime 作为普通文件打入离线包；
3. 不注册 Windows Installer 产品；
4. 不写注册表；
5. 不修改系统 PATH；
6. 目标机器直接使用该 runtime 创建 venv；
7. 再从 wheelhouse 安装固定依赖。

### 3.5 使用官方 CPython EXE 时的次优方案

如果必须继续使用官方安装器，不要将 Python 安装在会随解压位置变化的 `$Root\runtime\python311`。

改为稳定的用户级目录：

```powershell
$PythonHome = Join-Path $env:LOCALAPPDATA `
    "CASCAQit\runtimes\python-3.11.9-x64"
```

不同位置解压的 Finance Demo 包都复用该稳定 runtime。每次使用前必须验证真实解释器：

```powershell
function Test-Python311X64 {
    param([Parameter(Mandatory = $true)][string]$Executable)

    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        return $false
    }

    & $Executable -c `
        "import struct,sys; assert sys.version_info[:2] == (3,11); assert struct.calcsize('P') * 8 == 64" `
        2>$null

    return $LASTEXITCODE -eq 0
}
```

### 3.6 必须增加的失败诊断

安装器返回成功后仍应执行解释器验证：

```powershell
if (-not (Test-Python311X64 -Executable $BundledPython)) {
    throw @"
Python 安装器返回成功，但目标解释器不存在或不可运行。
可能存在同版本 Python 的残留安装注册，或者安装器进入了 Modify 模式。
预期解释器：$BundledPython
安装日志：$PythonInstallLog
"@
}
```

错误信息应包含：

- 安装器退出码；
- 预期 `python.exe` 路径；
- 安装日志路径；
- 已检测到的 Python 注册路径；
- 注册路径中的解释器是否真实存在；
- 建议用户执行修复、卸载或使用可重定位 runtime。

---

## 4. P2：Python 安装过程缺少诊断日志

### 4.1 问题

原 `install.ps1` 没有为 CPython 安装器传入 `/log`。当安装器返回 `0` 而目标目录为空时，无法直接判断它执行的是首次安装、Modify、Repair 还是无操作。

### 4.2 修复方法

为每次 Python 安装生成明确日志：

```powershell
$PythonInstallLog = Join-Path $Runtime "python-install.log"

$Arguments = @(
    "/quiet"
    "InstallAllUsers=0"
    "TargetDir=`"$PythonHome`""
    "PrependPath=0"
    "Include_launcher=0"
    "Include_pip=1"
    "Include_test=0"
    "Include_tcltk=0"
    "Include_doc=0"
    "Shortcuts=0"
    "AssociateFiles=0"
    "/log"
    "`"$PythonInstallLog`""
)

$Process = Start-Process `
    -FilePath $Installer `
    -ArgumentList $Arguments `
    -Wait `
    -PassThru
```

Windows PowerShell 的 `Start-Process -ArgumentList` 会重新拼接命令行。目标路径包含空格时，必须在测试中检查安装日志中的最终 `TargetDir`，确认引号未丢失。

---

## 5. P3：默认强制重装所有 wheel

### 5.1 问题

原安装命令始终使用：

```text
--upgrade
--force-reinstall
```

这会在每次运行 `install.ps1` 时卸载并重装 NumPy、SciPy、Pydantic、CASCAQit、Finance Demo 等全部包。

影响包括：

- 重复安装明显变慢；
- 安装中断时可能留下部分安装状态；
- 本地诊断补丁会被覆盖；
- 已经验证成功的环境仍被无条件修改。

### 5.2 修复方法

首次安装使用普通固定版本安装：

```powershell
& $VenvPython -m pip install `
    --disable-pip-version-check `
    --no-index `
    --find-links $Wheelhouse `
    --only-binary=:all: `
    "cascaqit-finance-demo==0.1.0"
```

只在明确要求修复或重装时增加：

```text
--upgrade --force-reinstall
```

建议增加脚本参数：

```powershell
[CmdletBinding()]
param(
    [switch]$ForceReinstall
)
```

根据 `$ForceReinstall` 组装 pip 参数。也可以检查 `runtime\install-ok.txt`、包版本和 smoke test，全部正常时跳过重装。

---

## 6. P4：安装自检没有覆盖真实模拟执行

### 6.1 问题

原安装 smoke check 只验证：

- CASCAQit 和 Finance Demo 版本可读取；
- Finance Demo 前端 `index.html` 存在。

这些检查均通过，但 settlement 场景执行仍然返回 500，因为没有触发模拟规划器中的 Windows 专用路径。

### 6.2 修复方法

安装完成后至少执行：

1. `HostResourceSnapshot.detect()`；
2. 一个低成本 settlement 场景；
3. 响应结构断言；
4. `pip check`；
5. 前端静态文件检查。

推荐将 smoke test 放入包内的正式模块，例如：

```python
import asyncio

from cascaqit.simulators.planning import HostResourceSnapshot
from cascaqit_finance_demo.api.app import RunRequest, run_scenario


def main() -> None:
    host = HostResourceSnapshot.detect()
    assert host.total_memory_bytes > 0
    assert host.cpu_count > 0

    result = asyncio.run(
        run_scenario(
            "settlement",
            RunRequest(shots=16, parameter_budget=1),
        )
    )
    assert {"scenario", "preset", "run"} <= result.keys()
    print("Runtime smoke test passed")


if __name__ == "__main__":
    main()
```

安装脚本调用：

```powershell
& $VenvPython -m cascaqit_finance_demo.smoke_test
if ($LASTEXITCODE -ne 0) {
    throw "安装后的场景执行自检失败。"
}
```

---

## 7. P5：Windows 调用 POSIX 专用 `os.sysconf`

### 7.1 问题现象

启动应用后，前端加载正常，但运行 settlement 场景返回：

```text
POST /api/scenarios/settlement/run HTTP/1.1
500 Internal Server Error
```

核心异常：

```text
AttributeError: module 'os' has no attribute 'sysconf'
```

调用路径：

```text
run_scenario
  -> ScenarioExecutor.run
  -> compiled.optimize
  -> LocalBackend.run
  -> SimulationPlanner.plan
  -> HostResourceSnapshot.detect
  -> _physical_memory_bytes
  -> os.sysconf
```

### 7.2 故障代码

文件：`cascaqit/simulators/planning.py`

```python
def _physical_memory_bytes() -> int:
    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        pages = int(os.sysconf("SC_PHYS_PAGES"))
        total = page_size * pages
    except (OSError, TypeError, ValueError):
        total = 8 * 1024**3
    return max(total, 1)
```

### 7.3 根因

`os.sysconf()` 是 POSIX 平台能力。Windows 的 `os` 模块没有 `sysconf` 属性，因此访问时抛出 `AttributeError`。

原函数已经设计了 8 GiB 回退值，但异常列表漏掉了 Windows 上实际出现的 `AttributeError`。

### 7.4 最低风险修复

```python
def _physical_memory_bytes() -> int:
    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        pages = int(os.sysconf("SC_PHYS_PAGES"))
        total = page_size * pages
    except (AttributeError, OSError, TypeError, ValueError):
        total = 8 * 1024**3
    return max(total, 1)
```

这个修复可以阻止 Windows 500，并且与原有 fallback 设计一致。但 Windows 永远得到固定 8 GiB，可能影响内存预算和模拟方法选择。

### 7.5 推荐正式修复

Windows 使用 `GlobalMemoryStatusEx` 获取真实物理内存，POSIX 继续使用 `os.sysconf()`：

```python
import ctypes
import os
import sys


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _physical_memory_bytes() -> int:
    try:
        if sys.platform == "win32":
            status = _MemoryStatusEx()
            status.dwLength = ctypes.sizeof(status)
            succeeded = ctypes.windll.kernel32.GlobalMemoryStatusEx(
                ctypes.byref(status)
            )
            if not succeeded:
                raise OSError("GlobalMemoryStatusEx failed")
            total = int(status.ullTotalPhys)
        else:
            page_size = int(os.sysconf("SC_PAGE_SIZE"))
            pages = int(os.sysconf("SC_PHYS_PAGES"))
            total = page_size * pages
    except (AttributeError, OSError, TypeError, ValueError):
        total = 8 * 1024**3

    return max(total, 1)
```

如果规划器同时需要 total 和 available memory，建议封装为一次平台调用并同时返回两者，避免重复检测。

### 7.6 本次本地验证结果

加入 `AttributeError` fallback 后：

- `HostResourceSnapshot.detect()` 成功；
- 检测结果使用 8 GiB fallback；
- CPU 数量检测成功；
- settlement 最小场景执行成功；
- 返回 `scenario`、`preset`、`run`；
- 16 shots 完整运行通过。

修改已加载模块后，必须重启 Uvicorn 服务。旧进程不会自动加载修改后的 site-packages 文件。

---

## 8. P6：缺少 Windows 平台测试

### 8.1 最低 fallback 测试

```python
def test_physical_memory_falls_back_without_sysconf(monkeypatch):
    monkeypatch.delattr(os, "sysconf", raising=False)

    assert _physical_memory_bytes() == 8 * 1024**3
```

### 8.2 Windows 资源检测测试

```python
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_detect_host_resources_on_windows():
    snapshot = HostResourceSnapshot.detect()

    assert snapshot.total_memory_bytes > 0
    assert snapshot.available_memory_bytes > 0
    assert snapshot.cpu_count > 0
```

### 8.3 Finance Demo 端到端测试

```python
import asyncio


def test_settlement_runs_on_windows():
    result = asyncio.run(
        run_scenario(
            "settlement",
            RunRequest(shots=16, parameter_budget=1),
        )
    )

    assert {"scenario", "preset", "run"} <= result.keys()
```

### 8.4 CI 建议

至少增加以下构建矩阵：

- Windows Server 2022 + CPython 3.11 x64；
- Ubuntu + CPython 3.11；
- 从构建产物 wheel 安装后测试；
- 完全离线 `--no-index --find-links wheelhouse` 安装测试；
- 无预装 Python 的 Windows VM 安装测试；
- 同一机器解压第二份包和移动包目录后的测试。

---

## 9. P7：README 和 Windows 文本编码

### 9.1 问题现象

在 Windows PowerShell 中读取 README 时出现类似：

```text
# 涓閰峰師...
```

通常是 UTF-8 无 BOM 文件被 Windows PowerShell 5.1 按本地 ANSI 编码读取造成的。

### 9.2 修复建议

- 面向 Windows PowerShell 5.1 的 `.ps1` 和用户说明可保存为 UTF-8 BOM；
- PowerShell 读取时显式使用 `-Encoding UTF8`；
- Python 3 源码保持标准 UTF-8，一般不需要 BOM；
- 构建阶段增加编码验证。

重点检查：

- `README.md`；
- `install.ps1`；
- `verify.ps1`；
- `run.ps1`；
- `.bat` 文件中的中文；
- Python 中文 docstring 和错误信息。

---

## 10. P8：Chrome DevTools 探测请求 404

日志：

```text
GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1
404 Not Found
```

这是 Chrome DevTools 自动探测，不是应用故障，不影响页面和 API。

处理建议：

- 保持 404 即可；
- 不需要增加业务路由；
- 不要将其纳入健康检查失败统计；
- 如需降低日志噪声，可过滤这一固定路径。

---

## 11. P9：生产包包含 JavaScript source map

日志显示多个 `.js.map` 返回 200：

```text
GET /assets/index-....js.map HTTP/1.1 200 OK
GET /assets/react-....js.map HTTP/1.1 200 OK
GET /assets/echarts-....js.map HTTP/1.1 200 OK
```

这不是运行错误，但会：

- 增加离线包体积；
- 允许浏览器查看更接近原始结构的前端源码。

如果生产交付不需要浏览器源码调试，关闭 Vite source map：

```typescript
export default defineConfig({
  build: {
    sourcemap: false,
  },
})
```

可以分别生成：

- Release 包：不含 source map；
- Debug 包：包含 source map。

修改后需要重新构建前端、Finance Demo wheel 和 SHA-256 manifest。

---

## 12. P10：本地补丁会被重新安装覆盖

本次临时修复发生在：

```text
runtime\venv\Lib\site-packages\cascaqit\simulators\planning.py
```

再次运行带 `--force-reinstall` 的 `install.ps1` 后，该文件会被 wheel 中的原始版本覆盖。

正式修复必须在 CASCAQit 源码仓库完成，然后重新构建 wheel。

不要继续使用相同的 `1.0.2a0` 版本号发布内容不同的 wheel。建议至少提升为：

```text
cascaqit==1.0.2a1
```

否则 pip 缓存、日志、manifest 和问题报告无法区分修复前后的构建产物。

---

## 13. P11：后端执行异常直接成为裸 500

当前 `run_scenario()` 主要捕获 `ValueError`。平台兼容错误、资源规划错误或 backend 异常会直接产生 ASGI traceback 和 500。

建议对已知领域异常做稳定映射，例如：

```python
except CapabilityError as exc:
    raise HTTPException(
        status_code=422,
        detail={
            "code": exc.code,
            "message": str(exc),
            "stage": exc.stage,
        },
    ) from exc
```

未知异常仍应记录完整 traceback，但前端响应使用稳定结构，并附带错误 ID：

```json
{
  "detail": {
    "code": "internal_execution_error",
    "message": "本地模拟执行失败",
    "error_id": "<generated-id>"
  }
}
```

异常映射不能替代平台兼容修复，但可以改善现场诊断，并避免前端只看到无上下文的 Request Failed。

---

## 14. 推荐的重新打包流程

### 14.1 修复源码

1. 修复 `cascaqit/simulators/planning.py` 的 Windows 内存检测；
2. 优先实现 `GlobalMemoryStatusEx`，至少捕获 `AttributeError`；
3. 增加 Windows 单元测试；
4. 增加 settlement 最小端到端测试；
5. 改善 API 已知异常映射；
6. 提升 CASCAQit 版本号。

### 14.2 构建 Python wheel

1. 清理旧的 `build/`、`dist/` 和 wheel 缓存；
2. 构建新的 CASCAQit wheel；
3. 在干净 venv 安装该 wheel；
4. 执行完整测试；
5. 更新 Finance Demo 对 CASCAQit 的精确依赖版本；
6. 构建新的 Finance Demo wheel；
7. 检查 wheel 内含前端 `index.html` 和静态资源。

### 14.3 重建 wheelhouse

1. 使用 Windows x64、CPython 3.11 目标解析依赖；
2. 只保留兼容 wheel；
3. 禁止混入源码包；
4. 执行：

```powershell
python -m pip install `
    --no-index `
    --find-links .\wheelhouse `
    --only-binary=:all: `
    "cascaqit-finance-demo==<new-version>"
```

5. 执行 `pip check`；
6. 保存最终锁定版本清单。

### 14.4 重建 Windows 离线包

1. 采用可重定位 Python runtime，或使用稳定 `%LOCALAPPDATA%` 安装路径；
2. 更新 `install.ps1` 的日志与验证逻辑；
3. 默认不强制重装全部 wheel；
4. 增加真实场景 smoke test；
5. 统一文本编码；
6. 决定是否排除 source map；
7. 更新以下文件：
   - `requirements.txt`；
   - `THIRD_PARTY_PACKAGES.txt`；
   - `bundle-info.json`；
   - `manifest-sha256.txt`；
   - `README.md`。
8. 从最终输出目录重新计算所有 SHA-256；
9. 不要复用旧 manifest。

---

## 15. 最终验收清单

### 15.1 干净环境准备

- [ ] 使用干净 Windows 10/11 x64 VM；
- [ ] VM 无预装 Python，或明确记录已有 Python 状态；
- [ ] 断开外网或通过防火墙确认安装期间无网络访问；
- [ ] 使用普通用户权限，不以管理员身份运行；
- [ ] 将离线包完整解压到本地磁盘。

### 15.2 完整性和安装

- [ ] `verify.ps1` 校验全部文件成功；
- [ ] `install.ps1` 成功退出；
- [ ] Python 为 CPython 3.11 x64；
- [ ] `runtime\venv\Scripts\python.exe` 存在且可运行；
- [ ] `pip check` 输出 `No broken requirements found`；
- [ ] CASCAQit 为修复后的新版本；
- [ ] Finance Demo 为重新打包版本；
- [ ] `runtime\install-ok.txt` 已生成；
- [ ] 安装日志中没有意外进入 `Modify/execute: None`；
- [ ] 安装期间未访问 Python 包索引。

### 15.3 启动和 API

- [ ] `run.ps1` 或 `RUN.bat` 成功启动；
- [ ] `/api/health` 返回 200；
- [ ] `/api/scenarios` 返回 200；
- [ ] 首页加载成功；
- [ ] CSS、JS、图片均加载成功；
- [ ] Chrome `/.well-known/...` 404 不计为失败；
- [ ] 服务日志中没有导入错误。

### 15.4 场景执行

- [ ] settlement analyze 返回 200；
- [ ] settlement run 返回 200；
- [ ] settlement 最小 16 shots 执行完成；
- [ ] 七个场景均至少完成一次最小运行；
- [ ] 不再出现 `os.sysconf` 异常；
- [ ] 内存检测结果大于 0；
- [ ] CPU 数量检测结果大于 0；
- [ ] 生成的业务、映射、量子和审计视图可正常切换；
- [ ] 报告可以写入 `artifacts\reports`。

### 15.5 重复安装和目录移动

- [ ] 再次运行 `install.ps1` 不会破坏已有环境；
- [ ] 默认重复安装不会无条件重装全部 wheel；
- [ ] 将整个离线包移动到另一个目录后仍可运行；
- [ ] 同一机器解压第二份包不会出现 Python 安装器空操作；
- [ ] 删除第一份解压目录后，第二份包仍可安装或运行；
- [ ] Python runtime 策略不依赖已经失效的旧包路径。

### 15.6 发布物检查

- [ ] wheel 文件名和包内 metadata 版本一致；
- [ ] 不同内容没有复用相同版本号；
- [ ] `bundle-info.json` 版本和 wheel 一致；
- [ ] `requirements.txt` 和实际 wheelhouse 一致；
- [ ] `manifest-sha256.txt` 由最终发布目录重新生成；
- [ ] README 在 Windows PowerShell 和常用编辑器中可正常显示中文；
- [ ] Release 包是否包含 source map 已明确决定并验证；
- [ ] 压缩、复制、重新解压后再次通过 `verify.ps1`。

---

## 16. 本次已验证结果

在当前测试环境完成临时恢复和 Windows fallback 补丁后：

```text
离线包完整性检查通过，共校验 40 个文件。
No broken requirements found.
CASCAQit 1.0.2a0
Finance Demo 0.1.0
离线安装完成。
```

前端静态资源检查：

```text
runtime\venv\Lib\site-packages\cascaqit_finance_demo\static\index.html = True
```

settlement 最小执行结果：

```text
result keys = ['preset', 'run', 'scenario']
shots = 16
```

这些结果证明：

1. wheelhouse 本身能够在 CPython 3.11 x64 上完成离线安装；
2. Python 安装失败来自 CPython 产品注册和可移动目录设计冲突；
3. settlement 500 来自 CASCAQit 的 Windows 平台兼容缺陷；
4. 捕获 `AttributeError` 后，当前测试场景可以完整执行；
5. 正式发布仍必须重新构建 CASCAQit wheel，不能依赖 site-packages 临时修改。


---

## 附录 A：P12 - UTF-8、LF-only BAT 被 cmd.exe 错误解析

### 问题现象

执行 `INSTALL.bat` 时出现：

```text
'汦xecutionPolicy' 不是内部或外部命令，也不是可运行的程序或批处理文件。
'锛岃淇濈暀绐楀彛涓殑閿欒淇℃伅銆?' 不是内部或外部命令。
'屽彲浠ュ弻鍑?RUN.bat' 不是内部或外部命令。
```

### 根因

三个入口 BAT 同时具有以下特征：

- UTF-8 无 BOM；
- 文件中包含中文；
- 仅使用 LF (`0A`) 换行，而不是 Windows CRLF (`0D 0A`)；
- 通过 `chcp 65001` 切换到 UTF-8 代码页。

Windows `cmd.exe` 对 UTF-8 多字节文本和 LF-only 行尾的组合处理不可靠。解析中文注释或 `echo` 后可能错过行边界，并吞掉下一条命令的部分字节。因此 `ExecutionPolicy` 被截断或与乱码拼接，中文提示也被当作命令执行。

这不是 `ExecutionPolicy` 参数拼写错误，也不是 PowerShell 执行策略阻止安装。

### 推荐修复

BAT 仅作为最薄的启动包装器，并满足：

1. 仅包含 ASCII；
2. 使用 Windows CRLF 换行；
3. 不调用 `chcp 65001`；
4. 中文提示放在 `.ps1` 中；
5. 保留 PowerShell 的真实退出码。

推荐的 `INSTALL.bat`：

```bat
@echo off
setlocal
cd /d "%~dp0"

REM Keep this wrapper ASCII-only. User-facing messages belong in install.ps1.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Installation failed. Review the PowerShell error above.
  pause
  exit /b %EXIT_CODE%
)

echo.
echo Installation completed. Run RUN.bat to start the application.
pause
exit /b 0
```

`RUN.bat` 和 `VERIFY.bat` 应采用同样结构，只替换 PowerShell 文件名和 ASCII 提示。

### 构建阶段检查

所有 `.bat` 发布前必须验证：

- 不存在 `0x80` 以上的非 ASCII 字节；
- 所有换行均为 CRLF；
- 不存在孤立 LF；
- 使用新的 `cmd.exe` 进程实际执行 BAT，而不是只测试对应的 `.ps1`。

Git 仓库建议增加：

```gitattributes
*.bat text eol=crlf
*.cmd text eol=crlf
*.ps1 text eol=crlf
```

其中 `.bat` 仍必须保持 ASCII。`.ps1` 如果包含中文且需要兼容 Windows PowerShell 5.1，建议使用 UTF-8 BOM。

---

## 附录 B：P13 - PowerShell 默认执行策略阻止直接运行 PS1

### 问题现象

用户直接双击、右键运行或在 PowerShell 中执行 `install.ps1` 时，系统可能提示：

```text
无法加载文件 install.ps1，因为在此系统上禁止运行脚本。
```

### 根因

Windows PowerShell 的默认执行策略可能是 `Restricted`。该策略允许交互命令，但不允许直接执行 `.ps1` 文件。企业环境还可能通过 `MachinePolicy` 或 `UserPolicy` 强制 `AllSigned`，这种策略优先级高于普通进程参数。

### 正式处理方式

用户入口统一为：

- `INSTALL.bat`
- `RUN.bat`
- `VERIFY.bat`

BAT 使用以下方式启动 PowerShell：

```bat
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
```

`Bypass` 只作用于当前 PowerShell 进程。安装包不会执行 `Set-ExecutionPolicy`，不会修改系统或当前用户的永久策略。用户不要直接运行包内 `.ps1`。

如果企业组策略仍然阻止 BAT 启动的 PowerShell 脚本，不应通过额外命令绕过管理策略。正式交付需要由企业管理员放行，或改用组织信任证书签名的脚本版本。

### 构建门禁

构建器和单元测试现在强制检查：

- BAT 只能包含 ASCII；
- BAT 必须使用 CRLF，不能存在孤立 LF；
- BAT 不能调用 `chcp 65001`；
- BAT 必须包含 `-ExecutionPolicy Bypass` 和 `-File`；
- BAT 必须保留 PowerShell 的真实退出码；
- PS1 必须为 UTF-8 BOM 和 CRLF；
- 发现含中文或其他非 ASCII 字节的 BAT 时直接终止打包。

---

## 附录 C：本轮正式修复与交付结果

已完成以下修复：

1. 三个 BAT 改为 ASCII-only、CRLF，不再调用 `chcp 65001`。
2. BAT 使用进程级 `ExecutionPolicy Bypass` 调用 PS1，并保留真实退出码。
3. 构建器统一生成 ASCII/CRLF BAT 和 UTF-8 BOM/CRLF PS1、README。
4. Windows README 明确要求只使用 BAT 入口，并说明企业组策略边界。
5. 新增三项字节级与构建失败回归测试。

当时的交付物，现已过期：

```text
文件：offline/cascaqit-finance-demo-windows-x64-py311.zip
大小：94447985 bytes
SHA256：3267de35b74a6cb8de75af68fe5530bd94e4aca31edab5a67062aed6ef3476c5
CASCAQit：1.0.2a1
Finance Demo：0.1.1
```

本地验收结果：

- Ruff：通过；
- Finance Demo：78 项测试通过；
- 40 个交付文件 SHA256：全部通过；
- Windows 条件依赖闭包：通过；
- 外层 ZIP 解压检查：通过；
- BAT：ASCII、CRLF、无 `chcp`，检查通过；
- PS1：UTF-8 BOM、CRLF，检查通过。

当前构建机为 macOS，无法替代 Windows `cmd.exe` 和 PowerShell 5.1 实机执行。新包仍需在 Windows 10/11 x64 上从全新目录解压，并依次运行 `VERIFY.bat`、`INSTALL.bat`、`RUN.bat` 完成最终验收。

---

## 附录 D：P14 - runtime 解压与长路径失败

### 两次实机故障

第一版安装器使用 Windows PowerShell 5.1 的 `Expand-Archive`。runtime ZIP 含 302 个显式目录项，归档模块清理时重复删除已经不存在的 `python\DLLs\`，安装在解压阶段终止。

改用 .NET `ZipFile.ExtractToDirectory` 后，安装器仍在包内创建 `runtime\python-extract-<guid>` 临时目录。用户目录与该临时层叠加后，pip 的 `found_candidates.cpython-311.pyc` 路径超过 Windows 默认 260 字符限制，.NET 返回 `DirectoryNotFoundException`。

### 当前修复

runtime 归档本身只有一个顶层 `python` 目录。安装器现在：

1. 删除已失效或不完整的 `runtime\python`；
2. 使用 .NET `ZipFile` 直接解压到 `runtime`；
3. 立即执行 `runtime\python\python.exe`，校验 CPython 3.11.9 x64；
4. 解压或校验失败时删除不完整的 `runtime\python`；
5. 不再创建包内 GUID 临时目录，也不再移动解压后的目录。

在本次用户路径中，已知最深文件的最终路径约 214 个字符；旧临时目录会把它增加到约 269 个字符。直接解压去掉了这段额外路径。用户仍应把离线包解压到较短目录，例如 `D:\CQFinance`，避免更长的企业目录或重复嵌套目录再次触发系统长路径限制。

### 修复包

```text
文件：cascaqit-finance-demo-windows-x64-py311.zip
大小：94600625 bytes
SHA256：4deb45cdd37b07034512aec89d5f7402152ebbdff8382fecff738bbbd593198a
```

构建侧已经完成 41 项 manifest、ZIP 结构、29 个 Windows wheel 依赖闭包、PowerShell 编码、134 项 Python 测试、20 项 React 测试、Ruff 和 TypeScript 检查。最终 Windows 安装、启动和场景运行仍以修复包的实机重试结果为准。
