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

> **详细设计**：`.dev/specs/m1-doc-parsing-design-2026-05-21.md`
> **Docling 参考**：`.dev/specs/docling-capabilities-reference-2026-05-21.md`

**核心原则**：准确性第一——复杂内容未通过质量门禁不得进入向量数据库。

---

#### ✅ 00060-01 — 项目骨架与配置系统 (config.py + pyproject.toml)

**功能描述：**
- 创建 m1-doc-parsing 项目结构（目录、pyproject.toml、requirements.txt）
- 实现 config.py：GPU 检测 + 后端/OCR 引擎选择 + 推荐逻辑
- 硬件检测：`nvidia-smi` + `torch.cuda.is_available()` + VRAM 查询
- 分层推荐：
  - GPU ≥ 8GB + Linux → vLLM + PaddleOCR-VL-1.5
  - GPU ≥ 8GB + Windows → Transformers + GraniteDocling-258M
  - GPU < 8GB → INT8 量化或 Standard Pipeline
  - 无 GPU → EasyOCR + CPU 模式
- 解析 deploy.yaml 中的 M1 专属配置段

**验证方法：** 4 个测试用例（有 GPU 场景 mock、无 GPU 场景、配置加载、无效配置报错）
**Task 类型：** 工具/原子函数类
**依赖：** 无
**关联文件：** `m1-doc-parsing/m1_parser/core/config.py`, `m1-doc-parsing/tests/test_config.py`

---

#### ✅ 00060-02 — 格式路由 (router.py)

**功能描述：**
- 文件类型嗅探（magic bytes + 扩展名）
- 格式分类：
  - PDF/IMAGE → 用户可选择 Docling/Marker/MinerU
  - DOCX/XLSX/PPTX/HTML → 强制 Docling
- 不支持格式 → 抛出明确错误信息

**验证方法：** 5 个测试用例（PDF 识别、DOCX 识别、图片识别、不支持的 zip 文件、无扩展名文件）
**Task 类型：** 工具/原子函数类
**依赖：** 无
**关联文件：** `m1-doc-parsing/m1_parser/core/router.py`, `m1-doc-parsing/tests/test_router.py`

---

#### 🔲 00060-03 — Docling 后端适配器 (docling_backend.py)

**功能描述：**
- 封装 Docling DocumentConverter 为标准接口
- 支持 Standard Pipeline 和 VLM Pipeline 切换
- 按格式配置 Pipeline（PDF→PdfFormatOption, DOCX→WordFormatOption, PPTX→PptxFormatOption, IMAGE→ImageFormatOption）
- 启用 `generate_page_images`, `generate_picture_images`, `images_scale=2.0`
- 批量转换：`convert_all()` with `raises_on_error=False`
- OCR 引擎可配置：`ocr_options = EasyOcrOptions/SuryaOcrOptions/TesseractCliOcrOptions/RapidOcrOptions`
- VLM 模式：通过 Preset 切换模型（`granite_docling`, `deepseek_ocr`, `paddleocr_vl` 等）
- 本地 VLM 用 Transformers 引擎；远程用 `ApiVlmEngineOptions`

**验证方法：** 4 个测试用例（PDF 转 MD、DOCX 转 MD、图片 OCR 转 MD、批量转换）
**Task 类型：** 模块/服务类
**依赖：** 00060-01, 00060-02
**关联文件：** `m1-doc-parsing/m1_parser/backends/docling_backend.py`, `m1-doc-parsing/tests/test_docling_backend.py`

---

#### 🔲 00060-04 — Marker 与 MinerU 后端适配器 (marker_backend.py + mineru_backend.py)

**功能描述：**
- Marker 后端：调用 Marker CLI/API，PDF → Markdown。封装为 Docling 兼容的 adapter 接口
- MinerU 后端：调用 MinerU CLI/API（`magic-pdf`），PDF → Markdown. 封装为同一 adapter 接口
- 两个适配器遵循相同的 `BackendInterface`（输入路径 → 输出 DoclingDocument 或 Markdown）
- 两后端仅处理 PDF + IMAGE 格式

**验证方法：** 2 个测试用例（Marker PDF→MD、MinerU PDF→MD；skip if 工具未安装）
**Task 类型：** 模块/服务类
**依赖：** 00060-03
**关联文件：** `m1-doc-parsing/m1_parser/backends/marker_backend.py`, `m1-doc-parsing/m1_parser/backends/mineru_backend.py`

