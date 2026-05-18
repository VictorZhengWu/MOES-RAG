# Tasks — M2 存储抽象层 (00050)

> 状态：🔲 待开始 / 🔄 进行中 / ✅ 已完成 / ❌ 熔断
> **全局规范**：所有 Python 源程序必须有详细英文注释（WHAT + WHY）。详见设计文档 Section 7。
> **设计依据**：`docs/superpowers/specs/2026-05-18-m2-storage-design.md`

---

## 🔲 00050-01 — 配置解析模块 (config.py)

**功能描述：**
- 实现 `deploy.yaml` 解析器，将 YAML 转换为类型安全的 dataclass 对象
- 包含以下配置类：
  - `StorageConfig` — 顶层，包含 `deployment_mode` + 4 个子配置
  - `VectorStoreConfig` / `ChromaDBConfig`
  - `DocumentIndexConfig` / `MeilisearchConfig`
  - `RelationalDBConfig` / `SQLiteConfig`
  - `FileStoreConfig` / `LocalFSConfig`
- 每个子配置类实现 `from_dict()` 工厂方法
- 每个配置类提供合理的默认值（缺失字段不报错）
- `load_config(path)` 函数：读取 YAML 文件 → 解析为 `StorageConfig`
- 无效的 `backend` 值抛出 `ValueError` 并给出明确提示

**输入**：`deploy.yaml` 文件路径
**输出**：`StorageConfig` 实例

**验证方法：**
- 测试用例 1：解析合法的 Personal 模式 YAML，验证所有字段正确
- 测试用例 2：解析缺失部分字段的 YAML，验证默认值填充
- 测试用例 3：传入不存在的 backend 值，验证抛出 ValueError
- 测试用例 4：传入不存在的文件路径，验证抛出 FileNotFoundError
- 通过标准：4 个测试用例全部通过

**自动化验证命令：** `python -m pytest tests/test_config.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 工具/原子函数类
**依赖：** 无
**关联文件：** `m2-storage/src/config.py`, `m2-storage/tests/test_config.py`, `m2-storage/deploy.yaml`

---

## 🔲 00050-02 — 工厂函数 (factory.py)

**功能描述：**
- 实现 5 个工厂函数：
  - `create_storage_manager(config_path)` — 顶层入口，组装 StorageManager
  - `_create_vector_store(cfg)` — 根据 backend 值创建 VectorStore 实例
  - `_create_document_index(cfg)` — 同上，DocumentIndex
  - `_create_relational_db(cfg)` — 同上，RelationalDB
  - `_create_file_store(cfg)` — 同上，FileStore
- 每个 `_create_*` 内部用 if/else 分支选择具体类
- 未实现的 backend 抛出 `ValueError(f"Unsupported backend: {backend}")`
- 工厂不负责初始化后端（initialize 由 StorageManager 调用）

**输入**：`StorageConfig` 实例（来自 config.py）
**输出**：`StorageManager` 实例（含 4 个后端引用）

**验证方法：**
- 测试用例 1：传入 Personal 模式配置，验证返回 StorageManager 且 4 个后端类型正确
- 测试用例 2：传入不支持的 backend，验证抛出 ValueError
- 通过标准：2 个测试用例全部通过

**自动化验证命令：** `python -m pytest tests/test_factory.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 工具/原子函数类
**依赖：** 00050-01 (config.py)
**关联文件：** `m2-storage/src/factory.py`, `m2-storage/tests/test_factory.py`

---

## 🔲 00050-03 — StorageManager 生命周期管理 (manager.py)

**功能描述：**
- 实现 `StorageManager` 类，持有 4 个后端实例的引用
- 方法：
  - `__init__(vs, di, rdb, fs)` — 注入 4 个后端
  - `async initialize()` — 并发初始化 4 个后端（`asyncio.gather`）
  - `async health_check()` — 并发执行 4 个后端的健康检查，返回 `dict[str, bool]`
  - `async close()` — 并发关闭 4 个后端连接
- Manager 不代理转发方法调用——上层直接用 `manager.vector_store.search(...)`
- 初始化失败时 log 错误但不阻断其他后端初始化
- 健康检查汇总各后端状态

**输入**：4 个后端实例
**输出**：可用的 `StorageManager` 实例

**验证方法：**
- 测试用例 1：用 mock 后端创建 Manager，验证 initialize 被并发调用
- 测试用例 2：health_check 返回各后端状态的字典
- 测试用例 3：close 被并发调用
- 测试用例 4：一个后端初始化失败，其他后端仍正常初始化
- 通过标准：4 个测试用例全部通过

