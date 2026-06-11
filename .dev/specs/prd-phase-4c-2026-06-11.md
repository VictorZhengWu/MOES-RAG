# PRD: Phase 4-C — 智能研究平台增强与收尾

> **版本**: v1.0 | **日期**: 2026-06-11
> **依赖**: Phase 4-A (00104), Phase 4-B (00105)
> **定位**: 4-A/4-B 的深度集成 + 体验完善 + 长期能力建设

---

## 1. 概述

### 1.1 背景

Phase 4-A (Deep Research) 和 Phase 4-B (Projects) 已完成核心功能。但存在三类缺口：

1. **集成深度不足**：M3 项目搜索仅在 M8 层做上下文注入，未接入 M3 pipeline；对话自动分类逻辑就绪但 M5 chat pipeline 未触发
2. **用户体验粗糙**：文件夹无树形展开、看板无拖放、合规矩阵不自动更新、Deep Research 质疑功能未开放
3. **长期能力缺失**：3 个额外 Agent（标准/案例/法规）、项目归档案例库、PDF 导出、K8s 部署

Phase 4-C 按优先级分两阶段处理——核心集成（P0+P1）和长期增强（P2+P3）。

### 1.2 范围选择

| 优先级 | 项数 | 内容 | 预计 |
|--------|------|------|------|
| **P0 核心集成** | 2 | M3 深度搜索 + 自动分类触发 | 3-5 天 |
| **P1 体验完善** | 4 | 文件夹树 + 看板拖放 + 合规自动更新 + DR 质疑 | 5-8 天 |
| **P2 增强能力** (本次 PRD 范围) | 4 | 标准/案例/法规 Agent + 归档案例库 + PDF 导出 + Markdown 升级 | 8-12 天 |
| **P3 基础设施** (后续) | 4 | 模板管理 + 协作 + K8s + README | 单独 PRD |

> **本次 PRD 覆盖 P0 + P1 + P2 = 10 项**

---

## 2. 目标

- **G1**: M3 项目范围搜索接入 M3 dense+sparse pipeline，实现 PRD 定义的混合排序算法
- **G2**: M5 chat pipeline 自动触发 `classify_conversation()` → `link_conversation()`
- **G3**: M6 文件夹树 UI（阶段→专业→子文件夹），可展开/折叠
- **G4**: M6 问题看板拖放改变状态（Kanban drag-drop）
- **G5**: 合规矩阵自动更新——结论关联到条款时自动设置 `needs_review` 状态
- **G6**: Deep Research FR-7 质疑深入——点击结论→展开推导→可质疑
- **G7**: 3 个新 Agent（ISO/ASTM/API 标准检索、事故案例检索、IMO 法规检索）
- **G8**: 项目归档 + 案例库——标记案例→可被 Deep Research 检索引用
- **G9**: PDF/Excel 导出——Deep Research 报告 + 项目合规报告
- **G10**: M6 报告渲染升级——`react-markdown` 替换简单正则

---

## 3. 用户故事

### P0: 核心集成

#### US-001: M3 项目范围搜索深度集成

**描述**: 作为项目经理，在项目内提问时，搜索结果应该项目文档优先排序，全局规范补充。

**验收标准**:
- [ ] M5 chat pipeline 接收 `project_id` 参数
- [ ] 当 `search_scope = "project_only"`: 仅检索项目文档（通过 M3 向量搜索 + SQLite 全文）
- [ ] 当 `search_scope = "hybrid"` (默认): 项目文档结果优先排序（权重 0.7-0.9），全局 M3 结果补充（权重 0.5-0.8）
- [ ] 排序算法: `score = 0.7 + (source_bonus) - 0.5 + similarity * 0.3 + (regulation_match_bonus)`
- [ ] 项目文档无匹配时自动回退到全局搜索（不报错）

#### US-002: 对话自动分类与关联

**描述**: 从项目详情页新建对话后，对话自动关联到该项目并分类到对应文件夹。

**验收标准**:
- [ ] M5 chat pipeline 末尾调用 `project_manager.classify_conversation(content, project)`
- [ ] 自动调用 `project_manager.link_conversation(project_id, conv_id, folder_path)`
- [ ] 分类规则: 内容关键词 → 专业推断 → 阶段推断 → 文件夹路径
- [ ] 用户可在侧边栏手动调整文件夹

### P1: 体验完善

#### US-003: 文件夹树 UI

**描述**: 项目详情页 Conversations tab 显示文件夹树结构而非平铺列表。

