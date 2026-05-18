# Plan C: M7 管理后台 — 实现规划

> **给执行者**：按 Task 顺序逐项执行。使用 `- [ ]` 复选框追踪进度。

**目标**：构建 Marine & Offshore Expert System 的管理后台——管理员通过 Web 界面完成文档上传与解析管理、知识库管理、知识图谱可视化浏览、LLM 多后端配置、用户与配额管理、系统监控等全部操作。

**架构**：独立的 Next.js 16 项目，与 M6 共享技术栈（shadcn/ui + Tailwind + next-intl + Zustand + Playwright），通过 Mock Server 获取假数据。管理后台有自己的侧边栏导航和页面布局，不依赖 M6 的任何组件。

**技术栈**：TypeScript strict · Next.js 16 · React 19 · shadcn/ui (Radix/Nova) · Tailwind CSS 4 · next-intl · Zustand · Playwright

---

## 文件地图

```
m7-admin-portal/
├── package.json / tsconfig.json / next.config.ts / tailwind.config.ts / postcss.config.mjs / components.json
├── messages/
│   ├── en.json / zh.json / ko.json / ja.json / no.json
├── src/
│   ├── middleware.ts
│   ├── i18n/request.ts
│   ├── types/index.ts
│   ├── app/
│   │   ├── layout.tsx                          # 根布局
│   │   ├── page.tsx                            # / → /en/admin
│   │   └── [locale]/
│   │       ├── layout.tsx                      # i18n Provider + AdminLayout
│   │       └── admin/
│   │           ├── layout.tsx                  # Admin sidebar + content
│   │           ├── page.tsx                    # Dashboard (default)
│   │           ├── documents/
│   │           │   ├── page.tsx                # 文档管理主页
│   │           │   └── [id]/page.tsx           # 文档详情/编辑页
│   │           ├── knowledge-graph/
│   │           │   └── page.tsx                # KG 可视化浏览
│   │           ├── llm-config/
│   │           │   └── page.tsx                # LLM 后端配置
│   │           ├── users/
│   │           │   ├── page.tsx                # 用户列表
│   │           │   └── [id]/page.tsx           # 用户详情/编辑
│   │           └── monitoring/
│   │               └── page.tsx                # 系统监控面板
│   ├── components/
│   │   ├── ui/                                 # shadcn/ui 组件（自动生成）
│   │   ├── layout/
│   │   │   ├── admin-layout.tsx                # 管理后台主布局
│   │   │   ├── admin-sidebar.tsx               # 管理后台侧边栏
│   │   │   └── language-switcher.tsx           # 语言切换器
│   │   ├── documents/
│   │   │   ├── upload-area.tsx                 # 拖放上传区域
│   │   │   ├── upload-progress.tsx             # 上传进度条
│   │   │   ├── metadata-form.tsx               # 元数据标注表单
│   │   │   ├── parse-status-badge.tsx          # 解析状态标签
│   │   │   └── document-table.tsx              # 文档列表表格
│   │   ├── knowledge-graph/
│   │   │   ├── kg-canvas.tsx                   # KG 可视化画布
│   │   │   ├── entity-card.tsx                 # 实体卡片
│   │   │   └── relation-editor.tsx             # 关系编辑器
│   │   ├── llm-config/
│   │   │   ├── backend-list.tsx                # LLM 后端列表
│   │   │   ├── backend-form.tsx                # LLM 后端编辑表单
│   │   │   └── backend-test-button.tsx         # 测试连接按钮
│   │   ├── users/
│   │   │   ├── user-table.tsx                  # 用户列表表格
│   │   │   ├── user-form.tsx                   # 用户创建/编辑表单
│   │   │   └── quota-manager.tsx               # 配额管理
│   │   └── monitoring/
│   │       ├── stats-cards.tsx                 # 统计卡片组
│   │       ├── latency-chart.tsx               # 延迟图表
│   │       └── log-viewer.tsx                  # 日志查看器
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts                       # HTTP 客户端
│   │   │   ├── documents.ts                    # 文档管理 API
│   │   │   ├── llm-config.ts                   # LLM 配置 API
│   │   │   ├── users.ts                        # 用户管理 API
│   │   │   └── monitoring.ts                   # 监控 API
│   │   └── stores/
│   │       ├── admin-store.ts                  # 管理后台全局状态
│   │       └── settings-store.ts               # 用户设置
│   └── hooks/
│       └── use-file-upload.ts                  # 文件上传 Hook
├── tests/e2e/
│   ├── documents.spec.ts
│   ├── llm-config.spec.ts
│   ├── users.spec.ts
│   └── monitoring.spec.ts
└── playwright.config.ts
```

