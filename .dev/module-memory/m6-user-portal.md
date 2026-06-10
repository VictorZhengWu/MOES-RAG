# M6 — User Web Portal 模块记忆

> **Purpose**: Record all development sessions, decisions, gotchas, and lessons learned for M6. Read this file before starting ANY new M6 development session.

---

## 1. Module Status

| Field | Value |
|-------|-------|
| Status | 🔄 In Development (core UI done, 18 placeholders) |
| Active Tasks | 00030 |
| First Dev Date | 2026-05-12 |
| Last Session Date | 2026-05-16 |
| Total Sessions | ~8 |
| Playwright Tests | 9/9 passing |

---

## 2. Session History

### 会话 #1-2 — 2026-05-12: 项目脚手架 + i18n 架构
**完成内容**：Next.js 16 + shadcn/ui (Radix/Nova) + next-intl 4.x + 5 语种资源文件 + TypeScript 类型定义
**关键决策**：
- D001: 选 Next.js 16 (App Router) + React 19，弃 Vue 3
- D002: shadcn/ui 使用 Radix/Nova 预设（注：shadcn v4 改用 @base-ui/react，非旧版 @radix-ui/react）
- D003: next-intl 4.x 需在 next.config.ts 注册 `createNextIntlPlugin()`，否则 `getMessages()` 报错
- D004: `usePathname()` 返回含 locale 的完整路径 `/en/chat`，非去掉前缀的路径

### 会话 #3-5 — 2026-05-13: 核心聊天功能
**完成内容**：消息气泡、流式输出、引用面板、侧边栏、聊天输入框
**关键决策**：
- D005: 引用面板用纯 CSS 滑出面板，不用 shadcn/ui Sheet（Sheet 总是渲染 backdrop overlay，会模糊内容区）
- D006: 侧边栏折叠态改为 56px 图标条，不完全隐藏
- D007: API 客户端默认连 `http://127.0.0.1:8000`，通过 `NEXT_PUBLIC_API_URL` 覆盖

### 会话 #6-7 — 2026-05-14: 设置、登录、知识库
**完成内容**：Settings 对话框（General/Profile/About）、登录/注册表单、知识库浏览
**关键决策**：
- D008: 语言切换从 header 移到 Settings > General（DeepSeek 风格）
- D009: 社交登录按钮用内联 SVG 图标（无额外依赖）
- D010: 登录后 redirect 参数传递原始 URL，避免丢失当前页面

### 会话 #8-9 — 2026-05-15: 跳转窄条重做
**完成内容**：DeepSeek 风格跳转窄条，经历 4 轮重做才达到用户要求
**关键决策**：
- D011: 跳转窄条用 fixed 定位（非 absolute），始终在视口居中
- D012: 横线和列表框为一体——打开时横线嵌入盒子右边缘
- D013: 横线间距固定 25px，不随问题数量变化

### 会话 #10-11 — 2026-05-16: 会话菜单、分享、拖放上传
**完成内容**：会话 "..." 菜单、Projects 按钮、Share 对话框、全局拖放上传
**关键决策**：
- D014: 文件附件通过 chatStore.attachedFiles 全局管理
- D015: 全局拖放用 window 级别 dragenter/dragleave 事件（含 dragCounter 防闪烁）

---

## 3. Key Design Decisions (Module-Internal)

| ID | 决策 | 原因 |
|----|------|------|
| D001 | Next.js 16 + React 19 | 最新稳定版，Server Components 性能好 |
| D002 | shadcn/ui Radix/Nova | 官方预设，组件库最新 |
| D003 | next-intl 需要 plugin | `createNextIntlPlugin()` 必须注册在 next.config.ts |
| D004 | usePathname 含 locale | 返回 `/en/chat` 完整路径 |
| D005 | 纯 CSS 引用面板 | Sheet 的 backdrop blur 无法接受 |
| D006 | 侧边栏图标条 | 不完全隐藏，保留快捷入口 |
| D011 | 跳转窄条 fixed | 不随滚动移动，始终可见 |
| D012 | 横线+列表框一体 | 展开时横线嵌入盒子右边缘 |
| D014 | chatStore 管理附件 | 全局状态，各组件共享 |

---

## 4. Known Pitfalls & Gotchas

1. ❌ **i18n key 缺失 = 整个应用崩溃**：next-intl 的 `t('missing.key')` 会抛出 `MISSING_MESSAGE` 异常，导致 React 树崩溃。新增 key 必须同时更新全部 5 个 locale 文件。
2. ❌ **Base UI 不支持 `asChild`**：shadcn v4 使用 @base-ui/react，不支持 Radix 的 `asChild` 属性。DropdownMenuTrigger、TooltipTrigger 等直接包裹子元素即可。
3. ❌ **`top:50%` + `translateY(-50%)` + `marginTop` 冲突**：同时使用会导致双重偏移，hit 区域错位。
4. ⚠️ **Next.js 16 middleware → proxy**：middleware.ts 已被标记 deprecated，后续需迁移到 proxy.ts。
5. ⚠️ **shadcn toast → sonner**：shadcn v4 已废弃 toast 组件，改用 sonner。

---

## 5. Interface Contract Deviations

- 用户消息新增 `attachments?: FileAttachment[]` 字段（contracts/qa_engine.py 的 Message 目前无此字段，后续需同步）
- 聊天请求新增 `web_search?: boolean` 字段（contracts 中 ChatRequest 目前无此字段）

---

## 6. Performance Notes

- 首屏加载：cold start ~4s（Next.js Turbopack 编译），warm ~200ms
- 流式渲染：SSE 解析稳定，30-80ms 令牌延迟模拟
- Bundle 大小：未优化，后续需分析

---

## 7. Open Issues

### 已完成对接（18 项，2026-06-09 验证）

| 功能 | 状态 | 对接方式 |
|------|------|---------|
| P1-P2 邮箱登录/注册 | ✅ | `auth.ts` → M8 `/auth/login` `/auth/register` |
| P3 社交登录 OAuth | ✅ | `social-buttons.tsx` → M8 `/auth/oauth/login?provider=` |
| P4-P9 会话 CRUD/分享/Pin | ✅ | `conversation-store.ts` → M8 `/api/v1/conversations/*` |
| P10/P21 文件上传/存储 | ✅ | `chat-input.tsx` → `uploadDocuments()` → M8 → M1 |
| P11 头像上传 | ✅ | `profile-tab.tsx` → M8 `/api/v1/user/avatar` |
| P12 Web Search | ✅ | `chat-input.tsx` 传 `web_search` 参数到 chat API |
| P14 会话搜索 | ✅ | `conversation-sidebar.tsx` 传 `searchQuery` 到 `fetchConversations()` |
| P16 Help 页面 | ✅ | `help/page.tsx` + sidebar 导航 |
| P17 Delete Account | ✅ | `profile-tab.tsx` 确认对话框 → `deleteAccount()` |
| P18 About 链接 | ✅ | 静态配置 |
| P19 忘记/重置密码 | ✅ | `forgot-password-form.tsx` + `reset-password-form.tsx` → M8 |

### 延后（需 M5 新 API）

| 功能 | 依赖 |
|------|------|
| P8 Move to Project | M5 Project API |
| P13 Deep Research | M5 Agent 流程 |
| P15/P20 Projects CRUD | M5 Project API |
