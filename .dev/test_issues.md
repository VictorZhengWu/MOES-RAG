# 端到端测试问题报告

## 测试环境
- 系统：Windows 11 Pro
- Python：3.13
- 日期：2026-06-07
- 测试目标：完整链路 M1→M2→M3→M4→M5→M8→M6

## 测试发现的问题

### 1. 端口冲突问题 (严重)
**位置**: 端口 8000
**问题描述**: 
- 端口 8000 被系统进程 Manager.exe (PID 7756) 占用
- 该进程运行在 Services 会话中，内存占用 162,788 K
- 无法通过常规 taskkill 命令终止

**影响**: 无法在默认端口 8000 启动 M8 API Gateway

**建议修复**:
1. 更改 M8 默认端口配置
2. 或提供端口自动检测和切换功能
3. 在文档中说明端口冲突风险

### 2. 模块导入问题 (严重)
**位置**: contracts 包导入
**问题描述**:
- contracts 包已安装 (marine-rag-contracts 0.1.0) 但无法直接导入
- 错误信息：`ModuleNotFoundError: No module named 'contracts'`
- 需要 sys.path manipulation 才能成功导入：
  ```python
  import sys
  sys.path.insert(0, '../contracts')
  from contracts.qa_engine import ChatRequest  # 这样才能工作
  ```

**影响**: 所有依赖 contracts 包的模块无法正常启动

**建议修复**:
1. 修复 contracts 包的安装配置
2. 在各模块的 pyproject.toml 中正确声明 contracts 依赖
3. 或使用相对导入替代绝对导入

### 3. 语法错误 (严重)
**位置**: `m8-api-gateway/m8_gateway/routes/auth.py` 第 752-754 行
**问题描述**:
- 存在未关闭的括号导致语法错误
- 错误代码：
  ```python
  provider_user_id = str(
      user_json.get("id", user_json.get("sub", user_json.get("openid", ""))
  )  # 这里的括号不匹配
  ```

**影响**: 
- M8 API Gateway 无法启动
- 语法错误阻止应用加载
- OAuth 认证功能不可用

**建议修复**:
- 修复括号匹配问题
- 添加代码语法检查到 CI/CD 流程

## 测试阻塞状态

**当前状态**: 测试无法继续
**阻塞原因**: 
1. 端口冲突导致服务无法启动
2. 模块导入问题阻止应用加载
3. 语法错误阻止应用正常启动

**需要的操作**:
1. 修复 auth.py 语法错误
2. 解决 contracts 包导入问题
3. 解决端口冲突或更改默认端口

## 后续测试计划

一旦上述问题解决，将进行以下测试：

### 阶段1：基础服务启动测试
- [ ] M8 API Gateway 启动
- [ ] M5 QA Engine 启动
- [ ] M3 Retrieval Engine 启动
- [ ] M2 Storage 初始化
- [ ] M1 Parsing Engine 启动
- [ ] M6 前端启动

### 阶段2：DeepSeek API 测试
- [ ] 使用 DeepSeek API key 进行问答测试
- [ ] 验证 API key 认证
- [ ] 测试请求/响应流程

### 阶段3：Ollama 本地测试
- [ ] 使用本地 Ollama 模型测试
- [ ] 验证模型加载和推理
- [ ] 性能测试

### 阶段4：端到端链路测试
- [ ] 完整链路：用户查询 → M6 → M8 → M5 → M3/M4 → M2
- [ ] 安全性测试
- [ ] 容错性测试
- [ ] 操作正确性测试

## 模块测试结果

### M2 Storage 模块测试 ✅ (部分通过)
**测试时间**: 2026-06-07
**测试方法**: 运行 `demo_m2.py` 脚本

**通过的功能**:
- ✅ Vector Store (ChromaDB): 正常工作
  - 成功插入 3 个测试块
  - 向量搜索功能正常
  - 元数据过滤功能正常
- ✅ File Store (LocalFS): 正常工作
  - 文件存储和检索功能正常
  - 文件列表功能正常
- ✅ Relational DB (SQLite): 正常工作
  - 数据库连接正常
  - SQL 执行正常
  - 事务处理正常

**问题**:
- ❌ Document Index (Meilisearch): 连接失败
  - 错误：无法连接到 Meilisearch (端口 7700)
  - 原因：Meilisearch 服务未启动
  - 影响：全文搜索功能不可用

### M8 API Gateway 模块测试 ❌ (无法启动)
**测试时间**: 2026-06-07
**测试方法**: 尝试启动 M8 服务

**阻塞问题**:
1. 端口 8000 冲突
2. contracts 模块导入失败
3. auth.py 语法错误

### M3 Retrieval 模块测试 ✅ (部分通过)
**测试时间**: 2026-06-07
**测试方法**: 运行 `demo_m3.py` 脚本

**通过的功能**:
- ✅ M1 文档解析: 正常工作
  - 成功解析 HTML 测试文档
  - 元数据提取正常（分类社、章节、语言等）
- ✅ M3 查询分析: 正常工作
  - 成功识别分类社（DNV）
  - 成功识别章节信息
  - 关键词提取正常
  - 语义查询生成正常
  - 搜索路径选择正常（fast/medium/full）
- ✅ M3 向量搜索: 正常工作
  - ChromaDB 搜索结果正常
  - 相关性排序正常
  - Top-K 结果返回正常

**问题**:
- ❌ Meilisearch 集成: 连接失败
  - ChromaDB 功能正常，插入了10个块
  - Meilisearch 索引创建失败
- ⚠️ M1 解析结果: 页面和表格计数为0
  - 可能是因为测试文档是简单的 HTML

### 依赖服务状态
- ❌ Meilisearch (端口 7700): 未启动，阻塞全文搜索功能
- ❌ M8 API Gateway (端口 8000): 无法启动，语法错误和导入问题
- ❌ M6 前端 (端口 3000): 未测试
- ⚠️ Ollama (端口 11434): 状态未知，未测试
- ✅ ChromaDB: 工作正常
- ✅ SQLite: 工作正常

## 备注

根据用户要求，本次测试仅进行问题发现，不修改源代码。所有问题需要由开发团队进行修复。

**已验证的组件**:
- M2 Storage 核心功能正常 (ChromaDB, SQLite, LocalFS)
- contracts 包可以通过 sys.path manipulation 导入
- M8 代码存在语法错误阻止启动