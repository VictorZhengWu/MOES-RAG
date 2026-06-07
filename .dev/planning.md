# Marine & Offshore Expert System — 开发规划文档

> **状态**：✅ Phase 1 完成 ✅ Phase 2 完成 ✅ Phase 3 核心完成 | **最后更新**：2026-06-07

---

## 〇、项目简介

本项目旨在构建一个面向船舶与海洋工程行业的专业 RAG（检索增强生成）智能问答系统——**Marine & Offshore Expert System**。系统整合全球主要船级社规范（CCS/DNV/ABS/LR 等）、国际海事规则（IMO）、多专业领域知识（结构/机械/管系/电气/通讯/自动化）、各类型船舶与海洋结构物设计建造运维资料、以及主流厂商配套产品数据，通过先进的 RAG 技术为工程师、设计师、检验人员和船东提供精准的知识检索与智能问答服务。系统以 Web 界面和 API 两种形式提供服务，支持个人单机、企业私有化和 SaaS 云服务三种部署模式。

### 额外设计约束

1. **国际化（i18n）**：系统 Web 界面（M6 用户前端 + M7 管理后台）支持英文/中文/韩文/日文/挪威文 5 种语言，缺省英文。UI 中所有文字零硬编码。用户切换语言时即时生效，无需刷新页面。
2. **系统名称**：Marine & Offshore Expert System。
3. **代码注释规范**：所有源程序（Python 和 TypeScript）必须有详细英文注释，不仅说明程序做什么（WHAT），还要交代为什么有这段程序（WHY）。

---

## 一、需求分析与系统规划（阶段 1 产出）

> 详见设计文档：`.dev/specs/rag-system-design-2026-05-12.md`

### 1.1 功能分层结构

- **System**：Marine & Offshore Expert System
  - **M1 文档解析引擎**：原始文件（PDF/DOCX/图纸/扫描件）→ 结构化文本 + 向量嵌入
  - **M2 存储抽象层**：向量存储 / 全文索引 / 关系数据库 / 文件存储 统一接口
  - **M3 检索引擎**：查询增强 → 多路检索 → 结果融合 → 精排 → 上下文压缩
  - **M4 知识图谱引擎**：实体抽取 / 关系构建 / 图查询 / 跨规范映射 / 版本追踪
  - **M5 智能问答引擎**：查询路由 → Multi-Agent 编排 → Self-RAG 循环 → 流式生成 → 引证溯源
  - **M6 用户前端**：问答交互 / 会话管理 / 知识库浏览 / 个人设置 / 语言切换 (5语种)
  - **M7 管理后台**：文档管理 / KG 管理 / LLM 配置 / 用户管理 / 监控面板 / 语言切换 (5语种)
  - **M8 API 网关**：OpenAI-compatible API / 认证 / 限流 / 计费

### 1.2 模块通信方式

- 模块间仅通过 `contracts/` 中定义的 Protocol 接口通信
- 同步调用：Python Protocol 接口（M3/M4 → M5）
- 异步 REST/SSE：M5 → M6/M7/M8
- 存储访问：所有模块通过 M2 的 Protocol 接口操作数据
- 不允许跨层直接调用

### 1.3 国际化架构

- M6 和 M7 共享 i18n 基础设施
- 每个语种独立 JSON 资源文件（`locales/en.json`, `zh.json`, `ko.json`, `ja.json`, `no.json`）
- UI 组件引用 i18n key，禁止硬编码文字
- 语言偏好持久化：localStorage + 服务端用户配置
- 缺省语言：English；fallback 链：用户选择 → 浏览器 Accept-Language → en

---

## 二、系统设计（阶段 2 产出）

> 详见设计文档：`.dev/specs/rag-system-design-2026-05-12.md`

### 2.1 代码注释规范（所有模块强制遵守）

- 所有源程序（Python + TypeScript）必须有**详细英文注释**
- 每个函数/类/关键代码块必须包含：
  - **WHAT**：功能说明、参数说明、返回值说明
  - **WHY**：为什么需要这段代码、为什么选择这个实现方案而非其他替代方案
- CI linting 检查公开函数的 docstring 完整性
- PR review 必须检查注释质量，WHY 部分不可或缺

---

## 三、流程设计（阶段 3 产出）

> 详见设计文档：`.dev/specs/rag-system-design-2026-05-12.md`

### 3.1 开发阶段

| 阶段 | 内容 | 模块 |
|------|------|------|
| Phase 1 | 前端骨架 + Mock Server + i18n 基础设施 | contracts → Mock Server → M6 → M7 |
| Phase 2 | 后端核心 | M2 → M1 → M3 → M4 → M5 |
| Phase 3 | 对外服务与部署 | M8 → deploy/ |
