# Windows 离线包构建与发布手册

## 1. 目标

本文固化 `cascaqit-industry-workbench` 的 Windows 10/11 x64 离线交付流程。最终制品必须在无系统 Python、无 Node.js、无管理员权限、安装阶段无网络的机器上完成校验、安装和启动。

正式制品名：

```text
cascaqit-industry-workbench-windows-x64-py311.zip
```

## 2. 固定输入

| 输入 | 固定方式 |
|---|---|
| 工作台源码 | 发布提交 SHA |
| CASCAQit | `vendor/cascaqit-1.0.7a0-py3-none-any.whl` 及固定 SHA-256 |
| Python runtime | CPython 3.11.9 python-build-standalone 发布号及固定 SHA-256 |
| 第三方 wheel | 已验收缓存或面向 CPython 3.11/Windows x64 的完整 wheel 闭包 |
| 前端依赖 | `frontend/package-lock.json` |
| fixture | manifest + artifact SHA-256，JSON 固定 LF |

发布不允许从未提交的相邻 SDK 源码隐式构建。需要验证 SDK 源码时必须显式传入 `--sdk-root`，正式发布优先使用固定 wheel。

## 3. 版本与命名

1. 在 `pyproject.toml` 更新 Python distribution 版本。
2. 在 `frontend/package.json` 和 lockfile 更新同一版本。
3. Windows 安装器不保存版本常量；它从构建生成的 `bundle-info.json.industry_workbench` 读取精确 requirement。
4. 主 CLI 使用 `cascaqit-industry-*`；旧金融 CLI 只作为兼容别名。
5. ZIP、目录、CI artifact 和 Release asset 使用同一个 `cascaqit-industry-workbench-windows-x64-py311` 基名。

## 4. 本地构建

准备开发依赖和前端依赖：

```bash
python3 -m pip install -e ".[dev]" build packaging
cd frontend && npm ci && cd ..
```

联网构建：

```bash
python3 scripts/build_windows_offline_bundle.py
```

复用已验收缓存：

```bash
python3 scripts/build_windows_offline_bundle.py \
  --cache-root offline/cascaqit-industry-workbench-windows-x64-py311
```

输出位于：

```text
offline/cascaqit-industry-workbench-windows-x64-py311/
offline/cascaqit-industry-workbench-windows-x64-py311.zip
```

## 5. 构建器强制检查

- React 生产入口存在且不包含 source map；
- 工作台 wheel 名称和版本来自项目元数据；
- wheel 中每个 fixture manifest 声明的 artifact 存在且 SHA-256 匹配；
- wheelhouse 没有新旧工作台 distribution 混装；
- 所有 Windows marker 依赖存在且版本满足约束；
- Python runtime 上游归档 SHA-256 匹配；
- BAT 为 ASCII + CRLF，PowerShell 为 UTF-8 BOM + CRLF；
- `bundle-info.json`、包清单和逐文件 manifest 完整生成；
- 最终 ZIP 只在全部步骤成功后创建。

## 6. Windows CI 验收

推送发布相关文件后，`.github/workflows/windows-offline-acceptance.yml` 必须在 `windows-2022` runner 完成：

1. 在 Windows checkout 上重新构建前端、wheel 和 ZIP；
2. 执行 `VERIFY.bat`；
3. 设置 `PIP_NO_INDEX=1` 后执行 `INSTALL.bat`；
4. 校验工作台与 CASCAQit 精确版本；
5. 通过 `RUN.bat` 启动已安装程序；
6. 检查健康接口、三个领域目录、六个生物医药和两个材料结构分析接口；
7. 上传与提交 SHA 绑定的 ZIP artifact。

安装与启动验收必须使用包内 runtime 和 wheelhouse，不能退回 runner 的系统 Python。

## 7. 浏览器验收

`.github/workflows/v3-browser-acceptance.yml` 必须完成三个视口、八个生物医药/材料场景的 Chromium 验收，检查：

- 场景执行成功；
- 结构 SVG 和量子图表非空；
- 页面无横向溢出、console error 或 page error；
- Pure Analog 页面不出现数字线路；
- 证据 revision 与发布提交一致。

## 8. Release 发布

1. 从成功的 Windows run 下载 ZIP artifact。
2. 本地执行 `unzip -t` 并计算 SHA-256。
3. 解开 ZIP，核对 `bundle-info.json`、wheel 数和 manifest 数。
4. 创建签注 tag，tag 指向已包含发布报告的提交。
5. 创建 GitHub Release 并上传 Windows runner 的原始 ZIP。
6. 读取 GitHub asset `digest`，必须与本地 SHA-256 一致。
7. 将该版本设为 Latest，并在发布报告记录 commit、run、大小、hash 和下载地址。

不得用 macOS 本地构建的 ZIP 替换已经通过 Windows 安装验收的 runner ZIP。

## 9. 故障与回滚

- 构建失败：不创建 ZIP，保留上一份缓存。
- `VERIFY.bat` 失败：停止安装，检查 manifest、编码和换行。
- `INSTALL.bat` 失败：不发布资产，读取 `runtime/install.log`。
- 场景接口失败：审计 wheel 内 fixture，而不是只检查源码文件。
- 已发布版本发现阻断问题：发布补丁版本，将旧 Release 标记停用并指向修复版，不覆盖原 tag 和资产。
- GitHub 上传失败：保留 Actions artifact；先确认 Release/tag 状态，再继续同一版本上传，避免重复草稿。

## 10. 发布清单

```text
[ ] 工作区干净，版本与命名一致
[ ] Ruff、Python 相关测试通过
[ ] TypeScript、React 测试和生产构建通过
[ ] 本地 wheel fixture 审计通过
[ ] Windows VERIFY / INSTALL / RUN 通过
[ ] 八个结构分析接口在已安装服务中通过
[ ] Chromium 三视口验收通过
[ ] ZIP 结构、大小和 SHA-256 已记录
[ ] GitHub asset digest 与本地一致
[ ] Release 报告和 Latest 标记已更新
```
