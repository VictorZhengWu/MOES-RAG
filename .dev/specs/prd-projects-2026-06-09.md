# PRD: Projects — 海事工程项目工作空间

> **版本**: v1.0 | **日期**: 2026-06-09 | **父功能**: Phase 4-B
> **依赖**: M1 (Doc Parsing), M2 (Storage), M5 (QA Engine), M6 (User Portal), M7 (Admin Portal)
> **关联 PRD**: [Deep Research](./prd-deep-research-2026-06-09.md) (Phase 4-A)

---

## 1. 概述

### 1.1 问题

海洋工程项目具有天然的长周期、多阶段、多专业特性：

- **周期长**: 从概念设计→详细设计→建造→交付→运营，2-5 年
- **阶段多**: 每个阶段关注不同技术问题（设计阶段看结构规范，建造阶段看焊接标准）
- **专业杂**: 结构/轮机/管系/电气/舾装/自动化，6+ 个专业各自独立又相互关联
- **文档海量**: 一个船型项目涉及数百份规范、图纸、计算书、检验记录
- **合规审计**: 交付时需逐条证明所有设计满足适用规范 → 追溯链必须完整

当前系统的对话是散落的一问一答，无法组织成项目视图。每次新对话都从零开始，丢失了之前已经查过的规范结论和上传过的文档上下文。

### 1.2 核心价值

> **Projects 将系统从"问答工具"升级为"工程合规项目工作台"**

| 能力 | 无 Projects | 有 Projects |
|------|-----------|------------|
| 对话组织 | 时间线平铺 | 按项目→阶段→专业三层文件夹 |
| 文档管理 | 单次上传即忘 | 项目文档库 + 自动专业分类 + 版本管理 |
| 知识复用 | 每次重新查 | 项目规范清单 + 关键结论卡片 + 案例库 |
| 合规审计 | 无追溯 | 规范满足度矩阵 + 偏差清单 + 完整引用链 |
| 多人协作 | 不支持 | 角色权限 + @提及 + 讨论串 |
| Deep Research 集成 | 孤立运行 | 从项目启动 → 报告存入项目 → 结论追踪 |

---

## 2. 目标

- **G1**: 组织长周期工程项目的对话、文档、研究结论，形成结构化工作空间
- **G2**: 按船型+阶段提供项目模板，降低创建成本
- **G3**: 项目内搜索范围可切换：仅项目文档 / 全局知识库 / 混合（项目优先）
- **G4**: 自动追踪规范满足度：每个被引用过的规范条款记录是否已验证
- **G5**: 项目归档后形成可检索的案例库，供后续项目参考
- **G6**: Phase 4-B 实现核心 CRUD + 对话分组 + 文档管理 + 合规追踪基础
- **G7**: Phase 4-C 实现协作、案例库、导出功能

### 2.3 项目生命周期管理

每个项目经历 4 个阶段，每个阶段有不同的核心任务和合规重点：

| 阶段 | 核心任务 | 合规重点 | 产出 |
|------|---------|---------|------|
| **设计** | 规范查询、计算验证、材料选择 | 规范满足度矩阵逐条验证 | 计算书、规格书、合规报告 |
| **建造** | 工艺评定、焊接标准、NDT | 建造规范符合性 (DNV Pt.5) | WPS/PQR、NDT 报告、检验记录 |
| **交付** | 审图意见回复、偏差清单、合规声明 | 所有偏差项审批和关闭 | 合规报告、证书、完工文件 |
| **运营** | 维护计划、特检、改装评估 | 服役规范要求（到期特检） | 检验报告、维修记录、改装评估 |

**阶段流转**: 用户手动切换 → 自动更新合规矩阵 → 记录变更日志 (who/when/from→to)。

### 2.4 Projects ↔ Deep Research 协同工作流

**工作流 1：从项目问题启动研究**
```
项目待研究问题 → "启动 Deep Research" → 问题标题作为研究主题
→ Planner → Retrieval → Analysis → Report → 弹窗"保存到项目"
→ 选择文件夹 → 报告存入项目对话
→ 报告中的结论自动提取为"项目结论卡片"
→ 报告引用的规范自动加入"项目合规矩阵"
```

**工作流 2：从 Deep Research 保存到项目**
```
Sidebar 启动 Deep Research → 生成报告 → "保存到项目"
→ 选择/创建项目 → 选择文件夹
→ 报告 + 结论 + 规范引用一并存入
```

