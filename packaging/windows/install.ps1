[CmdletBinding()]
param(
    [switch]$ForceReinstall
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runtime = Join-Path $Root "runtime"
$PythonHome = Join-Path $Runtime "python"
$PortablePython = Join-Path $PythonHome "python.exe"
$PortableArchive = Join-Path $Root "python\cpython-3.11.9-windows-x64-portable.zip"
$VenvRoot = Join-Path $Runtime "venv"
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
$Wheelhouse = Join-Path $Root "wheelhouse"
$InstallLog = Join-Path $Runtime "install.log"

function Write-InstallEvent {
    param([Parameter(Mandatory = $true)][string]$Message)

    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $Line = "[$Timestamp] $Message"
    Write-Host $Message
    Add-Content -LiteralPath $InstallLog -Value $Line -Encoding UTF8
}

function Test-Python311X64 {
    param([Parameter(Mandatory = $true)][string]$Executable)

    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        return $false
    }
    # 同时执行解释器并校验版本、实现和指针宽度。仅判断文件存在无法识别
    # 包移动后留下的失效 venv，也无法排除 ARM64 或 32 位解释器。
    & $Executable -c "import platform,struct,sys; assert platform.python_implementation() == 'CPython'; assert sys.version_info[:3] == (3,11,9); assert struct.calcsize('P') * 8 == 64" 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

# 安装前先校验可重定位 runtime、全部 wheel 和脚本。运行时生成目录不在清单中。
& (Join-Path $Root "verify.ps1")
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
Set-Content -LiteralPath $InstallLog -Value "" -Encoding UTF8
Write-InstallEvent "开始安装中科酷原金融量子实验台。"

if (-not (Test-Python311X64 -Executable $PortablePython)) {
    if (-not (Test-Path -LiteralPath $PortableArchive -PathType Leaf)) {
        throw "离线包缺少可重定位 Python runtime：$PortableArchive"
    }
    Write-InstallEvent "正在解压包内 CPython 3.11.9 x64 runtime……"
    $ExtractRoot = Join-Path $Runtime ("python-extract-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $ExtractRoot | Out-Null
    try {
        Expand-Archive -LiteralPath $PortableArchive -DestinationPath $ExtractRoot -Force
        $ExtractedPython = Join-Path $ExtractRoot "python\python.exe"
        if (-not (Test-Python311X64 -Executable $ExtractedPython)) {
            throw "解压后的 Python 解释器不存在、版本不符或无法运行：$ExtractedPython"
        }
        if (Test-Path -LiteralPath $PythonHome) {
            Remove-Item -LiteralPath $PythonHome -Recurse -Force
        }
        Move-Item -LiteralPath (Join-Path $ExtractRoot "python") -Destination $PythonHome
    } finally {
        if (Test-Path -LiteralPath $ExtractRoot) {
            Remove-Item -LiteralPath $ExtractRoot -Recurse -Force
        }
    }
}

if (-not (Test-Python311X64 -Executable $PortablePython)) {
    throw "包内 Python runtime 验证失败：$PortablePython。安装日志：$InstallLog"
}
Write-InstallEvent "包内 Python runtime 验证通过。"

if (-not (Test-Python311X64 -Executable $VenvPython)) {
    if (Test-Path -LiteralPath $VenvRoot) {
        Write-InstallEvent "检测到失效的隔离环境，正在清理并重建……"
        Remove-Item -LiteralPath $VenvRoot -Recurse -Force
    } else {
        Write-InstallEvent "正在创建隔离运行环境……"
    }
    & $PortablePython -m venv $VenvRoot
    if ($LASTEXITCODE -ne 0 -or -not (Test-Python311X64 -Executable $VenvPython)) {
        throw "创建 Python 虚拟环境失败。安装日志：$InstallLog"
    }
}

$PipArguments = @(
    "-m", "pip", "install",
    "--disable-pip-version-check",
    "--no-index",
    "--find-links", $Wheelhouse,
    "--only-binary=:all:"
)
if ($ForceReinstall) {
    Write-InstallEvent "正在强制重装 CASCAQit 和金融 Demo……"
    $PipArguments += @("--upgrade", "--force-reinstall")
} else {
    Write-InstallEvent "正在检查并安装 CASCAQit 和金融 Demo……"
}
$PipArguments += "cascaqit-finance-demo==0.1.1"
& $VenvPython @PipArguments
if ($LASTEXITCODE -ne 0) {
    throw "离线 Python 依赖安装失败。安装日志：$InstallLog"
}

& $VenvPython -m pip check
if ($LASTEXITCODE -ne 0) {
    throw "安装后的 Python 依赖一致性检查失败。安装日志：$InstallLog"
}

# 版本、静态资源和真实 settlement 执行必须同时通过。后者会覆盖资源规划器、
# Digital-Analog-Digital 编译、本地模拟、采样和结果映射，不再只验证 import。
$env:CASCAQIT_FINANCE_DATA_DIR = $Root
$VersionCheck = "from importlib.metadata import version; from cascaqit_finance_demo.api.app import FRONTEND_DIST; assert (FRONTEND_DIST / 'index.html').is_file(); print('CASCAQit', version('cascaqit')); print('Finance Demo', version('cascaqit-finance-demo'))"
& $VenvPython -c $VersionCheck
if ($LASTEXITCODE -ne 0) {
    throw "安装后的版本或静态资源自检失败。安装日志：$InstallLog"
}
& $VenvPython -m cascaqit_finance_demo.smoke_test
if ($LASTEXITCODE -ne 0) {
    throw "安装后的 settlement 场景执行自检失败。安装日志：$InstallLog"
}

Set-Content -LiteralPath (Join-Path $Runtime "install-ok.txt") -Value "ok" -Encoding ASCII
Write-InstallEvent "离线安装和真实场景自检完成。"
Write-Host "离线安装完成。" -ForegroundColor Green
