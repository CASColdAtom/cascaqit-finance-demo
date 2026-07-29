[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $Root "runtime\venv\Scripts\python.exe"
$Launcher = Join-Path $Root "runtime\venv\Scripts\cascaqit-industry-demo.exe"
$LegacyLauncher = Join-Path $Root "runtime\venv\Scripts\cascaqit-finance-demo.exe"

function Test-VenvPython {
    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
        return $false
    }
    # 包目录移动后 venv 文件可能仍在，但 pyvenv.cfg 指向的旧 runtime 已失效。
    & $VenvPython -c "import sys; assert sys.version_info[:3] == (3,11,9)" 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

if (-not (Test-VenvPython)) {
    Write-Host "尚未安装运行环境，先执行离线安装……"
    & (Join-Path $Root "install.ps1")
}
if (-not (Test-Path -LiteralPath $Launcher -PathType Leaf)) {
    if (Test-Path -LiteralPath $LegacyLauncher -PathType Leaf) {
        $Launcher = $LegacyLauncher
    } else {
        throw "启动程序不存在，请重新运行 INSTALL.bat。"
    }
}

# 运行数据固定写入离线包目录；服务只监听 127.0.0.1，不向局域网暴露端口。
$env:CASCAQIT_INDUSTRY_DATA_DIR = $Root
if ([string]::IsNullOrWhiteSpace($env:CASCAQIT_INDUSTRY_PORT)) {
    if ([string]::IsNullOrWhiteSpace($env:CASCAQIT_FINANCE_PORT)) {
        $env:CASCAQIT_INDUSTRY_PORT = "8000"
    } else {
        $env:CASCAQIT_INDUSTRY_PORT = $env:CASCAQIT_FINANCE_PORT
    }
}

Write-Host "中科酷原行业量子实验台正在启动：http://127.0.0.1:$($env:CASCAQIT_INDUSTRY_PORT)"
Write-Host "关闭窗口或按 Ctrl+C 可停止服务。"
& $Launcher
if ($LASTEXITCODE -ne 0) {
    throw "实验台进程异常退出，错误码 $LASTEXITCODE。"
}
