# Problem 映射旧前端热修复报告

## 结果

`Problem 映射` 点击后读取未定义数组 `.length` 的白屏问题已在当前前端修复。组件对旧分析响应缺少的 term group、几何证据和系数账本字段使用空数组或明确默认值，旧接口数据不会再中断整页渲染。

本次排查中的浏览器堆栈来自旧资源 `Views-CkQA8AS5.js`，当前服务提供的是 `Views-C4OLICMT.js`。为避免服务升级后入口 HTML 继续引用旧 chunk，FastAPI 现在对 `/` 和 `/index.html` 返回 `Cache-Control: no-store`、`Pragma: no-cache` 和过期时间 `0`。内容带哈希的 JavaScript 文件仍可正常缓存。

已经打开的旧页面不会自动替换内存中的 JavaScript，需要强制刷新一次。刷新后，后续重新打开页面会读取当前入口。

## 验证

- 旧分析响应点击 `Problem 映射` 的 React 回归测试通过。
- 前端 18 项测试、TypeScript 检查和生产构建通过。
- 入口缓存响应头集成测试覆盖 `/` 与 `/index.html`。
- Python 全量测试 125 项通过，Ruff 检查通过。

全量测试同时发现并修正 Python 3.11.14 标准 `tarfile` 过滤器与项目归档安全契约的差异。Windows runtime 解包现在在所有 Python 版本上先拒绝绝对路径、目录穿越和非普通成员，再按运行版本调用标准过滤解包或兼容解包。
