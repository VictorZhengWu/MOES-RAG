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

### ✅ 00060 — M1 文档解析引擎

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

#### ✅ 00060-08 — 输出序列化与图片管理 (serializer.py + image_manager.py)

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

#### ✅ 00060-09 — Chunking 封装 (chunker.py)

**功能描述：**
- 封装 Docling Hybrid Chunker + HuggingFace Tokenizer
- Tokenizer 与 M5 嵌入模型对齐（BAAI/bge-small-en-v1.5 默认，可选 BGE-M3）
- 配置：`max_tokens=512`, `merge_peers=True`, `repeat_table_header=True`
- 使用 docling v2.95+ 新 API：HuggingFaceTokenizer 包装器对象
- 依赖缺失时优雅降级，返回 None 而非崩溃

**验证方法：** 2 个测试用例（依赖缺失返回 None、正常创建 HybridChunker 实例）
**自动化验证命令：** `python -m pytest tests/test_chunker.py -v`
**通过条件：** 全部 passed，0 failed，无 deprecation warning
**Task 类型：** 模块/服务类
**依赖：** 00060-08
**关联文件：** `m1-doc-parsing/m1_parser/output/chunker.py`, `m1-doc-parsing/tests/test_chunker.py`

---

#### ✅ 00060-10 — M2 存储桥接 (m2_bridge.py)

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

#### ✅ 00060-12 — 打包与最终验证 (pyproject.toml + requirements.txt + 全量测试)

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

### ✅ 00070 — M3 检索引擎

> **详细设计**：`.dev/specs/m3-retrieval-design-2026-05-24.md`
> **核心原则**：精准优先——元数据过滤 > 精确匹配 > 语义检索

---

#### ✅ 00070-01 — 项目骨架与配置 (config.py + pyproject.toml)

**功能描述：**
- 创建 m3-retrieval 项目结构
- pyproject.toml：依赖 `m2-storage`, `flagembedding`(BGE-M3), `sentence-transformers`(Cross-Encoder)
- config.py：嵌入模型选择、融合参数(k=60)、重排序阈值、上下文窗口
- 默认配置：BGE-M3 dense, BM25 sparse, RRF fusion, BGE-Reranker-v2-m3 rerank

**验证方法：** 3 个测试用例（默认配置、自定义配置、无效模型报错）
**Task 类型：** 工具/原子函数类
**依赖：** 无
**关联文件：** `m3-retrieval/m3_retrieval/core/config.py`, `m3-retrieval/pyproject.toml`

---

#### ✅ 00070-02 — 查询分析器 (query_analyzer.py)

**功能描述：**
- 从自然语言查询提取元数据过滤条件
- 复用 M1 的 `marine_metadata.py` 正则规则
- 关键词分离：钢级标识、温度值、规范章节号
- 语义查询构建：去除已提取的关键词，生成纯语义查询字符串
- 返回 `QueryAnalysis` dataclass

**验证方法：** 5 个测试用例（DNV 章节查询、ABS 无章节查询、含温度值查询、纯关键词查询、无船级社查询）
**Task 类型：** 模块/服务类
**依赖：** 00060 (M1 marine_metadata.py)
**关联文件：** `m3-retrieval/m3_retrieval/stages/query_analyzer.py`, `m3-retrieval/tests/test_query_analyzer.py`

---

#### ✅ 00070-03 — 向量检索器 (dense_retriever.py)

**功能描述：**
- 封装 BGE-M3 嵌入模型
- 通过 M2 StorageManager 调用 ChromaDB 向量检索
- 支持 metadata where 过滤（classification_society, chapter_section）
- 返回 `list[ScoredChunk]` (source="dense")

**验证方法：** 4 个测试用例（基本检索、元数据过滤检索、空结果、嵌入模型初始化）
**Task 类型：** 模块/服务类
**依赖：** 00050 (M2), 00070-02
**关联文件：** `m3-retrieval/m3_retrieval/stages/dense_retriever.py`, `m3-retrieval/m3_retrieval/embeddings/embedder.py`, `m3-retrieval/tests/test_dense_retriever.py`

---

#### ✅ 00070-04 — 全文检索器 (sparse_retriever.py)

**功能描述：**
- 通过 M2 StorageManager 调用 Meilisearch BM25 搜索
- 查询构建：关键词 AND 连接
- 支持 metadata filter（Meilisearch SQL-like filter 语法）
- 返回 `list[ScoredChunk]` (source="bm25")

**验证方法：** 4 个测试用例（关键词检索、过滤检索、空结果、中文关键词）
**Task 类型：** 模块/服务类
**依赖：** 00050 (M2), 00070-02
**关联文件：** `m3-retrieval/m3_retrieval/stages/sparse_retriever.py`, `m3-retrieval/tests/test_sparse_retriever.py`

---

#### ✅ 00070-05 — 融合模块 (fusion.py)

**功能描述：**
- 实现 3 种融合策略：RRF (默认 k=60)、加权融合（基于原始分数）、混合（RRF + weighted）
- 输入：多个 `list[ScoredChunk]`（来自 dense + sparse）
- 输出：合并去重后的 `list[ScoredChunk]` (source="fusion")
- 分数归一化处理

**验证方法：** 4 个测试用例（RRF 融合去重、加权融合、空输入、单输入直通）
**Task 类型：** 工具/原子函数类
**依赖：** 00070-03, 00070-04
**关联文件：** `m3-retrieval/m3_retrieval/stages/fusion.py`, `m3-retrieval/tests/test_fusion.py`

---

#### ✅ 00070-06 — 重排序器 (reranker.py)

**功能描述：**
- 封装 BGE-Reranker-v2-m3 Cross-Encoder 模型
- 输入：query + Top 50 chunks（来自融合结果）
- 输出：Top 20 chunks（score 更新为 Cross-Encoder relevance 分数）
- 批处理：单次推理 50 对 (query, chunk.text)