**自动化验证命令：** `python -m pytest tests/test_manager.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 工具/原子函数类
**依赖：** 00050-02 (factory.py)
**关联文件：** `m2-storage/src/manager.py`, `m2-storage/tests/test_manager.py`

---

## 🔲 00050-04 — VectorStore 基类 + ChromaDB 实现

**功能描述：**
- `vector_store/base.py`：定义 `BaseVectorStore` 抽象类（继承 `VectorStoreProtocol` + `ABC`）
  - 补充生命周期方法：`initialize()`, `health_check()`, `close()`
- `vector_store/chromadb_store.py`：实现 `ChromaDBStore(BaseVectorStore)`
  - 使用 `chromadb.PersistentClient`
  - `initialize()`: 创建/获取 collection
  - `insert(chunks, embeddings)`: 批量插入，返回 chunk_id 列表
  - `search(query_vector, top_k, filters)`: ANN 搜索，支持 metadata `where` 过滤
  - `delete(doc_id)`: 按 doc_id metadata 过滤删除
  - `count(filters)`: 返回匹配总数
  - `health_check()`: 尝试获取 collection 信息
  - `close()`: 释放客户端

**输入**：`ChromaDBConfig`（persist_dir, collection_name）
**输出**：可用的 `ChromaDBStore` 实例，满足 `VectorStoreProtocol`

**验证方法：**
- 测试用例 1：`isinstance(store, VectorStoreProtocol)` → True
- 测试用例 2：insert 3 chunks → search 返回正确 chunk（按 score 排序）
- 测试用例 3：search 带 metadata filter → 只返回匹配项
- 测试用例 4：delete → count 减少
- 测试用例 5：search 空 collection → 返回空列表
- 测试用例 6：health_check → True
- 通过标准：6 个测试用例全部通过

**自动化验证命令：** `python -m pytest tests/test_chromadb.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 模块/服务类
**依赖：** 00050-03（需要 Manager 生命周期模型作为参考，但可独立测试）
**关联文件：** `m2-storage/src/vector_store/base.py`, `m2-storage/src/vector_store/chromadb_store.py`, `m2-storage/tests/test_chromadb.py`

---

## 🔲 00050-05 — DocumentIndex 基类 + Meilisearch 实现

**功能描述：**
- `document_index/base.py`：定义 `BaseDocumentIndex` 抽象类（继承 `DocumentIndexProtocol` + `ABC`）
  - 补充生命周期方法：`initialize()`, `health_check()`, `close()`
- `document_index/meilisearch_index.py`：实现 `MeilisearchIndex(BaseDocumentIndex)`
  - 使用 `meilisearch.Client`
  - `initialize()`: 创建 index，配置可搜索/可过滤/可排序属性
  - `index(chunks)`: 批量写入，以 `chunk_id` 为主键
  - `search(query, top_k, filters)`: 全文搜索，支持 metadata filter
  - `delete(doc_id)`: 按 `doc_id` 过滤器删除
  - `health_check()`: 调用 Meilisearch `/health` 端点
  - `close()`: 释放 HTTP 连接

**输入**：`MeilisearchConfig`（host, api_key, index_name）
**输出**：可用的 `MeilisearchIndex` 实例，满足 `DocumentIndexProtocol`

**验证方法：**
- 测试用例 1：`isinstance(index, DocumentIndexProtocol)` → True
- 测试用例 2：index 3 chunks → search 返回正确 chunk
- 测试用例 3：search 带 filter → 只返回匹配项
- 测试用例 4：delete → 搜索结果不包含已删除项
- 测试用例 5：search 不存在的内容 → 返回空列表
- 测试用例 6：health_check → True
- 通过标准：6 个测试用例全部通过

**自动化验证命令：** `python -m pytest tests/test_meilisearch.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 模块/服务类
**依赖：** 00050-03, 需要 Meilisearch 进程运行（`conftest.py` fixture 管理）
**关联文件：** `m2-storage/src/document_index/base.py`, `m2-storage/src/document_index/meilisearch_index.py`, `m2-storage/tests/test_meilisearch.py`

---

## 🔲 00050-06 — RelationalDB 基类 + SQLite 实现

**功能描述：**
- `relational_db/base.py`：定义 `BaseRelationalDB` 抽象类（继承 `RelationalDBProtocol` + `ABC`）
  - 补充生命周期方法：`initialize()`, `health_check()`, `close()`
- `relational_db/sqlite_db.py`：实现 `SQLiteDB(BaseRelationalDB)`
  - 使用 `sqlalchemy.ext.asyncio` + `aiosqlite`
  - `initialize()`: 创建异步引擎 + 运行 `create_all`（从 `Base.metadata`）
  - `get_session()`: 返回 `AsyncSession` context manager
  - `health_check()`: 执行 `SELECT 1`
  - `close()`: 释放引擎和连接池
- **M2 不定义 ORM 模型**——只提供数据库引擎。ORM 模型由上层模块（M5 等）定义

**输入**：`SQLiteConfig`（path）
**输出**：可用的 `SQLiteDB` 实例，满足 `RelationalDBProtocol`

**验证方法：**
- 测试用例 1：`isinstance(db, RelationalDBProtocol)` → True
- 测试用例 2：initialize 创建数据库文件，文件存在
- 测试用例 3：get_session 返回可用 session，能执行 `SELECT 1`
- 测试用例 4：health_check → True
- 测试用例 5：不存在的数据库路径自动创建父目录
- 通过标准：5 个测试用例全部通过

**自动化验证命令：** `python -m pytest tests/test_sqlite.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 模块/服务类
**依赖：** 00050-03
**关联文件：** `m2-storage/src/relational_db/base.py`, `m2-storage/src/relational_db/sqlite_db.py`, `m2-storage/tests/test_sqlite.py`