---

## 管理后台侧边栏导航结构

```
┌─────────────────────┐
│  MO Expert Admin    │  ← 品牌标识
├─────────────────────┤
│  📊 Dashboard       │  ← 系统概览
│  📄 Documents       │  ← 文档上传与管理
│  🧠 Knowledge Graph │  ← KG 可视化浏览
│  ⚙️  LLM Config     │  ← LLM 后端配置
│  👥 Users           │  ← 用户管理
│  📈 Monitoring      │  ← 系统监控
├─────────────────────┤
│  ⚙ Settings         │
│  ❓ Help            │
│  🌐 Language        │
│  👤 Admin User      │
└─────────────────────┘
```

---

## Task 列表

### Phase C-1：项目骨架 + i18n + 数据层

#### Task C1: 项目脚手架

**产出**：`m7-admin-portal/` 完整 Next.js 项目

- [ ] **Step 1**: `npx create-next-app@latest m7-admin-portal --typescript --tailwind --eslint --app --src-dir --no-import-alias --use-npm`
- [ ] **Step 2**: `npm install next-intl zustand react-markdown lucide-react` + `npm install -D @playwright/test`
- [ ] **Step 3**: `npx shadcn@latest init -d -f`（默认 Nova/Radix）
- [ ] **Step 4**: `npx shadcn@latest add button input textarea scroll-area dialog dropdown-menu tooltip avatar separator sheet card badge table tabs select progress accordion -y`
- [ ] **Step 5**: 验证 `npm run dev` → http://localhost:3001（与 M6 的 3000 错开）
- [ ] **Step 6**: Git 提交

---

#### Task C2: i18n 架构

**产出**：`middleware.ts`, `i18n/request.ts`, `messages/*.json`

与 M6 相同的 i18n 结构。**关键差异**：管理员特定的翻译 key 以 `admin.` 为前缀。

`messages/en.json` 核心结构：

