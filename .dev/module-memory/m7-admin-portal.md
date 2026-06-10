# M7 — Admin Web Portal 模块记忆

> **Purpose**: Record all development sessions, decisions, gotchas, and lessons learned for M7. Read this file before starting ANY new M7 development session.

---

## 1. Module Status

| Field | Value |
|-------|-------|
| Status | ✅ Core Pages Complete |
| Active Tasks | 00040 + 7 placeholders |
| First Dev Date | 2026-05-16 |
| Last Session Date | 2026-05-17 |
| Total Sessions | 2 |
| Playwright Tests | 13/13 passing |

---

## 2. Session History

### 会话 #1 — 2026-05-16: Phase C-1 完成
**完成内容**：
- Next.js 16 项目脚手架（m7-admin-portal/）
- shadcn/ui Radix/Nova + 16 组件
- next-intl 4.x + 5 语种文件 + admin 专用 en.json
- 管理后台类型定义（DocumentRecord, LLMBackend, AdminUser, SystemStats 等）
- API 客户端层（documents, llm-config, users, monitoring）
- Zustand admin-store
- [locale] 路由 + 布局 + 占位页面

**关键决策**：
- D001: M7 复用 M6 的技术栈模式（Next.js 16 + shadcn/Nova + next-intl + Zustand）
- D002: M7 使用独立端口 3000（M6 不运行时），与 M6 共享 Mock Server（8000/8002）
- D003: 管理后台翻译 key 使用 `admin.*` 前缀，区分于 M6 的 `chat.*`
- D004: API 客户端与 M6 共用模式（apiGet/apiPost/apiDelete），连同一个 Mock Server
- D005: 需补 [locale] 路由——C-1 只建了根布局，缺 [locale]/layout.tsx 导致所有页面 404

**遗留问题**：
- ⚠️ 4 个非英语 locale 文件仍是英文占位（zh/ko/ja/no 待翻译）
- ⚠️ middleware.ts 使用 deprecated 模式，后续需迁移到 proxy.ts

---

## 3. Key Design Decisions (Module-Internal)

| ID | 决策 | 原因 |
|----|------|------|
| D001 | 复用 M6 技术栈 | 一致性强，shadcn/Nova 已踩过坑 |
| D002 | 独立 Next.js 项目 | 与 M6 完全解耦，独立部署 |
| D003 | 管理后台用 admin.* 前缀 | 避免与 M6 chat.* 翻译冲突 |
| D004 | API 客户端共享模式 | apiGet/apiPost 与 M6 实现完全相同 |
| D005 | [locale] 路由必须有 | 否则 i18n 中间件无法找到对应布局 → 404 |

---

## 4. Known Pitfalls & Gotchas

1. ❌ **缺少 [locale]/layout.tsx = 全面 404**：`NextIntlClientProvider` 必须在 [locale] 布局中提供，否则 next-intl 中间件路由正常但无渲染出口。
2. ❌ **Base UI 不支持 `asChild`**：同 M6，DropdownMenuTrigger、TooltipTrigger 等不能用 asChild。
3. ⚠️ **middleware → proxy**：Next.js 16 标记 middleware.ts 为 deprecated。
4. ⚠️ **shadcn toast → sonner**：toast 组件已废弃。

---

## 5. Interface Contract Deviations

- 无（目前仅调用 Mock Server 的 admin 端点，与 contracts/ 定义一致）

---

## 6. Performance Notes

- Config page: ~200ms load (single fetch to M8 for features + SMTP)
- Monitoring page: 30s auto-refresh, initial load ~500ms (health + monitoring fetch)
- Auth guard: sub-millisecond sessionStorage check, ~200ms API key validation on login

---

## 7. Development Status

### All Core Pages: ✅ Complete (2026-05-17)

### Pending Features Status

| ID | 功能 | 状态 |
|----|------|------|
| 00040-P1 | 付款/计费模块 | ⏸️ 需 Stripe + M5 Billing API |
| 00040-P2 | 部署 feature 开关 | ✅ 已对接 M8 features API，按 deployMode 显隐 |
| 00040-P3 | 忘记密码/重置密码 (admin) | ⏸️ M8 API 就绪，M7 UI 未实现 |
| 00040-P4 | 社交登录 OAuth 配置 | ✅ OAuth 标签页已完整实现 |
| 00040-P5 | KG 可视化 (D3.js) | ⏸️ 独立前端大工程 |
| 00040-P6 | 系统监控真实数据 | ✅ 已对接 M8 `/admin/monitoring`，30s 自动刷新 |
| 00040-P7 | 管理员登录保护 | ✅ `auth-guard.tsx` → M8 `/auth/admin-login` |

---

## 8. New Session Recovery Checklist

新会话开始 M7 开发时，按顺序读取：

1. `.dev/specs/rag-system-design-2026-05-12.md` — 架构总览
2. `.dev/decisions.md` — 全局决策
3. `.dev/tasks.md` — 任务状态（00040 已完成）
4. `.dev/module-memory/m7-admin-portal.md` — 本文件
5. `.dev/plans/plan-c-m7-admin-portal-2026-05-16.md` — M7 详细实现计划

然后启动开发：
```bash
cd E:\myCode\RAG\m7-admin-portal
npm run dev                # → http://localhost:3000
```

Mock Server（如需测试 API）：
```bash
cd E:\myCode\RAG
python -c "from mock_server.app import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8002)"
```

M6 用户端（如同时开发）：
```bash
cd E:\myCode\RAG\m6-user-portal
set NEXT_PUBLIC_API_URL=http://127.0.0.1:8002
npm run dev                # → http://localhost:3001
```