**验收标准**:
- [ ] 树形结构: 阶段 → 专业 → 对话列表
- [ ] 点击文件夹展开/折叠子节点
- [ ] 每个节点显示对话计数 badge
- [ ] 空文件夹显示 "—" 占位
- [ ] 右键菜单: 新建子文件夹 / 重命名 / 删除（仅空文件夹）

#### US-004: 看板拖放

**描述**: 在 Issues tab 中，可以拖放问题卡片改变其状态。

**验收标准**:
- [ ] 拖放卡片从一列到另一列 → `PATCH /issues/{id}` 更新 status
- [ ] 拖放过程中列高亮（drop indicator）
- [ ] 移动端降级为下拉选择状态
- [ ] 拖放后乐观更新 UI（不等待 API 响应），失败时回滚

#### US-005: 合规矩阵自动更新

**描述**: 当结论被关联到合规条款时，自动标记该条款为 `needs_review`。

**验收标准**:
- [ ] `create_conclusion()` 时如果 `citation` 包含规范引用 → 找到对应 compliance_item → 更新状态为 `needs_review`
- [ ] `update_compliance()` 手动标记 `verified` 后不被自动覆盖
- [ ] 合规进度条实时更新

#### US-005-b: 结论删除时合规状态回滚

**描述**: 删除结论时，检查是否是最后一个引用某条款的结论。如果是，回退合规状态。

**验收标准**:
- [ ] 删除结论时遍历其 `citation` 字段 → 找到所有被引用的 compliance_item
- [ ] 检查是否有其他结论引用同一条款 → 有则保持当前状态
- [ ] 如果无其他引用 → `needs_review` 回退到 `unverified`（`verified` 不自动回退）
- [ ] 回退操作记录到 `linked_conclusions`
- [ ] 测试: 创建 2 个结论引用同一条款 → 删除 1 个 → 验证状态不变

#### US-003-b: 文件夹树拖放对话

**描述**: 在文件夹树中拖放对话到目标文件夹。

**验收标准**:
- [ ] 拖放对话到文件夹 → `link_conversation()` 更新 folder_path
- [ ] 拖放过程中目标文件夹高亮
- [ ] 批量拖放: 选中多个对话 → 拖到文件夹
- [ ] 移动端降级: 长按选择目标文件夹
- [ ] 乐观更新 + 失败回滚

#### US-006: Deep Research 质疑深入 (FR-7)

**描述**: 在 Deep Research 报告中点击任意结论，展开推导过程并提出质疑。

**验收标准**:
- [ ] 结论点击展开面板显示: 原始检索结果（Top 5 条）+ 推理步骤 + 引用原文（可展开）
- [ ] 质疑输入框: 多行文本、500 字限制、提交+取消按钮
- [ ] 质疑中: "AI 正在重新分析..." 加载 + 禁用其他操作（防重复提交）
- [ ] 质疑完成: 更新结论（高亮变化部分）+ 报告末尾追加"人工复核"时间戳
- [ ] 错误处理: 质疑失败不影响原结论，提示"AI 重新分析失败，请稍后重试"
- [ ] 调用 `POST /research/{id}/question` → M5 重新分析 → 更新结论

### P2: 增强能力

#### US-007: 标准/案例/法规 Agent

**描述**: Deep Research 检索范围扩展到 ISO/ASTM 标准、事故案例、IMO 法规。

**验收标准**:
- [ ] Agent_标准: 内置 Top 30 ISO/ASTM/API 标准字典（从 4-A 的 10 个扩展到 30 个），支持关键词检索标题+范围
- [ ] Agent_案例: Web Search 优化——查询自动追加 "marine accident report MAIB NTSB" 后缀
- [ ] Agent_法规: Web Search 优化——查询自动追加 "IMO SOLAS MARPOL MSC MEPC" 后缀
- [ ] Phase 4-C 不建独立 Agent 类，通过 Web Search Agent 查询优化实现

#### US-008: 项目归档与案例库

**描述**: 项目完成后归档，优秀项目标记为"案例"供后续参考。

**验收标准**:
- [ ] 归档: 项目设为只读，所有对话/文档/结论保留
- [ ] 标记案例: `is_archived=1` + `tags` 包含 "case_study"
- [ ] 案例检索: `GET /api/v1/projects?archived=true&tag=case_study`
- [ ] Deep Research 引用案例: 研究页面增加 "Include case studies" 复选框
- [ ] 归档摘要: `generate_report()` 增强版（已有基础）

#### US-009: PDF/Excel 导出

**描述**: 导出 Deep Research 报告和项目合规报告。

