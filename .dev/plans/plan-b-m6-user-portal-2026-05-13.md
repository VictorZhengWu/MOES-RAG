# Plan B: M6 用户前端 — 实现规划（修订版）

> **给执行者**：按 Task 顺序逐项执行。每步 2-5 分钟。使用 `- [ ]` 复选框追踪进度。

**目标**：构建 Marine & Offshore Expert System 的用户问答前端。体验对标 ChatGPT / DeepSeek——可折叠左侧栏、游客模式、流式聊天、Markdown 渲染、右侧引用滑出面板、对话快速定位窄条、附件上传、联网搜索开关。

**架构**：Next.js 14 App Router + shadcn/ui + Tailwind CSS + next-intl + Zustand。纯前端，接入 Mock Server（Plan A），Phase 2 切真实 API 零改动。

**技术栈**：TypeScript strict · Next.js 14+ · React 18 · shadcn/ui · Tailwind CSS 4 · next-intl · Zustand · Playwright

**核心交互约定**：
- 未登录 = 游客模式：可聊天但会话不保存，左侧栏不显示历史列表
- 已登录：会话列表全量展示，侧边栏底部显示头像+名字
- 左侧栏可折叠（⇔ 箭头），收起时只显示窄图标条
- 引用标注点击后在右侧以滑出面板（Sheet）展示，不遮挡对话
- 对话区右侧悬浮窄条列出本会话中所有用户提问，点击跳转到对应消息

---

## 文件地图

```
m6-user-portal/
├── package.json
├── tsconfig.json / next.config.ts / tailwind.config.ts / postcss.config.js / components.json
├── messages/
│   ├── en.json / zh.json / ko.json / ja.json / no.json
├── src/
│   ├── middleware.ts                     # i18n 路由中间件
│   ├── i18n/request.ts                  # next-intl 配置
│   ├── app/
│   │   ├── layout.tsx                   # 根布局
│   │   ├── page.tsx                     # / → /en
│   │   ├── [locale]/
│   │   │   ├── layout.tsx               # i18n Provider + AppLayout
│   │   │   ├── page.tsx                 # / → /chat
│   │   │   ├── (auth)/
│   │   │   │   ├── login/page.tsx
│   │   │   │   └── register/page.tsx
│   │   │   └── (main)/
│   │   │       ├── layout.tsx           # 空壳（sidebar 来自 AppLayout）
│   │   │       ├── chat/page.tsx        # 新对话
│   │   │       ├── chat/[id]/page.tsx   # 已有对话
│   │   │       ├── knowledge/page.tsx   # 知识库浏览
│   │   │       └── settings/page.tsx    # 设置 + API Key
│   ├── components/
│   │   ├── ui/                          # shadcn/ui（自动生成）
│   │   ├── chat/
│   │   │   ├── chat-panel.tsx           # 聊天区容器（含跳转窄条）
│   │   │   ├── message-list.tsx
│   │   │   ├── message-bubble.tsx       # Markdown 渲染 + 引用编号
│   │   │   ├── chat-input.tsx           # 输入框 + 附件 + Web Search
│   │   │   ├── empty-state.tsx
│   │   │   └── citation-panel.tsx       # 右侧滑出引用详情
│   │   ├── conversation/
│   │   │   ├── conversation-sidebar.tsx # 可折叠侧边栏（全部按钮+登录态）
│   │   │   ├── conversation-item.tsx
│   │   │   └── conversation-search.tsx
│   │   ├── navigation/
│   │   │   └── jump-navigation.tsx      # 对话快速定位窄条
│   │   ├── layout/
│   │   │   ├── app-layout.tsx           # 主布局：sidebar + 内容 + 引用面板
│   │   │   └── language-switcher.tsx
│   │   └── auth/
│   │       ├── login-form.tsx
│   │       └── register-form.tsx
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts / chat.ts / conversations.ts / models.ts
│   │   ├── stores/
│   │   │   ├── chat-store.ts
│   │   │   ├── conversation-store.ts
│   │   │   ├── settings-store.ts
│   │   │   └── auth-store.ts            # 登录状态
│   │   └── hooks/
│   │       ├── use-chat-stream.ts
│   │       └── use-intersection.ts
│   └── types/
│       └── index.ts
├── tests/e2e/
│   ├── chat.spec.ts / conversations.spec.ts / i18n.spec.ts / auth.spec.ts
└── playwright.config.ts
```

---

## Task 列表

### Task B1: Next.js 项目脚手架 + shadcn/ui 集成

**产出文件**: `package.json`, `tsconfig.json`, `next.config.ts`, `tailwind.config.ts`, `postcss.config.js`, `components.json`

- [ ] **Step 1: 用 create-next-app 初始化**

```bash
cd E:\myCode\RAG
npx create-next-app@latest m6-user-portal --typescript --tailwind --eslint --app --src-dir --no-import-alias --use-npm
```
全部选 Yes。

- [ ] **Step 2: 安装依赖**

```bash
cd m6-user-portal
npm install next-intl zustand react-markdown lucide-react
npm install -D @playwright/test
```

- [ ] **Step 3: 初始化 shadcn/ui**

```bash
npx shadcn@latest init
# Style: New York / Base: Neutral / CSS variables: Yes
```

- [ ] **Step 4: 安装 shadcn 组件（含本次新增的 sheet, switch, file-upload 等）**

```bash
npx shadcn@latest add button input textarea scroll-area dialog dropdown-menu tooltip avatar separator sheet popover toast tabs card badge switch
```

