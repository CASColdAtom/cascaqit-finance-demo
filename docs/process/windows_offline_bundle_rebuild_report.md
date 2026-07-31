# Windows 离线包构建与发布报告

## 交付结果

行业量子实验台 `0.2.1` 已生成 Windows 10/11 x64 离线安装包：

```text
offline/cascaqit-finance-demo-windows-x64-py311.zip
```

GitHub Release：

<https://github.com/CASColdAtom/cascaqit-finance-demo/releases/download/v0.2.1/cascaqit-finance-demo-windows-x64-py311.zip>

目标机器不需要联网、管理员权限、系统 Python、Node.js 或编译器。解压后依次运行 `VERIFY.bat`、`INSTALL.bat` 和 `RUN.bat`；服务默认打开 `http://127.0.0.1:8000`。

## 制品身份

| 项目 | 值 |
|---|---|
| 构建基线 | `037119c9e05b130c99bd5af55ce80745eeedd413` |
| 目标环境 | Windows 10/11 x64 |
| Python runtime | 可重定位 CPython `3.11.9` |
| 行业实验台 | `cascaqit-finance-demo==0.2.1` |
| CASCAQit | `cascaqit==1.0.5a0` |
| CASCAQit wheel SHA256 | `af665bcd8dc81d7afe1370c1acee656dcc3192b63552429692655dc0159ee97e` |
| wheel 数 | 30 |
| manifest 文件数 | 42 |
| ZIP 大小 | `95,010,380` 字节 |
| ZIP SHA256 | `2963b7b413c9310fea42c7faa138ca842cce1cf53e57205f85200dc20da1ac34` |

包内包含完整 React 生产资源、金融场景、六个生物医药场景和两个材料场景。CASCAQit 使用仓库内固定 wheel，不再依赖相邻源码仓库的分支状态；许可证从 wheel 的标准 license 目录进入交付包。

## Windows 验收

GitHub Actions `windows-2022` run `30616731109` 已完成真实 Windows 全链路验收：

<https://github.com/CASColdAtom/cascaqit-finance-demo/actions/runs/30616731109>

已通过项目：

- 在 Windows runner 上重新构建前端、Demo wheel 和最终 ZIP；
- `VERIFY.bat` 对 42 个文件逐一执行 SHA-256 校验；
- 设置 `PIP_NO_INDEX=1` 后执行 `INSTALL.bat`，完成 runtime 解压、venv 创建和 30 个 wheel 的离线安装；
- 安装后确认行业实验台 `0.2.1` 与 CASCAQit `1.0.5a0`；
- 安装器内置的金融结算场景 smoke 执行通过；
- 通过 `RUN.bat` 启动已安装程序并取得健康响应；
- 确认金融、生物医药、材料三个行业域，并逐一请求 6 个生物医药和 2 个材料场景的结构分析接口；
- 对 Demo wheel 中 35 个 fixture artifact 逐一复算 manifest SHA-256，结果为 0 个不一致；
- Windows runner 上传的 ZIP 下载后再次通过压缩结构和 SHA-256 复核。

同一 UI 发布基线的八场景 Chromium 验收 run `30613853589` 也已通过：

<https://github.com/CASColdAtom/cascaqit-finance-demo/actions/runs/30613853589>

## 构建加固

- `0.2.0` 的 Windows checkout 将 fixture JSON 从 LF 转换为 CRLF，造成内容语义未变但字节 SHA-256 失配；`0.2.1` 通过 `.gitattributes` 固定 JSON 为 LF。
- 打包器在生成 Demo wheel 后立即审计全部 fixture manifest 和 artifact，换行或内容漂移会直接终止构建。
- 打包器默认使用 `vendor/cascaqit-1.0.5a0-py3-none-any.whl`，同时保留显式 `--sdk-wheel` 和 `--sdk-root` 入口。
- Windows 下通过 PATH 解析 `npm.cmd` 等命令 shim，避免 Python `subprocess` 直接调用失败。
- 完整性脚本使用 .NET SHA-256，不依赖可能未加载的 `Get-FileHash` cmdlet。
- BAT 固定为 ASCII + CRLF，PowerShell 固定为 UTF-8 BOM + CRLF。
- runtime 上游归档和 SDK wheel 都使用固定 SHA-256；wheelhouse 在打包时执行 Windows marker 依赖闭包审计。
- Demo wheel 不包含 source map；客户界面禁用话术扫描为零。

## 支持边界

当前交付目标是 Windows 10/11 x64，不支持 Windows ARM64、32 位 Windows 或 Windows 7。运行数据只写入解压目录，服务默认只监听本机回环地址；移动整个目录后，启动器会在需要时重建失效的隔离环境。
