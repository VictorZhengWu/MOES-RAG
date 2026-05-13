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

### 🔲 00030 — M6 用户前端（含 i18n）

**功能描述：**
- 类 DeepSeek 问答对话界面
- Markdown 渲染 + 代码高亮 + 引用标注
- 会话管理（新建/切换/搜索/删除）
- 知识库浏览
- 个人设置 & API Key 管理
- 响应式布局
- **i18n**: 5 语种支持（EN/ZH/KO/JA/NO），缺省英文；所有 UI 文字零硬编码，语言资源文件化管理；语言切换即时生效无需刷新
- **代码注释**: 所有 TypeScript/TSX 文件必须包含详细英文注释（WHAT + WHY）

**验证方法：** Playwright E2E 测试覆盖核心用户路径
**自动化验证命令：** `npx playwright test`
**通过条件：** 全部 passed，0 failed
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
