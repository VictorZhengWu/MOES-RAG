# M6 用户前端 — 设计规范

> **日期**：2026-05-13 | **更新**：2026-06-07 (Phase 3)
> **依赖**：M8 (00100), Mock Server (00020)
> **定位**：Layer 4 (UI)，最终用户问答交互门户

---

## 1. 模块定位

M6 是面向最终用户的 Web 界面。提供自然语言问答、文档上传、会话管理、社交登录和个性化设置。

**核心原则**：
- **OpenAI 兼容接口** — 调用 M8 `/v1/chat/completions`，零代码切换后端
- **流式响应** — SSE 逐 token 展示，即时反馈
- **5 语种 i18n** — URL 路由 + 即时切换，零硬编码
- **拖放上传** — 浏览器任意位置拖 PDF，即时解析入库

---

## 2. 技术栈

| 组件 | 选型 |
|------|------|
| 框架 | Next.js 14+ (App Router) |
| UI | Tailwind CSS + shadcn/ui |
| 状态管理 | Zustand (auth, chat, conversation stores) |
| i18n | next-intl (en/zh/ko/ja/no) |
| 流式 | SSE (EventSource + ReadableStream) |
| 测试 | Playwright (9 tests) |

---

## 3. 页面与组件

### 3.1 页面

| 页面 | 路径 | 说明 |
|------|------|------|
| 聊天主页 | `/chat` | 核心问答界面 |
| 登录 | `/login` | 邮箱 + OAuth 按钮 |
| 注册 | `/register` | 邮箱注册 |
| OAuth 回调 | `/auth/callback` | 接收 M8 返回的 API Key |
| 分享查看 | `/shared/:token` | 公开只读 |

### 3.2 核心组件

| 组件 | 功能 |
|------|------|
| `ChatInput` | 文本输入 + 文件附件 + Web Search 开关 + 发送/停止 |
| `ChatMessage` | 消息气泡、Markdown 渲染、引用标记 |
| `ConversationSidebar` | 会话列表、搜索、新建、右键菜单（重命名/分享/Pin/删除/移入项目） |
| `ConversationSearch` | 服务端关键词过滤 |
| `ShareDialog` | 生成分享链接 → 复制到剪贴板 |
| `LoginForm` / `RegisterForm` | 邮箱密码 + 前端校验 |
| `SocialButtons` | 6 个 OAuth Provider 图标 → 重定向到 M8 |
| `ProfileTab` | 头像上传、用户名/邮箱显示 |
| `SettingsDialog` | 语言、主题 (Light/Dark/System) |
| `AuthGuard` | 未登录时重定向到 login 页 |

---

## 4. 数据流

```
M6 → M8 (8000)
  POST /v1/chat/completions       → SSE 流式问答
  GET  /api/v1/conversations      → 会话列表
  PATCH /api/v1/conversations/:id → 重命名
  DELETE /api/v1/conversations/:id → 删除
  POST /api/v1/conversations/:id/share → 分享
  PATCH /api/v1/conversations/:id/pin → Pin
  POST /api/v1/documents/upload   → 文件上传
  POST /auth/register             → 注册
  POST /auth/login                → 登录
  GET  /auth/oauth/login?provider= → OAuth
  POST /api/v1/user/avatar        → 头像上传
```

---

## 5. Phase 3 后端对接

| 占位 ID | 功能 | Phase 2 | Phase 3 |
|---------|------|:--:|:--:|
| P1 | 邮箱登录 | Mock | ✅ M8 auth |
| P2 | 邮箱注册 | Mock | ✅ M8 auth |
| P3 | 社交登录 (6 provider) | console.log | ✅ M8 OAuth |
| P4 | 会话历史 | Mock 3 条 | ✅ M5 API |
| P5 | 重命名 | Mock | ✅ M5 API |
| P6 | 删除 | Mock | ✅ M5 API |
| P7 | 分享 | alert() | ✅ M8 share |
| P8 | Move to Project | console.log | ✅ M8 projects |
| P9 | Pin | console.log | ✅ M8 pin |
| P10 | 文件上传 | UI 就绪 | ✅ M1→M2→M8 |
| P11 | 头像上传 | console.log | ✅ M8 avatar |
| P12 | Web Search | 开关 UI | ✅ M5 search |
| P17 | 删除账号 | disabled | ✅ M8 delete |

---

*设计规范结束。*
