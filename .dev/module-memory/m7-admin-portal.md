# M7 — Admin Web Portal 模块记忆

> **Purpose**: Record all development sessions, decisions, gotchas, and lessons learned for M7. Read this file before starting ANY new M7 development session.

---

## 1. Module Status

| Field | Value |
|-------|-------|
| Status | 🔄 In Development (Phase C-1 done) |
| Active Tasks | 00040 |
| First Dev Date | 2026-05-16 |
| Last Session Date | 2026-05-16 |
| Total Sessions | 1 |
| Playwright Tests | 0 (not yet set up) |

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

- 待记录

---

## 7. Development Roadmap

### Phase C-1: ✅ Complete (2026-05-16)
- C1: Scaffold ✅
- C2: i18n ✅
- C3: Types ✅
- C4: API client + Store ✅

### Phase C-2: Next (待开始)
- C5: AdminLayout + AdminSidebar（6 个导航项 + 侧边栏）

### Phase C-3: Core Pages (待开始)
- C6: Dashboard
- C7: Document Management
- C8: Knowledge Graph Browser
- C9: LLM Config
- C10: User Management
- C11: System Monitoring

### Phase C-4: Test & Wrap-up (待开始)

---

## 6.5 Pending Features (Recorded for Future)

| ID | 功能 | 说明 |
|----|------|------|
| 00040-P1 | 付款/计费模块 | SaaS 模式专属，deploy.yaml features.billing 控制显隐 |
| 00040-P2 | 部署模式 feature 开关 | deploy.yaml → 控制 billing/web_search/deep_research |
| 00040-P3 | 忘记密码/重置密码 | M6 登录页 + M7 用户管理 → SMTP 邮件服务 |
| 00040-P4 | 社交登录 OAuth | 6 按钮 UI 就绪 → Phase 2 接真实 OAuth |
| 00040-P5 | KG 可视化（图形版） | D3.js/vis.js → 真实 KG 数据 |
| 00040-P6 | 系统监控真实数据 | Phase 2 接 M5 Monitoring API |
| 00040-P7 | 管理员登录保护 | 当前无鉴权 → Phase 2 加 Auth Guard |

### Phase C-4: Test & Wrap-up (待开始)
- C12: Playwright E2E
- C13: Translations
- C14: Wrap-up

---

## 8. New Session Recovery Checklist

新会话开始 M7 开发时，按顺序读取：

1. `docs/superpowers/specs/rag-system-design-2026-05-12.md` — 架构总览
2. `.dev/decisions.md` — 全局决策
3. `.dev/tasks.md` — 任务状态（00040 待开始）
4. `.dev/module-memory/m7-admin-portal.md` — 本文件
5. `docs/superpowers/plans/plan-c-m7-admin-portal-2026-05-16.md` — M7 详细实现计划

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