**验证方法：** 3 个测试用例（重排序改变顺序、输出数量正确、模型初始化）
**Task 类型：** 模块/服务类
**依赖：** 00070-05
**关联文件：** `m3-retrieval/m3_retrieval/stages/reranker.py`, `m3-retrieval/tests/test_reranker.py`

---

#### ✅ 00070-07 — 上下文扩展器 (context_expander.py)

**功能描述：**
- 每个 chunk 从 M2 FileStore 读取父文档 (`full.md`)
- 扩展逻辑：向前取 3 段 + 向后取 3 段
- 表格 chunk：附加表标题 + column headers
- 返回的 chunk.text 不变，新增 `expanded_context` 字段

**验证方法：** 3 个测试用例（文本块扩展、表格块扩展、父文档不存在降级）
**Task 类型：** 模块/服务类
**依赖：** 00050 (M2), 00070-06
**关联文件：** `m3-retrieval/m3_retrieval/stages/context_expander.py`, `m3-retrieval/tests/test_context_expander.py`

---

#### ✅ 00070-08 — 管线编排 + 主引擎 (pipeline.py + engine.py)

**功能描述：**
- `pipeline.py`：编排 7 阶段顺序执行。阶段 2a/2b 通过 `asyncio.gather` 并行。阶段 5（去重）内联实现
- `engine.py`：实现 `RetrievalEngineProtocol`，`retrieve()` 方法
- 支持 `RetrievalRequest` 所有参数：top_k, filters, enable_query_rewriting, enable_hyde, fusion_strategy
- **自适应快速路径**：精确匹配→BM25 only，关键词查询→混合不重排，完整查询→7 阶段
- **检索缓存**：内存 LRU, TTL 1h, key=md5(query+filters)，命中时 <1ms 响应
- `health_check()`：验证 ChromaDB + Meilisearch 连通性

**验证方法：** 5 个测试用例（完整管线、快速路径、缓存命中、HyDE 关闭/开启、health_check）
**Task 类型：** 集成/跨模块类
**依赖：** 00070-01 ~ 00070-07
**关联文件：** `m3-retrieval/m3_retrieval/core/pipeline.py`, `m3-retrieval/m3_retrieval/core/engine.py`, `m3-retrieval/tests/test_pipeline.py`, `m3-retrieval/tests/test_engine.py`

---

#### ✅ 00070-09 — 质量度量 (metrics.py)

**功能描述：**
- 计算 Recall@k, MRR, NDCG@k, Precision@k
- 输入：标注好的查询-文档对
- 离线评估模式 + 在线记录模式

**验证方法：** 4 个测试用例（Recall@20 计算、MRR 计算、NDCG 计算、空结果处理）
**Task 类型：** 工具/原子函数类
**依赖：** 无
**关联文件：** `m3-retrieval/m3_retrieval/core/metrics.py`, `m3-retrieval/tests/test_metrics.py`

---

#### 🔲 00070-10 — M2 集成 + 打包验证 (m2_client.py + pyproject.toml)

**功能描述：**
- `m2_client.py`：封装 StorageManager 调用，统一错误处理
- pyproject.toml：依赖分组
- requirements.txt：锁定版本
- 全量测试套件通过

**验证方法：** pip install 成功、全量 pytest 通过
**Task 类型：** 集成/跨模块类
**依赖：** 00070-08
**关联文件：** `m3-retrieval/m3_retrieval/integration/m2_client.py`, `m3-retrieval/pyproject.toml`, `m3-retrieval/requirements.txt`

---

**依赖关系图：**

```
00070-01 (config)
    ↓
00070-02 (query_analyzer) ← 依赖 M1 marine_metadata
    ↓
┌───────────────────────┐
│ 00070-03  00070-04    │  ← 并行：dense + sparse 独立
│ (dense)   (sparse)    │
└──────────┬────────────┘
           ↓
    00070-05 (fusion)
           ↓
    00070-06 (reranker)
           ↓
    00070-07 (context_expander)
           ↓
    00070-08 (pipeline + engine)
           ↓
    00070-09 (metrics)   ← 独立，可并行
           ↓
    00070-10 (M2 集成 + 打包)
```

**并行机会**：00070-03/04 可并行，00070-09 可与其他任务并行。

### ✅ 00080 — M4 知识图谱引擎

> **详细设计**：`.dev/specs/m4-knowledge-graph-design-2026-05-24.md`
> **核心原则**：建图离线（LLM 花费），搜索在线（图遍历免费）

---

#### ✅ 00080-01 — 项目骨架与配置 (config.py + pyproject.toml)

**功能描述：**
- 创建 m4-knowledge-graph 项目结构
- pyproject.toml：`kuzu>=0.3.0`, `openai`, `httpx`
- config.py：`ExtractionConfig`（LLM 后端、max_tokens_per_batch=6000、max_concurrent=2、fallback_to_rules=True）、`UserTier`（basic/pro/enterprise 三级）
- LLM 后端配置支持：Ollama (本地)、DeepSeek/OpenAI/Claude (API)

**验证方法：** 3 个测试用例（默认配置、自定义 LLM 后端、用户分级取值）
**Task 类型：** 工具/原子函数类
**依赖：** 无
**关联文件：** `m4-knowledge-graph/m4_kg/core/config.py`, `m4-knowledge-graph/m4_kg/core/tier.py`, `m4-knowledge-graph/pyproject.toml`

---

#### ✅ 00080-02 — 规则抽取器 (rule_extractor.py)

**功能描述：**
- 正则+字典匹配快速覆盖 70% 实体
- 实体类型：`steel_grade` (`[A-Z]{2,4}\d{2,3}`)、`regulation_clause` (Pt./Ch./§)、`equipment` (Type-XXX)、`parameter` (温度值/厚度值/压力值)
- 关系类型：`references`（规范条目之间引用）、`constrains`（参数约束实体）
- **否定词检测**：过滤 except/excluding/not applicable to 后的目标，防止误报
- 返回 `list[Entity]` + `list[Relation]`
- Ship type 字典匹配支持 30+ 种船舶类型

