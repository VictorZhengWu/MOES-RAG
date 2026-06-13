# 船舶与海洋工程专家系统

面向船舶与海洋工程行业的专业检索增强生成（RAG）智能问答系统。

**支持语言**：English | 中文 | 한국어 | 日本語 | Norsk

---

## 概述

本系统整合全球主要船级社规范（DNV、ABS、CCS、LR、BV、RINA、NK、KR）、IMO 国际法规（SOLAS、MARPOL、IGC/IGF Code）、多专业领域工程知识及各船型资料，提供精准的、带引证溯源的智能问答服务。

**核心功能**：

- **多船级社交叉验证**：自动对比 DNV/ABS/CCS/LR 规范要求，检测数值冲突
- **Deep Research 深度研究**：多步 AI Agent，自动分解问题、并行检索、交叉分析、生成 7 节结构化报告
- **项目工作空间**：按工程设计阶段（设计/建造/交付/运营）+ 专业方向组织对话、文档和合规追踪
- **合规追踪**：逐条款规范验证矩阵 + 偏差管理 + 审计就绪
- **引证追溯**：每条回答标注船级社条款编号（如 DNV Pt.3 Ch.3 §6.2, 2025 版），点击查看原文
- **团队协作**：@提及成员、讨论串、通知中心、三级权限（Owner/Editor/Viewer）
- **OpenAI API 兼容**：任何 OpenAI SDK 客户端只需更换 base_url 和 api_key 即可接入

## 系统架构

8 大独立模块，5 层架构：

```
第 5 层 — 网关
  M8: API Gateway (FastAPI, port 8000)
       — 认证（API Key）、限流（内存/Redis）、路由
       — OpenAI 兼容 /v1/chat/completions、/v1/models

第 4 层 — 智能引擎
  M5: RAG QA Engine
       — 3 种管线模式（simple/pipeline/self_rag）
       — Deep Research 多步研究 Agent
       — Project 项目工作空间（10 张数据表）
       — LLM 可插拔后端（DeepSeek、OpenAI、Claude、Ollama）

第 3 层 — 检索
  M3: Retrieval Engine       M4: Knowledge Graph Engine
       — Dense + Sparse 双路检        — 规则 + LLM 实体抽取
         索 + RRF 融合 + 重排序         — Kuzu 嵌入式图数据库
       — 命题式索引                    — BFS 图遍历 + 跨船级社引用
                                       — 30+ 实体类型

第 2 层 — 存储
  M2: Storage Abstraction Layer
       — 6 种后端：ChromaDB/FAISS/Qdrant/Milvus（向量存储）
                   Meilisearch/Elasticsearch（全文检索引擎）
                   SQLite/PostgreSQL（关系数据库）
                   LocalFS/MinIO/S3（文件存储）
       — 通过 deploy.yaml 在部署时选择后端

第 1 层 — 文档解析
  M1: Document Parsing Engine
       — 3 种后端：Docling、Marker、MinerU
       — GPU 自动检测 + 后端推荐
       — 跨页表格合并 + 复杂度质量门禁

前端
  M6: User Portal (Next.js, port 3000)
  M7: Admin Portal (Next.js, port 3001)
```

## 部署模式

| 模式 | 存储后端 | 适用场景 |
|------|---------|---------|
| **个人版** | ChromaDB + SQLite + LocalFS | 个人电脑，单用户 |
| **企业版** | 可选 Qdrant/PostgreSQL/MinIO | 企业内部服务器，多人团队 |
| **SaaS 版** | Qdrant + PostgreSQL + MinIO/S3 + Redis | 多租户云服务 |

## 快速开始（个人版）