```json
{
  "app": { "name": "Marine & Offshore Expert System", "shortName": "MO Expert Admin" },
  "nav": {
    "dashboard": "Dashboard",
    "documents": "Documents",
    "knowledgeGraph": "Knowledge Graph",
    "llmConfig": "LLM Config",
    "users": "Users",
    "monitoring": "Monitoring",
    "settings": "Settings",
    "help": "Help",
    "backToChat": "Back to Chat"
  },
  "admin": {
    "dashboard": {
      "title": "Dashboard",
      "subtitle": "System overview and key metrics",
      "totalDocuments": "Total Documents",
      "totalChunks": "Total Chunks",
      "totalEntities": "Entities",
      "totalRelations": "Relations",
      "totalUsers": "Users",
      "totalConversations": "Conversations",
      "storageUsed": "Storage Used",
      "avgLatency": "Avg Retrieval Latency"
    },
    "documents": {
      "title": "Document Management",
      "subtitle": "Upload, parse, and manage knowledge base documents",
      "upload": {
        "title": "Upload Documents",
        "dragDrop": "Drag & drop files here, or click to browse",
        "supportedFormats": "Supported: PDF, DOCX, DWG, TIFF, PNG (max 500MB per file)",
        "uploading": "Uploading...",
        "success": "Upload successful",
        "error": "Upload failed"
      },
      "metadata": {
        "classificationSociety": "Classification Society",
        "regulationName": "Regulation Name",
        "versionYear": "Version Year",
        "domain": "Domain",
        "vesselTypes": "Vessel Types",
        "systemType": "System Type",
        "manufacturer": "Manufacturer",
        "language": "Document Language",
        "customTags": "Custom Tags"
      },
      "status": { "queued": "Queued", "processing": "Processing", "completed": "Completed", "failed": "Failed", "active": "Active", "deprecated": "Superseded", "error": "Error" },
      "table": { "filename": "Filename", "society": "Society", "domain": "Domain", "version": "Version", "chunks": "Chunks", "status": "Status", "ingested": "Ingested", "actions": "Actions" },
      "actions": { "view": "View Details", "reparse": "Re-parse", "deprecate": "Mark Deprecated", "delete": "Delete", "deleteConfirm": "Permanently delete this document and all its chunks? This cannot be undone." }
    },
    "knowledgeGraph": {
      "title": "Knowledge Graph",
      "subtitle": "Visualize entities and relations extracted from documents",
      "search": "Search entities...",
      "entityTypes": { "regulation_clause": "Regulation Clause", "vessel_type": "Vessel Type", "system": "System", "equipment": "Equipment", "manufacturer": "Manufacturer" },
      "relationTypes": { "regulates": "Regulates", "references": "References", "applies_to": "Applies To", "equivalent_to": "Equivalent To", "replaces": "Replaces", "requires": "Requires", "prohibits": "Prohibits" },
      "noData": "No knowledge graph data yet. Upload and parse documents to build the graph."
    },
    "llmConfig": {
      "title": "LLM Backend Configuration",
      "subtitle": "Manage AI model backends for different domain agents",
      "addBackend": "Add Backend",
      "backendType": "Backend Type",
      "modelName": "Model Name",
      "baseUrl": "Base URL",
      "apiKey": "API Key",
      "maxTokens": "Max Tokens",
      "temperature": "Temperature",
      "isDefault": "Default",
      "assignedAgents": "Assigned Agents",
      "testConnection": "Test Connection",
      "testing": "Testing...",
      "connected": "Connected",
      "failed": "Connection Failed",
      "deleteConfirm": "Remove this LLM backend configuration?"
    },
    "users": {
      "title": "User Management",
      "subtitle": "Manage user accounts, roles, and quotas",
      "addUser": "Add User",
      "table": { "username": "Username", "email": "Email", "role": "Role", "status": "Status", "queries": "Queries", "apiKeys": "API Keys", "created": "Created", "actions": "Actions" },
      "roles": { "admin": "Admin", "editor": "Editor", "viewer": "Viewer" },
      "status": { "active": "Active", "suspended": "Suspended" },
      "form": { "createTitle": "Create User", "editTitle": "Edit User", "username": "Username", "email": "Email", "password": "Password", "role": "Role", "quotaLimit": "Monthly Query Limit", "save": "Save User" },
      "deleteConfirm": "Permanently delete this user account? All associated data will be removed."
    },
    "monitoring": {
      "title": "System Monitoring",
      "subtitle": "Real-time system health and performance metrics",
      "health": { "title": "Module Health", "ok": "Healthy", "degraded": "Degraded", "down": "Down" },
      "metrics": { "requestsPerMinute": "Requests/min", "avgResponseTime": "Avg Response Time", "errorRate": "Error Rate", "uptime": "Uptime" },
      "logs": { "title": "Recent Logs", "level": "Level", "timestamp": "Time", "message": "Message", "module": "Module" }
    }
  },
  "common": {
    "loading": "Loading...", "error": "Something went wrong", "retry": "Retry", "cancel": "Cancel",
    "save": "Save", "delete": "Delete", "search": "Search", "noResults": "No results found",
    "close": "Close", "back": "Back", "more": "More", "confirm": "Confirm"
  }
}
```

其他 4 个语种（zh/ko/ja/no）在 Task C2 中先用英文占位，后续翻译。

- [ ] **Step 1**: `next.config.ts` 注册 `createNextIntlPlugin()`
- [ ] **Step 2**: 验证 `npm run dev`，语言路由正常
- [ ] **Step 3**: Git 提交

---

#### Task C3: TypeScript 类型定义

**产出**：`src/types/index.ts`