**工作流 3：项目间知识复用**
```
项目 A 完成 → 归档 → 标记为"案例"
→ 项目 B 创建时推荐相似历史项目
→ 项目 B 可引用项目 A 的结论和验证记录
→ 合规矩阵可引用历史验证（避免重复工作）
```

### 1.3 合规审计就绪

海洋工程项目交付时，船东和船级社要求完整的合规证明。Projects 确保：

| 审计需求 | Projects 如何满足 |
|---------|-----------------|
| **完整引用链** | 每个设计决策 → 规范条款 → 对话/结论/文档 → 可点击追溯 |
| **偏差管理** | 未满足的条款 → 偏差清单 (理由+替代方案+审批状态) |
| **实时合规状态** | 进度条 56% + 按 Part 拆分 + 高风险条款识别 |
| **一键审计报告** | Markdown 报告: 规范清单+验证记录+偏差清单+引用链 (Phase 4-B) |
| **导出格式** | PDF + Excel (Phase 4-C) |

---

## 3. 用户故事

### US-001: 创建项目（模板化）

**描述**: 作为项目经理，我可以从模板快速创建项目，预设阶段和文件夹结构。

**验收标准**:
- [ ] 项目类型下拉: 新造船 / 改造船 / 维护特检 / 海工 / 自定义
- [ ] 选择类型后自动预设:
  - 文件夹结构（设计/建造/验证/运营）
  - 适用规范清单（根据船型+入级社推荐）
  - 专业范围（可多选：结构/轮机/管系/电气/舾装/自动化）
- [ ] 必填: 项目名称、船型、主入级社、规范年度
- [ ] 选填: 辅助入级社、DWT、描述、团队成员
- [ ] 创建后跳转项目详情页

### US-002: 项目基本信息管理

**描述**: 作为项目成员，我可以查看和编辑项目配置。

**验收标准**:
- [ ] 项目详情页显示: 名称/船型/DWT/入级/阶段/专业范围/成员
- [ ] 可编辑字段: 名称、描述、阶段、专业范围
- [ ] 阶段变更记录到项目日志
- [ ] "归档项目"按钮（确认后只读）

### US-003: 对话分组

**描述**: 我可以把对话按阶段和专业组织到文件夹中。

**验收标准**:
- [ ] 项目内文件夹树: 阶段 → 专业 → 自定义子文件夹
- [ ] 右侧对话列表: 当前选中文件夹下的对话
- [ ] 右键菜单: 移动到文件夹 / 重命名 / 标签 / 删除
- [ ] 标签系统: 多选标签（规范咨询/计算验证/材料选择/争议点/已解决/需外部确认）
- [ ] 搜索: 当前项目内全文搜索对话标题和内容

### US-004: 项目内搜索范围控制

**描述**: 在项目内提问时，可以选择搜索范围。

**验收标准**:
- [ ] 三种搜索范围:
  - 仅项目文档（本项目的规格书/计算书/图纸）
  - 仅全局知识库（全量规范+工程知识）
  - 混合：项目文档优先排序，全局补充（默认）
- [ ] 切换方式: 输入框旁的下拉选择或开关
- [ ] 从项目内发起的对话自动带 `project_id` 参数

### US-005: 项目文档管理

**描述**: 我可以上传项目专属文档（规格书/计算书/图纸），系统自动解析和分类。

**验收标准**:
- [ ] 上传: 拖放或点击 → M1 解析（PDF/DOCX/XLSX/DWG/TIFF）
- [ ] 自动专业分类: 根据文件名+解析内容推断专业（结构/轮机/管系/...）
- [ ] 文档列表: 按专业筛选、按时间/名称排序
- [ ] 文档状态: 解析中 → 已解析 → 解析失败（带错误信息）
- [ ] 文档关联: "这份计算书验证了 DNV Pt.3 Ch.3 §6.2"
- [ ] 版本管理: 同名文档重新上传 → 保留旧版本
- [ ] 搜索: 全文搜索文档内容（通过 Meilisearch/ES）

### US-006: 待研究问题看板

**描述**: 我可以创建、分配和追踪项目中的待研究问题。

**验收标准**:
- [ ] 创建问题: 标题 + 描述 + 优先级(高/中/低) + 分配给(可选)
- [ ] 状态: 待研究 → 进行中 → 已解决 → 已关闭
- [ ] 每个问题可关联: 对话 / 文档 / 规范条款
- [ ] "启动 Deep Research"按钮 → 将问题作为研究主题 → 结果自动关联
- [ ] 看板视图: 按状态分列（Kanban）
- [ ] 列表视图: 按优先级排序的表格
- [ ] 进度统计: 已解决 X / 总计 Y