`sheet` 用于右侧引用滑出面板和侧边栏移动端适配。`switch` 用于 Web Search 开关。

- [ ] **Step 5: 验证 `npm run dev` 能跑**

打开 http://localhost:3000 确认 Next.js 默认首页出现。

- [ ] **Step 6: 提交**

```bash
git add m6-user-portal/
git commit -m "[00030] chore: scaffold Next.js project with shadcn/ui and dependencies"
```

---

### Task B2: i18n 架构（next-intl + 5 语种完整翻译）

**产出文件**: `src/middleware.ts`, `src/i18n/request.ts`, `messages/en.json`, `messages/zh.json`, `messages/ko.json`, `messages/ja.json`, `messages/no.json`

**说明**：所有 UI 文字零硬编码。`en.json` 是 canonical 源文件。其他 4 个语种文件 key 结构完全一致。

- [ ] **Step 1: 创建 messages/en.json**

```json
{
  "app": {
    "name": "Marine & Offshore Expert System",
    "shortName": "MO Expert",
    "tagline": "Professional RAG Q&A for ship and offshore engineering"
  },
  "sidebar": {
    "newChat": "New Chat",
    "searchChats": "Search chats",
    "deepResearch": "Deep Research",
    "settings": "Settings",
    "help": "Help",
    "logIn": "Log in",
    "logOut": "Log out",
    "collapse": "Collapse sidebar",
    "expand": "Expand sidebar",
    "guestWarning": "Sign in to save conversations"
  },
  "chat": {
    "input": {
      "placeholder": "Ask anything about ship & offshore engineering...",
      "send": "Send",
      "stopGeneration": "Stop generating",
      "attachFile": "Attach file",
      "webSearch": "Web search",
      "webSearchOn": "Web search enabled",
      "webSearchOff": "Web search disabled"
    },
    "empty": {
      "title": "Marine & Offshore Expert System",
      "subtitle": "Ask questions about classification society rules, engineering standards, equipment specifications, and more.",
      "suggestions": {
        "title": "Try asking:",
        "items": [
          "What are DNV requirements for LNG cargo tank structures?",
          "Compare ABS and DNV rules for bulk carrier hatch covers",
          "What does IMO require for ballast water treatment?",
          "What is the minimum plate thickness for a container ship's main deck according to CCS?",
          "Explain the fatigue assessment procedure for offshore crane pedestals"
        ]
      }
    },
    "citation": {
      "title": "References",
      "source": "Source",
      "section": "Section",
      "clause": "Clause",
      "excerpt": "Excerpt",
      "viewSource": "View source",
      "noReferences": "No references for this answer"
    },
    "jumpNav": {
      "title": "Questions in this chat",
      "empty": "No questions yet"
    },
    "streaming": "Generating...",
    "error": {
      "send": "Failed to send message. Please try again.",
      "stream": "Stream interrupted. Please try again.",
      "network": "Network error. Check your connection."
    }
  },
  "conversation": {
    "title": "Chat History",
    "search": "Search chats...",
    "new": "New conversation",
    "delete": {
      "label": "Delete conversation",
      "confirm": "Are you sure you want to delete this conversation?",
      "cancel": "Cancel",
      "confirmButton": "Delete"
    },
    "rename": {
      "label": "Rename",
      "placeholder": "Conversation title"
    },
    "empty": "No conversations yet. Start a new chat.",
    "guestEmpty": "Sign in to view your conversation history."
  },
  "knowledge": {
    "title": "Knowledge Base",
    "subtitle": "Documents and regulations available in the system",
    "search": "Search documents...",
    "filter": {
      "society": "Classification Society",
      "domain": "Domain",
      "year": "Version Year",
      "all": "All"
    },
    "table": {
      "name": "Document Name", "society": "Society", "domain": "Domain",
      "year": "Year", "chunks": "Sections", "status": "Status"
    },
    "status": { "active": "Active", "deprecated": "Superseded", "error": "Error" },
    "empty": "No documents found."
  },
  "settings": {
    "title": "Settings",
    "language": {
      "label": "Interface Language",
      "description": "Change the language of the user interface.",
      "en": "English", "zh": "中文", "ko": "한국어", "ja": "日本語", "no": "Norsk"
    },
    "theme": { "label": "Theme", "light": "Light", "dark": "Dark", "system": "System" },
    "apiKeys": { "title": "API Keys", "create": "Create API Key", "empty": "No API keys yet." }
  },
  "auth": {
    "login": {
      "title": "Sign In", "subtitle": "Welcome back",
      "email": "Email", "password": "Password", "submit": "Sign In",
      "noAccount": "Don't have an account?", "register": "Create one"
    },
    "register": {
      "title": "Create Account", "subtitle": "Get started",
      "username": "Username", "email": "Email",
      "password": "Password", "confirmPassword": "Confirm Password",
      "submit": "Create Account",
      "hasAccount": "Already have an account?", "login": "Sign In"
    },
    "errors": {
      "invalidEmail": "Please enter a valid email address.",
      "passwordLength": "Password must be at least 8 characters.",
      "passwordsMatch": "Passwords do not match.",
      "loginFailed": "Invalid email or password.",
      "registerFailed": "Registration failed. Please try again."
    }
  },
  "common": {
    "loading": "Loading...", "error": "Something went wrong",
    "retry": "Retry", "cancel": "Cancel", "save": "Save",
    "delete": "Delete", "search": "Search", "noResults": "No results found",
    "close": "Close", "back": "Back", "more": "More"
  }
}
```