```typescript
// Admin-specific types mirroring contracts/api_schemas.py

export interface ParseTask {
  task_id: string; doc_id: string; status: string;
  progress_pct: number; chunks_count: number;
  error_message?: string; started_at?: string; completed_at?: string;
}

export interface DocumentRecord {
  doc_id: string; source_filename: string;
  classification_society?: string; regulation_name?: string;
  version_year?: number; domain: string;
  chunks_count: number; ingested_at: string; status: string;
}

export interface KGEntity {
  entity_id: string; name: string; entity_type: string;
  properties: Record<string, unknown>; source_doc_id?: string;
}

export interface KGRelation {
  relation_id: string; source_entity_id: string; target_entity_id: string;
  relation_type: string; source_entity_name: string; target_entity_name: string;
  confidence: number;
}

export interface LLMBackend {
  backend_id: string; backend_type: string; model_name: string;
  base_url?: string; api_key?: string; max_tokens: number;
  temperature: number; is_default: boolean; assigned_agents: string[];
}

export type LLMBackendType = 'openai' | 'deepseek' | 'claude' | 'ollama' | 'vllm' | 'lmstudio' | 'custom';

export interface AdminUser {
  user_id: string; username: string; email: string;
  role: 'admin' | 'editor' | 'viewer'; is_active: boolean;
  api_key_count: number; total_queries: number; created_at: string;
}

export interface SystemStats {
  total_documents: number; total_chunks: number;
  total_entities: number; total_relations: number;
  total_conversations: number; total_users: number;
  storage_size_bytes: number; avg_retrieval_latency_ms: number;
}

export interface ModuleHealth {
  m1_doc_parsing: string; m2_storage: string; m3_retrieval: string;
  m4_knowledge_graph: string; m5_qa_engine: string; m8_api_gateway: string;
}

export type SupportedLanguage = 'en' | 'zh' | 'ko' | 'ja' | 'no';
export const SUPPORTED_LANGUAGES = [
  { code: 'en' as SupportedLanguage, label: 'English' },
  { code: 'zh' as SupportedLanguage, label: '中文' },
  { code: 'ko' as SupportedLanguage, label: '한국어' },
  { code: 'ja' as SupportedLanguage, label: '日本語' },
  { code: 'no' as SupportedLanguage, label: 'Norsk' },
];
```

---

#### Task C4: API 客户端 + Zustand Store

**产出**：
- `src/lib/api/client.ts` — 与 M6 相同的 `apiGet/apiPost/apiDelete/apiPatch`
- `src/lib/api/documents.ts` — `uploadDocument`, `getParseStatus`, `listDocuments`, `deleteDocument`
- `src/lib/api/llm-config.ts` — `listBackends`, `createBackend`, `updateBackend`, `deleteBackend`
- `src/lib/api/users.ts` — `listUsers`, `createUser`, `updateUser`, `deleteUser`
- `src/lib/api/monitoring.ts` — `getStats`, `getHealth`
- `src/lib/stores/admin-store.ts` — 管理后台全局状态

API 函数与 M6 的 `src/lib/api/` 结构一致，指向 Mock Server `http://127.0.0.1:8000/api/v1/admin/*`。

---

### Phase C-2：布局与导航

#### Task C5: AdminLayout + AdminSidebar

**产出**：
- `src/app/[locale]/admin/layout.tsx` — AdminLayout 包裹所有管理页面
- `src/components/layout/admin-layout.tsx` — 侧边栏 + 内容区布局
- `src/components/layout/admin-sidebar.tsx` — 管理后台侧边栏

AdminSidebar 结构：
```
┌─────────────────────┐
│  [MO Expert Admin]  │  ← 品牌标识，点回 Dashboard
├─────────────────────┤
│  📊 Dashboard       │  ← 当前高亮：bg-accent
│  📄 Documents       │
│  🧠 Knowledge Graph │
│  ⚙️  LLM Config     │
│  👥 Users           │
│  📈 Monitoring      │
├─────────────────────┤
│  ← Back to Chat     │  ← 返回 M6 用户端
└─────────────────────┘
```

每种导航项的图标：
- Dashboard → LayoutDashboard
- Documents → FileText
- Knowledge Graph → Share2 (graph icon)
- LLM Config → Cpu
- Users → Users
- Monitoring → Activity

底部：Settings / Help / LanguageSwitcher / Admin User

---

### Phase C-3：核心管理页面

#### Task C6: Dashboard 页面

**产出**：`src/app/[locale]/admin/page.tsx`