### US-007: 关键结论提取

**描述**: 系统自动从项目对话中提取关键结论，形成项目知识卡片。

**验收标准**:
- [ ] AI 自动识别对话中的"结论""要求""建议"语句
- [ ] 每个结论卡片包含: 一句话摘要 + 引用来源 + 对话链接
- [ ] 人工可标注: 重要 / 已应用 / 需复核
- [ ] 人工可编辑卡片内容
- [ ] 结论可关联到合规矩阵的具体条款

### US-008: 合规追踪（规范满足度矩阵）

**描述**: 我可以按规范章节追踪项目合规状态。

**验收标准**:
- [ ] 项目创建时自动生成适用规范清单（基于船型+入级社+年度）
- [ ] 规范清单按 Part→Chapter→Section 树形展开
- [ ] 每个条款的状态: 🔲 未验证 / ⚠️ 待确认 / ✅ 已验证 / ❌ 不适用
- [ ] 点击条款: 显示相关对话/结论/文档
- [ ] 合规进度条: `[████░░] 28/50 (56%)`
- [ ] 偏差清单: 未满足的条款 + 偏离理由 + 替代方案 + 审批状态

### US-009: 项目归档与案例库

**描述**: 项目完成后归档，形成可检索的案例，供后续项目参考。

**验收标准**:
- [ ] 归档: 项目设为只读，保留全部对话/文档/结论
- [ ] 归档摘要: AI 自动生成（项目概述 + 关键技术点 + 经验教训）
- [ ] 标记为"案例": 优秀项目可标记 → 进入案例库
- [ ] 案例检索: 按船型/技术点/规范/专业搜索
- [ ] 案例引用: 新项目 Deep Research 可引用案例作为参考
- [ ] Phase 4-B 做归档 + 标记案例，Phase 4-C 做案例检索和引用

### US-010: Deep Research 协同

**描述**: Projects 和 Deep Research 无缝集成。

**验收标准**:
- [ ] 从项目待研究问题一键启动 Deep Research → 问题标题作为研究主题
- [ ] Deep Research 报告完成后 → 自动存入项目的对应文件夹
- [ ] 报告中的结论自动提取为项目结论卡片
- [ ] 报告引用的规范自动加入项目规范清单
- [ ] 从 Deep Research 报告页面 → "保存到项目"按钮 → 选择或创建项目

---

## 4. 功能需求

### 4.1 M5 后端 — 项目引擎

**FR-1: 项目 CRUD API**

```
POST   /api/v1/projects                    # 创建项目
GET    /api/v1/projects                    # 列出用户的所有项目
GET    /api/v1/projects/{id}               # 项目详情
PATCH  /api/v1/projects/{id}               # 更新项目
DELETE /api/v1/projects/{id}               # 删除项目
POST   /api/v1/projects/{id}/archive       # 归档项目
```

项目数据模型:

```python
# projects 表 (SQLite, M5 管理)
project_id: str (UUID)
name: str
type: str  # "new_build" | "retrofit" | "maintenance" | "offshore" | "custom"
vessel_type: str | None  # "bulk_carrier" | "lng_carrier" | "tanker" | ...
dwt: int | None
primary_class: str  # "DNV" | "ABS" | "CCS" | ...
secondary_class: str | None
regulation_year: str  # "2025"
phase: str  # "design" | "construction" | "delivery" | "operation"
disciplines: JSON  # ["structural", "machinery", "piping", "electrical"]
description: str | None
owner_id: str  # user_id
team_members: JSON | None  # [{user_id, role: "editor"|"viewer"}]
tags: JSON | None  # ["key_project", "external_review"]
is_archived: bool
created_at: float
updated_at: float
```

**FR-2: 项目对话关联 API**

```
POST   /api/v1/projects/{id}/conversations/{conv_id}     # 关联对话到项目
DELETE /api/v1/projects/{id}/conversations/{conv_id}     # 取消关联
PATCH  /api/v1/projects/{id}/conversations/{conv_id}     # 更新对话在项目中的元数据
GET    /api/v1/projects/{id}/conversations               # 列出项目内对话
```

