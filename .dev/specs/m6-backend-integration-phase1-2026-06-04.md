# M6 Backend Integration Phase 1 — M8 Conversation Routes

> **日期**：2026-06-04 | **状态**：进行中
> **依赖**：M5 (00090), M8 (00100)
> **目标**：给 M8 补 `/api/v1/conversations` 路由，解锁 M6 的会话历史/重命名/删除功能

---

## 1. 背景

M6 前端已完美对接 M8：

```
M6 client.ts → BASE_URL = http://127.0.0.1:8000 (M8端口)
M6 client.ts → Authorization: Bearer <token> (M8格式)  
M6 chat.ts  → POST /v1/chat/completions ✅
M6 conversations.ts → GET/DELETE/PATCH /api/v1/conversations ❌ 路由缺失
```

M5 已有对话管理方法，但未通过 M8 暴露。

---

## 2. 需要做的事情

### 2.1 M5 补充 `rename_conversation` 方法

当前 M5 `ConversationManager` 缺少 `rename_conversation`。M6 前端调用 `PATCH /api/v1/conversations/:id {title}`。

### 2.2 M8 新增 conversation 路由

```
GET    /api/v1/conversations          → M5 list_conversations()
GET    /api/v1/conversations/:id      → M5 get_conversation()
DELETE /api/v1/conversations/:id      → M5 delete_conversation()
PATCH  /api/v1/conversations/:id      → M5 rename_conversation()
```

### 2.3 鉴权

所有 conversation 路由使用 M8 现有的 `get_api_key` 中间件——同一个 `sk-m8-xxx` key。

---

## 3. 解锁的 M6 占位功能

| ID | 功能 | M6 前端代码 | 后端 API | 状态 |
|----|------|-----------|---------|:--:|
| P4 | 会话历史持久化 | `listConversations()` 已调用 | `GET /api/v1/conversations` | 待对接 |
| P5 | 会话重命名 | `renameConversation()` 已调用 | `PATCH /api/v1/conversations/:id` | 待对接 |
| P6 | 会话删除 | `deleteConversation()` 已调用 | `DELETE /api/v1/conversations/:id` | 待对接 |

---

## 4. 实现清单

1. M5 `ConversationManager` 加 `rename_conversation(conv_id, title)` 方法
2. M5 `QAEngine` 加 `rename_conversation()` 桥接
3. M8 新增 `routes/conversations.py` — 4 个端点
4. M8 `app.py` 注册 conversations router
5. 测试：M5 3 个 + M8 4 个 = 7 个测试

---

*设计结束。开始实现。*
