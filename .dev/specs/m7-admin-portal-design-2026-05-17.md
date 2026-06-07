# M7 管理后台 — 设计规范

> **日期**：2026-05-17 | **更新**：2026-06-07 (Phase 3)
> **依赖**：M8 (00100), contracts/ (00010)
> **定位**：Layer 4 (UI)，管理员配置中心

---

## 1. 模块定位

M7 是管理员门户。通过 M8 API 管理 LLM 后端、系统配置、用户、API Key、知识图谱浏览和系统监控。

**核心原则**：
- **全部配置通过 UI** — 零 deploy.yaml 编辑
- **实时生效** — 配置变更热重载到运行中的服务
- **5 语种 i18n** — 与 M6 共享基础设施

---

## 2. 技术栈

| 组件 | 选型 |
|------|------|
| 框架 | Next.js 14+ (App Router) |
| UI | Tailwind CSS + shadcn/ui |
| 图表 | D3.js (力导向图) |
| i18n | next-intl (5 语种) |
| API | M8 REST API (localhost:8000) |

---

## 3. 页面清单

| 页面 | 路径 | Phase 2 | Phase 3 |
|------|------|:--:|:--:|
| 概览仪表板 | `/admin` | ✅ | — |
| 文档管理 | `/admin/documents` | ✅ | — |
| LLM 配置 | `/admin/llm-config` | ✅ | 对接真实 API |
| 知识图谱 | `/admin/knowledge-graph` | ✅ | +D3.js 图形 |
| 用户管理 | `/admin/users` | ✅ | +API Key 对话框 |
| 系统配置 | `/admin/config` | — | ✅ 新增 |
| 系统监控 | `/admin/monitoring` | ✅ | — |
| 系统设置 | `/admin/settings` | ✅ | — |

## 4. 认证

`AuthGuard` 组件要求输入 M8 API Key 才能访问任何管理页面。Key 存储在 sessionStorage。Phase 3 从硬编码凭证升级为真实 M8 auth。

---

*设计规范结束。*
