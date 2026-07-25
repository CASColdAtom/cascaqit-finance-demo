"""构建可复制到 Windows x64 的金融 Demo CPython 3.11 离线安装包。

脚本在 macOS 开发机上完成前端构建、两个本地 wheel 构建、Windows 二进制依赖
下载、可重定位 Python runtime 准备、版本清单与 SHA256 清单生成，最后输出 zip。
目标机器不需要 Node.js、编译器、网络或管理员权限。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from email.message import Message
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SDK_ROOT = ROOT.parent / "cascaqit-new" / "CASCAQit"
TEMPLATE_ROOT = ROOT / "packaging" / "windows"
FRONTEND_DIST = ROOT / "frontend" / "dist"
PACKAGE_STATIC = ROOT / "src" / "cascaqit_finance_demo" / "static"
BUNDLE_NAME = "cascaqit-finance-demo-windows-x64-py311"
PYTHON_VERSION = "3.11.9"
PYTHON_RUNTIME_RELEASE = "20240726"
PYTHON_RUNTIME_SOURCE_NAME = (
    f"cpython-{PYTHON_VERSION}+{PYTHON_RUNTIME_RELEASE}-"
    "x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
)
PYTHON_RUNTIME_SOURCE_URL = (
    "https://github.com/astral-sh/python-build-standalone/releases/download/"
    f"{PYTHON_RUNTIME_RELEASE}/{PYTHON_RUNTIME_SOURCE_NAME.replace('+', '%2B')}"
)
PYTHON_RUNTIME_SOURCE_SHA256 = (
    "2e67e46b1e59d12583f3079c97dba46de3c8a158c9a83234a31613e969d0fd90"
)
PYTHON_RUNTIME_ZIP_NAME = f"cpython-{PYTHON_VERSION}-windows-x64-portable.zip"
# pip 的 --platform 参数会选择 Windows wheel，但不会把构建机的环境标记整体切换为
# Windows。这里给依赖审计提供目标机环境，确保 click 等包的 Windows 条件依赖被检查。
WINDOWS_MARKER_ENVIRONMENT = {
    "implementation_name": "cpython",
    "implementation_version": PYTHON_VERSION,
    "os_name": "nt",
    "platform_machine": "AMD64",
    "platform_python_implementation": "CPython",
    "platform_release": "",
    "platform_system": "Windows",
    "platform_version": "",
    "python_full_version": PYTHON_VERSION,
    "python_version": ".".join(PYTHON_VERSION.split(".")[:2]),
    "sys_platform": "win32",
    # 本离线包没有请求可选依赖组，因此带 extra 条件的依赖不应进入基础闭包。
    "extra": "",
}


def _run(command: list[str], *, cwd: Path) -> None:
    """执行构建命令并在任一步失败时立即终止，避免生成半成品离线包。"""

    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def _reset_directory(path: Path) -> None:
    """仅重建脚本负责的输出目录，不触碰源码或用户的其他构建产物。"""

    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _copy_windows_template(template: Path, destination: Path) -> None:
    """按 Windows 5.1/cmd.exe 约束复制入口脚本和用户说明。"""

    suffix = template.suffix.lower()
    if suffix not in {".bat", ".cmd", ".ps1", ".md"}:
        shutil.copy2(template, destination)
        return

    # 先统一为 LF，再一次性转换为 CRLF，避免源文件本身已有 CRLF 时产生 CRCRLF。
    text = template.read_text(encoding="utf-8-sig")
    windows_text = text.replace("\r\n", "\n").replace("\r", "\n")
    windows_text = windows_text.replace("\n", "\r\n")
    if suffix in {".bat", ".cmd"}:
        try:
            payload = windows_text.encode("ascii")
        except UnicodeEncodeError as exc:
            raise RuntimeError(
                f"Windows 批处理入口必须只包含 ASCII：{template.name}"
            ) from exc
    else:
        # Windows PowerShell 5.1 需要 BOM 才能稳定按 UTF-8 解析中文脚本。
        payload = b"\xef\xbb\xbf" + windows_text.encode("utf-8")
    destination.write_bytes(payload)


def _sync_frontend() -> None:
    """构建 React 并同步到 Python 包内，使 wheel 可独立提供完整页面。"""

    _run(["npm", "run", "build"], cwd=ROOT / "frontend")
    _reset_directory(PACKAGE_STATIC)
    shutil.copytree(FRONTEND_DIST, PACKAGE_STATIC, dirs_exist_ok=True)


def _build_local_wheels(sdk_root: Path, build_root: Path) -> tuple[Path, Path]:
    """分别构建当前金融 Demo 和指定 CASCAQit 源码的纯 Python wheel。"""

    finance_dir = build_root / "finance"
    sdk_dir = build_root / "sdk"
    finance_dir.mkdir()
    sdk_dir.mkdir()
    _run(
        ["uv", "build", "--wheel", "--clear", "--out-dir", str(finance_dir), "."],
        cwd=ROOT,
    )
    _run(
        ["uv", "build", "--wheel", "--clear", "--out-dir", str(sdk_dir), "."],
        cwd=sdk_root,
    )
    finance_wheel = next(finance_dir.glob("cascaqit_finance_demo-*.whl"))
    sdk_wheel = next(sdk_dir.glob("cascaqit-*.whl"))
    return finance_wheel, sdk_wheel


def _download_windows_wheels(
    finance_wheel: Path,
    sdk_wheel: Path,
    wheelhouse: Path,
) -> None:
    """解析并下载 CPython 3.11/Windows x64 的完整二进制依赖闭包。"""

    wheelhouse.mkdir()
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--dest",
            str(wheelhouse),
            "--platform",
            "win_amd64",
            "--python-version",
            "3.11",
            "--implementation",
            "cp",
            "--abi",
            "cp311",
            "--only-binary=:all:",
            "--find-links",
            str(sdk_wheel.parent),
            "--find-links",
            str(finance_wheel.parent),
            # click 在 Windows 上依赖 colorama。pip download 的平台参数不会影响
            # platform_system 环境标记，因此必须把它作为目标平台根依赖显式下载。
            "colorama>=0.4",
            str(sdk_wheel),
            str(finance_wheel),
        ],
        cwd=ROOT,
    )
    unexpected = [path.name for path in wheelhouse.iterdir() if path.suffix != ".whl"]
    if unexpected:
        raise RuntimeError(f"wheelhouse 中出现非 wheel 文件：{unexpected}")
    _audit_windows_dependency_closure(wheelhouse)


def _read_wheel_metadata(wheel: Path) -> Message:
    """读取 wheel 的核心元数据，供包清单与离线依赖闭包审计复用。"""

    with ZipFile(wheel) as archive:
        metadata_name = next(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        return BytesParser().parsebytes(archive.read(metadata_name))


def _audit_windows_dependency_closure(wheelhouse: Path) -> None:
    """按目标 Windows 环境验证 wheelhouse 包含全部运行时依赖及兼容版本。"""

    # 先从元数据建立规范化包名到版本的索引，避免 wheel 文件名中的连字符、下划线
    # 和大小写差异影响匹配。离线安装目录中同一包只允许出现一个确定版本。
    installed: dict[str, tuple[Version, Path, Message]] = {}
    for wheel in sorted(wheelhouse.glob("*.whl")):
        metadata = _read_wheel_metadata(wheel)
        name = metadata.get("Name")
        version_text = metadata.get("Version")
        if not name or not version_text:
            raise RuntimeError(f"wheel 缺少 Name 或 Version 元数据：{wheel.name}")
        normalized_name = canonicalize_name(name)
        if normalized_name in installed:
            previous = installed[normalized_name][1]
            raise RuntimeError(
                f"wheelhouse 包含同一包的多个 wheel：{previous.name}, {wheel.name}"
            )
        installed[normalized_name] = (Version(version_text), wheel, metadata)

    problems: list[str] = []
    for package_name, (_, wheel, metadata) in installed.items():
        for requirement_text in metadata.get_all("Requires-Dist", []):
            requirement = Requirement(requirement_text)
            if requirement.marker and not requirement.marker.evaluate(
                environment=WINDOWS_MARKER_ENVIRONMENT
            ):
                continue

            dependency_name = canonicalize_name(requirement.name)
            dependency = installed.get(dependency_name)
            if dependency is None:
                problems.append(
                    f"{package_name} ({wheel.name}) 缺少依赖 {requirement}"
                )
                continue

            dependency_version = dependency[0]
            if (
                requirement.specifier
                and dependency_version not in requirement.specifier
            ):
                problems.append(
                    f"{package_name} 需要 {requirement}，实际为 "
                    f"{requirement.name}=={dependency_version}"
                )

    if problems:
        details = "\n- ".join(problems)
        raise RuntimeError(f"Windows 离线依赖闭包不完整：\n- {details}")


def _download_file(url: str, destination: Path) -> None:
    """通过 HTTPS 下载构建输入，网络只发生在开发机打包阶段。"""

    print(f"+ download {url}")
    with (
        urllib.request.urlopen(url, timeout=120) as response,
        destination.open("wb") as output,
    ):
        shutil.copyfileobj(response, output)


def _extract_runtime_archive(archive: tarfile.TarFile, destination: Path) -> None:
    """安全解压 runtime，并兼容没有 ``tarfile.data_filter`` 的 Python 3.9。

    构建脚本需要在项目支持的最低 Python 版本运行。Python 3.9 没有标准
    ``data`` filter，因此先验证全部成员：只允许归档内的普通文件和目录，拒绝
    绝对路径、目录穿越、符号链接、硬链接和设备文件。目标目录由构建器新建，
    验证后一次性解压不会经过归档内创建的链接。
    """

    if hasattr(tarfile, "data_filter"):
        archive.extractall(destination, filter="data")
        return

    destination_root = destination.resolve()
    for member in archive.getmembers():
        relative = PurePosixPath(member.name)
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"Python runtime 归档包含越界路径：{member.name}")
        if not (member.isfile() or member.isdir()):
            raise RuntimeError(f"Python runtime 归档包含不安全成员：{member.name}")
        target = (destination / Path(*relative.parts)).resolve()
        try:
            target.relative_to(destination_root)
        except ValueError as exc:
            raise RuntimeError(
                f"Python runtime 归档成员越过目标目录：{member.name}"
            ) from exc

    archive.extractall(destination)


def _prepare_python_runtime(destination: Path) -> None:
    """下载、验签并转为 PowerShell 可直接解压的 Windows Python runtime。"""

    destination.parent.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="cascaqit-python-runtime-") as temporary:
        temporary_root = Path(temporary)
        source_archive = temporary_root / PYTHON_RUNTIME_SOURCE_NAME
        extracted_root = temporary_root / "extracted"
        extracted_root.mkdir()
        _download_file(PYTHON_RUNTIME_SOURCE_URL, source_archive)
        actual_sha256 = _sha256(source_archive)
        if actual_sha256 != PYTHON_RUNTIME_SOURCE_SHA256:
            raise RuntimeError(
                "python-build-standalone SHA256 校验失败："
                f"期望 {PYTHON_RUNTIME_SOURCE_SHA256}，实际 {actual_sha256}"
            )

        # 归档中的顶层 python 目录会原样进入最终 ZIP；兼容层在 Python 3.9
        # 主动执行与标准 data filter 等价的路径和成员类型检查。
        with tarfile.open(source_archive, mode="r:gz") as archive:
            _extract_runtime_archive(archive, extracted_root)
        python_executable = extracted_root / "python" / "python.exe"
        if not python_executable.is_file():
            raise RuntimeError("可重定位 Python 归档缺少 python/python.exe")

        archive_base = destination.with_suffix("")
        generated = Path(
            shutil.make_archive(
                str(archive_base),
                "zip",
                root_dir=extracted_root,
                base_dir="python",
            )
        )
        if generated != destination:
            raise RuntimeError(f"Python runtime 输出路径异常：{generated}")


def _wheel_requirement(wheel: Path) -> str:
    """读取 wheel METADATA，生成不受文件名规范化影响的精确版本要求。"""

    metadata = _read_wheel_metadata(wheel)
    return f"{metadata['Name']}=={metadata['Version']}"


def _write_package_inventory(wheelhouse: Path, bundle_root: Path) -> list[str]:
    """记录离线包中每个 Python 包的精确版本，便于客户环境审计。"""

    requirements = sorted(_wheel_requirement(path) for path in wheelhouse.glob("*.whl"))
    content = "\n".join(requirements) + "\n"
    (bundle_root / "requirements.txt").write_text(content, encoding="utf-8")
    (bundle_root / "THIRD_PARTY_PACKAGES.txt").write_text(content, encoding="utf-8")
    return requirements


def _sha256(path: Path) -> str:
    """流式计算大文件 SHA256，避免一次性把 runtime 或 SciPy wheel 读入内存。"""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(bundle_root: Path) -> None:
    """为交付目录中除清单本身外的所有文件生成可迁移完整性校验。"""

    manifest = bundle_root / "manifest-sha256.txt"
    lines = []
    for path in sorted(item for item in bundle_root.rglob("*") if item.is_file()):
        if path == manifest:
            continue
        relative = path.relative_to(bundle_root).as_posix()
        lines.append(f"{_sha256(path)}  {relative}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_bundle(output_root: Path, sdk_root: Path) -> Path:
    """生成目录版和 zip 版 Windows 离线交付物，并返回 zip 路径。"""

    if not (sdk_root / "pyproject.toml").is_file():
        raise FileNotFoundError(f"CASCAQit 源码目录无效：{sdk_root}")
    _sync_frontend()

    bundle_root = output_root / BUNDLE_NAME
    output_root.mkdir(parents=True, exist_ok=True)
    _reset_directory(bundle_root)
    with tempfile.TemporaryDirectory(prefix="cascaqit-finance-offline-") as temporary:
        build_root = Path(temporary)
        finance_wheel, sdk_wheel = _build_local_wheels(sdk_root, build_root)
        _download_windows_wheels(finance_wheel, sdk_wheel, bundle_root / "wheelhouse")

    for template in TEMPLATE_ROOT.iterdir():
        if template.is_file():
            destination = bundle_root / template.name
            _copy_windows_template(template, destination)
    shutil.copy2(sdk_root / "LICENSE", bundle_root / "CASCAQit-LICENSE.txt")
    runtime_archive = bundle_root / "python" / PYTHON_RUNTIME_ZIP_NAME
    _prepare_python_runtime(runtime_archive)
    requirements = _write_package_inventory(bundle_root / "wheelhouse", bundle_root)
    info = {
        "bundle": BUNDLE_NAME,
        "target_os": "Windows 10/11",
        "target_arch": "x64",
        "python": PYTHON_VERSION,
        "python_runtime": "python-build-standalone",
        "python_runtime_release": PYTHON_RUNTIME_RELEASE,
        "python_runtime_source_sha256": PYTHON_RUNTIME_SOURCE_SHA256,
        "python_runtime_archive": PYTHON_RUNTIME_ZIP_NAME,
        "python_runtime_archive_sha256": _sha256(runtime_archive),
        "finance_demo": next(
            item
            for item in requirements
            if item.lower().startswith("cascaqit-finance-demo==")
        ),
        "cascaqit": next(
            item for item in requirements if item.lower().startswith("cascaqit==")
        ),
        "wheel_count": len(requirements),
        "network_required_at_install": False,
    }
    (bundle_root / "bundle-info.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_manifest(bundle_root)

    archive_base = output_root / BUNDLE_NAME
    archive = archive_base.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    shutil.make_archive(str(archive_base), "zip", output_root, BUNDLE_NAME)
    return archive


def main() -> None:
    """解析命令行参数并打印最终可交付压缩包路径。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "offline",
        help="目录版与 zip 版离线包的输出目录",
    )
    parser.add_argument(
        "--sdk-root",
        type=Path,
        default=DEFAULT_SDK_ROOT,
        help="当前 CASCAQit 源码仓库目录",
    )
    args = parser.parse_args()
    archive = build_bundle(args.output_root.resolve(), args.sdk_root.resolve())
    print(f"Windows 离线包已生成：{archive}")


if __name__ == "__main__":
    main()