**验证方法：** 30 个测试用例（钢级提取 3、规范条目提取 3、参数提取 5、设备提取 3、船型提取 3、否定词过滤 5、空输入 2、编排器 3、关系生成 3）
**Task 类型：** 模块/服务类
**依赖：** 无
**关联文件：** `m4-knowledge-graph/m4_kg/extraction/rule_extractor.py`, `m4-knowledge-graph/tests/test_rule_extractor.py`

---

#### ✅ 00080-03 — LLM 抽取器 (llm_extractor.py + prompt_templates.py)

**功能描述：**
- Prompt 模板管理（中英文），控制 JSON 输出格式
- 调用 LLM（Ollama / DeepSeek / OpenAI / Claude），支持并发控制
- 格式归一化：三层解析（`json.loads` → regex 提取 `{...}` → 规则回退）
- **Token 感知分批**：`batch_by_tokens()` 按 1 token≈4 chars 估算，每批 ≤6000 tokens（非固定 20 个 chunk）
- `asyncio.Semaphore(2)` 控制本地模型并发
- 返回 `list[Entity]` + `list[Relation]`

**验证方法：** 5 个测试用例（Mock LLM 响应、有效 JSON 解析、无 JSON 正则提取、token 分批验证、LLM 失败规则回退）
**Task 类型：** 模块/服务类
**依赖：** 00080-02
**关联文件：** `m4-knowledge-graph/m4_kg/extraction/llm_extractor.py`, `m4-knowledge-graph/m4_kg/extraction/prompt_templates.py`, `m4-knowledge-graph/tests/test_llm_extractor.py`

---

#### ✅ 00080-04 — 合并去重器 (merger.py)

**功能描述：**
- 规则结果 + LLM 结果合并
- 去重策略：同名+同类型实体合并（同名但不同类型保留）
- LLM 结果优先（置信度更高），规则结果补充 LLM 漏掉的实体
- **实体消歧义**：regulation_clause 和 equipment 类型加船级社前缀（"DNV-§5.2" vs "ABS-§5.2"），steel_grade/ship_type 保持全局
- 关系去重：同一对 (source, target, relation_type) 只保留一条，优先 LLM

**验证方法：** 4 个测试用例（同名实体去重、跨文档消歧义、关系去重、LLM 优先）
**Task 类型：** 工具/原子函数类
**依赖：** 00080-02, 00080-03
**关联文件：** `m4-knowledge-graph/m4_kg/extraction/merger.py`, `m4-knowledge-graph/tests/test_merger.py`

---

#### ✅ 00080-05 — Kuzu 图存储 (kuzu_store.py + schema.py)

**功能描述：**
- Schema 定义：Entity 节点表（entity_id, name, entity_type, properties, source_doc_id, doc_society, ref_count, created_at）, Rel 边表（from, to, relation_type, properties, confidence, source_doc_id, created_at）
- **索引创建**：5 个索引（name, entity_type, doc_society, relation_type, source_doc_id）加速查询
- 批量写入：100 实体/批，单事务
- 查询：节点查询（按 name/type/society）、边查询（按 entity_ids/relation_types/doc_id）
- 数据库文件默认路径：`./data/graph/marine_rag.db`

**验证方法：** 5 个测试用例（节点写入读取、边写入读取、按类型查询、按船级社查询、空结果）
**Task 类型：** 模块/服务类
**依赖：** 00080-04
**关联文件：** `m4-knowledge-graph/m4_kg/graph/kuzu_store.py`, `m4-knowledge-graph/m4_kg/graph/schema.py`, `m4-knowledge-graph/tests/test_kuzu_store.py`

---

#### ✅ 00080-06 — 图遍历 (traversal.py)

**功能描述：**
- BFS 遍历：从 seed 实体出发，按 depth 参数扩展
- 支持遍历边类型过滤（`relation_types` 参数）
- 支持用户等级限制（Basic depth=1, Pro depth=3, Enterprise depth=5）
- 返回 `Subgraph`（entities + relations）

**验证方法：** 3 个测试用例（单跳遍历、多跳遍历+深度限制、空种子返回空）
**Task 类型：** 工具/原子函数类
**依赖：** 00080-05
**关联文件：** `m4-knowledge-graph/m4_kg/graph/traversal.py`, `m4-knowledge-graph/tests/test_traversal.py`

---

#### ✅ 00080-07 — 图谱搜索 + 交叉引用 (graph_search.py + cross_reference.py)

**功能描述：**
- `graph_search(topic, depth)`：按主题词搜索实体 → BFS 扩展 → 返回 Subgraph
- `cross_reference(source_clause, source_society, target_society)`：**混合策略**——先查图中已有 `similar_to` 边，无结果则 LLM 实时计算，结果缓存为图边
- **注意**：M4 不实现 `combined_search`——联合检索是 M5 的职责（并行调用 M3+M4 并合并）

**验证方法：** 5 个测试用例（图谱搜索 2、图查交叉引用 1、LLM fallback 1、无匹配 1）
**Task 类型：** 模块/服务类
**依赖：** 00080-06
**关联文件：** `m4-knowledge-graph/m4_kg/search/graph_search.py`, `m4-knowledge-graph/m4_kg/search/cross_reference.py`, `m4-knowledge-graph/tests/test_graph_search.py`, `m4-knowledge-graph/tests/test_cross_reference.py`

---

#### ✅ 00080-08 — 主引擎 + M1 异步集成 (engine.py + m1_bridge.py)

**功能描述：**
- `engine.py`：实现 `KGEngineProtocol`，`extract_entities()`, `extract_relations()`, `query_entities()`, `query_relations()`, `graph_search()`, `cross_reference()`, `health_check()`
- M1 异步钩子：`on_parse_complete()` 接收 M1 完成事件，`asyncio.create_task` 异步启动建图，M1 立即返回不阻塞
- 增量更新：CASCADE_DELETE 删专属实体（ref_count==1），SHARED_RETAIN 保留共享实体（ref_count>1）
- `m2_bridge.py`：从 M2 FileStore 读取 chunk 文本，向 M2 RelationalDB 写入图谱构建状态（`m4_graphs` 表）

