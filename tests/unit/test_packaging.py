"""离线 wheel 的静态资源、启动配置和 Windows 依赖闭包测试。"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import tarfile
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from scripts.build_windows_offline_bundle import (
    BUNDLE_NAME,
    PYTHON_RUNTIME_RELEASE,
    PYTHON_RUNTIME_SOURCE_SHA256,
    PYTHON_RUNTIME_ZIP_NAME,
    _audit_demo_fixture_checksums,
    _audit_windows_dependency_closure,
    _copy_sdk_license,
    _copy_windows_template,
    _extract_runtime_archive,
    _populate_windows_wheelhouse_from_cache,
    _prepare_python_runtime,
    _preserve_cache_for_rebuild,
    _reset_directory,
    _run,
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


def test_runtime_requires_validated_cascaqit_release_series() -> None:
    """验证 Demo 不会安装缺少 QUBO 完整参考布局契约的旧版 CASCAQit。"""

    project = Path("pyproject.toml").read_text(encoding="utf-8")

    assert '"cascaqit>=1.0.7a0,<1.0.8"' in project


def test_project_and_windows_bundle_use_industry_identity() -> None:
    project = Path("pyproject.toml").read_text(encoding="utf-8")
    frontend = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    workflow = Path(".github/workflows/windows-offline-acceptance.yml").read_text(
        encoding="utf-8"
    )

    assert 'name = "cascaqit-industry-workbench"' in project
    assert frontend["name"] == "cascaqit-industry-workbench"
    assert BUNDLE_NAME == "cascaqit-industry-workbench-windows-x64-py311"
    assert "${{ github.server_url }}/${{ github.repository }}" in workflow
    assert "version('cascaqit-industry-workbench') == '0.3.0'" not in workflow


def test_industry_entrypoints_delegate_to_unified_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cascaqit_industry_demo import entrypoints

    application = importlib.import_module("cascaqit_finance_demo.api.app")
    calls: list[str] = []
    monkeypatch.setattr(application, "run", lambda: calls.append("run"))
    monkeypatch.setattr(application, "launch", lambda: calls.append("launch"))

    entrypoints.run()
    entrypoints.launch()

    assert calls == ["run", "launch"]


def test_windows_bundle_uses_standard_pep517_wheel_build() -> None:
    """发布构建不依赖会初始化宿主网络配置的第三方构建前端。"""

    script = Path("scripts/build_windows_offline_bundle.py").read_text(
        encoding="utf-8"
    )

    assert 'sys.executable, "-m", "build"' in script
    assert '"--no-isolation"' in script
    assert '["uv", "build"' not in script


def test_fixture_json_line_endings_are_stable_on_windows_checkout() -> None:
    attributes = Path(".gitattributes").read_text(encoding="utf-8")

    assert "*.json text eol=lf" in attributes


def test_demo_wheel_rejects_fixture_line_ending_drift(tmp_path: Path) -> None:
    wheel = tmp_path / "demo.whl"
    domain_lf = b'{"value": 1}\n'
    manifest = {
        "artifacts": [
            {
                "path": "domain.json",
                "sha256": hashlib.sha256(domain_lf).hexdigest(),
            }
        ]
    }
    with ZipFile(wheel, "w") as archive:
        root = "cascaqit_biomedicine_demo/data/example/case/1"
        archive.writestr(f"{root}/manifest.json", json.dumps(manifest))
        archive.writestr(f"{root}/domain.json", domain_lf.replace(b"\n", b"\r\n"))

    with pytest.raises(RuntimeError, match="domain.json checksum mismatch"):
        _audit_demo_fixture_checksums(wheel)


def test_build_command_resolves_platform_specific_path_entry(
    tmp_path: Path,
) -> None:
    executable = tmp_path / ("bundle-tool.cmd" if os.name == "nt" else "bundle-tool")
    executable.write_text(
        "@echo off\r\nexit /b 0\r\n" if os.name == "nt" else "#!/bin/sh\nexit 0\n",
        encoding="ascii",
    )
    executable.chmod(0o755)
    original_path = os.environ.get("PATH", "")
    os.environ["PATH"] = str(tmp_path) + os.pathsep + original_path
    try:
        _run(["bundle-tool"], cwd=tmp_path)
    finally:
        os.environ["PATH"] = original_path


def test_windows_bundle_extracts_license_from_pinned_sdk_wheel(
    tmp_path: Path,
) -> None:
    sdk_wheel = tmp_path / "cascaqit-1.0.7a0-py3-none-any.whl"
    with ZipFile(sdk_wheel, "w") as archive:
        archive.writestr(
            "cascaqit-1.0.7a0.dist-info/licenses/LICENSE",
            "Apache License 2.0\n",
        )

    destination = tmp_path / "CASCAQit-LICENSE.txt"
    _copy_sdk_license(sdk_wheel, destination)

    assert destination.read_text(encoding="utf-8") == "Apache License 2.0\n"


def test_windows_bundle_cache_replaces_both_local_wheels(tmp_path: Path) -> None:
    """缓存只提供第三方闭包，当前源码 wheel 必须覆盖旧发布版本。"""

    cache_root = tmp_path / "cache"
    cached_wheels = cache_root / "wheelhouse"
    cached_wheels.mkdir(parents=True)
    _write_test_wheel(cached_wheels, "cascaqit", "9.9.9")
    _write_test_wheel(cached_wheels, "cascaqit-finance-demo", "9.9.9")
    _write_test_wheel(cached_wheels, "cascaqit-industry-workbench", "9.9.9")
    _write_test_wheel(cached_wheels, "third-party", "1.2.3")

    current = tmp_path / "current"
    current.mkdir()
    _write_test_wheel(current, "cascaqit", "1.0.7a0", ["third-party>=1"])
    _write_test_wheel(
        current,
        "cascaqit-industry-workbench",
        "0.3.0",
        ["cascaqit>=1.0.7a0,<1.0.8"],
    )
    output = tmp_path / "output"
    _populate_windows_wheelhouse_from_cache(
        next(current.glob("cascaqit_industry_workbench-*.whl")),
        next(current.glob("cascaqit-*.whl")),
        output,
        cache_root,
    )

    names = {path.name for path in output.glob("*.whl")}
    assert "cascaqit-9.9.9-py3-none-any.whl" not in names
    assert "cascaqit_finance_demo-9.9.9-py3-none-any.whl" not in names
    assert "cascaqit_industry_workbench-9.9.9-py3-none-any.whl" not in names
    assert "cascaqit-1.0.7a0-py3-none-any.whl" in names
    assert "cascaqit_industry_workbench-0.3.0-py3-none-any.whl" in names
    assert "third_party-1.2.3-py3-none-any.whl" in names


def test_windows_bundle_cache_verifies_runtime_identity(tmp_path: Path) -> None:
    """缓存 runtime 只有身份和派生 ZIP hash 全部匹配时才可复用。"""

    cache_root = tmp_path / "cache"
    runtime = cache_root / "python" / PYTHON_RUNTIME_ZIP_NAME
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"validated-runtime")
    digest = hashlib.sha256(runtime.read_bytes()).hexdigest()
    (cache_root / "bundle-info.json").write_text(
        json.dumps(
            {
                "python": "3.11.9",
                "python_runtime_release": PYTHON_RUNTIME_RELEASE,
                "python_runtime_source_sha256": PYTHON_RUNTIME_SOURCE_SHA256,
                "python_runtime_archive": PYTHON_RUNTIME_ZIP_NAME,
                "python_runtime_archive_sha256": digest,
            }
        ),
        encoding="utf-8",
    )

    destination = tmp_path / "out" / PYTHON_RUNTIME_ZIP_NAME
    _prepare_python_runtime(destination, cache_root)
    assert destination.read_bytes() == b"validated-runtime"

    runtime.write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="SHA256"):
        _prepare_python_runtime(destination, cache_root)


def test_windows_bundle_preserves_in_place_cache_during_rebuild(
    tmp_path: Path,
) -> None:
    """默认输出目录可直接复用自身上一版，不会先删掉缓存输入。"""

    bundle_root = tmp_path / "bundle"
    cached_wheel = bundle_root / "wheelhouse" / "dependency.whl"
    cached_wheel.parent.mkdir(parents=True)
    cached_wheel.write_bytes(b"cached-wheel")
    (bundle_root / "bundle-info.json").write_text("{}", encoding="utf-8")

    with _preserve_cache_for_rebuild(bundle_root, bundle_root) as preserved:
        assert preserved is not None
        assert preserved != bundle_root
        _reset_directory(bundle_root)
        assert (preserved / "wheelhouse" / "dependency.whl").read_bytes() == (
            b"cached-wheel"
        )
        assert (preserved / "bundle-info.json").is_file()


def test_windows_bundle_restores_in_place_cache_after_failed_rebuild(
    tmp_path: Path,
) -> None:
    """构建失败时恢复上一版目录，不能只留下半成品和旧 ZIP。"""

    bundle_root = tmp_path / "bundle"
    previous_manifest = bundle_root / "manifest-sha256.txt"
    previous_manifest.parent.mkdir(parents=True)
    previous_manifest.write_text("previous-release\n", encoding="utf-8")

    with pytest.raises(
        RuntimeError, match="wheel build failed"
    ), _preserve_cache_for_rebuild(bundle_root, bundle_root):
        _reset_directory(bundle_root)
        (bundle_root / "partial-wheel.whl").write_bytes(b"partial")
        raise RuntimeError("wheel build failed")

    assert previous_manifest.read_text(encoding="utf-8") == "previous-release\n"
    assert not (bundle_root / "partial-wheel.whl").exists()


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
    verify_script = Path("packaging/windows/verify.ps1").read_text(encoding="utf-8")

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
    assert "$BundleInfo.industry_workbench" in install_script
    assert 'cascaqit-industry-workbench==0.3.0' not in install_script
    assert "version('cascaqit-industry-workbench')" in install_script
    assert "cascaqit_finance_demo.smoke_test" in install_script
    assert "中科酷原行业量子实验台" in install_script
    assert "中科酷原行业量子实验台" in run_script
    assert "cascaqit-industry-demo.exe" in run_script
    assert "CASCAQIT_INDUSTRY_DATA_DIR" in install_script
    assert "CASCAQIT_INDUSTRY_DATA_DIR" in run_script
    assert "CASCAQIT_INDUSTRY_PORT" in run_script
    assert "Test-VenvPython" in run_script
    assert "System.Security.Cryptography.SHA256" in verify_script
    assert "Get-FileHash" not in verify_script
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