```python
# project_conversations 表
project_id: str
conversation_id: str
folder_path: str  # "design/structural" → 文件夹路径
tags: JSON | None  # ["规范咨询", "已解决"]
order_index: int  # 排序
linked_since: float
```

**FR-3: 项目文档 API**

```
POST   /api/v1/projects/{id}/documents         # 上传文档 (multipart) → M1 解析
GET    /api/v1/projects/{id}/documents         # 列出项目文档
DELETE /api/v1/projects/{id}/documents/{doc_id} # 删除文档
GET    /api/v1/projects/{id}/documents/{doc_id}/versions  # 文档版本历史
```

```python
# project_documents 表
project_id: str
document_id: str (UUID)
filename: str
discipline: str | None  # auto-detected by M1
parse_status: str  # "pending" | "parsing" | "done" | "error"
parse_result_json: JSON | None  # M1 parse result (markdown, tables, metadata)
file_key: str  # M2 FileStore key
version: int
uploaded_by: str
uploaded_at: float
```

**FR-4: 待研究问题 API**

```
POST   /api/v1/projects/{id}/issues              # 创建问题
GET    /api/v1/projects/{id}/issues              # 列出项目问题
PATCH  /api/v1/projects/{id}/issues/{issue_id}   # 更新状态/分配
DELETE /api/v1/projects/{id}/issues/{issue_id}   # 删除问题
```

```python
# research_issues 表
issue_id: str (UUID)
project_id: str
title: str
description: str | None
status: str  # "pending" | "in_progress" | "resolved" | "closed"
priority: str  # "high" | "medium" | "low"
assignee: str | None  # user_id
related_conversation_id: str | None
related_document_id: str | None
related_regulation: str | None  # "DNV Pt.3 Ch.3 §6.2"
deadline: float | None
created_at: float
updated_at: float
```

**FR-5: 项目结论 API**

```
POST   /api/v1/projects/{id}/conclusions          # 提取/创建结论
GET    /api/v1/projects/{id}/conclusions          # 列出项目结论
PATCH  /api/v1/projects/{id}/conclusions/{c_id}   # 更新结论
```

```python
# project_conclusions 表
conclusion_id: str (UUID)
project_id: str
text: str  # 一句话摘要
detail: str | None  # 详细说明
source_type: str  # "ai_extracted" | "manual" | "deep_research"
source_conversation_id: str | None
source_report_id: str | None  # Deep Research report_id
citation: JSON | None  # [{"society": "DNV", "clause": "Pt.3 Ch.3 §6.2"}]
status: str  # "important" | "applied" | "needs_review" | "general"
tags: JSON | None
created_at: float
```

**FR-6: 合规追踪 API**

```
GET  /api/v1/projects/{id}/compliance              # 项目合规状态
POST /api/v1/projects/{id}/compliance/{clause_id}  # 更新单条合规状态
```

```python
# compliance_items 表
project_id: str
clause_id: str  # "DNV-Pt3-Ch3-§6.2"
society: str
regulation: str  # "Pt.3 Ch.3 §6.2"
title: str  # 条款标题
status: str  # "unverified" | "needs_review" | "verified" | "not_applicable"
verified_by: str | None  # user_id
verified_at: float | None
deviation_note: str | None  # 偏差说明
linked_conclusions: JSON | None  # [conclusion_id, ...]
linked_conversations: JSON | None  # [conversation_id, ...]
```

**FR-7: 项目内搜索（范围控制）**

在 `POST /v1/chat/completions` 中新增参数:

```python
class ChatRequest:
    # ... 现有字段 ...
    project_id: str | None = None
    search_scope: str = "hybrid"  # "project_only" | "global_only" | "hybrid"
```

- `project_only`: 仅从 `project_documents` + `project_conclusions` 检索
- `global_only`: M3 全量检索（与无项目时相同）
- `hybrid` (默认): 项目结果优先排序，全局结果补充

### 4.2 M5 后端 — 项目辅助功能

**FR-8: 项目仪表板 API**

```
GET /api/v1/projects/{id}/dashboard
  → 项目进度统计 (对话数/文档数/问题数/合规进度)
  → 最近活动时间线 (最近 10 条操作)
  → 高优先级待办 (到期问题 + 未验证条款)
  → 合规风险告警 (低完成度的 Part 章节)
```

**FR-9: 项目总结报告生成**

Phase 4-B 提供 Markdown 版本（Phase 4-C PDF/Excel）:

