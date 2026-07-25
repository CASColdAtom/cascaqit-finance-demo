"""离线 wheel 的静态资源、启动配置和 Windows 依赖闭包测试。"""

from __future__ import annotations

import tarfile
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from scripts.build_windows_offline_bundle import (
    PYTHON_RUNTIME_SOURCE_SHA256,
    PYTHON_RUNTIME_ZIP_NAME,
    _audit_windows_dependency_closure,
    _copy_windows_template,
    _extract_runtime_archive,
)

from cascaqit_finance_demo.api.app import FRONTEND_DIST, HOST, PORT


def _write_test_wheel(
    wheelhouse: Path,
    name: str,
    version: str,
    requirements: list[str] | None = None,
) -> None:
    """生成只含必要元数据的测试 wheel，避免单元测试访问网络或真实离线包。"""

    distribution = name.replace("-", "_")
    wheel = wheelhouse / f"{distribution}-{version}-py3-none-any.whl"
    metadata_lines = [
        "Metadata-Version: 2.1",
        f"Name: {name}",
        f"Version: {version}",
    ]
    for requirement in requirements or []:
        metadata_lines.append(f"Requires-Dist: {requirement}")
    metadata = "\n".join(metadata_lines) + "\n\n"
    with ZipFile(wheel, "w") as archive:
        archive.writestr(f"{distribution}-{version}.dist-info/METADATA", metadata)


def test_packaged_frontend_entry_exists() -> None:
    """验证后端读取包内前端入口，不再依赖源码仓库目录层级。"""

    assert FRONTEND_DIST.name == "static"
    assert (FRONTEND_DIST / "index.html").is_file()


def test_packaged_frontend_excludes_source_maps() -> None:
    """验证客户 Release wheel 不携带浏览器可读取的 JavaScript source map。"""

    assert list(FRONTEND_DIST.rglob("*.map")) == []


def test_runtime_requires_qubo_layout_capable_cascaqit() -> None:
    """验证 Demo 不会安装缺少 QUBO 完整参考布局契约的旧版 CASCAQit。"""

    project = Path("pyproject.toml").read_text(encoding="utf-8")

    assert '"cascaqit>=1.0.7a0,<1.0.8"' in project


def test_default_server_is_local_only() -> None:
    """验证离线演示服务默认只监听本机，并使用约定端口。"""

    assert HOST == "127.0.0.1"
    assert PORT == 8000


def test_windows_dependency_audit_rejects_missing_marker_dependency(
    tmp_path: Path,
) -> None:
    """验证在 macOS 构建时也能发现仅 Windows 生效的 colorama 依赖。"""

    _write_test_wheel(
        tmp_path,
        "click",
        "8.4.2",
        ['colorama; platform_system == "Windows"'],
    )

    with pytest.raises(RuntimeError, match="缺少依赖 colorama"):
        _audit_windows_dependency_closure(tmp_path)


def test_windows_dependency_audit_accepts_complete_marker_dependency(
    tmp_path: Path,
) -> None:
    """验证 Windows 条件依赖存在且版本满足约束时闭包审计通过。"""

    _write_test_wheel(
        tmp_path,
        "click",
        "8.4.2",
        ['colorama>=0.4; platform_system == "Windows"'],
    )
    _write_test_wheel(tmp_path, "colorama", "0.4.6")

    _audit_windows_dependency_closure(tmp_path)


def test_windows_installer_uses_portable_runtime_and_real_smoke() -> None:
    """验证安装模板使用兼容 PowerShell 5.1 的 runtime 解压与真实自检。"""

    install_script = Path("packaging/windows/install.ps1").read_text(encoding="utf-8")
    run_script = Path("packaging/windows/run.ps1").read_text(encoding="utf-8")

    assert PYTHON_RUNTIME_ZIP_NAME in install_script
    assert "Expand-Archive" not in install_script
    assert "System.IO.Compression.FileSystem" in install_script
    assert "[System.IO.Compression.ZipFile]::ExtractToDirectory" in install_script
    assert (
        "Expand-PortablePythonArchive -Archive $PortableArchive -Destination $Runtime"
        in install_script
    )
    assert "python-extract-" not in install_script
    assert "Move-Item" not in install_script
    assert "python-3.11.9-amd64.exe" not in install_script
    assert "--force-reinstall" in install_script
    assert "if ($ForceReinstall)" in install_script
    assert "cascaqit_finance_demo.smoke_test" in install_script
    assert "Test-VenvPython" in run_script
    assert len(PYTHON_RUNTIME_SOURCE_SHA256) == 64


