# M6/M7 开发会话总结

> **日期**：2026-05-12 ~ 2026-05-17 | **Phase 1 前端骨架完成**

---

## 整体进度

| 模块 | 状态 | 核心功能 | 占位功能 | Playwright |
|------|------|---------|---------|-----------|
| M6 | 🔄 | 11 项 | 21 项 | 9/9 |
| M7 | ✅ | 6 页管理后台 | 7 项 | 13/13 |
| Mock Server | ✅ | 独立模块 | — | 21/21 |
| contracts/ | ✅ | 45 符号导出 | — | 23/23 |

---

## M6 已实现功能

- 聊天界面（消息气泡 + Markdown + 流式 + 停止）
- 引用面板（右侧第三列滑出）
- 可折叠侧边栏（展开/图标条双态）
- 5 语种 i18n（URL 路由 + Settings 中管理 + 即时切换）
- 主题切换（Light/Dark/System）
- 跳转窄条（固定定位横线 + 悬停列表框 + 滚动同步）
- 登录/注册页（表单校验 + 社交登录 6 按钮）
- Settings（General/Profile/About 三标签）
- 知识库浏览（搜索 + 船级社/专业筛选）
- 全局拖放上传（覆盖层 + 文件图标显示）
- 会话右键菜单（Share/Rename/Move/Pin/Delete）
- 消息复制按钮 + 👍👎反馈 + Follow-up 建议

## M6 待完善（21 项占位）

详见 `.dev/tasks.md` 00030-P1 至 P21

## M7 已实现功能

- Dashboard（统计卡片 + 模块健康 + 存储/延迟）
- 文档管理（文件名正则解析上传 + 批量 + 列表/筛选/删除 + 排序列宽可调）
- 知识图谱（Entities/Relations/Cross-Reference + 编辑/删除）
- LLM 配置（7 框固定页面 + Purpose + 角色权限标签）
- 用户管理（列表/创建/停用激活/社交标签/管理员分组/防自禁用 + 排序列宽可调）
- 系统监控（模块健康 + 指标 + 日志）
- Settings（语言下拉 + 主题切换）
- 可折叠侧边栏 + 管理员登录保护（3 个账密）
- 5 语种完整翻译

## M7 待完善（7 项占位）

详见 `.dev/tasks.md` 00040-P1 至 P7

---

## 关键技术决策记录

| 日期 | 决策 | 原因 |
|------|------|------|
| 05-12 | Next.js 16 + React 19 | 最新稳定版 |
| 05-12 | shadcn/ui Radix/Nova | 官方预设，@base-ui/react 替代旧 @radix-ui |
| 05-12 | next-intl 4.x 需 Plugin | `createNextIntlPlugin()` 必须注册 |
| 05-13 | 引用面板纯 CSS | Sheet 的 backdrop blur 不可接受 |
| 05-13 | 侧边栏图标条 | 不完全隐藏，保留快捷入口 |
| 05-14 | 语言切换移入 Settings | DeepSeek 风格 |
| 05-15 | 跳转窄条 fixed 定位 | 始终在视口居中 |
| 05-15 | 横线+列表框一体 | 展开时横线嵌入盒子右边缘 |
| 05-16 | LLM 7 框 + Purpose 字段 | 按用途分配模型 |
| 05-16 | 文件名正则解析上传 | 免维护目录对照表 |
| 05-16 | USER_ROLES 配置化 | 非硬编码，可扩展层级 |
| 05-17 | M7 Auth Guard | localStorage + 多账密 |
| 05-17 | KG 手动修正 | 编辑名称 + 删除实体/关系 |

---

## 已知代码坑位

1. **Base UI 不支持 `asChild`** — 所有 Trigger 组件直接包裹子元素
2. **i18n key 缺失 = 应用崩溃** — 新增 key 必须同时更新全部 5 个 locale
3. **`top:50%` + `translateY` + `marginTop` 冲突** — 只用前两者
4. **middleware → proxy** — Next.js 16 标记 deprecated
5. **shadcn toast → sonner** — toast 组件已废弃
6. **DialogDescription = `<p>`** — 不能嵌套 `<p>` 或 `<div>`
7. **M6 M7 .env.development 端口 8003** — 系统占用 8000, Mock 用 8003

---

## 下一阶段开发路径

1. **Phase 2 后端**：M2（存储抽象）→ M1（文档解析）→ M3（检索）→ M4（KG）→ M5（问答引擎）
2. **Phase 3**：M8（API 网关）→ deploy/（部署配置）
3. **M6/M7 占位功能**：随 M5 就绪后逐个接入真实 API

---

## 快速恢复开发

```bash
# 终端 1：Mock Server
cd E:\myCode\RAG
python -c "from mock_server.app import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8003)"

# 终端 2：M6 用户端
cd E:\myCode\RAG\m6-user-portal
npm run dev   # → http://localhost:3000

# 终端 3：M7 管理后台
cd E:\myCode\RAG\m7-admin-portal
npm run dev   # → http://localhost:3001
```

M7 管理员：`admin`/`admin123` · `editor`/`editor123` · `victor`/`victor123`

M6 用户端：任意邮箱 + 8 位密码即可登录