**验证方法：** 4 个测试用例（实体提取全流程、增量删除、图谱搜索、健康检查）
**Task 类型：** 集成/跨模块类
**依赖：** 00080-07, M1, M2
**关联文件：** `m4-knowledge-graph/m4_kg/core/engine.py`, `m4-knowledge-graph/m4_kg/integration/m1_bridge.py`, `m4-knowledge-graph/m4_kg/integration/__init__.py`, `m4-knowledge-graph/tests/test_engine.py`

---

#### ✅ 00080-09 — 打包与最终验证 (pyproject.toml + 全量测试)

**功能描述：**
- requirements.txt：kuzu, openai, httpx
- pyproject.toml：依赖分组（`[core]`, `[llm]`, `[dev]`）
- 全量测试套件通过

**验证方法：** pip install 成功、全量 pytest 通过
**Task 类型：** 集成/跨模块类
**依赖：** 00080-01 ~ 00080-08
**关联文件：** `m4-knowledge-graph/pyproject.toml`, `m4-knowledge-graph/requirements.txt`

---

**依赖关系图：**

```
00080-01 (config)
    ↓
00080-02 (rule_extractor) ──→ 00080-03 (llm_extractor)
                                       ↓
                                 00080-04 (merger)
                                       ↓
                                 00080-05 (kuzu_store)
                                       ↓
                                 00080-06 (traversal)
                                       ↓
                                 00080-07 (graph_search)
                                       ↓
                                 00080-08 (engine + M2 bridge)
                                       ↓
                                 00080-09 (打包验证)
```

00080-02 和 00080-03 可部分并行（规则抽取无 LLM 依赖）。00080-05（Kuzu 存储）和 00080-06（图遍历）可部分并行（先写 Schema 测试再写遍历）。

### ✅ 00090 — M5 智能问答引擎

> **详细设计**：`.dev/specs/m5-qa-engine-design-2026-06-03.md` (v2)
> **核心原则**：一套引擎三种模式，OpenAI 兼容 API，分级服务 + Premium 配额 + 动态 Token 预算

---

#### ✅ 00090-01 — 骨架 + 配置 + 等级系统 (config.py + tier.py + router.py + pyproject.toml)

**功能描述：**
- 创建 m5-qa-engine 项目结构
- pyproject.toml：`openai`, `httpx`, `aiosqlite`
- config.py：`QAConfig`（LLMBackend, db_path, system_prompt_id）
- tier.py：`UserTier`（三级 + 上下文窗口 4K/8K/16K）+ `PremiumQuota`（`can_use()`/`consume()`）
- router.py：`ModeRouter.select_mode(user_id, tier)` → "simple"/"pipeline"/"self_rag"

**验证方法：** 12 个测试用例（默认配置、自定义 LLM、自定义 db_path/阈值、Basic 等级、Pro 等级、配额消耗/耗尽、Enterprise 无限、Basic 路由、Pro 路由、Premium 升级、Premium 耗尽回退、未知等级 fallback）
**Task 类型：** 工具/原子函数类
**依赖：** 无
**关联文件：** `m5-qa-engine/m5_qa/core/config.py`, `m5-qa-engine/m5_qa/core/tier.py`, `m5-qa-engine/m5_qa/core/router.py`, `m5-qa-engine/pyproject.toml`

---

#### ✅ 00090-02 — LLM 客户端 + 流式生成 (llm_client.py + streaming.py)

**功能描述：**
- `LLMClient`：单一客户端，`openai.AsyncOpenAI` 覆盖 Ollama/DeepSeek/OpenAI/Claude
- `complete()` 非流式，`complete_stream()` SSE 迭代器
- Token 估算：`estimate_tokens(text)` 字符数 ÷ 4
- **不创建独立 provider 文件**——base_url 区分后端

**验证方法：** 4 个测试用例（Mock 响应、token 估算、流式 mock、base_url 构造）
**Task 类型：** 模块/服务类
**依赖：** 00090-01
**关联文件：** `m5-qa-engine/m5_qa/generation/llm_client.py`, `m5-qa-engine/m5_qa/generation/streaming.py`

---

#### ✅ 00090-03 — Prompt 管理器 (prompt_manager.py)

**功能描述：**
- `PromptManager`：DB 存储 Prompt 模板（SQLite 表 `m5_prompts`）
- `get_prompt(prompt_id)`：按 ID 取模板
- `get_prompt_by_language(base_id, language)`：语言降级（→ en → 硬编码默认）
- `set_prompt(prompt_id, name, language, content)`：增/改模板
- 预置中英文 system prompt + citation prompt
- 模板变量 `{retrieved_context}`, `{graph_context}` 运行时填充
- **Phase 3 加版本控制，当前不做**

**验证方法：** 6 个测试用例（取英文模板、中文降级到英文、硬编码默认回退、UPSERT、变量填充、列出模板）
**Task 类型：** 工具/原子函数类
**依赖：** 无
**关联文件：** `m5-qa-engine/m5_qa/generation/prompt_manager.py`, `m5-qa-engine/tests/test_prompt_manager.py`

---

#### ✅ 00090-04 — 引用溯源 + Token 预算 (citation_builder.py + token_budget.py)

**功能描述：**
- `citation_builder.py`：从 ScoredChunk 构建 Citation，去重，映射 [1][2] 标记
- `token_budget.py`：`TokenBudget` + `allocate_budget(tier, query)` 按等级 + 查询长度因子动态分配
  - Basic 4K: retrieval 30% / history 20% / generation 50%
  - Pro 8K: retrieval 40% / history 20% / generation 40%
  - Enterprise 16K: retrieval 50% / history 20% / generation 30%
  - **查询长度因子**（0.5x~1.5x）：长查询给更多检索 budget，短查询给更多生成 budget