---

#### 🔲 00060-05 — 主转换器 (converter.py)

**功能描述：**
- `convert(input_path, options) → ParsedDocument`：单文件转换入口
- `convert_batch(input_paths, options) → list[ParsedDocument]`：批量转换
- 集成 router → backend 选择 → Docling 解析 → 元数据提取 → 表格增强 → 质量门禁
- 完整的 6 阶段管线编排
- 进度回调机制（`on_progress` callback，大文件长时间运行需要）

**验证方法：** 3 个测试用例（单文件转换全流程、批量转换、失败文件不中断批量）
**Task 类型：** 集成/跨模块类
**依赖：** 00060-03, 00060-04
**关联文件：** `m1-doc-parsing/m1_parser/core/converter.py`, `m1-doc-parsing/tests/test_converter.py`

---

#### 🔲 00060-06 — 海洋工程元数据提取 (marine_metadata.py)

**功能描述：**
- 自动提取 5 个字段：
  1. `classification_society`：正则 `DNV|ABS|CCS|LR|BV|NK|RINA|KR|IACS|IMO`
  2. `regulation_name`：文件名模式 + 文档标题首行匹配
  3. `version_year`：正则 `(20\d{2}|19\d{2})`，取第一个匹配
  4. `chapter_section`：正则 `Pt\.?\s*\d+|Ch\.?\s*\d+|§\s*[\d.]+`
  5. `language`：langdetect 或 Docling 内部语言检测
- 作为 Docling Enrichment Model 实现（`BaseItemAndImageEnrichmentModel` 子类）
- 提取结果写入 `ParsedDocument.metadata`
- 用户可在 M7 核查并修改

**验证方法：** 5 个测试用例（每个字段一个，用预设文本片段验证正则提取）
**Task 类型：** 模块/服务类
**依赖：** 00060-05
**关联文件：** `m1-doc-parsing/m1_parser/enrichments/marine_metadata.py`, `m1-doc-parsing/tests/test_marine_metadata.py`

---

#### ✅ 00060-07 — 复杂表格处理 (table_annotator.py + table_merger.py + quality.py)

**功能描述：**
- `table_merger.py`：跨页表格检测与合并（检测缺少表头行 → 向前回溯 → 复用表头）
- `table_annotator.py`：Header-to-Cell 关联（规则引擎：每个数据单元格关联到其行表头和列表头）
- `quality.py`：复杂度评分引擎（7项评分标准，3级门禁）
- 低置信度 Chunk：`confidence < 1.0`, `review_required = True`
- 复杂 Chunk：阻止写入 VectorStore，通知 M7 审核

**验证方法：** 5 个测试用例（跨页合并、header-cell 关联、得分0自动通过、得分3+阻止、得分1-2低置信度）
**Task 类型：** 模块/服务类
**依赖：** 00060-05
**关联文件：** `m1-doc-parsing/m1_parser/enrichments/table_annotator.py`, `m1-doc-parsing/m1_parser/enrichments/table_merger.py`, `m1-doc-parsing/m1_parser/core/quality.py`, `m1-doc-parsing/tests/test_table_annotator.py`, `m1-doc-parsing/tests/test_table_merger.py`, `m1-doc-parsing/tests/test_quality.py`

---

#### 🔲 00060-08 — 输出序列化与图片管理 (serializer.py + image_manager.py)

**功能描述：**
- `serializer.py`：ParsedDocument → Markdown / JSON / HTML 三格式输出
- `image_manager.py`：
  - 提取内嵌图片（原格式保存到 `figures/`）
  - 生成页面截图（PNG, 144 DPI, `pages/`）
  - 生成表格截图（PNG, `tables/`）
  - 图片元数据侧车写入（`.meta.json`）
  - 路径穿越校验（复用 M2 已验证的 `_is_safe_key()` 逻辑）
- 输出目录结构：`{output_dir}/{doc_id}/full.md` + 子目录
- Markdown 内部使用相对路径引用图片

**验证方法：** 4 个测试用例（MD 输出含图片引用、JSON 输出完整、HTML 输出正确、图片侧车内容正确）
**Task 类型：** 模块/服务类
**依赖：** 00060-05
**关联文件：** `m1-doc-parsing/m1_parser/output/serializer.py`, `m1-doc-parsing/m1_parser/output/image_manager.py`, `m1-doc-parsing/tests/test_serializer.py`, `m1-doc-parsing/tests/test_image_manager.py`

