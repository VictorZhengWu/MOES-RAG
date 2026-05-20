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
| 00030-P19 | 忘记密码 / 重置密码 | 未开始（UI 入口待加） | M5 Auth API + SMTP |
| 00030-P20 | 项目/Project CRUD | 占位页面，4 个 mock 项目 | M5 Project API |
| 00030-P21 | 文件上传 — 真实存储 | UI 就绪（拖放+解析+预览），仅 Mock | M1 文件处理管线 + M2 存储 |

**验证方法：** Playwright E2E 测试覆盖核心用户路径
**自动化验证命令：** `npx playwright test`
**通过条件：** 全部 passed，0 failed（当前 9/9）
**Task 类型：** 模块/服务类
**依赖：** 00020（Mock Server）
**关联文件：** `m6-user-portal/src/`

---

### ✅ 00040 — M7 管理后台（含 i18n）

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

**M7 待实现功能（ 🔸 跨模块 / Phase 2 实现）：**

| ID | 功能 | 当前状态 | 依赖 |
|----|------|---------|------|
| 00040-P1 | 付款/计费模块 | 未开始 | deploy.yaml features.billing 开关 + M5 Billing API + Stripe/PayPal |
| 00040-P2 | 部署模式 feature 开关 | 未开始 | deploy.yaml → 控制 billing/web_search/deep_research 显隐 |
| 00040-P3 | 忘记密码 / 重置密码流程 | 未开始（UI 入口待加） | M5 Auth API + SMTP 邮件服务 |
| 00040-P4 | 社交登录真实 OAuth | 6 按钮 UI 就绪，仅 console.log | M5 OAuth 集成 |
| 00040-P5 | 知识图谱可视化（图形版） | 当前为卡片+列表 | D3.js/vis.js + 真实 KG 数据 |
| 00040-P6 | 系统监控真实数据 | Mock 数据 | M5 Monitoring API |
| 00040-P7 | 管理员登录保护 | 无鉴权，直接可访问 | M5 Auth + 管理员角色校验 |

> 注：付款模块仅在 SaaS 部署模式下启用（`deploy.yaml` → `features.billing: true`）。
> Personal 和 Enterprise 模式自动隐藏。

---

## Phase 2: 后端核心

### ✅ 00050 — M2 存储抽象层

> **详细设计**：`.dev/specs/m2-storage-design-2026-05-18.md`
> **全局规范**：所有 Python 源程序必须有详细英文注释（WHAT + WHY）。

---

#### ✅ 00050-01 — 配置解析模块 (config.py)

**功能描述：**
- 实现 `deploy.yaml` 解析器，将 YAML 转换为类型安全的 dataclass 对象
- 包含：`StorageConfig`、`VectorStoreConfig`/`ChromaDBConfig`、`DocumentIndexConfig`/`MeilisearchConfig`、`RelationalDBConfig`/`SQLiteConfig`、`FileStoreConfig`/`LocalFSConfig`
- 每个子配置类实现 `from_dict()` 工厂方法，提供合理默认值
- `load_config(path)` 函数：读取 YAML → 解析为 `StorageConfig`
- 无效 `backend` 值抛出 `ValueError`

**验证方法：** 4 个测试用例（合法 YAML、缺失字段默认值、无效 backend、文件不存在）
**自动化验证命令：** `python -m pytest m2-storage/tests/test_config.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 工具/原子函数类
**依赖：** 无
**关联文件：** `m2-storage/src/config.py`, `m2-storage/tests/test_config.py`, `m2-storage/deploy.yaml`

---

#### ✅ 00050-02 — 工厂函数 (factory.py)

**功能描述：**
- 实现 `create_storage_manager(config_path)` + 4 个 `_create_*` 内部函数
- 每个 `_create_*` 根据 `backend` 字段用 if/else 选择具体实现类
- 未实现的 backend 抛出 `ValueError`

**验证方法：** 2 个测试用例（正确配置返回正确类型、无效 backend 抛异常）
**自动化验证命令：** `python -m pytest m2-storage/tests/test_factory.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 工具/原子函数类
**依赖：** 00050-01
**关联文件：** `m2-storage/src/factory.py`, `m2-storage/tests/test_factory.py`

---

#### ✅ 00050-03 — StorageManager 生命周期管理 (manager.py)

**功能描述：**
- `StorageManager` 持有 4 个后端引用；不代理转发方法
- `initialize()`: `asyncio.gather` 并发初始化 4 个后端
- `health_check()`: 并发健康检查，返回 `dict[str, bool]`
- `close()`: 并发关闭所有连接
- 单个后端初始化失败不阻断其他后端

**验证方法：** 4 个测试用例（并发初始化、健康检查汇总、并发关闭、部分失败场景）
**自动化验证命令：** `python -m pytest m2-storage/tests/test_manager.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 工具/原子函数类
**依赖：** 00050-02
**关联文件：** `m2-storage/src/manager.py`, `m2-storage/tests/test_manager.py`

---

#### ✅ 00050-04 — VectorStore 基类 + ChromaDB 实现

**功能描述：**
- `vector_store/base.py`：`BaseVectorStore` 抽象类（继承 `VectorStoreProtocol`），补生命周期方法
- `vector_store/chromadb_store.py`：`ChromaDBStore`，使用 `chromadb.PersistentClient`
- 实现 `insert/search/delete/count/health_check/close`

**验证方法：** 6 个测试用例（协议合规、insert+search、filter 过滤、delete、空搜索、健康检查）
**自动化验证命令：** `python -m pytest m2-storage/tests/test_chromadb.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 模块/服务类
**依赖：** 00050-03
**关联文件：** `m2-storage/src/vector_store/base.py`, `m2-storage/src/vector_store/chromadb_store.py`, `m2-storage/tests/test_chromadb.py`