- [ ] **Step 2: 创建 src/middleware.ts**

```typescript
/**
 * next-intl middleware: intercepts requests without locale prefix and
 * redirects to the appropriate locale (/en, /zh, /ko, /ja, /no).
 *
 * WHY: Path-based locale routing enables SEO-friendly URLs and makes
 * language switching a simple client-side navigation. The middleware
 * reads the Accept-Language header and falls back to 'en'.
 */
import createMiddleware from 'next-intl/middleware';

export default createMiddleware({
  locales: ['en', 'zh', 'ko', 'ja', 'no'],
  defaultLocale: 'en',
  localeDetection: true,
});

export const config = { matcher: ['/((?!_next|api|favicon.ico|.*\\.).*)'] };
```

- [ ] **Step 3: 创建 src/i18n/request.ts**

```typescript
import { getRequestConfig } from 'next-intl/server';

export default getRequestConfig(async ({ requestLocale }) => {
  let locale = await requestLocale;
  if (!locale || !['en', 'zh', 'ko', 'ja', 'no'].includes(locale)) {
    locale = 'en';
  }
  return {
    locale,
    messages: (await import(`../../messages/${locale}.json`)).default,
  };
});
```

- [ ] **Step 4: 创建其他 4 个翻译文件（先用 en.json 占位，Task B16 翻译）**

```bash
cd m6-user-portal/messages
for lang in zh ko ja no; do cp en.json $lang.json; done
```

- [ ] **Step 5: 验证** — http://localhost:3000 → 自动跳转 /en/chat

- [ ] **Step 6: 提交**

```bash
git add m6-user-portal/messages/ m6-user-portal/src/middleware.ts m6-user-portal/src/i18n/
git commit -m "[00030] feat: add i18n infrastructure with 5 locales and complete en.json"
```

---

### Task B3: TypeScript 类型定义

**产出文件**: `src/types/index.ts`

```typescript
/**
 * Shared TypeScript type definitions.
 * Mirror contracts/ Pydantic schemas. Add frontend-only types
 * for auth state, file upload, web search, and jump navigation.
 */

// ── Chat ───────────────────────────────────────────────────────────

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  /** Server-generated message ID for jump-navigation targeting */
  id?: string;
}

export interface Citation {
  index: number;
  source_doc: string;
  section: string;
  clause_id?: string;
  excerpt: string;
  url?: string;
}

export interface ChatRequest {
  model: string;
  messages: Message[];
  stream?: boolean;
  temperature?: number;
  max_tokens?: number;
  conversation_id?: string;
  domain_filter?: string;
  vessel_type_filter?: string;
  web_search?: boolean;
}

export interface ChatResponse {
  id: string; object: string; created: number; model: string;
  choices: Choice[]; usage?: Usage; citations: Citation[];
}

export interface Choice { index: number; message: Message; finish_reason: string; }
export interface Usage { prompt_tokens: number; completion_tokens: number; total_tokens: number; }

export interface StreamChunk {
  id: string; object: string; created: number; model: string;
  choices: StreamChoice[];
}
export interface StreamChoice { index: number; delta: { content?: string }; finish_reason: string | null; }

// ── Auth ────────────────────────────────────────────────────────────

export interface UserProfile {
  user_id: string;
  username: string;
  email: string;
  avatar_url?: string;
  role: 'admin' | 'editor' | 'viewer';
}

export type AuthStatus = 'loading' | 'guest' | 'authenticated';

// ── File Upload ─────────────────────────────────────────────────────

export interface FileAttachment {
  file: File;
  previewUrl: string;
  status: 'pending' | 'uploading' | 'uploaded' | 'error';
}

// ── Conversations / Models / Knowledge Base / Settings ──────────────

export interface ConversationSummary {
  conversation_id: string; title: string;
  created_at: string; updated_at: string; message_count: number;
}
export interface ConversationListResponse { conversations: ConversationSummary[]; total: number; }
export interface ConversationDetailResponse { conversation_id: string; messages: Message[]; }
export interface ModelInfo { id: string; object: string; created: number; owned_by: string; }
export interface ModelListResponse { object: string; data: ModelInfo[]; }
export interface DocumentInfo {
  doc_id: string; source_filename: string;
  classification_society: string | null; regulation_name: string | null;
  version_year: number | null; domain: string; chunks_count: number;
  ingested_at: string; status: string;
}
export interface DocumentListResponse { documents: DocumentInfo[]; total: number; }
export interface UserSettings { language: string; theme: string; }

export type SupportedLanguage = 'en' | 'zh' | 'ko' | 'ja' | 'no';
export const SUPPORTED_LANGUAGES: { code: SupportedLanguage; label: string }[] = [
  { code: 'en', label: 'English' }, { code: 'zh', label: '中文' },
  { code: 'ko', label: '한국어' }, { code: 'ja', label: '日本語' }, { code: 'no', label: 'Norsk' },
];

// ── Jump Navigation ─────────────────────────────────────────────────

export interface JumpEntry {
  index: number;
  messageId: string;
  preview: string;       // first ~60 chars of the user's question
}
```

- [ ] **验证**: `npx tsc --noEmit` 无误
- [ ] **提交**: `git commit -m "[00030] feat: add TypeScript types with auth, file upload, web search, jump nav"`

---

### Task B4: API 客户端层

**产出文件**: `src/lib/api/client.ts`, `src/lib/api/chat.ts`, `src/lib/api/conversations.ts`, `src/lib/api/models.ts`