```python
def generate_project_report(project_id: str) -> str:
    """生成项目总结报告 (Markdown)"""
    return f"""# {project.name} — Project Summary

## Project Info
- Vessel Type: {project.vessel_type} | Class: {project.primary_class}
- Phase: {project.phase} | Year: {project.regulation_year}

## Compliance Status
- Overall: {compliance.progress}%
- Verified: {compliance.verified}/{compliance.total} clauses
- Deviations: {compliance.deviation_count}

## Key Conclusions (Top 10)
{format_conclusions(conclusions[:10])}

## Open Issues ({len(issues)})
{format_issues(issues)}

## Compliance Matrix (Major Sections)
{format_compliance_matrix(compliance.major_items)}
"""
```

**FR-10: 自动文件夹分类**

对话创建时根据内容自动推断文件夹（用户可手动调整）:

```python
def classify_conversation(content: str, project) -> str:
    discipline_map = {
        "焊接": "焊接", "WPS": "焊接", "结构": "结构",
        "强度": "结构", "管系": "管系", "泵": "管系",
        "电气": "电气", "电缆": "电气"
    }
    discipline = next((v for k, v in discipline_map.items() if k in content), "通用")
    phase = "设计阶段" if any(w in content for w in ["设计","计算"]) else project.phase
    return f"{phase}/{discipline}"
```

**FR-11: 内置规范模板库**

项目创建时根据船型+入级社自动填充规范清单（硬编码模板）:

```python
REGULATION_TEMPLATES = {
    "bulk_carrier_dnv": [
        "DNV Pt.1 Ch.1", "DNV Pt.3 Ch.4", "DNV Pt.5 Ch.5",
        "IACS UR S11", "IACS UR S21", "MARPOL Annex VI",
    ],
    "lng_carrier_dnv": [
        "DNV Pt.5 Ch.5", "DNV Pt.5 Ch.6", "IGC Code", "IGF Code",
    ],
    # ... 更多模板
}
```

### 4.3 M6 前端 — 项目界面

**FR-12: 项目列表页**

代替当前的 mock `projects/page.tsx`:
- 卡片网格: 每个项目 1 张卡片（名称/类型/阶段/最后活跃时间/完成度）
- [+ 新建项目] 按钮 → 创建对话框（US-001 的模板选择）
- 搜索: 按名称过滤 / 按类型/阶段/状态筛选

**FR-13: 项目详情页 — Overview 仪表板**

```
┌─────────────────────────────────────────────────┐
│ ← 返回    Ballard 82000 DWT BC    [⚙设置] [归档] │
│ 设计阶段 | DNV 2025 | 结构+轮机+管系              │
├─────────────────────────────────────────────────┤
│ 项目进度统计                                     │
│ ├─ 💬 对话: 23 条                               │
│ ├─ 📄 文档: 15 份 (3 份待解析)                   │
│ ├─ ❓ 问题: 8 个 (2 个高优)                      │
│ └─ ✅ 合规: 56% (28/50 已验证)                   │
├─────────────────────────────────────────────────┤
│ 最近活动 (Timeline)                              │
│ • 2h ago: 新建对话 "舱口盖强度计算"               │
│ • 昨天: 上传文档 WPS-001                         │
│ • 2d ago: 解决问题 "材料选择"                     │
├─────────────────────────────────────────────────┤
│ ⚠️ 待办 + 合规风险                               │
│ • 高优问题 2 个 | 即将到期 3 个                   │
│ • DNV Pt.5 Ch.5 §7.3 未验证 (高优)               │
│ • 偏差项 2 个待审批                              │
└─────────────────────────────────────────────────┘
```

**FR-14: 项目详情页 — 文件夹 + 对话面板**

```
┌────────────┬────────────────┬───────────────────┐
│ 文件夹树    │  对话/文档列表  │  右侧详情面板      │
│ ▼ 设计阶段  │  [+] 新建对话  │  (选中对话内容)    │
│  ├ 结构     │  [🔍 搜索]    │                   │
│  ├ 轮机     │  📄 舱口盖强度  │                   │
│  └ 管系     │  📄 焊接预热    │                   │
│ ▼ 建造阶段  │  ...           │                   │
├────────────┴────────────────┴───────────────────┤
│ [Overview] [对话] [问题看板] [合规] [文档] [设置] │
└─────────────────────────────────────────────────┘
```

**FR-15: 项目内对话**

