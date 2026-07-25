# v0.1.1 发布验收报告

## 发布范围

本次发布冻结现有七个金融场景及其 Digital、Hybrid、Analog 执行链，不再加入新的交互或算法能力。最后一项功能改动是衍生品九格压力重估：绝对 P&L 生成 MWIS 权重，权重进入 Analog 局域失谐，近邻边进入 Rydberg interaction。

Git 仓库发布源码和随 Python wheel 安装的 React 生产构建，不提交 Windows runtime、wheelhouse 或离线压缩包。Windows 10/11 x64 离线包作为独立 Release 资产发布，内含 CPython 3.11.9、CASCAQit `1.0.7a0`、Finance Demo `0.1.1` 和全部运行依赖。

## 发布门禁

| 检查 | 结果 |
|---|---|
| Python 全量测试 | `134 passed` |
| React 测试 | `20 passed` |
| Ruff | 通过 |
| TypeScript | 通过 |
| React 生产构建 | 通过 |
| npm 依赖审计 | 0 vulnerabilities |
| 文档风格检查 | 19 个 Markdown 文件，0 warnings |
| Python sdist 与 wheel | 构建通过 |
| wheel 内容 | 40 个文件，包含最新 React 静态资源 |
| 安装后首页与 API | 首页、7 个场景目录和衍生品 Analog 运行通过 |
| Chrome 页面烟雾检查 | `1440 x 900` 页面完整渲染，无明显重叠或空白图表 |
| Windows wheel 闭包 | 29 个 wheel，目标平台依赖审计通过 |
| Windows 离线包 | 41 项 manifest 和 ZIP 压缩结构检查通过 |

安装后烟雾验证使用 CASCAQit `1.0.7a0` 和 Finance Demo `0.1.1`。衍生品请求返回 Analog 模式，8 次末端采样计数守恒。

## 已知边界

- 当前执行来自本地模拟器，不是量子硬件或云端结果。
- ECharts 生产 chunk 约 669 kB，构建工具会给出体积提示，但不影响离线加载和当前功能。
- Windows 离线包已发布并完成构建侧校验，仍需在目标 Windows 机器验证 BAT、PowerShell、DLL 加载、浏览器启动和目录移动后的重复安装。
- 当前结果不构成投资、清算、风控、授信或定价建议，也不用于证明量子优势。