- `estimate_tokens(text)`：字符数 ÷ 4

**验证方法：** 15 个测试用例（单引用、多引用去重、引用附加、格式化、Basic/Pro/Enterprise 预算、等级分配、查询长度因子、空查询无调整）
**Task 类型：** 工具/原子函数类
**依赖：** 无
**关联文件：** `m5-qa-engine/m5_qa/context/citation_builder.py`, `m5-qa-engine/m5_qa/context/token_budget.py`

---

#### ✅ 00090-05 — 检索融合 (retriever.py + fusion.py)

**功能描述：**
- `retriever.py`：`RetrievalClient` 封装 M3+M4 调用
  - `simple_retrieve(query)` → 仅 M3
  - `parallel_retrieve(query, depth)` → M3+M4 `asyncio.gather`
- `fusion.py`：`RetrievalContext` 构建 + 图层格式化为文本描述

**验证方法：** 4 个测试用例（M3 调用、M3+M4 并行、M4 失败降级、上下文格式）
**Task 类型：** 模块/服务类
**依赖：** 无（Mock M3/M4）
**关联文件：** `m5-qa-engine/m5_qa/context/retriever.py`, `m5-qa-engine/m5_qa/context/fusion.py`

---

#### ✅ 00090-06 — 三种管线 (simple.py + pipeline.py + self_rag.py)

**功能描述：**
- `simple.py`：M3 → token_budget → prompt → LLM → 答案（4K 上下文）
- `pipeline.py`：M3+M4 并行 → fusion → citation → token_budget → prompt → LLM → 答案+引用（8K 上下文）
- `self_rag.py`：简化版 Self-RAG，最多 3 次迭代
  1. 检索（M3+M4）→ 2. 检查检索分数（M3 cosine sim ≥ 0.5）→ 3. 不够则同义词扩展改查询 → 4. LLM 生成 → 5. 返回答案+引用
  - **Phase 1 无独立评估器和引用验证器**——直接用 M3 检索分数作为质量信号

**验证方法：** 6 个测试用例（simple 全流程、pipeline 全流程、self_rag 评估通过、self_rag 重试、self_rag 超限终止、空检索）
**Task 类型：** 模块/服务类
**依赖：** 00090-02, 00090-04, 00090-05
**关联文件：** `m5-qa-engine/m5_qa/pipelines/simple.py`, `m5-qa-engine/m5_qa/pipelines/pipeline.py`, `m5-qa-engine/m5_qa/pipelines/self_rag.py`

---

#### ✅ 00090-07 — 对话管理 + 上下文压缩 (manager.py + compressor.py)

**功能描述：**
- `manager.py`：`ConversationManager` 使用 `aiosqlite` 管理 M5 自有的 `m5_qa.db`
  - 三张表：`conversations`, `messages`, `quotas`
  - `create/get/list/delete` + `add_message/get_messages`
  - **不通过 M2**——M2 是存储抽象层，不应感知 M5 业务逻辑
- `compressor.py`：`ContextCompressor.compress(messages, max_tokens)`

**验证方法：** 4 个测试用例（创建+读取、消息追加、删除、压缩截断）
**Task 类型：** 模块/服务类
**依赖：** 00090-01
**关联文件：** `m5-qa-engine/m5_qa/conversation/manager.py`, `m5-qa-engine/m5_qa/conversation/compressor.py`

---

#### ✅ 00090-08 — 主引擎 + 监控 (engine.py + monitoring/metrics.py + logger.py)

**功能描述：**
- `engine.py`：`QAEngine` 实现 `QAEngineProtocol`
  - `chat()` → `ChatResponse`、`chat_stream()` → SSE、`list_conversations/get_conversation/delete_conversation`、`list_models`、`health_check()`
- `monitoring/metrics.py`：`MetricsCollector` 记录延迟/token/模式，`get_summary()` 聚合
- `monitoring/logger.py`：`StructuredLogger` JSON 结构化日志

**验证方法：** 10 个测试用例（chat 流程 4、其他 API 2、metrics 4）
**Task 类型：** 集成/跨模块类
**依赖：** 00090-03, 00090-04, 00090-06, 00090-07
**关联文件：** `m5-qa-engine/m5_qa/core/engine.py`, `m5-qa-engine/m5_qa/monitoring/__init__.py`, `m5-qa-engine/m5_qa/monitoring/metrics.py`, `m5-qa-engine/m5_qa/monitoring/logger.py`, `m5-qa-engine/tests/test_engine.py`, `m5-qa-engine/tests/test_metrics.py`

---

#### ✅ 00090-09 — 打包与最终验证

**功能描述：**
- requirements.txt：openai, httpx, aiosqlite
- pyproject.toml：依赖分组（`[core]`, `[dev]`）
- 全量测试套件通过

**验证方法：** pip install 成功、全量 pytest 通过
**Task 类型：** 集成/跨模块类
**依赖：** 00090-01 ~ 00090-08
**关联文件：** `m5-qa-engine/pyproject.toml`, `m5-qa-engine/requirements.txt`

---

**依赖关系图：**

```
00090-01 (config+tier) ──→ 00090-02 (LLM client)    00090-03 (prompt)    00090-04 (citation)
                                │                         │                    │
                                ▼                         ▼                    ▼
                           00090-07 (conversation)   00090-05 (retriever — M3+M4 integration)
                                                             │
                                                             ▼
                                                      00090-06 (pipelines)
                                                             │
                                                             ▼
                                                      00090-08 (engine + router)
                                                             │
                                                             ▼
                                                      00090-09 (packaging)
```

- 00090-02/03/04/05/07 全部可并行（5 个 agent 同时开工）——各自 Mock 依赖、独立测试
- 00090-06 是最大任务（三种管线），串行于 -02/-04/-05 之后
- 00090-08 集合所有模块，串行于 -03/-04/-06/-07 之后

---

## Phase 2-3 过渡：Mock 迁移

### 🔲 00085 — Mock Data 渐进迁移

