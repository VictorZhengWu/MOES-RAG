# M2 存储抽象层 — 详细设计规范

> **日期**: 2026-05-18 | **状态**: 待审批 | **依赖**: contracts/ (00010)

---

## 1. 模块定位

M2 是系统的存储抽象层，位于 Layer 1 (Data)，为上层所有模块（M1/M3/M4/M5）提供统一的存储接口。上层模块依赖 `contracts/storage.py` 中定义的 4 个 Protocol，M2 负责提供具体的后端实现。

**核心约束**：上层模块永远不直接导入具体后端类，只通过 `StorageManager` 和 Protocol 交互。

---

## 2. 模块目录结构

```
m2-storage/
├── src/
│   ├── __init__.py              # 模块入口，导出 StorageManager
│   ├── config.py                # deploy.yaml 解析 + 配置 dataclass 模型
│   ├── factory.py               # 工厂函数，根据配置实例化后端
│   ├── manager.py               # StorageManager：统一入口，持有 4 个后端实例
│   ├── vector_store/
│   │   ├── __init__.py
│   │   ├── base.py              # VectorStore 适配层基类
│   │   └── chromadb_store.py    # ChromaDB 实现
│   ├── document_index/
│   │   ├── __init__.py
│   │   ├── base.py              # DocumentIndex 适配层基类
│   │   └── meilisearch_index.py # Meilisearch 实现
│   ├── relational_db/
│   │   ├── __init__.py
│   │   ├── base.py              # RelationalDB 适配层基类（SQLAlchemy）
│   │   └── sqlite_db.py         # SQLite + SQLAlchemy 实现
│   └── file_store/
│       ├── __init__.py
│       ├── base.py              # FileStore 适配层基类
│       └── local_fs.py          # 本地文件系统实现
├── tests/
│   ├── conftest.py              # 共享 fixtures
│   ├── test_config.py           # 配置解析测试
│   ├── test_factory.py          # 工厂函数测试
│   ├── test_manager.py          # StorageManager 集成测试
│   ├── test_chromadb.py         # ChromaDB 后端测试
│   ├── test_meilisearch.py      # Meilisearch 后端测试
│   ├── test_sqlite.py           # SQLite 后端测试
│   └── test_local_fs.py         # Local FS 后端测试
├── deploy.yaml                  # 本模块开发/测试用配置
├── requirements.txt             # 模块依赖
└── pyproject.toml
```

---

## 3. 各组件详细设计

### 3.1 deploy.yaml 配置格式

```yaml
# m2-storage/deploy.yaml
# 部署时由运维编辑；开发环境使用 Personal 默认值

deployment_mode: personal  # personal | enterprise | saas

storage:
  vector_store:
    backend: chromadb
    chromadb:
      persist_dir: ./data/chromadb
      collection_name: marine_rag

  document_index:
    backend: meilisearch
    meilisearch:
      host: http://127.0.0.1:7700
      api_key: ""
      index_name: marine_rag_docs

  relational_db:
    backend: sqlite
    sqlite:
      path: ./data/marine_rag.db

  file_store:
    backend: local_fs
    local_fs:
      root_dir: ./data/files
```

### 3.2 config.py — 配置解析

**职责**：将 deploy.yaml 解析为类型安全的 dataclass 对象。

**设计要点**：
- 使用 stdlib `dataclass`（不引入 Pydantic，减少 M2 依赖）
- 使用 `pyyaml` 解析 YAML
- 每个后端配置有独立的 dataclass 和 `from_dict()` 工厂方法
- 缺失字段提供合理默认值
- 不存在的 backend 值抛出明确错误信息

**类结构**：
```
StorageConfig
├── deployment_mode: str
├── vector_store: VectorStoreConfig
├── document_index: DocumentIndexConfig
├── relational_db: RelationalDBConfig
└── file_store: FileStoreConfig

VectorStoreConfig
├── backend: str  # "chromadb"
└── chromadb: ChromaDBConfig

ChromaDBConfig
├── persist_dir: str
└── collection_name: str
```

### 3.3 factory.py — 工厂函数

**职责**：读取配置，创建 4 个后端实例，组装 StorageManager。

**核心函数签名**：
```python
async def create_storage_manager(config_path: str = "deploy.yaml") -> StorageManager
```

**内部逻辑**：
1. `load_config(config_path)` → `StorageConfig`
2. `_create_vector_store(cfg)` → 根据 `cfg.backend` 创建具体实例
3. `_create_document_index(cfg)` → 同上
4. `_create_relational_db(cfg)` → 同上
5. `_create_file_store(cfg)` → 同上
6. `StorageManager(vs, di, rd, fs)` → 返回

每个 `_create_*` 函数内部是简单的 if/else 分支。未实现的 backend 抛出 `ValueError`。