**验收标准**:
- [ ] Deep Research 报告 → PDF（Markdown → HTML → PDF，使用 `weasyprint` 或 `markdown-pdf`）
- [ ] 项目合规报告 → Excel（使用 `openpyxl`，包含合规矩阵 + 偏差清单 + 结论表）
- [ ] 导出按钮: 研究页面 "Export PDF" + 项目报告页面 "Export Excel"
- [ ] M8 端点: `GET /api/v1/agent/research/{id}/export` + `GET /api/v1/projects/{id}/report/export`

#### US-010: Markdown 渲染升级

**描述**: M6 前端使用 `react-markdown` 库替换当前的正则渲染。

**验收标准**:
- [ ] 安装 `react-markdown` + `remark-gfm`（表格支持）
- [ ] 研究页面报告渲染替换为 `<ReactMarkdown>` 组件
- [ ] 支持: 标题/列表/粗体/表格/代码块/引用/链接
- [ ] 当前正则渲染保留为 fallback（无 JS 环境时）

---

## 4. 功能需求

### 4.1 M5 后端

**FR-1: M3 项目范围搜索 (search_scope.py)**

```python
# m5_qa/project/search_scope.py (新文件)
async def project_scoped_search(
    query: str, project_id: str, search_scope: str,
    m3_engine, project_manager,
) -> list[ScoredChunk]:
    project_docs = await project_manager.search_project_documents(project_id, query)
    project_chunks = _convert_docs_to_chunks(project_docs)  # base_score=0.7

    if search_scope == "project_only":
        return project_chunks

    global_chunks = await m3_engine.retrieve(RetrievalRequest(query=query, top_k=20))

    return _hybrid_rank(project_chunks, global_chunks, project_manager, project_id)
```

**性能优化**: 如果 project_docs 中 ≥5 条相似度 > 0.7 的匹配，跳过 M3 全局检索。权重可通过 `_HYBRID_WEIGHTS` 字典配置（非数据库持久化）。

**FR-2: 对话自动分类触发**

在 M5 `engine.py` 的 `chat()` 方法末尾：

```python
if hasattr(self, '_project_id') and self._project_id:
    try:
        last_msg = request.messages[-1].content
        proj = await self._project_manager.get_project(self._project_id)
        folder = await self._project_manager.classify_conversation(last_msg, proj)
        await self._project_manager.link_conversation(
            self._project_id, response.conversation_id, folder, []
        )
    except Exception as e:
        logger.warning("Auto-classify failed: %s", e)
```

### 4.2 M6 前端

**FR-3: 文件夹树组件**

```
Component: FolderTree
Props: { conversations, onSelect }
State: expandedFolders: Set<string>

Renders:
├─ 设计阶段 (3)
│  ├─ 结构 (2)
│  │  ├─ 📄 舱口盖强度计算
│  │  └─ 📄 材料等级确认
│  └─ 轮机 (1)
│     └─ 📄 主机选型分析
├─ 建造阶段 (1)
│  └─ 焊接 (1)
│     └─ 📄 WPS 预热温度
```

**FR-4: 看板拖放**

使用 HTML5 Drag and Drop API（无额外依赖）：

```typescript
const onDragStart = (issueId: string) => { ... }
const onDrop = (column: string) => {
  PATCH /issues/{issueId} { status: column }
  // Optimistic update
}
const onDragOver = (e) => { e.preventDefault() }
```

**FR-5: 合规自动更新**

在 `create_conclusion()` 中：

```python
if citation and len(citation) > 0:
    for ref in citation:
        clause_id = f"{project_id}-{_hash_clause(ref['clause'])}"
        # Only update if not already verified
        current = await get_compliance_status(project_id, clause_id)
        if current != "verified":
            await update_compliance(project_id, clause_id, {"status": "needs_review"})
```

### 4.3 导出与升级

**FR-6: PDF 导出**

```python
# m5_qa/research/export.py
import markdown
import weasyprint

async def export_report_pdf(report_md: str) -> bytes:
    html = markdown.markdown(report_md, extensions=['tables', 'fenced_code'])
    styled = f"<html><body style='font-family: Arial'>{html}</body></html>"
    return weasyprint.HTML(string=styled).write_pdf()
```

**FR-7: Excel 导出**

```python
# m5_qa/project/export.py
import openpyxl

async def export_compliance_excel(project_id: str) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Compliance Matrix"
    # Headers: Clause | Status | Deviation | Verified By | Date
    # Data rows from compliance list
    return _to_bytes(wb)
```

**FR-8: Markdown 升级**

```bash
npm install react-markdown remark-gfm
```

```tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

<ReactMarkdown remarkPlugins={[remarkGfm]} className="prose prose-sm dark:prose-invert max-w-none">
  {report}
</ReactMarkdown>
```

---

### 用户体验要求