Dashboard 显示系统概览统计卡片：
- 4 个主统计卡片（总文档数、总块数、用户数、会话数），带图标和数字
- 存储用量进度条
- 平均检索延迟指标
- 模块健康状态指示灯（M1-M8 每模块一个绿/黄/红圆点）

所有数据从 `GET /api/v1/admin/stats` 和 `GET /api/v1/admin/health` 获取。

---

#### Task C7: 文档管理页面

**产出**：
- `src/app/[locale]/admin/documents/page.tsx` — 文档管理主页
- `src/app/[locale]/admin/documents/[id]/page.tsx` — 文档详情页
- `src/components/documents/upload-area.tsx` — 拖放上传区域
- `src/components/documents/document-table.tsx` — 文档列表表格
- `src/components/documents/metadata-form.tsx` — 元数据标注表单

**文档管理主页布局**：

```
┌────────────────────────────────────────────┐
│  Document Management      [+ Upload]       │
│  Upload, parse, and manage documents       │
├────────────────────────────────────────────┤
│  [拖放上传区域 — 虚线边框，支持点击浏览]       │
│  Supported: PDF, DOCX, DWG, TIFF, PNG      │
├────────────────────────────────────────────┤
│  [🔍 Search...]  [船级社▼] [专业▼] [状态▼] │
├────────────────────────────────────────────┤
│  Filename        │Society│Domain│Ver│Chunks│
│  DNV-RU-SHIP...  │ DNV   │struct│24 │ 312  │
│  ABS-Rules-...   │ ABS   │struct│24 │ 278  │
│  IMO-BWMS-...    │ IMO   │machin│23 │ 156  │
├────────────────────────────────────────────┤
│  Showing 3 of 3 documents                  │
└────────────────────────────────────────────┘
```

**上传流程**：
1. 用户拖放文件或点击浏览选择
2. 弹出元数据标注对话框（船级社、规范名、版本年、专业、船型、系统、厂商、语言）
3. 确认后 POST `/api/v1/admin/documents/upload`
4. 表格中出现新行，状态为 "queued" → "processing" → "completed"
5. 完成后显示文档信息和块数

**文档详情页**：
- 文档基本信息（文件名、船级社、规范名、版本、领域、块数、状态）
- 块列表（文本块、表格块、图纸块，带标签分类）
- 操作按钮（重新解析、标记为已替代、删除）

---

#### Task C8: 知识图谱浏览页面

**产出**：`src/app/[locale]/admin/knowledge-graph/page.tsx`

知识图谱可视化浏览页面：
- 顶部搜索栏：搜索实体名称
- 左侧实体列表：按类型分组（规范条款、船型、系统、设备、厂商）
- 中间主区：实体关系图（简化为卡片列表 + 连线，不用 D3/Canvas——用 CSS flex/grid 模拟）
- 右侧详情面板：选中实体后显示属性，选中关系后显示类型和置信度
- 跨规范映射视图：切换显示 DNV ↔ ABS ↔ CCS 等船级社之间的等价条款映射

数据从 `GET /api/v1/admin/knowledge-graph/entities` 和 `relations` 获取。

> **注**：完整的图形可视化（D3.js/vis.js）在 Phase 2 用真实 KG 数据后实现。Phase 1 用卡片+列表的多列布局模拟展示。

---

#### Task C9: LLM 配置页面

**产出**：`src/app/[locale]/admin/llm-config/page.tsx`

LLM 后端配置管理页面：
- 已有的 LLM 后端列表（每项一个 Card）
  - 显示：后端类型、模型名、Base URL、Max Tokens、Temperature、默认标记、分配 Agent 列表
  - 操作按钮：编辑、测试连接（Phase 1 console.log，Phase 2 真实 ping）、删除
- 表格底部 "Add Backend" 按钮
- 点击添加/编辑 → 弹出 Dialog 表单：
  - Backend Type 下拉（OpenAI/DeepSeek/Claude/Ollama/vLLM/LM Studio/Custom）
  - Model Name 输入
  - Base URL 输入
  - API Key 输入（password 类型）
  - Max Tokens 数字输入
  - Temperature 滑块（0-2）
  - Is Default 复选框
  - Assigned Agents 多选（Structure/Machinery/Piping/Electrical/Communication/Automation）