> **依赖**：M3 (00070), M4 (00080), M5 (00090) 完成后执行
> **策略来源**：审查报告 `.dev/advisor/20260524-112101-m2-m6-m7-review.md`

**功能描述：**
- 将 M6/M7 的 18+7 项 mock 功能分三阶段切换到真实后端 API

**三阶段切换清单：**

| 阶段 | 功能 | 从 (Mock) | 到 (真实后端) |
|:--:|------|-----------|-------------|
| 1 | Settings 加载 | Mock Server | M5 Config API |
| 1 | 语言切换持久化 | localStorage only | M5 User API |
| 1 | 文档列表加载 | Mock Server | M2 RelationalDB → M7 API |
| 1 | 用户列表加载 | Mock Server | M5 User API |
| 2 | 文档上传+解析 | Mock Server | M1 解析 → M2 FileStore |
| 2 | 元数据标注保存 | Mock Server | M2 RelationalDB |
| 2 | 知识库搜索 | Mock Server | M3 Retrieval API |
| 2 | LLM 配置保存 | Mock Server | M5 Config API |
| 3 | 聊天消息 | Mock Server | M5 QA Engine (RAG + SSE) |
| 3 | 文件真实上传 | Mock Server | M1 文件处理管线 + M2 存储 |
| 3 | 流式输出 | Mock Server | M5 SSE 流式 |
| 3 | 会话历史 | Mock Server | M5 Conversation API |

**回滚策略**：每阶段保留快速回滚到 Mock Server 的能力（环境变量 `USE_MOCK=true`）

**验证方法：** 每阶段切换后运行 Playwright E2E，确认原有功能无回归
**Task 类型：** 集成/跨模块类
**依赖：** 00060 (M1), 00070 (M3), 00080 (M4), 00090 (M5)
**关联文件：** `m6-user-portal/src/`, `m7-admin-portal/src/`, `mock-server/`

---

## Phase 3: 对外服务与部署

### ✅ 00100 — M8 API 网关

> **详细设计**：`.dev/specs/m8-api-gateway-design-2026-06-03.md`
> **核心原则**：独立 FastAPI 进程（8000），自管 API Key (`sk-m8-xxx`)，分级限流

---

#### ✅ 00100-01 — 骨架 + 配置 + FastAPI 工厂 (config.py + app.py + pyproject.toml)

**功能描述：**
- 创建 m8-api-gateway 项目结构
- pyproject.toml：`fastapi`, `uvicorn`, `aiosqlite`, `httpx`
- config.py：`GatewayConfig`（host, port, db_path, rate_limits dict）
- app.py：`create_app()` FastAPI 工厂 + 生命周期（startup 建表，shutdown 关 DB）

**验证方法：** 3 个测试用例（默认配置、app 创建、health endpoint）
**Task 类型：** 工具/原子函数类
**依赖：** 无
**关联文件：** `m8-api-gateway/m8_gateway/core/config.py`, `m8-api-gateway/m8_gateway/core/app.py`, `m8-api-gateway/pyproject.toml`

---

#### ✅ 00100-02 — API Key 管理 (key_manager.py)

**功能描述：**
- `KeyManager`：完整的 Key 生命周期
  - `generate_key(user_id, tier)` → 返回 `sk-m8-{16hex}`，存 sha256 哈希
  - `validate_key(raw_key)` → 查哈希，返回 `APIKey \| None`
  - `revoke_key(key_prefix)` → 设 `is_active=0`
  - `list_keys(user_id)` → 返回列表（只显示 prefix，不显示完整 key）
  - `touch_key(key_prefix)` → 更新 `last_used_at`
- SQLite 表 `api_keys`（key_hash, key_prefix, user_id, tier, created_at, is_active, last_used_at）
- 生成后只展示一次完整 key

**验证方法：** 4 个测试用例（生成 key、验证有效 key、验证无效 key、撤销后验证失败）
**Task 类型：** 模块/服务类
**依赖：** 00100-01
**关联文件：** `m8-api-gateway/m8_gateway/auth/key_manager.py`

---

#### ✅ 00100-03 — 限流器 (limiter.py)

**功能描述：**
- `RateLimiter`：内存滑动窗口
  - `check(key_prefix, tier)` → bool（是否允许）
  - 窗口：60 秒滑动
  - 限制：Basic 30/min, Pro 120/min, Enterprise unlimited (-1)
  - 过期窗口自动清理
- 非持久化（重启丢失计数，Personal 模式可接受）

**验证方法：** 3 个测试用例（未达限制允许、达限制拒绝、enterprise 无限流）
**Task 类型：** 工具/原子函数类
**依赖：** 00100-01
**关联文件：** `m8-api-gateway/m8_gateway/rate_limit/limiter.py`

---

#### ✅ 00100-04 — 路由 + 中间件 (routes/ + auth/middleware.py)

**功能描述：**
- `auth/middleware.py`：`get_api_key()` FastAPI Dependency
  - 提取 `Authorization: Bearer sk-m8-xxx`
  - 验证 key → `APIKey` 对象，401 若无效
- `routes/chat.py`：`POST /v1/chat/completions`
  - 鉴权 + 限流 + 调用 M5 `QAEngine.chat()` → 返回 ChatResponse
- `routes/models.py`：`GET /v1/models`
  - 鉴权 + 调用 M5 `QAEngine.list_models()`
- `routes/keys.py`：key 管理端点
  - `POST /admin/keys` — 生成新 key
  - `GET /admin/keys` — 列出 key
  - `DELETE /admin/keys/{prefix}` — 撤销 key

**验证方法：** 5 个测试用例（无 key 返回 401、有效 key 200、超出限流 429、admin 生成 key、**OpenAI SDK 兼容**）
**Task 类型：** 模块/服务类
**依赖：** 00100-02, 00100-03
**关联文件：** `m8-api-gateway/m8_gateway/routes/chat.py`, `m8-api-gateway/m8_gateway/routes/models.py`, `m8-api-gateway/m8_gateway/routes/keys.py`, `m8-api-gateway/m8_gateway/auth/middleware.py`, `m8-api-gateway/tests/test_openai_compat.py`