（代码与初版 Plan B 一致，无需改动。保留 Task B4 原内容，此处不重复粘贴。）

---

### Task B5: Zustand 状态管理（4 个 Store）

**产出文件**: `src/lib/stores/auth-store.ts`, `src/lib/stores/chat-store.ts`, `src/lib/stores/conversation-store.ts`, `src/lib/stores/settings-store.ts`

- [ ] **Step 1: 创建 auth-store.ts（新增）**

```typescript
/**
 * Authentication state store.
 *
 * WHY: Multiple components (sidebar footer, header, chat, conversation
 * sidebar) need to react to login/logout. A centralized store avoids
 * prop drilling and keeps auth logic in one place.
 *
 * Guest mode: authStatus='guest', user=null. User can chat but
 * conversations are not saved. On login, authStatus transitions to
 * 'authenticated' and the sidebar fetches the conversation list.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { UserProfile, AuthStatus } from '@/types';

interface AuthState {
  authStatus: AuthStatus;
  user: UserProfile | null;
  token: string | null;

  login: (user: UserProfile, token: string) => void;
  logout: () => void;
  setGuest: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      authStatus: 'loading',
      user: null,
      token: null,

      login: (user, token) => set({ authStatus: 'authenticated', user, token }),
      logout: () => set({ authStatus: 'guest', user: null, token: null }),
      setGuest: () => set({ authStatus: 'guest', user: null, token: null }),
    }),
    {
      name: 'm6-auth',
      partialize: (state) => ({ token: state.token, user: state.user, authStatus: state.authStatus }),
    },
  ),
);
```

- [ ] **Step 2: 更新 chat-store.ts**

在初版基础上加 `selectedCitationIndex` 和 `webSearchEnabled`：

```typescript
interface ChatState {
  // ... 原有字段 ...
  selectedCitationIndex: number | null;  // 点击引用编号 → 打开 CitationPanel
  webSearchEnabled: boolean;
  // ... actions: setSelectedCitation, toggleWebSearch ...
}
```

完整代码在实现时按初版模式编写。

- [ ] **Step 3: conversation-store.ts 和 settings-store.ts**（与初版一致）

- [ ] **Step 4: 验证编译 + 提交**

---

### Task B6: SSE 流式 Hook

**产出文件**: `src/lib/hooks/use-chat-stream.ts`, `src/lib/hooks/use-intersection.ts`

（与初版一致，已含完整代码。保留 Task B6 原内容。）

---

### Task B7: 根布局 + 路由结构

**产出文件**: `src/app/layout.tsx`, `src/app/page.tsx`, `src/app/[locale]/layout.tsx`, `src/app/[locale]/page.tsx`

（与初版一致。）

---

### Task B8: 可折叠 AppLayout + LanguageSwitcher

**产出文件**: `src/components/layout/app-layout.tsx`, `src/components/layout/language-switcher.tsx`

**关键变更**：侧边栏从固定宽度改为**可折叠**。收起时只留一窄条图标栏。展开/收起状态由 `useSidebarStore`（或 app-layout 内部 useState）管理。

- [ ] **Step 1: 创建 app-layout.tsx**

```typescript
/**
 * Main app layout with collapsible sidebar.
 *
 * Layout structure (3 columns when expanded):
 * ┌──────────┬──────────────────────┬──────────┐
 * │ Sidebar  │  Chat Messages       │ Jump Nav │  ← expanded
 * │ 260px    │  flex-1              │  48px    │
 * ├──────────┤                      │          │
 * │ New Chat │  [message bubbles]   │ [Q]      │
 * │ Search.. │                      │ [Q]      │
 * │ Deep Rsrch│                     │ [Q]      │
 * │ -------- │                      │          │
 * │ History  │                      │          │
 * │ -------- │                      │          │
 * │ Settings │                      │          │
 * │ Help     │                      │          │
 * │ Avatar   │                      │          │
 * └──────────┴──────────────────────┴──────────┘
 *
 * Collapsed: sidebar → 0 width (icon-only strip), jump nav stays.
 *
 * WHY: Professional users need maximum reading space for long
 * regulation excerpts. The collapsible sidebar gives them control.
 */

'use client';

import { useState } from 'react';
import { ConversationSidebar } from '@/components/conversation/conversation-sidebar';
import { JumpNavigation } from '@/components/navigation/jump-navigation';
import { CitationPanel } from '@/components/chat/citation-panel';
import { LanguageSwitcher } from './language-switcher';
import { useTranslations } from 'next-intl';
import { PanelLeftClose, PanelLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const t = useTranslations();

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Collapsible Sidebar */}
      <div
        className={`transition-all duration-200 ease-in-out overflow-hidden border-r bg-muted/30 flex flex-col ${
          sidebarOpen ? 'w-[260px]' : 'w-0 border-r-0'
        }`}
      >
        <ConversationSidebar />
      </div>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar: collapse toggle + language switcher */}
        <header className="flex h-11 items-center justify-between border-b px-3">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            title={sidebarOpen ? t('sidebar.collapse') : t('sidebar.expand')}
          >
            {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
          </Button>
          <LanguageSwitcher />
        </header>

        {/* Chat content + right jump nav */}
        <div className="flex flex-1 overflow-hidden">
          <main className="flex-1 overflow-y-auto">{children}</main>
          <JumpNavigation />
        </div>
      </div>

      {/* Citation Panel (right-side sheet, overlays when open) */}
      <CitationPanel />
    </div>
  );
}
```