---

#### ✅ 00050-05 — DocumentIndex 基类 + Meilisearch 实现

**功能描述：**
- `document_index/base.py`：`BaseDocumentIndex` 抽象类（继承 `DocumentIndexProtocol`）
- `document_index/meilisearch_index.py`：`MeilisearchIndex`，使用 `meilisearch.Client`
- 实现 `index/search/delete/health_check/close`

**验证方法：** 6 个测试用例（协议合规、index+search、filter、delete、空搜索、健康检查）
**自动化验证命令：** `python -m pytest m2-storage/tests/test_meilisearch.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 模块/服务类
**依赖：** 00050-03, Meilisearch 进程（conftest fixture 管理）
**关联文件：** `m2-storage/src/document_index/base.py`, `m2-storage/src/document_index/meilisearch_index.py`, `m2-storage/tests/test_meilisearch.py`

---

#### ✅ 00050-06 — RelationalDB 基类 + SQLite 实现

**功能描述：**
- `relational_db/base.py`：`BaseRelationalDB` 抽象类（继承 `RelationalDBProtocol`）
- `relational_db/sqlite_db.py`：`SQLiteDB`，使用 `sqlalchemy.ext.asyncio` + `aiosqlite`
- M2 不定义 ORM 模型——只提供引擎和 session，模型由上层模块定义
- 实现 `initialize/get_session/health_check/close`

**验证方法：** 5 个测试用例（协议合规、建表、session 可用、健康检查、自动创建父目录）
**自动化验证命令：** `python -m pytest m2-storage/tests/test_sqlite.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 模块/服务类
**依赖：** 00050-03
**关联文件：** `m2-storage/src/relational_db/base.py`, `m2-storage/src/relational_db/sqlite_db.py`, `m2-storage/tests/test_sqlite.py`

---

#### ✅ 00050-07 — FileStore 基类 + LocalFS 实现

**功能描述：**
- `file_store/base.py`：`BaseFileStore` 抽象类（继承 `FileStoreProtocol`）
- `file_store/local_fs.py`：`LocalFSStore`，使用 `aiofiles`
- 路径安全：拒绝 `../` 穿越，`os.path.realpath` 校验
- 实现 `put/get/delete/list/get_url/health_check/close`

**验证方法：** 8 个测试用例（协议合规、put+get 往返、metadata、delete、list、不存在 key、路径穿越拒绝、健康检查）
**自动化验证命令：** `python -m pytest m2-storage/tests/test_local_fs.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 模块/服务类
**依赖：** 00050-03
**关联文件：** `m2-storage/src/file_store/base.py`, `m2-storage/src/file_store/local_fs.py`, `m2-storage/tests/test_local_fs.py`

---

#### ✅ 00050-08 — 测试基础设施 + 集成测试 (conftest.py + test_manager.py)

**功能描述：**
- `conftest.py`：共享 fixtures（tmp_config_path, tmp_data_dir, 4 个已初始化后端实例, storage_manager）
- `test_manager.py`：StorageManager 端到端集成测试

**验证方法：** 5 个测试用例（完整生命周期、4 后端健康检查、跨后端操作、关闭后不可用）
**自动化验证命令：** `python -m pytest m2-storage/tests/test_manager.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 集成/跨模块类
**依赖：** 00050-04, 00050-05, 00050-06, 00050-07
**关联文件：** `m2-storage/tests/conftest.py`, `m2-storage/tests/test_manager.py`

---

#### ✅ 00050-09 — 模块打包与最终验证 (pyproject.toml + requirements.txt + __init__.py)

**功能描述：**
- `pyproject.toml`：包元数据，依赖按后端分组 `[project.optional-dependencies]`
- `requirements.txt`：锁定开发依赖
- `src/__init__.py`：导出 `StorageManager`, `create_storage_manager`
- 全量测试套件运行验证

**验证方法：** pip install -e . 成功、全量 pytest 通过
**自动化验证命令：** `python -m pytest m2-storage/tests/ -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 集成/跨模块类
**依赖：** 00050-08
**关联文件：** `m2-storage/pyproject.toml`, `m2-storage/requirements.txt`, `m2-storage/src/__init__.py`

---

**依赖关系图：**

```
00050-01 (config.py)
    ↓
00050-02 (factory.py)
    ↓
00050-03 (manager.py)
    ↓
┌───────────────────────────────────────┐
│  00050-04  00050-05  00050-06  00050-07 │  ← 4 个后端可并行
│  (ChromaDB)(MeiliSrch)(SQLite) (LocalFS)│
└───────────────────────────────────────┘
    ↓
00050-08 (集成测试 + conftest)
    ↓
00050-09 (打包 + 最终验证)
```

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