**前提条件**：[Docker Desktop](https://www.docker.com/products/docker-desktop/)

### 一键启动

```
Windows:  双击 deploy/personal/start.bat
Mac/Linux: cd deploy/personal && ./start.sh
```

首次运行会下载 Docker 镜像（约 5-10 分钟），后续启动约 30 秒。

### 手动启动

```bash
cd deploy/personal
docker compose up -d
```

### 访问地址

| URL | 用途 |
|-----|------|
| `http://localhost:3000` | 用户端 |
| `http://localhost:8000/docs` | API 文档 |
| `http://localhost:3000/help` | 在线帮助 |

**离线帮助**：参见 `deploy/personal/HELP.md`

### 停止

```bash
cd deploy/personal
docker compose down
# Windows 用户可双击 stop.bat
```

个人版使用嵌入式后端（ChromaDB、SQLite、LocalFS），无需安装任何外部数据库。可选启用文件解析（`--profile parsing`）和本地大模型（`--profile llm`）。

## API 接入

OpenAI 兼容 API 端点：

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-m8-your-api-key"
)

response = client.chat.completions.create(
    model="m5-qa",
    messages=[{
        "role": "user",
        "content": "DNV Pt.4 Ch.3 对 EH36 钢板焊接工艺有哪些要求？"
    }]
)

print(response.choices[0].message.content)
# 回答包含规范条款引证编号
```

API Key 从管理端 → API Keys 页面生成。

## 功能概览

### 核心问答
- 引证溯源的智能回答，含船级社条款编号
- 5 语种即时切换（中/英/韩/日/挪威）
- SSE 流式输出
- Web Search 集成（DuckDuckGo、Tavily、Brave、Google）
- 拖放上传文件（PDF、DOCX、XLSX、PPTX、图片）

### Deep Research 深度研究
- 多步研究 Agent + 实时进度
- 并行检索：规范（M3+M4）+ Web 搜索
- 跨船级社规范冲突检测
- 7 节结构化报告（执行摘要、对比矩阵、方案建议、检验清单、风险矩阵、引用追溯、局限说明）

### Projects 项目工作空间
- 按船型 + 入级社创建项目模板
- 文件夹树：阶段 → 专业 → 子文件夹
- 看板式问题追踪（Kanban + 拖放）
- 逐条款规范合规矩阵
- 案例库归档（关键挑战/解决方案/经验教训）
- 跨项目结论引用

### 管理后台 (M7)
- 系统配置（LLM、检索参数、功能开关、存储后端、部署模式、OAuth、SMTP）
- 存储后端连接测试（PostgreSQL、Elasticsearch、MinIO）
- 运行监控 + 自动刷新
- API Key 管理

## 存储后端矩阵

| 接口 | 个人版 | 企业版 | SaaS 版 |
|------|--------|--------|---------|
| 向量存储 | ChromaDB / FAISS | Qdrant / Milvus | Qdrant / Milvus |
| 全文索引 | Meilisearch | Meilisearch / Elasticsearch | Elasticsearch |
| 关系数据库 | SQLite | SQLite / PostgreSQL | PostgreSQL |
| 文件存储 | 本地文件系统 | 本地文件系统 / MinIO | MinIO / S3 |
| 限流器 | 内存 | 内存 / Redis | Redis |

## 开发

```bash
# 安装
pip install -e contracts/
pip install -e m1-doc-parsing/
pip install -e m2-storage/
pip install -e m3-retrieval/
pip install -e m4-knowledge-graph/
pip install -e m5-qa-engine/
pip install -e m8-api-gateway/

# 前端
cd m6-user-portal && npm install
cd m7-admin-portal && npm install

# 运行测试
python -m pytest m1-doc-parsing/tests/ -q
python -m pytest m2-storage/tests/ -q
python -m pytest m3-retrieval/tests/ -q
python -m pytest m4-knowledge-graph/tests/ -q
python -m pytest m5-qa-engine/tests/ -q
python -m pytest m8-api-gateway/tests/ -q
```

**测试覆盖**：6 个模块共 536 个测试全部通过。

## 文档

| 文件 | 用途 |
|------|------|
| `.dev/specs/rag-system-design-2026-05-12.md` | 系统架构设计 |
| `.dev/planning.md` | 开发规划 |
| `.dev/decisions.md` | 跨模块设计决策 |
| `.dev/tasks.md` | 任务列表（全部完成） |
| `.dev/specs/phase-4a-deep-research-design-2026-06-09.md` | Deep Research 产品需求文档 |
| `.dev/specs/phase-4b-projects-design-2026-06-09.md` | Projects 产品需求文档 |

## 许可证

专有软件。保留所有权利。