- [ ] **Step 2: 创建 language-switcher.tsx**（与初版一致，稍简）

- [ ] **Step 3: 验证** — 侧边栏展开/收起切换流畅

- [ ] **Step 4: 提交** `git commit -m "[00030] feat: add collapsible AppLayout with LanguageSwitcher"`

---

### Task B9: 消息气泡 + 引用面板（取代 popover）

**产出文件**: `src/components/chat/message-bubble.tsx`, `src/components/chat/message-list.tsx`, `src/components/chat/citation-panel.tsx`

**关键变更**：引用标注从 popover 弹出 → **右侧 Sheet 滑出面板**。点引用编号 `[1]`，右侧滑出一个面板显示该引用的规范名、章节、条款号和原文摘录。面板有关闭按钮，也可点面板外区域关闭。

- [ ] **Step 1: 创建 message-bubble.tsx**

```typescript
/**
 * Chat message bubble with Markdown rendering and citation badges.
 *
 * WHY: Citations appear as numbered badges [1] [2] inline at the
 * bottom of each assistant message. Clicking a badge sets
 * selectedCitationIndex in the chat store, which opens the
 * CitationPanel on the right side. This replaces the old popover
 * design — a slide-out panel can display multiple citations
 * simultaneously and doesn't obscure the conversation.
 */

'use client';

import ReactMarkdown from 'react-markdown';
import { cn } from '@/lib/utils';
import type { Message, Citation } from '@/types';
import { useChatStore } from '@/lib/stores/chat-store';
import { Badge } from '@/components/ui/badge';

interface Props {
  message: Message;
  citations?: Citation[];
  isStreaming?: boolean;
}

export function MessageBubble({ message, citations, isStreaming }: Props) {
  const isUser = message.role === 'user';
  const setSelectedCitation = useChatStore((s) => s.setSelectedCitationIndex);

  return (
    <div className={cn('flex w-full gap-3 py-4', isUser && 'justify-end')}>
      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
          MO
        </div>
      )}
      <div
        className={cn(
          'max-w-[75%] rounded-2xl px-4 py-3',
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted',
        )}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}
        {isStreaming && (
          <span className="ml-1 inline-block h-4 w-1 animate-pulse bg-current" />
        )}
        {/* Citation badges → click opens right panel */}
        {citations && citations.length > 0 && !isUser && (
          <div className="mt-3 flex flex-wrap gap-1.5 border-t pt-2">
            {citations.map((c) => (
              <Badge
                key={c.index}
                variant="secondary"
                className="cursor-pointer text-xs hover:bg-secondary/80"
                onClick={() => setSelectedCitation(c.index)}
              >
                [{c.index}] {c.source_doc.split(' ').slice(0, 2).join(' ')}
              </Badge>
            ))}
          </div>
        )}
      </div>
      {isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-bold">
          U
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 创建 citation-panel.tsx（替代原 citation-popover.tsx）**

```typescript
/**
 * Right-side slide-out citation details panel.
 *
 * WHY: Replaces the per-citation popover. When the user clicks a
 * citation badge [1], this panel slides in from the right showing
 * the full source document name, section, clause ID, and excerpt.
 * The panel can be closed with the X button or by clicking outside.
 * Multiple citations are scrollable within the panel.
 *
 * Architecture: Uses shadcn/ui Sheet component positioned on the
 * right side ("right" side prop). The open state is driven by
 * chatStore.selectedCitationIndex !== null.
 */

'use client';

import { useTranslations } from 'next-intl';
import { useChatStore } from '@/lib/stores/chat-store';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';