### 3.4 manager.py — StorageManager

**职责**：M2 对外的唯一入口，持有 4 个后端实例的引用。

**核心方法**：
| 方法 | 功能 |
|------|------|
| `__init__(vs, di, rdb, fs)` | 注入 4 个后端实例 |
| `async initialize()` | 并发初始化 4 个后端（`asyncio.gather`） |
| `async health_check()` | 并发健康检查，返回 `{name: bool}` |
| `async close()` | 并发关闭 4 个后端连接 |

**设计要点**：
- Manager 不代理转发方法调用——上层直接 `manager.vector_store.search(...)` 
- 这避免了 Manager 成为臃肿的中间层
- Manager 只负责生命周期管理：初始化、健康检查、关闭

### 3.5 各后端 base.py — 适配层基类

每个存储子目录的 `base.py` 定义一个抽象基类（ABC），在 contracts Protocol 基础上补充**生命周期方法**：

```python
# vector_store/base.py
class BaseVectorStore(VectorStoreProtocol, ABC):
    @abstractmethod
    async def initialize(self) -> None: ...
    @abstractmethod
    async def health_check(self) -> bool: ...
    @abstractmethod
    async def close(self) -> None: ...
```

4 个 base.py 的结构完全一致，只是继承的 Protocol 不同。这些生命周期方法不属于 contracts/（contracts 只定义业务操作接口），但属于 M2 实现层的公共接口。

---

## 4. 四个后端实现详情

### 4.1 ChromaDB VectorStore (`chromadb_store.py`)

**职责**：实现 `BaseVectorStore`，对接 ChromaDB 嵌入式向量数据库。

**核心实现**：
- 使用 `chromadb` Python 客户端（`PersistentClient`）
- `initialize()`: 创建/获取 collection，配置 embedding function
- `insert(chunks, embeddings)`: 批量插入向量+元数据，返回 chunk_id 列表
- `search(query_vector, top_k, filters)`: 执行 ANN 搜索，支持 metadata 过滤
- `delete(doc_id)`: 按 doc_id metadata 过滤删除
- `count(filters)`: 返回 collection 中匹配的 chunk 数量
- `close()`: 释放客户端资源

**注意事项**：
- ChromaDB 的 PersistentClient 是线程安全的，但 M2 统一用 async 接口
- Embedding 由 M1 生成后传入，M2 不负责 embedding 计算
- Metadata 过滤使用 ChromaDB 的 `where` 子句

### 4.2 Meilisearch DocumentIndex (`meilisearch_index.py`)

**职责**：实现 `BaseDocumentIndex`，对接 Meilisearch 全文搜索引擎。

**核心实现**：
- 使用 `meilisearch` Python SDK
- `initialize()`: 创建 index，配置可搜索属性、排序属性、过滤器属性
- `index(chunks)`: 将 chunks 批量写入 Meilisearch
- `search(query, top_k, filters)`: 全文搜索，支持 metadata 过滤
- `delete(doc_id)`: 按 doc_id 过滤器删除
- `close()`: 释放 HTTP 连接

**注意事项**：
- Meilisearch 需要独立进程运行（`meilisearch` CLI 或 Docker）。开发测试时 `conftest.py` 负责启动/停止
- 搜索字段：`text`（主要内容）+ `metadata.*`（可过滤属性）
- Meilisearch 的 `filter` 语法与 ChromaDB 不同，需在适配层做转换

### 4.3 SQLite RelationalDB (`sqlite_db.py`)

**职责**：实现 `BaseRelationalDB`，使用 SQLAlchemy 2.0 async 引擎对接 SQLite。

**核心实现**：
- 使用 `sqlalchemy.ext.asyncio` + `aiosqlite`
- `initialize()`: 创建所有表（`create_all`），运行迁移
- `get_session()`: 返回 `AsyncSession` context manager
- `health_check()`: 执行 `SELECT 1`
- `close()`: 释放引擎和连接池

**设计要点**：
- **M2 不定义 ORM 模型**——ORM 模型由各上层模块自行定义。M2 只提供数据库引擎和 session 管理
- 这意味着 M2 的 RelationalDB 是**基础设施层**：提供连接，不定义表结构
- 上层模块（M5 的用户管理、M7 的配置存储等）通过 `manager.relational_db.get_session()` 获取 session，用自己的 ORM 模型操作数据库
- 这种设计避免了 M2 成为"上帝模块"——M2 不需要知道所有上层模块的数据模型

### 4.4 LocalFS FileStore (`local_fs.py`)

**职责**：实现 `BaseFileStore`，对接本地文件系统。