---

#### 🔲 00060-09 — Chunking 封装 (chunker.py)

**功能描述：**
- 封装 Docling Hybrid Chunker + HuggingFace Tokenizer
- Tokenizer 与 M5 嵌入模型对齐（BGE-M3 / GTE-Qwen2）
- 配置：`max_tokens`, `merge_peers=True`, `repeat_table_header=True`
- 输出 `list[Chunk]` 符合 `contracts/document.py`
- 每个 Chunk 附带 `confidence` 和 `review_required` 字段
- 支持 `contextualize()` 添加标题路径前缀

**验证方法：** 3 个测试用例（分块数正确、token 不超限、表格跨块表头重复）
**Task 类型：** 模块/服务类
**依赖：** 00060-08
**关联文件：** `m1-doc-parsing/m1_parser/output/chunker.py`, `m1-doc-parsing/tests/test_chunker.py`

---

#### 🔲 00060-10 — M2 存储桥接 (m2_bridge.py)

**功能描述：**
- `write_document_record(doc) → doc_id`：写入 `m1_documents` 表
- `create_parsing_task(doc_id, config) → task_id`：写入 `m1_parsing_tasks` 表
- `store_file(manager, key, data) → key`：写入 FileStore
- `store_chunks(manager, chunks)`：写入 VectorStore（仅 `review_required=False` 的）
- `store_fulltext(manager, chunks)`：写入 DocumentIndex
- 自动检查 `chunk.review_required`，阻止未审核内容写入 VectorStore

**验证方法：** 3 个测试用例（文档记录写入、文件存储往返、复杂 chunk 被阻止写入 VectorStore）
**Task 类型：** 集成/跨模块类
**依赖：** 00060-09, M2 (00050)
**关联文件：** `m1-doc-parsing/m1_parser/integration/m2_bridge.py`, `m1-doc-parsing/tests/test_m2_bridge.py`

---

#### 🔲 00060-11 — Standalone CLI 与 Web UI (cli.py + web_server.py + web_ui.html)

**功能描述：**
- CLI：`m1-parser input.pdf --backend docling --ocr paddleocr --output ./out/ --format md`
- Web Server：FastAPI 单进程，`/upload` 上传端点，`/parse` 解析端点，`/download/{doc_id}` 下载端点
- Web UI：单文件 HTML + CSS + JS，拖放上传 + 下拉配置 + Markdown 实时预览 + 下载按钮
- 独立模式不依赖 M6/M7

**验证方法：** 3 个测试用例（CLI 单文件、CLI 批量、Web upload API 返回成功）
**Task 类型：** 模块/服务类
**依赖：** 00060-05
**关联文件：** `m1-doc-parsing/m1_parser/standalone/cli.py`, `m1-doc-parsing/m1_parser/standalone/web_server.py`, `m1-doc-parsing/m1_parser/standalone/web_ui.html`, `m1-doc-parsing/tests/test_cli.py`

---

#### 🔲 00060-12 — 打包与最终验证 (pyproject.toml + requirements.txt + 全量测试)

**功能描述：**
- pyproject.toml：依赖分组（`[core]`, `[vlm]`, `[ocr]`, `[all]`, `[dev]`）
- requirements.txt：锁定开发依赖
- `__init__.py` 公开 API 导出（`convert`, `convert_batch`, `detect_hardware`）
- 全量测试套件通过

**验证方法：** pip install 成功、全量 pytest 通过、CLI 可执行
**Task 类型：** 集成/跨模块类
**依赖：** 00060-01 ~ 00060-11
**关联文件：** `m1-doc-parsing/pyproject.toml`, `m1-doc-parsing/requirements.txt`, `m1-doc-parsing/m1_parser/__init__.py`

---

**依赖关系图：**

```
00060-01 (config) ──→ 00060-02 (router) ──→ 00060-03 (Docling backend)
                                                │
                           00060-04 (Marker/MinerU)
                                                │
                           00060-05 (converter) ←┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
    00060-06              00060-07              00060-08
  (marine_metadata)   (表格处理+质量门禁)    (序列化+图片管理)
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                │
                          00060-09 (chunker)
                                │
                          00060-10 (M2 bridge)
                                │
                          00060-11 (CLI + Web UI)
                                │
                          00060-12 (打包验证)
```

**并行机会**：00060-06, 00060-07, 00060-08 互不依赖，可并行开发。

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