export function CitationPanel() {
  const t = useTranslations();
  const citations = useChatStore((s) => s.citations);
  const selectedIndex = useChatStore((s) => s.selectedCitationIndex);
  const setSelectedCitation = useChatStore((s) => s.setSelectedCitationIndex);

  const open = selectedIndex !== null;
  const selectedCitation = citations.find((c) => c.index === selectedIndex);

  return (
    <Sheet open={open} onOpenChange={(o) => !o && setSelectedCitation(null)}>
      <SheetContent side="right" className="w-[400px] sm:w-[480px]">
        <SheetHeader>
          <SheetTitle>{t('chat.citation.title')}</SheetTitle>
        </SheetHeader>
        <ScrollArea className="mt-4 h-[calc(100vh-120px)]">
          {/* Show all citations when panel is open, highlight selected */}
          {citations.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('chat.citation.noReferences')}</p>
          ) : (
            <div className="space-y-6">
              {citations.map((c) => (
                <div
                  key={c.index}
                  className={`rounded-lg border p-4 ${
                    c.index === selectedIndex ? 'border-primary bg-primary/5' : ''
                  }`}
                >
                  <p className="font-semibold text-sm">
                    [{c.index}] {c.source_doc}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">{c.section}</p>
                  {c.clause_id && (
                    <p className="mt-1 font-mono text-xs bg-muted px-2 py-0.5 rounded inline-block">
                      {c.clause_id}
                    </p>
                  )}
                  {c.excerpt && (
                    <blockquote className="mt-3 border-l-2 pl-3 text-xs italic text-muted-foreground">
                      {c.excerpt}
                    </blockquote>
                  )}
                  {c.url && (
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 inline-block text-xs text-primary underline"
                    >
                      {t('chat.citation.viewSource')}
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
```

- [ ] **Step 3: 更新 message-list.tsx**（与初版一致）
- [ ] **Step 4: 验证** — 点引用编号，右侧面板滑出显示详情，关闭面板
- [ ] **Step 5: 提交**

---

### Task B10: 聊天输入框（含附件上传 + Web Search 开关）

**产出文件**: `src/components/chat/chat-input.tsx`, `src/components/chat/chat-panel.tsx`, `src/components/chat/empty-state.tsx`

**关键变更**：输入框左侧加 📎 附件上传按钮 + Web Search 开关（Switch 组件）。

- [ ] **Step 1: 创建 chat-input.tsx**

```typescript
/**
 * Chat input bar: textarea + file attachment button + Web Search toggle + send.
 *
 * Layout (bottom of chat area):
 * ┌─────────────────────────────────────────────────────────┐
 * │ [📎] [_______________________________] [Web⇄] [Send]  │
 * │      placeholder text                                │
 * └─────────────────────────────────────────────────────────┘
 *
 * WHY: Web Search toggle lets users optionally augment RAG results
 * with live web search. File attachment supports uploading drawings,
 * specification sheets, or photos for VLM analysis. Both are optional
 * — the core experience is pure text input.
 */

'use client';

import { useRef, KeyboardEvent, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Paperclip, Globe } from 'lucide-react';
import { useChatStore } from '@/lib/stores/chat-store';
import { useChatStream } from '@/lib/hooks/use-chat-stream';

export function ChatInput() {
  const t = useTranslations();
  const {
    inputValue, setInputValue, isLoading, isStreaming,
    messages, webSearchEnabled, toggleWebSearch,
  } = useChatStore();
  const { startStream, stopStream } = useChatStream();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = async () => {
    const content = inputValue.trim();
    if (!content || isLoading) return;
    setInputValue('');
    await startStream({
      model: 'marine-rag-mock',
      messages: [...messages, { role: 'user', content }],
      web_search: webSearchEnabled,
    });
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    // Phase 2: upload file and attach to request. Phase 1: placeholder.
    console.log('File selected:', e.target.files?.[0]?.name);
  }, []);

  return (
    <div className="border-t bg-background p-3">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        {/* File attachment button */}
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 shrink-0"
          onClick={() => fileInputRef.current?.click()}
          title={t('chat.input.attachFile')}
        >
          <Paperclip className="h-4 w-4" />
        </Button>
        <input ref={fileInputRef} type="file" className="hidden" onChange={handleFileSelect} />

        {/* Text input */}
        <Textarea
          ref={textareaRef}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t('chat.input.placeholder')}
          rows={1}
          className="min-h-[40px] resize-none"
          disabled={isLoading}
        />

        {/* Web Search toggle */}
        <Button
          variant={webSearchEnabled ? 'default' : 'ghost'}
          size="icon"
          className="h-9 w-9 shrink-0"
          onClick={toggleWebSearch}
          title={webSearchEnabled ? t('chat.input.webSearchOn') : t('chat.input.webSearchOff')}
        >
          <Globe className={`h-4 w-4 ${webSearchEnabled ? '' : 'text-muted-foreground'}`} />
        </Button>

        {/* Send / Stop button */}
        {isStreaming ? (
          <Button variant="destructive" size="icon" className="h-9 w-9 shrink-0" onClick={stopStream}>
            <span className="text-sm">■</span>
          </Button>
        ) : (
          <Button
            onClick={handleSend}
            disabled={!inputValue.trim() || isLoading}
            className="h-9 shrink-0"
          >
            {t('chat.input.send')}
          </Button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: chat-panel.tsx 和 empty-state.tsx**（与初版一致）

- [ ] **Step 3: 验证** — 附件按钮可点击、Web Search 开关可切换、发送正常

- [ ] **Step 4: 提交**

---

### Task B11: 聊天页面路由

**产出文件**: `src/app/[locale]/(main)/layout.tsx`, `chat/page.tsx`, `chat/[id]/page.tsx`

（与初版一致）

---

### Task B12: 会话侧边栏（完整版）

**产出文件**: `src/components/conversation/conversation-sidebar.tsx`, `conversation-item.tsx`, `conversation-search.tsx`

**关键变更**：侧边栏改为完整 ChatGPT 风格布局——

```
┌──────────────────┐
│ [+ New Chat]     │  ← 上部固定按钮区（游客也可用）
│ [🔍 Search chats]│
│ [🧠 Deep Research]│  ← 仅登录用户可用
├──────────────────┤
│                  │
│  会话历史列表      │  ← 仅登录用户可见；游客显示 "登录后查看历史"
│  (ScrollArea)    │
│                  │
├──────────────────┤
│ [⚙ Settings]    │  ← 下部固定按钮区
│ [❓ Help]        │
├──────────────────┤
│ [👤 用户名/头像]  │  ← 已登录显示头像+名字
│ [Log in]         │  ← 未登录显示登录按钮
└──────────────────┘
```

- [ ] **Step 1: 创建 conversation-sidebar.tsx**

```typescript
/**
 * Full-featured conversation sidebar with login-state-aware rendering.
 *
 * WHY: The sidebar serves different content based on auth status:
 * - Guest: New Chat + Search Chats enabled, Deep Research disabled,
 *   no history list, "Sign in to save" message, Log in button at bottom.
 * - Authenticated: All buttons active, history list populated from API,
 *   avatar + username at bottom with logout option.
 */

'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { useAuthStore } from '@/lib/stores/auth-store';
import { useConversationStore } from '@/lib/stores/conversation-store';
import { useChatStore } from '@/lib/stores/chat-store';
import { ConversationItem } from './conversation-item';
import { ConversationSearch } from './conversation-search';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Plus, Brain, Settings, HelpCircle, LogIn, LogOut, Search } from 'lucide-react';

export function ConversationSidebar() {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const { authStatus, user, logout } = useAuthStore();
  const { conversations, activeId, fetchConversations, setActiveId } = useConversationStore();
  const clearMessages = useChatStore((s) => s.clearMessages);
  const isLoggedIn = authStatus === 'authenticated';

  useEffect(() => {
    if (isLoggedIn) fetchConversations();
  }, [isLoggedIn, fetchConversations]);

  const handleNewChat = () => { clearMessages(); setActiveId(null); router.push(`/${locale}/chat`); };
  const handleSelect = (id: string) => { setActiveId(id); router.push(`/${locale}/chat/${id}`); };
  const handleDeepResearch = () => { /* Phase 2: trigger deep research agent */ };

  const userInitials = user?.username?.slice(0, 2).toUpperCase() || '??';

  return (
    <div className="flex h-full flex-col">
      {/* ── Top action buttons ── */}
      <div className="space-y-1 p-3">
        <Button variant="outline" className="w-full justify-start gap-2 h-9 text-sm" onClick={handleNewChat}>
          <Plus className="h-4 w-4" />{t('sidebar.newChat')}
        </Button>
        <Button variant="ghost" className="w-full justify-start gap-2 h-9 text-sm text-muted-foreground">
          <Search className="h-4 w-4" />{t('sidebar.searchChats')}
        </Button>
        <Button
          variant="ghost"
          className="w-full justify-start gap-2 h-9 text-sm text-muted-foreground"
          disabled={!isLoggedIn}
          onClick={handleDeepResearch}
        >
          <Brain className="h-4 w-4" />{t('sidebar.deepResearch')}
        </Button>
      </div>

      <Separator />

      {/* ── Conversation history ── */}
      {isLoggedIn ? (
        <>
          <div className="px-3 pt-2">
            <ConversationSearch />
          </div>
          <ScrollArea className="flex-1">
            <div className="space-y-0.5 px-2">
              {conversations.length === 0 ? (
                <p className="px-3 py-8 text-center text-xs text-muted-foreground">{t('conversation.empty')}</p>
              ) : (
                conversations.map((conv) => (
                  <ConversationItem
                    key={conv.conversation_id}
                    conversation={conv}
                    isActive={conv.conversation_id === activeId}
                    onSelect={() => handleSelect(conv.conversation_id)}
                  />
                ))
              )}
            </div>
          </ScrollArea>
        </>
      ) : (
        <div className="flex-1 flex items-center justify-center px-4">
          <p className="text-xs text-center text-muted-foreground">{t('conversation.guestEmpty')}</p>
        </div>
      )}

      <Separator />

      {/* ── Bottom: Settings, Help, Login/Avatar ── */}
      <div className="space-y-1 p-3">
        <Button variant="ghost" className="w-full justify-start gap-2 h-9 text-sm text-muted-foreground"
          onClick={() => router.push(`/${locale}/settings`)}>
          <Settings className="h-4 w-4" />{t('sidebar.settings')}
        </Button>
        <Button variant="ghost" className="w-full justify-start gap-2 h-9 text-sm text-muted-foreground">
          <HelpCircle className="h-4 w-4" />{t('sidebar.help')}
        </Button>

        <Separator className="my-2" />

        {isLoggedIn ? (
          <div className="flex items-center gap-2 px-1 py-1">
            <Avatar className="h-7 w-7">
              <AvatarFallback className="text-xs">{userInitials}</AvatarFallback>
            </Avatar>
            <span className="flex-1 truncate text-sm">{user?.username}</span>
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={logout} title={t('sidebar.logOut')}>
              <LogOut className="h-3 w-3" />
            </Button>
          </div>
        ) : (
          <Button variant="outline" className="w-full justify-start gap-2 h-9 text-sm"
            onClick={() => router.push(`/${locale}/login`)}>
            <LogIn className="h-4 w-4" />{t('sidebar.logIn')}
          </Button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: conversation-item.tsx 和 conversation-search.tsx**（与初版一致）

- [ ] **Step 3: 验证**

1. 未登录 → 侧边栏显示 "登录后查看历史" + 底部署名 "Log in"
2. 点击 Log in → 登录后 → 侧边栏显示会话列表 + 底部头像+名字
3. Deep Research 按钮在未登录时 disabled
4. New Chat 游客也可用

- [ ] **Step 4: 提交**

---

### Task B13: 登录/注册页面

**产出文件**: `src/app/[locale]/(auth)/login/page.tsx`, `register/page.tsx`, `src/components/auth/login-form.tsx`, `register-form.tsx`

**关键变更**：登录"成功"后调用 `useAuthStore().login()` 设置登录态。Phase 1 Mock：表单校验通过即视为登录成功。

- [ ] **Step 1: 创建 login-form.tsx**

```typescript
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { useAuthStore } from '@/lib/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export function LoginForm() {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault(); setError('');
    if (!email.includes('@')) { setError(t('auth.errors.invalidEmail')); return; }
    if (password.length < 8) { setError(t('auth.errors.passwordLength')); return; }
    // Phase 1 mock login
    login({ user_id: 'user_mock_01', username: email.split('@')[0], email, role: 'viewer' }, 'mock-token');
    router.push(`/${locale}/chat`);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h1 className="text-2xl font-bold">{t('auth.login.title')}</h1>
      <p className="text-muted-foreground">{t('auth.login.subtitle')}</p>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Input type="email" placeholder={t('auth.login.email')} value={email} onChange={(e) => setEmail(e.target.value)} required />
      <Input type="password" placeholder={t('auth.login.password')} value={password} onChange={(e) => setPassword(e.target.value)} required />
      <Button type="submit" className="w-full">{t('auth.login.submit')}</Button>
      <p className="text-center text-sm text-muted-foreground">
        {t('auth.login.noAccount')}{' '}<a href={`/${locale}/register`} className="underline">{t('auth.login.register')}</a>
      </p>
    </form>
  );
}
```

- [ ] **Step 2: register-form.tsx**（同模式，增加 username + confirm password）
- [ ] **Step 3: 页面路由** — 与初版一致
- [ ] **Step 4: 验证 + 提交**

---

### Task B14: 设置页面 + 知识库浏览页面

**产出文件**: `src/app/[locale]/(main)/settings/page.tsx`, `knowledge/page.tsx`

（与初版一致）

---

### Task B15: 对话快速定位窄条（Jump Navigation）

**产出文件**: `src/components/navigation/jump-navigation.tsx`

- [ ] **Step 1: 创建 jump-navigation.tsx**

```typescript
/**
 * Right-side narrow strip showing all user questions in the current chat.
 * Clicking a question scrolls to that message in the chat area.
 *
 * Visual: a ~48px wide vertical strip on the right edge of the chat area.
 * Each user question is collapsed to a compact icon+first-line preview.
 *
 * WHY: In long conversations with dozens of exchanges, users need a quick
 * way to jump to earlier questions. DeepSeek and ChatGPT both have this
 * feature. The strip only appears when there are ≥ 2 user messages.
 */

'use client';

import { useChatStore } from '@/lib/stores/chat-store';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { MessageSquare } from 'lucide-react';

export function JumpNavigation() {
  const messages = useChatStore((s) => s.messages);

  // Extract user questions with their index
  const userMessages = messages
    .map((msg, i) => ({ ...msg, index: i }))
    .filter((msg) => msg.role === 'user');

  if (userMessages.length < 2) return null; // Don't show for single-question chats

  const scrollToMessage = (index: number) => {
    const el = document.getElementById(`msg-${index}`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  return (
    <div className="hidden w-12 shrink-0 border-l bg-muted/10 md:block">
      <ScrollArea className="h-full">
        <div className="flex flex-col items-center gap-1 p-1">
          {userMessages.map((msg) => (
            <Tooltip key={msg.index}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => scrollToMessage(msg.index)}
                >
                  <MessageSquare className="h-3 w-3 text-muted-foreground" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="left" className="max-w-[200px]">
                <p className="text-xs line-clamp-2">{msg.content}</p>
              </TooltipContent>
            </Tooltip>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
```

- [ ] **Step 2: 更新 message-bubble.tsx** — 每条消息加 `id={`msg-${index}`}` 属性以支持跳转定位

```typescript
// In MessageBubble's outermost div, add:
id={`msg-${messageIndex}`}  // messageIndex passed as prop from MessageList
```

- [ ] **Step 3: 更新 message-list.tsx** — 传递 index 给 MessageBubble

- [ ] **Step 4: 验证** — 多轮对话后右侧出现窄条，点图标跳转到对应消息

- [ ] **Step 5: 提交**

---

### Task B16: Playwright E2E 测试

**产出文件**: `playwright.config.ts`, `tests/e2e/chat.spec.ts`, `tests/e2e/conversations.spec.ts`, `tests/e2e/i18n.spec.ts`, `tests/e2e/auth.spec.ts`

- [ ] **Step 1: playwright.config.ts**（与初版一致）
- [ ] **Step 2: chat.spec.ts** — 覆盖游客聊天、流式输出、引用面板打开/关闭、附件按钮、Web Search 开关、跳转窄条
- [ ] **Step 3: conversations.spec.ts** — 侧边栏展开/收起、登录后面列表加载
- [ ] **Step 4: i18n.spec.ts** — 5 语种切换
- [ ] **Step 5: auth.spec.ts** — 登录/登出、游客模式、侧边栏登录态变化

（完整测试代码在实现时编写，此处省略。）

---

### Task B17: 翻译非英文语言文件

- [ ] **Step 1:** 将 `en.json` 中所有 value 翻译为中文/韩文/日文/挪威文
- [ ] **Step 2:** 切换到每种语言逐个页面验证

---

### Task B18: 收尾

- [ ] 更新 `.dev/tasks.md`（00030 → ✅）
- [ ] 写 `.dev/test_records/00030.md`
- [ ] 更新 `.dev/module-memory/m6-user-portal.md`
- [ ] 最终提交

---

## 自审清单

- [ ] 侧边栏展开/收起切换流畅，无布局抖动
- [ ] 游客模式可聊天、无历史列表、底部署名 "Log in"
- [ ] 登录后历史列表加载、底部显示头像+名字
- [ ] Deep Research 按钮游客 disabled
- [ ] 5 语种 URL 路由正确，语言切换即时
- [ ] 所有 UI 文字零硬编码（i18n key）
- [ ] 流式聊天正常
- [ ] 引用编号点击 → 右侧面板滑出 → 显示引用详情
- [ ] 附件按钮 + Web Search 开关存在
- [ ] 多轮对话后右侧跳转窄条出现，点击跳转
- [ ] E2E 测试全部通过
- [ ] TypeScript 0 错误