---

## 🔲 00050-07 — FileStore 基类 + LocalFS 实现

**功能描述：**
- `file_store/base.py`：定义 `BaseFileStore` 抽象类（继承 `FileStoreProtocol` + `ABC`）
  - 补充生命周期方法：`initialize()`, `health_check()`, `close()`
- `file_store/local_fs.py`：实现 `LocalFSStore(BaseFileStore)`
  - `initialize()`: 确保 root_dir 存在，创建必要子目录
  - `put(key, data, metadata)`: 写入文件到 `root_dir/key`，metadata 写入 `key.meta.json`
  - `get(key)`: 读取文件字节，不存在返回 None
  - `delete(key)`: 删除文件 + metadata，不存在返回 False
  - `list(prefix)`: 列出匹配前缀的所有文件 key
  - `get_url(key, expires_in)`: 返回 `file://` 绝对路径（LocalFS 无 presigned URL）
  - `health_check()`: 检查 root_dir 是否可读写
  - `close()`: 无操作
- **路径安全**：所有 key 做路径穿越校验（拒绝 `../`），用 `os.path.realpath` 验证结果在 root_dir 内

**输入**：`LocalFSConfig`（root_dir）
**输出**：可用的 `LocalFSStore` 实例，满足 `FileStoreProtocol`

**验证方法：**
- 测试用例 1：`isinstance(store, FileStoreProtocol)` → True
- 测试用例 2：put → get 返回相同数据
- 测试用例 3：put 带 metadata → metadata 文件正确写入
- 测试用例 4：delete → get 返回 None
- 测试用例 5：list 返回正确文件列表
- 测试用例 6：get 不存在的 key → None
- 测试用例 7：路径穿越 `../etc/passwd` → 拒绝
- 测试用例 8：health_check → True
- 通过标准：8 个测试用例全部通过

**自动化验证命令：** `python -m pytest tests/test_local_fs.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 模块/服务类
**依赖：** 00050-03
**关联文件：** `m2-storage/src/file_store/base.py`, `m2-storage/src/file_store/local_fs.py`, `m2-storage/tests/test_local_fs.py`

---

## 🔲 00050-08 — 测试基础设施 + 集成测试 (conftest.py + test_manager.py)

**功能描述：**
- `conftest.py`：提供共享 pytest fixtures
  - `tmp_config_path`: 生成临时 deploy.yaml（指向临时目录）
  - `tmp_data_dir`: 创建/清理临时数据目录（`tmp_path`）
  - `chromadb_store`: 已初始化 ChromaDB 实例
  - `meilisearch_index`: 已初始化 Meilisearch 实例（检测进程可用性，不可用则 skip）
  - `sqlite_db`: 已初始化 SQLite 实例
  - `local_fs_store`: 已初始化 LocalFS 实例
  - `storage_manager`: 完整装配的 StorageManager（含全部 4 个后端）
- `test_manager.py`：StorageManager 端到端集成测试
  - 完整生命周期：创建 → 初始化 → 健康检查 → 业务操作 → 关闭
  - 4 个后端协作场景验证

**验证方法：**
- 测试用例 1：storage_manager fixture 成功创建并初始化
- 测试用例 2：health_check 返回全部 4 个后端状态
- 测试用例 3：通过 manager.vector_store 插入并搜索
- 测试用例 4：通过 manager.file_store 写入并读取文件
- 测试用例 5：close 后所有后端不可用
- 通过标准：5 个测试用例全部通过

**自动化验证命令：** `python -m pytest tests/test_manager.py -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 集成/跨模块类
**依赖：** 00050-04, 00050-05, 00050-06, 00050-07（所有后端实现）
**关联文件：** `m2-storage/tests/conftest.py`, `m2-storage/tests/test_manager.py`

---

## 🔲 00050-09 — 模块打包与最终集成 (pyproject.toml + requirements.txt + src/__init__.py)

**功能描述：**
- `pyproject.toml`：配置包元数据，依赖项，`[project.optional-dependencies]` 按后端分组
- `requirements.txt`：锁定开发依赖版本
- `src/__init__.py`：导出公开 API（`StorageManager`, `create_storage_manager`）
- 验证模块可被外部正确导入
- 验证所有 4 个后端 Protocol 合规

**验证方法：**
- 测试用例 1：`pip install -e .` 成功，`from m2_storage import StorageManager` 无错误
- 测试用例 2：所有 4 个后端实例通过 `isinstance(x, XProtocol)` 检查
- 测试用例 3：全量测试套件运行（`pytest tests/ -v`）
- 通过标准：全部 passed，0 failed

**自动化验证命令：** `python -m pytest tests/ -v`
**通过条件：** 全部 passed，0 failed
**Task 类型：** 集成/跨模块类
**依赖：** 00050-08（所有测试就绪后才能最终验证）
**关联文件：** `m2-storage/pyproject.toml`, `m2-storage/requirements.txt`, `m2-storage/src/__init__.py`

---

## 依赖关系图

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

**并行机会**：00050-04 ~ 00050-07 四个后端互不依赖，可并行开发。
