# Windows 离线包构建与发布报告

## 交付结果

中科酷原行业量子实验台 `0.3.0` 已生成 Windows 10/11 x64 离线安装包：

```text
cascaqit-industry-workbench-windows-x64-py311.zip
```

GitHub Release：

<https://github.com/CASColdAtom/cascaqit-industry-workbench/releases/download/v0.3.0/cascaqit-industry-workbench-windows-x64-py311.zip>

目标机器不需要联网、管理员权限、系统 Python、Node.js 或编译器。解压后依次运行 `VERIFY.bat`、`INSTALL.bat` 和 `RUN.bat`；服务默认打开 `http://127.0.0.1:8000`。

## 制品身份

| 项目 | 值 |
|---|---|
| 构建基线 | `e099754aa041002a0c98b7dfd3bdcf710f55c26c` |
| 目标环境 | Windows 10/11 x64 |
| Python runtime | 可重定位 CPython `3.11.9` |
| 行业实验台 | `cascaqit-industry-workbench==0.3.0` |
| CASCAQit | `cascaqit==1.0.5a0` |
| CASCAQit wheel SHA256 | `af665bcd8dc81d7afe1370c1acee656dcc3192b63552429692655dc0159ee97e` |
| wheel 数 | 30 |
| 包文件清单条目 | 42 |
| fixture manifest / artifact | 20 / 35 |
| ZIP 大小 | `95,011,688` 字节 |
| ZIP SHA256 | `b3286608549e2e7a4e0f3482028663fd1e21bd149d0cbfa1e2a005ada07248df` |

包内包含 React 生产资源、金融七场景、生物医药六场景和材料科学两场景。项目级 Python 分发、前端包、主 CLI 和 Windows 制品均使用 `cascaqit-industry-workbench` 身份；旧金融 CLI 与 Python 导入路径仅作为兼容入口保留。

## Windows 验收

GitHub Actions `windows-2022` run `30620921440` 已完成 Windows 全链路验收：

<https://github.com/CASColdAtom/cascaqit-industry-workbench/actions/runs/30620921440>

已通过项目：

- 在 Windows runner 上重新构建前端、工作台 wheel 和最终 ZIP；
- `VERIFY.bat` 对 42 个文件逐一执行 SHA-256 校验；
- 设置 `PIP_NO_INDEX=1` 后执行 `INSTALL.bat`，完成 runtime 解压、venv 创建和 30 个 wheel 的离线安装；
- 安装后依据 `bundle-info.json` 确认行业实验台 `0.3.0` 与 CASCAQit `1.0.5a0`；
- 通过 `RUN.bat` 启动已安装程序并取得健康响应；
- 确认金融、生物医药、材料科学三个领域，并逐一请求六个生物医药和两个材料场景的结构分析接口；
- 对工作台 wheel 中 35 个 fixture artifact 逐一复算 manifest SHA-256，结果为 0 个不一致；
- Windows runner 上传的 ZIP 下载后再次通过压缩结构、内容身份和 SHA-256 复核。

同一构建基线的 Chromium 验收 run `30620921420` 已通过八场景主流程和材料场景隔离流程：

<https://github.com/CASColdAtom/cascaqit-industry-workbench/actions/runs/30620921420>

## 质量门禁

- Ruff：通过；
- 项目身份、Windows 打包与统一领域 API：`55 passed`；
- 前端类型检查：通过；
- React：`59 passed`；
- React 生产构建：通过；
- Python wheel：`cascaqit_industry_workbench-0.3.0-py3-none-any.whl` 构建通过；
- 完整 Python 套件：`332 passed, 2 failed`。两项失败是 docking Hybrid 固定 seed `11`、`17` 的候选可行性断言，未涉及本次项目身份、文档、安装器或 Windows 制品路径；Windows 与 Chromium 发布场景均通过。

## 构建加固

- `bundle-info.json.industry_workbench` 是安装器和 Windows CI 的版本事实源，不在 PowerShell 或 workflow 中重复硬编码工作台版本。
- Windows workflow 使用当前仓库上下文定位历史依赖缓存，仓库更名后无需修改组织与仓库 URL。
- 打包器在生成工作台 wheel 后立即审计全部 fixture manifest 和 artifact，换行或内容漂移会直接终止构建。
- Windows 缓存会排除 CASCAQit、新工作台和旧金融项目 wheel，只复用第三方依赖与已验签 runtime。
- BAT 固定为 ASCII + CRLF，PowerShell 固定为 UTF-8 BOM + CRLF。
- runtime 上游归档和 SDK wheel 均使用固定 SHA-256；wheelhouse 在打包时执行 Windows marker 依赖闭包审计。

完整构建、验收、发布与回滚步骤见 [Windows 离线发布手册](windows_offline_release_playbook.md)。