def test_windows_batch_entrypoints_are_ascii_crlf_and_bypass_process_policy() -> None:
    """验证 cmd.exe 入口没有中文多字节、孤立 LF 或缺失的进程级策略参数。"""

    for name in ("INSTALL.bat", "RUN.bat", "VERIFY.bat"):
        payload = (Path("packaging/windows") / name).read_bytes()
        text = payload.decode("ascii")

        assert b"\r\n" in payload
        assert b"\n" not in payload.replace(b"\r\n", b"")
        assert b"\r" not in payload.replace(b"\r\n", b"")
        assert "chcp" not in text.lower()
        assert "-ExecutionPolicy Bypass" in text
        assert "-File" in text
        assert "exit /b %EXIT_CODE%" in text


def test_windows_template_copy_enforces_encoding_and_line_endings(
    tmp_path: Path,
) -> None:
    """验证构建器强制生成 ASCII BAT 和带 BOM 的 CRLF PowerShell。"""

    batch_source = tmp_path / "source.bat"
    batch_output = tmp_path / "output.bat"
    batch_source.write_text("@echo off\necho ok\n", encoding="ascii")
    _copy_windows_template(batch_source, batch_output)
    assert batch_output.read_bytes() == b"@echo off\r\necho ok\r\n"

    script_source = tmp_path / "source.ps1"
    script_output = tmp_path / "output.ps1"
    script_source.write_text('Write-Host "安装"\n', encoding="utf-8")
    _copy_windows_template(script_source, script_output)
    script_payload = script_output.read_bytes()
    assert script_payload.startswith(b"\xef\xbb\xbf")
    assert script_payload.decode("utf-8-sig") == 'Write-Host "安装"\r\n'


def test_windows_template_copy_rejects_non_ascii_batch(tmp_path: Path) -> None:
    """验证新增中文 BAT 会在打包阶段失败，而不是到客户机器才暴露乱码。"""

    source = tmp_path / "invalid.bat"
    source.write_text("echo 安装\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="必须只包含 ASCII"):
        _copy_windows_template(source, tmp_path / "invalid-output.bat")


def test_python39_runtime_extraction_accepts_regular_files(tmp_path: Path) -> None:
    """验证最低 Python 版本的兼容路径可以安全解压 runtime 普通文件。"""

    source = tmp_path / "runtime.tar"
    payload = b"portable-python"
    with tarfile.open(source, mode="w") as archive:
        member = tarfile.TarInfo("python/python.exe")
        member.size = len(payload)
        archive.addfile(member, BytesIO(payload))

    destination = tmp_path / "runtime"
    destination.mkdir()
    with tarfile.open(source, mode="r") as archive:
        _extract_runtime_archive(archive, destination)

    assert (destination / "python" / "python.exe").read_bytes() == payload


@pytest.mark.parametrize("member_name", ["../outside.txt", "/absolute.txt"])
def test_python39_runtime_extraction_rejects_out_of_tree_paths(
    tmp_path: Path,
    member_name: str,
) -> None:
    """验证旧版 tarfile 兼容路径也会拒绝绝对路径和目录穿越。"""

    source = tmp_path / "unsafe.tar"
    with tarfile.open(source, mode="w") as archive:
        member = tarfile.TarInfo(member_name)
        member.size = 1
        archive.addfile(member, BytesIO(b"x"))

    destination = tmp_path / "runtime"
    destination.mkdir()
    with (
        tarfile.open(source, mode="r") as archive,
        pytest.raises(RuntimeError, match="越界路径"),
    ):
        _extract_runtime_archive(archive, destination)