- 在项目详情页点击"新建对话" → 在右侧打开聊天面板
- 聊天面板自动携带 `project_id` → M5 的 `search_scope`
- 对话保存后自动出现在当前文件夹中
- 支持拖放对话到其他文件夹

**FR-16: 文档管理面板**

- 文档列表: 表格（文件名/专业/状态/上传日期/版本）
- 拖放上传区
- 点击文档: 预览解析后的 Markdown + 元数据
- 搜索: 全文搜索文档内容

**FR-17: 合规追踪面板**

- 规范树: Part→Chapter→Section 三层展开
- 每条: 状态图标 + 标题 + 关联对话数
- 点击: 展开详情（关联对话/结论/偏差说明）
- 进度条: 整体 + 按 Part 拆分
- 偏差清单: 独立的表格视图

**FR-18: 待研究问题看板**

- 看板视图: 按状态分列
- 问题卡片: 标题/优先级/分配给/截止日期
- 点击: 展开详情 + [启动 Deep Research]按钮
- 拖放改变状态

### 4.4 与 Deep Research 的知识闭环

```
单个项目的闭环:
  遇到问题 → Deep Research (4-A) → 报告存入项目
  → 结论提取 → 关联合规矩阵 → 项目归档 → 标记为案例

组织级知识积累:
  多个项目归档 → 形成案例库 → Deep Research 可检索案例
  → 新项目引用历史结论 → 知识持续积累 → 组织能力提升
```

详见 [Deep Research PRD §9](./prd-deep-research-2026-06-09.md)。

---

## 5. 技术设计

### 5.1 模块关系

```
M6 (User Portal)
  ├── 项目 CRUD → M8 → M5 project APIs
  ├── 对话关联 → M5 conversation APIs + project_id
  ├── 文档上传 → M8 → M1 → M2
  └── 合规追踪 → M5 compliance APIs

M5 (QA Engine) — 新增 project 模块
  m5_qa/project/
  ├── __init__.py
  ├── manager.py          # FR-1: CRUD + SQLite tables
  ├── conversations.py    # FR-2: 对话关联
  ├── documents.py        # FR-3: 文档上传 → M1 调用
  ├── issues.py           # FR-4: 待研究问题
  ├── conclusions.py      # FR-5: 结论提取 (AI + 手动)
  ├── compliance.py       # FR-6: 合规追踪
  └── search_scope.py     # FR-7: 项目范围搜索

M5 SQLite 新增表:
  projects, project_conversations, project_documents,
  research_issues, project_conclusions, compliance_items
```

### 5.2 M8 路由扩展

```
# Projects
GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{id}
PATCH  /api/v1/projects/{id}
DELETE /api/v1/projects/{id}
POST   /api/v1/projects/{id}/archive

# Conversations in project
POST   /api/v1/projects/{id}/conversations/{conv_id}
DELETE /api/v1/projects/{id}/conversations/{conv_id}
GET    /api/v1/projects/{id}/conversations

# Documents in project
POST   /api/v1/projects/{id}/documents
GET    /api/v1/projects/{id}/documents

# Issues in project
POST   /api/v1/projects/{id}/issues
GET    /api/v1/projects/{id}/issues
PATCH  /api/v1/projects/{id}/issues/{issue_id}

# Conclusions
GET    /api/v1/projects/{id}/conclusions
POST   /api/v1/projects/{id}/conclusions

# Compliance
GET    /api/v1/projects/{id}/compliance
POST   /api/v1/projects/{id}/compliance/{clause_id}
```

### 5.3 Deep Research ↔ Projects 集成

两个功能的双向集成通过以下 API 调用实现:

**Deep Research → Project**:
```
POST /api/v1/projects/{id}/conclusions
  Body: {
    "source_type": "deep_research",
    "source_report_id": "rpt-xxx",
    "text": "DNV 要求舱口盖强度 ≥ 1.5× 设计载荷",
    "citation": [{"society": "DNV", "clause": "Pt.3 Ch.3 §6.2"}]
  }
```

**Project → Deep Research**:
```
GET /api/v1/projects/{id}/issues/{issue_id}
  → 前端点击"启动 Deep Research"
  → 打开 Deep Research 页面，传递 issue.title 作为研究主题
  → 研究完成 → POST 结论到项目
```

### 5.4 数据流