以下要求适用于**所有**用户故事：

**Loading 状态**:
- [ ] 所有异步操作必须有具体 loading 文案（"正在生成报告..."而非"处理中..."）
- [ ] 超过 30 秒的操作显示进度百分比

**错误提示**（三段式）:
- [ ] 发生了什么（用户可理解的语言）
- [ ] 为什么发生（可选，技术细节折叠）
- [ ] 如何解决（具体操作建议）
- ❌ 反例: "Error 500"  ✅ 正例: "无法连接服务器。请检查网络后重试。"

**空状态**:
- [ ] 所有列表/看板必须有空状态提示，说明"为什么为空"+"如何开始"
- [ ] 示例: "暂无待研究问题。点击'+ New Issue'创建第一个问题。"

**成功反馈**:
- [ ] 关键操作有 Toast 提示，3秒内消失
- [ ] 示例: "对话已保存到'设计阶段/结构'文件夹"

**降级策略**:
- [ ] 所有 API 调用包裹 try-except + logger.error
- [ ] M3 检索失败 → 仅检索项目文档（不发错误给用户）
- [ ] 分类失败 → 对话不关联到项目（不发错误，仅记录日志）
- [ ] 导出失败 → "下载失败，请稍后重试"提示

---

## 5. 非目标（Phase 4-C 不做）

- ❌ 用户自定义规范模板 — P3
- ❌ 协作功能（@提及/讨论串/角色权限） — P3
- ❌ K8s 部署 — P3
- ❌ README 文档 — P3
- ❌ 项目间链接（Project B 引用 Project A 结论） — P3
- ❌ Agent_标准/案例/法规 的独立 Agent 类 — Phase 4-C 通过 Web Search 查询优化近似

---

## 6. 任务分解

### P0: 核心集成 (00106)

| Task | 内容 | 模块 |
|------|------|------|
| 00106-01 | `search_scope.py`: M3 pipeline 项目搜索 + 混合排序 | M5 |
| 00106-02 | M5 engine: 对话自动分类触发 + project_id 传递 | M5/M8 |

### P1: 体验完善 (00107, 6 Task)

| Task | 内容 | 模块 |
|------|------|------|
| 00107-01 | M6 FolderTree 组件 (树形展开/折叠/右键菜单) | M6 |
| 00107-02 | M6 Issues Kanban 拖放 (HTML5 DnD + 移动端长按 + 乐观更新) | M6 |
| 00107-03 | M5 合规自动更新 (conclusion citation → compliance needs_review) | M5 |
| 00107-04 | M5+M6 Deep Research 质疑深入 (FR-7, 展开面板 + 质疑输入 + 重新分析) | M5/M6 |
| 00107-05 | M5 结论删除时合规状态回滚 (last-reference check) | M5 |
| 00107-06 | M6 文件夹树拖放对话 (FolderTree DnD) | M6 |

### P2: 增强能力 (00108)

| Task | 内容 | 模块 |
|------|------|------|
| 00108-01 | Agent 标准/案例/法规 (Web Search 查询优化) | M5 |
| 00108-02 | 项目归档 + 案例库 (标记案例/检索/DR 引用) | M5/M6 |
| 00108-03 | PDF + Excel 导出 (weasyprint + openpyxl) | M5/M8 |
| 00108-04 | M6 react-markdown 升级 | M6 |

### 集成验证 (00109)

| Task | 内容 | 模块 |
|------|------|------|
| 00109-01 | 全模块集成验证 + 测试 | ALL |

---

## 7. 依赖关系

```
P0: 00106-01 → 00106-02                    (串行, 3-5 天)
P1: 00107-01 ‖ 00107-02 ‖ 00107-03 ‖ 00107-04 ‖ 00107-05 ‖ 00107-06  (可并行, 7-10 天)
P2: 00108-01 ‖ 00108-02 ‖ 00108-03 ‖ 00108-04                      (可并行, 8-12 天)

P0 → P1 → P2 → 00109 (总计 18-27 天)
```

P0 必须先做（M5 pipeline 改动影响 P1 的合规自动更新）。
P1 六项互相独立可并行（建议 00107-01 先做，文件夹树是其他 UI 的基础）。
P2 四项互相独立可并行。

---

## 8. 成功指标

- **S1**: 项目内搜索的项目文档命中率 > 50%（项目有 ≥3 份文档时）
- **S2**: 对话自动分类准确率 > 70%（用户手动调整率 < 30%）
- **S3**: 看板拖放操作延迟 < 200ms（乐观更新）
- **S4**: 质疑功能响应 < 10s
- **S5**: PDF 导出 < 5s（10 页以内报告）