**OpenAI SDK 兼容测试（必须）：**
```python
# test_openai_compat.py
def test_openai_python_sdk_chat():
    """Verify official openai Python SDK can call M8."""
    import openai
    client = openai.OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="sk-m8-test-key",
    )
    response = client.chat.completions.create(
        model="m5-qa",
        messages=[{"role": "user", "content": "EH36 preheat requirements?"}],
    )
    assert response.choices[0].message.content
    assert hasattr(response, "citations")
```

---

#### ✅ 00100-05 — 打包与最终验证

**功能描述：**
- requirements.txt：fastapi, uvicorn, aiosqlite, httpx
- pyproject.toml：依赖分组
- pip install 成功
- 全量 pytest 通过

**验证方法：** pip install + 全量测试
**Task 类型：** 集成/跨模块类
**依赖：** 00100-01 ~ 00100-04
**关联文件：** `m8-api-gateway/pyproject.toml`, `m8-api-gateway/requirements.txt`

---

```
依赖关系图：

00100-01 (config+app) ──→ 00100-02 (key manager) ──┐
                      └──→ 00100-03 (rate limiter) ─┤
                                                      ├──→ 00100-04 (routes)
                                                      │         │
                                                      └─────────┤
                                                                 ▼
                                                          00100-05 (packaging)
```

00100-02 和 00100-03 可并行。

#### 🔲 00100-10 — Redis 基础层 (redis_client.py + base.py + RedisConfig)

**功能描述：**
- 创建 `rate_limit/base.py`：`BaseRateLimiter` 抽象基类，定义 `check(key_prefix, tier) -> bool` 和 `get_usage(key_prefix) -> int` 两个抽象方法，可选 `close()` 和 `health_check()` 钩子（默认 no-op）
- 创建 `rate_limit/redis_client.py`：`create_redis_client(host, port, db, password, max_connections, socket_timeout) -> Redis | None` 纯工厂函数，无全局变量，失败返回 None
- 扩展 `core/config.py`：
  - 新增 `RedisConfig` dataclass（8 个字段：host, port, db, password, max_connections, backend, strict_mode, window_seconds），所有字段有合理默认值
  - `GatewayConfig.rate_limit_backend` 默认值改为 `"auto"`（非 `"memory"`），新增 `rate_limit_redis: RedisConfig` 字段
  - `GatewayConfig.__post_init__` 新增 `_resolve_rate_limit_backend()` 方法：`backend == "auto"` 时根据 `deployment_mode` 自动选择（SaaS → redis，其他 → memory），显式指定则不覆盖
- 更新 `requirements.txt`：新增 `redis>=5.0.0` 和 `fakeredis>=2.20.0`（dev dependency）

**验证方法：**
- 测试用例 1：`RedisConfig` 默认值正确
- 测试用例 2：`create_redis_client` 连接无效地址返回 None（不抛异常）
- 测试用例 3：`GatewayConfig(deployment_mode="saas")` 自动选择 redis 后端
- 测试用例 4：`GatewayConfig(deployment_mode="personal")` 自动选择 memory 后端
- 测试用例 5：`GatewayConfig(rate_limit_backend="redis", deployment_mode="personal")` 显式覆盖生效
- 测试用例 6：`BaseRateLimiter` 不可直接实例化（抽象类）