```
创建项目
  → M5 project_manager.create() → SQLite INSERT
  → M5 compliance.build_initial_matrix() → 基于船型+入级社生成条款清单

项目内对话
  → M6 chat panel (带 project_id)
  → M8 → M5 chat() (FR-7 search_scope)
  → 检索优先项目文档 → 生成回答
  → 保存对话 → project_conversations INSERT

文档上传
  → M6 拖放 → M8 /api/v1/projects/{id}/documents
  → M5 → M1 /parse (异步) → 解析结果存入 M2
  → project_documents INSERT + parse_status 更新
```

---

## 6. 非目标（Phase 4-B 不做）

- ❌ 多人实时协作（@提及、讨论串、通知）— Phase 4-C
- ❌ 案例库全文检索和 AI 引用 — Phase 4-C（Phase 4-B 做归档+标记案例）
- ❌ PDF/Excel 合规报告导出 — Phase 4-C
- ❌ 角色级权限系统 — Phase 4-C（Phase 4-B 仅 owner 可编辑）
- ❌ AI 自动生成项目模板（根据船型推断规范清单）— 规范清单手动维护或硬编码
- ❌ 对话内容自动标记（AI 自动建议标签）— Phase 4-C
- ❌ 项目间链接（"本项目参考了项目 X 的结论"）— Phase 4-C

---

## 7. 非功能需求

| 需求 | 目标 | 测量方式 |
|------|------|---------|
| 项目列表加载 | < 500ms | 计时 |
| 文档上传+Parsing | UI 立即返回，后台异步解析 | 测试 |
| 文件夹树展开 | < 200ms（客户端渲染） | 计时 |
| 合规矩阵加载 | < 1s（最多 500 条） | 计时 |
| 对话搜索 | < 500ms (Meilisearch) | 计时 |

---

## 8. 成功指标

- **S1**: 用户创建项目后重复使用率 > 60%（不是一次性创建就废弃）
- **S2**: 项目内对话平均 ≥ 5 条（说明对话被有效组织）
- **S3**: 每个项目平均上传 ≥ 3 份文档
- **S4**: 合规矩阵使用率 > 30%（至少 30% 的项目使用合规追踪功能）

---

## 9. 与 Deep Research 的集成边界

| 功能 | Deep Research (4-A) | Projects (4-B) | 集成方式 |
|------|-------------------|----------------|---------|
| 研究启动 | ✅ 从 Sidebar/输入框 | ✅ 从问题卡片 | Projects → 传递 issue 标题 |
| 研究执行 | ✅ Planner+Agent+分析 | — | 独立执行 |
| 报告生成 | ✅ SSE 流式 | — | 独立执行 |
| 报告存储 | ⚠️ 仅对话中 | ✅ 存入项目文件夹 | Deep Research → Projects |
| 结论提取 | — | ✅ AI 自动+手动 | Projects 调用 M5 结论提取 |
| 合规追踪 | — | ✅ 规范满足度矩阵 | 结论关联到条款 |
| 案例库 | — | ✅ 归档+标记 | 项目完成后归档 |

---

## 11. 任务分解预览

| Task | 内容 | 模块 |
|------|------|------|
| 00105-01 | `manager.py`: 项目 CRUD + SQLite 建表 + M8 路由 | M5/M8 |
| 00105-02 | `conversations.py`: 对话关联 + 文件夹 + 标签 + 自动分类 (FR-10) | M5 |
| 00105-03 | `documents.py`: 文档上传 + M1 集成 + 版本管理 | M5/M1 |
| 00105-04 | `issues.py` + `conclusions.py`: 待研究问题 + 结论提取 | M5 |
| 00105-05 | `compliance.py`: 合规矩阵 + 偏差清单 + 规范模板库 (FR-11) | M5 |
| 00105-06 | `search_scope.py`: 项目范围搜索 (混合排序) | M5 |
| 00105-07 | M6 项目列表 + 仪表板 Overview (FR-13) | M6 |
| 00105-08 | M6 文件夹树 + 对话面板 + 文档管理 | M6 |
| 00105-09 | M6 问题看板 + 合规面板 + Deep Research 入口 | M6 |
| 00105-10 | 项目总结报告生成 (FR-9 Markdown) | M5 |
| 00105-11 | 测试 + 集成验证（含 Phase 4-A 双向集成测试） | M5/M6 |

**依赖关系**:
```
01 → 02 → 03 → 04 → 05 → 06 → 10
                                    ↓
                               07 → 08 → 09 → 11
```
(01-06,10 M5 后端可先做，07-09 M6 前端依赖后端 API)