**核心实现**：
- 使用 `aiofiles` 进行异步文件 I/O
- `put(key, data, metadata)`: 写入文件到 `root_dir/key`，metadata 写入同路径 `.meta.json`
- `get(key)`: 读取文件字节
- `delete(key)`: 删除文件和 metadata
- `list(prefix)`: 列出目录下所有文件 key
- `get_url(key, expires_in)`: 返回 `file://` 路径（LocalFS 不支持 presigned URL，直接返回本地路径）
- `initialize()`: 确保 root_dir 存在
- `close()`: 无操作（LocalFS 无需关闭连接）

**路径安全**：
- 所有 key 必须做路径穿越校验（拒绝 `../`）
- 用 `os.path.realpath` 确保解析后的路径在 root_dir 内

---

## 5. 测试策略

### 5.1 测试分层

| 层级 | 测试文件 | 被测对象 | 说明 |
|------|---------|---------|------|
| 单元 | `test_config.py` | config.py | 正确 YAML 解析、缺失字段默认值、无效 backend 报错 |
| 单元 | `test_factory.py` | factory.py | Mock 后端类，验证工厂正确实例化 |
| 单元 | `test_chromadb.py` | ChromaDBStore | insert/search/delete/count，使用临时目录 |
| 单元 | `test_meilisearch.py` | MeilisearchIndex | index/search/delete，需 Meilisearch 进程 |
| 单元 | `test_sqlite.py` | SQLiteDB | initialize/get_session/health_check，使用临时文件 |
| 单元 | `test_local_fs.py` | LocalFSStore | put/get/delete/list/get_url，使用临时目录 |
| 集成 | `test_manager.py` | StorageManager | 完整生命周期：创建→初始化→健康检查→关闭 |

### 5.2 测试基础设施 (`conftest.py`)

- `tmp_config_path`: 生成临时 deploy.yaml 文件
- `tmp_dir`: 创建/清理临时数据目录
- `chromadb_store`: 已初始化的 ChromaDB 实例
- `meilisearch_index`: 已初始化的 Meilisearch 实例（需进程可用）
- `sqlite_db`: 已初始化的 SQLite 实例
- `local_fs_store`: 已初始化的 LocalFS 实例
- `storage_manager`: 完整装配的 StorageManager

### 5.3 每个后端的测试用例模板

每个后端测试覆盖 2 类用例：
1. **协议合规测试**：验证实现确实满足对应的 Protocol（`isinstance(store, VectorStoreProtocol)`）
2. **业务逻辑测试**：正常路径 + 边界条件 + 错误路径

以 ChromaDB 为例：
- `test_insert_and_search`: 插入 3 个 chunks，搜索返回正确结果
- `test_search_with_filters`: metadata 过滤正常工作
- `test_delete`: 删除后 count 减少
- `test_search_empty`: 空 collection 返回空列表
- `test_protocol_compliance`: isinstance 检查

---

## 6. 依赖项

```
# m2-storage/requirements.txt
chromadb>=0.5.0,<1.0.0
meilisearch>=0.31.0,<1.0.0
sqlalchemy[asyncio]>=2.0.0,<3.0.0
aiosqlite>=0.20.0
aiofiles>=24.0.0
pyyaml>=6.0
```

**依赖原则**：只列 M2 自己需要的东西。contracts/ 的依赖通过项目根 `pip install -e contracts/` 间接引入。

---

## 7. 不在本期范围（Phase 3 补充）

| 后端 | 类型 | 补充时机 |
|------|------|---------|
| Qdrant | VectorStore | Phase 3 + deploy/enterprise |
| Milvus | VectorStore | Phase 3 + deploy/saas |
| FAISS | VectorStore | Phase 3（可选，纯本地备选） |
| Elasticsearch | DocumentIndex | Phase 3 + deploy/saas |
| PostgreSQL | RelationalDB | Phase 3 + deploy/enterprise |
| MariaDB | RelationalDB | Phase 3（可选，企业备选） |
| MinIO | FileStore | Phase 3 + deploy/enterprise |
| S3/OSS | FileStore | Phase 3 + deploy/saas |

> 此清单已同步记录至 `.dev/decisions.md` D013。

---

## 8. 与其他模块的接口

M2 只导出 `StorageManager` 和工厂函数。其他模块的使用方式：

```python
# M3/M4/M5 中使用 M2
from m2_storage import create_storage_manager

manager = await create_storage_manager("deploy.yaml")
await manager.initialize()

# 直接通过 Protocol 接口调用
results = await manager.vector_store.search(query_vec, top_k=10)
chunks  = await manager.doc_index.search("welding procedure", top_k=5)
async with manager.relational_db.get_session() as session:
    ...
file_data = await manager.file_store.get("documents/abc.pdf")
```

---

*设计规范结束。待审批后生成实现计划。*