**自动化验证命令：** `python -m pytest m8-api-gateway/tests/test_config.py m8-api-gateway/tests/test_redis_client.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 工具/原子函数类
**依赖：** 00100-05 (M8 基础已完成)
**关联文件：** `m8-api-gateway/m8_gateway/rate_limit/base.py`, `m8-api-gateway/m8_gateway/rate_limit/redis_client.py`, `m8-api-gateway/m8_gateway/core/config.py`, `m8-api-gateway/tests/test_config.py`, `m8-api-gateway/tests/test_redis_client.py`

---

#### 🔲 00100-11 — RedisRateLimiter 实现 + InMemory 重构 + Factory

**功能描述：**
- 重构 `rate_limit/limiter.py`：`RateLimiter` → `InMemoryRateLimiter(BaseRateLimiter)`，新增 `window_seconds: int = 60` 参数替代硬编码的 60.0
- 创建 `rate_limit/redis_limiter.py`：`RedisRateLimiter(BaseRateLimiter)`
  - Redis Sorted Set 滑动窗口实现：ZREMRANGEBYSCORE → ZCARD → 判断 → ZADD → EXPIRE
  - Member 加 8 位随机 hex 后缀防同纳秒碰撞
  - EXPIRE 设为 `window_seconds * 2` 自动回收闲置 key
  - `strict_mode=True`：Redis 异常时 return False + CRITICAL 日志
  - `strict_mode=False`：Redis 异常时降级到内存计数 + ERROR 日志
  - Enterprise unlimited tier：`limit == -1` 直接 return True，跳过 Redis 操作
- 更新 `rate_limit/__init__.py`：实现 `create_rate_limiter(config: GatewayConfig) -> BaseRateLimiter` 工厂函数
  - `backend == "redis"` 且连接成功 → `RedisRateLimiter`
  - `backend == "redis"` 连接失败 + `strict_mode=True` → 抛 RuntimeError
  - 其他情况 → `InMemoryRateLimiter`

**验证方法：**
- 测试用例 1：`InMemoryRateLimiter` 行为与重构前完全一致（现有 3 个测试仍通过）
- 测试用例 2：`create_rate_limiter(memory_config)` 返回 `InMemoryRateLimiter`
- 测试用例 3：`create_rate_limiter(redis_config)` 连接成功返回 `RedisRateLimiter`

**自动化验证命令：** `python -m pytest m8-api-gateway/tests/test_limiter.py -v`
**通过条件：** 全部 passed，0 failed（重构不破坏现有测试）
**Task 类型：** 模块/服务类
**依赖：** 00100-10
**关联文件：** `m8-api-gateway/m8_gateway/rate_limit/limiter.py`, `m8-api-gateway/m8_gateway/rate_limit/redis_limiter.py`, `m8-api-gateway/m8_gateway/rate_limit/__init__.py`, `m8-api-gateway/tests/test_limiter.py`

---

#### 🔲 00100-12 — App 集成 + 配置端点 + Docker Compose

**功能描述：**
- 修改 `core/app.py`：
  - `app.state.limiter = create_rate_limiter(cfg)` 替换旧的 `RateLimiter(cfg.rate_limits)`（单行替换）
  - shutdown handler 中调用 `limiter.close()` 释放 Redis 连接池（如为 InMemoryRateLimiter 则 no-op）
- 新增 `GET /admin/config/rate-limit` 端点：返回当前限流配置状态（backend、Redis 连接状态、连接池统计）
- 新增 `PATCH /admin/config/rate-limit` 端点，四步安全热替换：
  1. 创建新 limiter 实例（旧 limiter 仍在服务请求）
  2. Health check 新 limiter（`RedisRateLimiter.health_check()` 验证 Redis 连通性）
  3. 原子替换 `app.state.limiter = new_limiter`（Python GIL 保证引用赋值原子性）
  4. 关闭旧 limiter（`old_limiter.close()` 释放连接池）
  - 并发安全：`threading.Lock` 串行化配置更新，防止多管理员竞争
  - 参数校验：backend ∈ {auto, memory, redis}、port 1-65535、db 0-15、max_connections 5-200、window_seconds 10-300、strict_mode=true + backend=memory 返回 400 错误
- 更新 `deploy/docker-compose.yml`：新增 `redis` 服务（`redis:7-alpine`，maxmemory 256mb + allkeys-lru + AOF + RDB 双持久化）
- 更新 `deploy/saas/deploy.yaml`：新增 `rate_limit` 配置段（backend: redis, strict_mode: true）
- 更新 M8 环境变量段：注入 `REDIS_HOST=redis`, `REDIS_PASSWORD`

**验证方法：**
- 测试用例 1：`GET /admin/config/rate-limit` 返回当前配置（含 backend 和 redis 连接状态）
- 测试用例 2：`PATCH /admin/config/rate-limit` 更新 backend 后 limiter 实例被替换
- 测试用例 3：无效参数（port=99999）返回 422
- 测试用例 4：`docker compose config` 语法验证通过（不实际启动）
- 测试用例 5：shutdown 调用 `limiter.close()`（验证 close 被调用）

**自动化验证命令：** `python -m pytest m8-api-gateway/tests/test_config_endpoint.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 集成/跨模块类
**依赖：** 00100-11
**关联文件：** `m8-api-gateway/m8_gateway/core/app.py`, `m8-api-gateway/m8_gateway/routes/admin.py`, `deploy/docker-compose.yml`, `deploy/saas/deploy.yaml`

---

#### 🔲 00100-13 — Redis 限流测试 + 全量回归

**功能描述：**
- 创建 `tests/test_redis_limiter.py`：5 个测试用例，使用 `fakeredis` + `unittest.mock.patch`（零外部依赖）
  1. `test_basic_rate_limit`：fakeredis 正常流程，前 N 个通过，第 N+1 拒绝
  2. `test_unlimited_tier`：Enterprise 无限流，200 请求全部通过，验证不写 Redis（跳过 ZADD）
  3. `test_sliding_window_expiry`：fakeredis 不支持真实时间推进，通过 `patch.object(redis, 'zremrangebyscore')` + `patch.object(redis, 'zcard', return_value=0)` 模拟窗口过期，验证请求恢复放行
  4. `test_strict_mode_rejects`：`patch.object(redis, 'zcard', side_effect=ConnectionError)` 模拟 Redis 断连，strict_mode=True → return False
  5. `test_non_strict_fallback`：`patch.object(redis, 'zcard', side_effect=ConnectionError)` + strict_mode=False → 降级到内存计数放行，ERROR 日志记录
- 新增 `test_redis_limiter_health_check`：验证 `health_check()` 在 Redis 正常/异常时的返回值
- 更新 `tests/test_limiter.py`：更新 import 路径（`InMemoryRateLimiter`），现有 3 个测试继续通过
- 运行 M8 全量测试套件回归

**验证方法：** 全量 pytest 通过，新增 6 个测试 + 现有 17 个测试 = 23 tests
**自动化验证命令：** `python -m pytest m8-api-gateway/tests/ -v`
**通过条件：** 23 passed，0 failed
**Task 类型：** 集成/跨模块类
**依赖：** 00100-12
**关联文件：** `m8-api-gateway/tests/test_redis_limiter.py`, `m8-api-gateway/tests/test_limiter.py`

---

**依赖关系图：**

```
00100-10 (base + RedisConfig + redis_client)
    ↓
00100-11 (InMemory重构 + RedisRateLimiter + Factory)
    ↓
00100-12 (App集成 + 配置端点 + Docker Compose)
    ↓
00100-13 (测试 + 全量回归)
```

> 严格串行，每个 Task 完成并验证通过后再进入下一个。

### ✅ 00110 — deploy/ 部署配置

**功能描述：**
- `deploy/docker-compose.yml`：6 个服务（m8, m1, meilisearch, searxng, ollama）
- `deploy/Dockerfile`：multi-stage（m8 轻量 ~2GB, m1 重量 ~8GB）
- `deploy/.env.example`：LLM/API Key/端口配置模板
- `deploy/start.ps1` + `deploy/start.sh`：一键启动脚本
- M8 打包 M3+M4+M5 同容器（ChromaDB 嵌入式，无额外服务）
- M1 独立容器（docling+OCR 重量依赖隔离）

**验证方法：** `docker compose -f deploy/docker-compose.yml up -d --build` → 4 个服务健康
**Task 类型：** 集成/跨模块类
**依赖：** 全部模块
