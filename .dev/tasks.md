# Tasks — Marine & Offshore Expert System

> 状态：🔲 待开始 / 🔄 进行中 / ✅ 已完成 / ❌ 熔断
> **全局规范**：所有 Python 和 TypeScript 源程序必须有详细英文注释（WHAT 程序做什么 + WHY 为什么需要这段程序）。详见设计文档 Section 7。

---

## Phase 1: 前端骨架 + Mock Server

### ✅ 00010 — contracts/ 接口契约包

**功能描述：**
- 定义全部模块间通信的 Protocol 接口
- 定义公共数据模型（Document, Chunk, Entity, Relation 等）
- 定义 REST API Schema（Pydantic models）
- 输出可 pip install 的共享包

**验证方法：** 所有 Protocol 可被正确 import，类型检查通过
**自动化验证命令：** `python -c "from contracts import *; print('OK')"`
**通过条件：** 无 import 错误，无类型错误
**Task 类型：** 工具/原子函数类
**依赖：** 无
**关联文件：** `contracts/__init__.py`, `contracts/document.py`, `contracts/storage.py`, `contracts/retrieval.py`, `contracts/knowledge_graph.py`, `contracts/qa_engine.py`, `contracts/api_schemas.py`

---

### ✅ 00020 — Mock Server

**功能描述：**
- 基于 contracts/ 中的 API Schema 生成 Mock HTTP 服务
- 所有端点返回符合格式的假数据
- 支持 SSE 流式模拟
- 前端无需任何后端即可完整运行

**验证方法：** 所有 API 端点返回 200，响应格式符合 OpenAPI Schema
**自动化验证命令：** `pytest tests/ -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 模块/服务类
**依赖：** 00010
**关联文件：** `mock-server/src/mock_server/`（独立模块，不归属 M5，调试复用）

---

### 🔄 00030 — M6 用户前端（含 i18n）

> **核心 UI 已完成（11 项功能），18 项占位功能待后端就绪后完善。**
> **Playwright: 9/9 tests passing.**

**已完成功能：**
- ✅ 聊天界面（消息气泡、Markdown、流式输出、停止生成）
- ✅ 引用面板（右侧第三列，规范来源/章节/条款/摘录）
- ✅ 可折叠侧边栏（展开/图标条双态，New Chat/Search/Deep Research/Projects）
- ✅ 5 语种 i18n（URL 路由、即时切换、Settings 中管理）
- ✅ 主题切换（Light/Dark/System，即时生效）
- ✅ 跳转窄条（固定定位横线、悬停列表框、点击跳转、滚动同步）
- ✅ Settings 对话框（General/Profile/About 三标签）
- ✅ 知识库浏览（从 API 加载、搜索+船级社+专业筛选）
- ✅ 全局拖放上传（浏览器任意位置、覆盖层提示、消息气泡显示文件图标）
- ✅ 会话右键菜单（Share/Rename/Move to Project/Pin/Delete）
- ✅ 登录/注册 UI（表单校验、社交登录按钮）
- ✅ 输入框（附件按钮、Web Search 开关、Enter/Shift+Enter）
- ✅ Playwright E2E（9 tests, all passing）

**占位功能（🔸 待后端就绪后完善）：**

| ID | 功能 | 当前状态 | 依赖 |
|----|------|---------|------|
| 00030-P1 | 邮箱登录 | 客户端校验+localStorage，永远成功 | M5 Auth API |
| 00030-P2 | 邮箱注册 | 客户端校验后直接"登录" | M5 Auth API |
| 00030-P3 | 社交登录(OAuth) | 6 图标按钮，点击仅 console.log | M5 OAuth |
| 00030-P4 | 会话历史持久化 | Mock Server 3 条假数据 | M5 Conversation API |
| 00030-P5 | 会话重命名 | 调用 Mock API | M5 Conversation API |
| 00030-P6 | 会话删除 | 调用 Mock API | M5 Conversation API |
| 00030-P7 | 会话分享 | 弹窗显示假链接+复制 | M5 Share API |
| 00030-P8 | Move to Project | 10 个 mock 项目，仅 console.log | M5 Project API |
| 00030-P9 | Pin 对话 | console.log | M5 Conversation API |
| 00030-P10 | 文件真实上传 | UI 就绪，仅存文件名 | M1 文件处理管线 |
| 00030-P11 | 头像上传 | Profile 页文件选择器，仅 log | M5 User API |
| 00030-P12 | Web Search | UI 开关可切换 | M5 搜索集成 |
| 00030-P13 | Deep Research | 按钮 disabled 或 console.log | M5 Agent 流程 |
| 00030-P14 | 会话搜索 | 客户端输入过滤 | M5 Search API |
| 00030-P15 | Projects 页面 | 4 个 mock 项目 | M5 Project API |
| 00030-P16 | Help 页面 | 按钮无响应 | 文档编写 |
| 00030-P17 | Delete Account | 按钮 disabled | M5 User API |
| 00030-P18 | About 社交链接 | 占位 URL | 真实地址配置 |

**验证方法：** Playwright E2E 测试覆盖核心用户路径
**自动化验证命令：** `npx playwright test`
**通过条件：** 全部 passed，0 failed（当前 9/9）
**Task 类型：** 模块/服务类
**依赖：** 00020（Mock Server）
**关联文件：** `m6-user-portal/src/`

---

### 🔲 00040 — M7 管理后台（含 i18n）

**功能描述：**
- 文档上传界面（拖拽 + 批量 + 进度条）
- 元数据标注表单
- 解析任务状态列表
- 知识库管理（查看/编辑/删除）
- 知识图谱可视化浏览
- LLM 多后端配置页面
- 用户管理 & 配额设置
- 监控仪表板
- **i18n**: 5 语种支持，与 M6 共享 i18n 基础设施；所有 UI 文字零硬编码
- **代码注释**: 所有 TypeScript/TSX 文件必须包含详细英文注释（WHAT + WHY）

**验证方法：** Playwright E2E 测试覆盖管理操作全链路
**自动化验证命令：** `npx playwright test`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 模块/服务类
**依赖：** 00020（Mock Server）
**关联文件：** `m7-admin-portal/src/`

---

## Phase 2: 后端核心

### 🔲 00050 — M2 存储抽象层

（详细设计将在开发本模块时制定）

### 🔲 00060 — M1 文档解析引擎

（详细设计将在开发本模块时制定）

### 🔲 00070 — M3 检索引擎

（详细设计将在开发本模块时制定）

### 🔲 00080 — M4 知识图谱引擎

（详细设计将在开发本模块时制定）

### 🔲 00090 — M5 智能问答引擎

（详细设计将在开发本模块时制定）

---

## Phase 3: 对外服务与部署

### 🔲 00100 — M8 API 网关

（详细设计将在开发本模块时制定）

### 🔲 00110 — deploy/ 部署配置

（详细设计将在开发本模块时制定）