数据从 `GET/POST/PUT/DELETE /api/v1/admin/llm/backends` 获取。

---

#### Task C10: 用户管理页面

**产出**：
- `src/app/[locale]/admin/users/page.tsx` — 用户列表
- `src/app/[locale]/admin/users/[id]/page.tsx` — 用户详情/编辑

用户管理页面：
- 用户列表表格：
  - 列：Username | Email | Role | Status | Queries | API Keys | Created | Actions
  - 排序、搜索、分页（Mock 无分页，显示全部）
- "Add User" 按钮 → Dialog 表单：
  - Username, Email, Password, Role（admin/editor/viewer）, Monthly Query Limit
- 每行的 Actions：编辑、启用/停用、删除（带确认）
- 用户详情页：个人资料 + API Key 列表 + 使用统计图表

数据从 `GET/POST /api/v1/admin/users` 获取。

---

#### Task C11: 系统监控页面

**产出**：`src/app/[locale]/admin/monitoring/page.tsx`

系统监控 Dashboard：
- **Module Health**（6 个模块状态卡片）：
  - m1_doc_parsing / m2_storage / m3_retrieval / m4_knowledge_graph / m5_qa_engine / m8_api_gateway
  - 每个卡片：模块名 + 绿/黄/红圆点状态 + 响应时间
- **性能指标卡片**：
  - Requests/min, Avg Response Time, Error Rate, Uptime
- **最近日志列表**：
  - Level (INFO/WARN/ERROR 颜色标签) | Timestamp | Module | Message
  - Phase 1 用 Mock 数据

数据从 `GET /api/v1/admin/stats` 和 `GET /api/v1/admin/health` 获取。

---

### Phase C-4：测试与收尾

#### Task C12: Playwright E2E 测试

**产出**：`playwright.config.ts`, `tests/e2e/*.spec.ts`

4 个测试文件覆盖管理后台核心流程：

1. **documents.spec.ts**：上传文档 → 查看状态 → 列表显示 → 删除
2. **llm-config.spec.ts**：后端列表 → 添加 → 编辑 → 删除
3. **users.spec.ts**：用户列表 → 创建 → 编辑 → 删除
4. **monitoring.spec.ts**：Dashboard 统计卡 → 模块健康 → 日志列表

---

#### Task C13: 翻译非英文语种

同 M6 Task B16，将 `en.json` 中的 admin key 翻译为 zh/ko/ja/no。

---

#### Task C14: 收尾

- [ ] 更新 `.dev/tasks.md`（00040 → ✅）
- [ ] 写 `.dev/test_records/00040.md`
- [ ] 更新 `.dev/module-memory/m7-admin-portal.md`
- [ ] 更新 `.dev/module-memory/index.md`

---

## 与 M6 的关系

| 方面 | M6 | M7 |
|------|----|----|
| 项目 | `m6-user-portal/` | `m7-admin-portal/` |
| 端口 | 3000 | 3001 |
| 用户 | 普通用户 + 游客 | 管理员 |
| 路由 | `/chat`, `/login`, `/settings` 等 | `/admin/documents`, `/admin/llm-config` 等 |
| Mock | `http://127.0.0.1:8000` | 同样 |
| 组件 | 聊天、会话、设置 | 表格、表单、仪表板 |
| i18n | `en.json` (chat.*, conv.*, settings.*) | `en.json` (admin.*, nav.*) |

**共享部分**：shadcn/ui 组件、i18n 架构模式、API 客户端模式、Playwright 测试模式。

**独立部分**：页面路由、组件、翻译文件、API 调用——完全不依赖 M6 代码。

---

## 自审清单

- [ ] AdminSidebar 6 个导航项全部可点击跳转
- [ ] 所有表格从 Mock Server 加载数据
- [ ] 文档上传拖放区域正常工作
- [ ] LLM 配置 CRUD 流程完整
- [ ] 用户管理 CRUD 流程完整
- [ ] 监控面板显示模块健康状态
- [ ] 5 种语言切换正常
- [ ] TypeScript 0 错误
- [ ] Playwright 全部通过
