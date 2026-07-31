[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Manifest = Join-Path $Root "manifest-sha256.txt"

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Path)

    $Algorithm = [System.Security.Cryptography.SHA256]::Create()
    $Stream = [System.IO.File]::OpenRead($Path)
    try {
        $Hash = $Algorithm.ComputeHash($Stream)
        return ([System.BitConverter]::ToString($Hash)).Replace("-", "").ToLowerInvariant()
    } finally {
        $Stream.Dispose()
        $Algorithm.Dispose()
    }
}

if (-not (Test-Path -LiteralPath $Manifest -PathType Leaf)) {
    throw "缺少完整性清单：$Manifest"
}

# 清单使用“SHA256 + 两个空格 + 相对路径”的通用格式；路径统一保存为正斜杠，
# 校验时再转换为 Windows 路径，确保压缩包可以在不同目录中解压。
$Checked = 0
foreach ($Line in Get-Content -LiteralPath $Manifest -Encoding UTF8) {
    if ([string]::IsNullOrWhiteSpace($Line)) {
        continue
    }
    $Separator = $Line.IndexOf("  ")
    if ($Separator -lt 1) {
        throw "完整性清单格式错误：$Line"
    }
    $Expected = $Line.Substring(0, $Separator).ToLowerInvariant()
    $Relative = $Line.Substring($Separator + 2).Replace("/", "\")
    $Target = Join-Path $Root $Relative
    if (-not (Test-Path -LiteralPath $Target -PathType Leaf)) {
        throw "离线包缺少文件：$Relative"
    }
    $Actual = Get-Sha256Hex -Path $Target
    if ($Actual -ne $Expected) {
        throw "文件校验失败：$Relative"
    }
    $Checked += 1
}

Write-Host "离线包完整性检查通过，共校验 $Checked 个文件。" -ForegroundColor Green
