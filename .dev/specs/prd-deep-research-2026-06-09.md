# PRD: Deep Research — 海事工程多步研究 Agent

> **版本**: v1.0 | **日期**: 2026-06-09 | **父功能**: Phase 4-A
> **依赖**: M3 (Retrieval), M4 (Knowledge Graph), M5 (QA Engine), M6 (User Portal)

---

## 1. 概述

### 1.1 问题

当前系统一问一答模式无法处理海洋工程的复杂研究需求：

- **多规范交叉验证**: 同一问题需查阅 DNV、ABS、CCS、LR 等至少 3 个船级社规范
- **规范层级依赖**: 一条核心条款可能被 5 个其他章节引用，形成引用链
- **版本追溯**: 规范每年修订，工程师需知道"2025 版为什么把系数从 0.85 改为 0.80"
- **跨学科整合**: 结构设计 → 材料选择 → 焊接工艺 → NDT 检测 → 每个环节有自己的规范要求
- **合规验证闭环**: 设计完成后需逐条证明满足规范 → 需要完整的引用追溯链

普通问答无法处理"三者以上"的复杂度的查询。Deep Research 解决这个问题。

### 1.2 核心价值

> **Deep Research 将系统从"问答工具"升级为"工程合规研究引擎"**

| 能力 | 普通 Q&A | Deep Research |
|------|---------|---------------|
| 单问题回答 | ✅ | ✅ |
| 多规范交叉对比 | ❌ | ✅ 跨船级社对比矩阵 |
| 规范引用链追溯 | ❌ | ✅ M4 图遍历 |
| 版本演进分析 | ❌ | ✅ 规则引擎 + AI |
| 合规告警 | ❌ | ✅ 冲突检测 |
| 结构化报告输出 | ❌ | ✅ 7 节专业报告 |

---

## 2. 目标

- **G1**: 处理"3 个以上规范交叉"的复杂问题，生成结构化研究报告
- **G2**: 自动分解问题为子研究任务，并行检索多个知识源
- **G3**: 检测规范冲突并生成对比矩阵（DNV vs ABS vs CCS）
- **G4**: 每个结论可追溯到具体规范条款 + 原文摘录
- **G5**: 研究进度实时可见，用户可干预（调整研究计划、深入某个子问题）
- **G6**: Phase 4-A 仅实现核心流程：Planner + 2 Agent（规范 + Web）+ 报告生成

---

## 3. 用户故事

### US-001: 智能触发建议

**描述**: 作为工程师，当我提出复杂查询时（涉及 3+ 规范或含"对比""全面分析"关键词），系统主动建议升级到 Deep Research，并提供预估研究范围。

**验收标准**:
- [ ] 问题复杂度自动评分：多规范 (3+) + 关键词 + 跨学科 + 版本查询
- [ ] 分数 ≥ 阈值时在回答末尾显示"🔬 Deep Research"按钮
- [ ] 显示预估：将检索 N 个规范 / M 个知识域 / 预计耗时 T 秒
- [ ] 用户可拒绝，继续普通 Q&A
- [ ] M6: 流式回答完成后展示升级建议

### US-002: 手动触发

**描述**: 作为工程师，我可以通过 Sidebar "Deep Research"按钮或输入框旁的 🔬 图标，手动启动深度研究。

**验收标准**:
- [ ] Sidebar "🧠 Deep Research"按钮 → 打开研究输入界面
- [ ] 输入框旁边 "🔬" 图标 → 将当前输入作为研究问题
- [ ] 两种方式均进入 Phase 1（研究规划）流程

### US-003: 研究规划展示

**描述**: 启动 Deep Research 后，展示 AI 制定的研究计划（子问题分解 + 检索策略），我可以在执行前调整。

**验收标准**:
- [ ] Phase 1 展示:
  - 子问题列表（每个 1 句话描述）
  - 每子问题对应的检索策略（规范/Web/标准/案例）
  - 预计总耗时
- [ ] 每个子问题可勾选取消（不检索）
- [ ] 用户点击"开始研究"进入 Phase 2
- [ ] 研究计划保存到对话历史中

### US-004: 多源并行检索

**描述**: 研究执行期间，系统并行检索多个知识源，实时展示进度。

**验收标准**:
- [ ] Phase 2 并行启动 2 个 Agent:
  - Agent_规范: M3 dense+sparse 双路 + M4 图遍历
  - Agent_Web: DuckDuckGo/Tavily Web Search
- [ ] 进度条实时更新: `[████░░] 规范检索完成 | Web 检索中...`
- [ ] 检索结果缓存在对话中，用户可展开查看每个 Agent 的原始结果
- [ ] 单个 Agent 失败不影响其他 Agent（graceful degradation）

### US-005: 交叉分析

**描述**: 检索完成后，AI 对结果进行交叉分析——检测规范冲突、分析版本差异、关联历史案例。

**验收标准**:
- [ ] Phase 3 执行:
  - 规范冲突检测: ≥2 个规范条款对同一要求给出不同数值 → 标记告警
  - 版本差异: 不同年份规范对比，标注变化原因（如能找到）
  - 案例关联: 如 Web 搜到事故报告 → 关联到违反的具体条款
- [ ] 分析结果展示为结构化列表（每个发现 1 个卡片）
- [ ] 用户可在分析阶段暂停并查看中间结果

### US-006: 结构化报告生成

**描述**: 所有分析完成后，生成 7 节专业报告。

**验收标准**:
- [ ] 报告包含:
  - §1 执行摘要（1 页，研究结论 + 关键发现）
  - §2 规范对比矩阵（表格: 条款 | DNV | ABS | CCS | LR）
  - §3 技术方案建议（推荐方案/替代方案/不推荐方案）
  - §4 检验清单（设计阶段/建造阶段/运营阶段审查点）
  - §5 风险矩阵（风险项 | 概率 | 后果 | 缓解措施）
  - §6 引用追溯（每条结论点击可查规范原文）
  - §7 疑问与局限（AI 不确定的部分 + 建议人工确认）
- [ ] 报告支持 Markdown 渲染 + 可折叠展开
- [ ] 研究过程 + 报告保存为对话的一部分

### US-007: 交互式深入

**描述**: 生成报告后，我可以点击任意结论深入查看推导过程，或提出质疑触发重新分析。

**验收标准**:
- [ ] 点击结论 → 展开面板显示: 原始检索结果 + 推理步骤 + 引用条款原文
- [ ] "质疑"按钮 → 输入疑点 → AI 重新审视相关证据 → 更新该结论
- [ ] 质疑过程追加到报告中（标注"人工复核"）

### US-008: 研究导出

**描述**: 我可以将研究报告保存到项目、导出为文档、或分享链接。

**验收标准**:
- [ ] "保存到项目"按钮 → 如已有项目则选择，否则创建新项目（US for Projects）
- [ ] "复制分享链接" → 生成可分享的对话链接
- [ ] Phase 4-A 暂不做 PDF/Excel 导出（Phase 4-C）

---

## 4. 功能需求

### 4.1 M5 后端 — 研究引擎

**FR-1: 问题复杂度评分**
- 输入: 用户查询文本
- 评分规则:
  - 识别规范名称: DNV/ABS/CCS/LR/BV/RINA/NK/KR/IACS/IMO → 每个 +1 分
  - 识别关键词: "对比""总结""全面分析""版本""演进""事故" → 每个 +2 分
  - 识别跨章节: 正则匹配 "Pt\.\d+" 或 "Ch\.\d+" 或 "§\s*\d" → 每个 +1 分
  - 识别跨学科: 匹配钢级/材料/焊接/NDT/疲劳等关键词 → 每个 +1 分
- 输出: 0-10 分，≥5 分建议 Deep Research

**FR-2: 研究规划（Planner Agent）**
- 调用 LLM (`deepseek-chat`) 进行问题分解
- Prompt 要求输出 JSON:
  ```json
  {
    "sub_questions": [
      {
        "id": 1,
        "question": "DNV Pt.3 Ch.3 §6 舱口盖强度要求",
        "search_strategy": ["regulations", "web"],
        "search_query": "DNV 2025 hatch cover strength Pt.3 Ch.3 §6"
      }
    ],
    "estimated_runtime_seconds": 45
  }
  ```
- 验证: 至少 1 个子问题，至多 8 个
- 利用 M4 KG 的 `cross_reference()` 发现跨规范关联，注入子问题

**FR-3: 并行检索（Retrieval Agents）**

Agent_规范: M3 dense + sparse 双路检索 → M4 图遍历（1-hop） → RRF 融合去重

Agent_Web: DuckDuckGo / Tavily → 每子问题 top 5 结果

- 2 个 Agent 通过 `asyncio.gather` 并行执行
- 单个 Agent 异常不阻断其他 Agent（graceful degradation）
- 检索结果写入内存缓存: `{query_hash: results}` TTL=1h

**FR-4: 交叉分析（Analysis Agent）**
- 调用 LLM 分析检索结果，输出结构化 JSON:
  ```json
  {
    "conflicts": [
      {
        "clause_a": "DNV Pt.3 Ch.3 §6.2 (strength ≥ 1.5× load)",
        "clause_b": "ABS Pt.5B §3-8 (strength ≥ 1.67× load)",
        "severity": "warning",
        "recommendation": "ABS requires 11% higher strength. If dual-class, use ABS."
      }
    ],
    "version_diffs": [...],
    "case_correlations": [...],
    "key_findings": [...]
  }
  ```
- M4 KG `cross_reference()` 用于发现规范间的 explicit 引用关系
- LLM 用于发现 implicit 冲突（数值差异、范围差异）

**FR-5: 报告生成（Report Agent）**
- 调用 LLM，输入: 原始问题 + 检索结果 + 分析结果 + 报告模板
- 输出: 7 节 Markdown 报告
- 每节标注生成方式: "AI 生成" 或 "基于规范原文" 或 "需人工确认"
- 引用格式: `[规范-1] DNV Pt.3 Ch.3 §6.2, 2025 edition`

**FR-6: 流式进度通知**
- `POST /api/v1/agent/research` 返回 SSE 事件流:
  - `event: progress` — 阶段变化 + 进度百分比
  - `event: report_chunk` — 报告流式渲染
  - `event: done` — 研究完成 + 完整报告

**FR-7: 质疑与深入**
- `POST /api/v1/agent/research/{report_id}/question`
  - Body: `{"conclusion_id": 3, "question": "为什么推荐 ABS 的 1.67 而不是 DNV 的 1.50？"}`
  - 返回: 追加的推导段落 + 更新后的报告

### 4.2 M6 前端 — 研究界面

**FR-8: 研究入口**
- Sidebar "🧠 Deep Research" 按钮 → 切换到研究模式 → 显示研究输入界面

**FR-9: 研究计划展示 (Phase 1)**
- 卡片列表: 每个子问题 1 个卡片（标题 + 检索策略标签）
- 复选框: 取消不需要的子问题
- [开始研究] 按钮 + 预计耗时
- 阶段指示器: Phase 1 → 2 → 3 → 4

**FR-10: 检索进度 (Phase 2)**
- 并行 Agent 卡片: 每个有独立进度
- 检索结果可展开（原始结果预览）

**FR-11: 报告渲染 (Phase 3-4)**
- 7 节报告 → Markdown 渲染（复用 message-bubble）
- §2 对比矩阵 → 表格组件（横向滚动）
- §5 风险矩阵 → 表格 + 颜色编码（红/黄/绿）
- §6 引用 → 可点击，展开规范原文

**FR-12: 交互操作**
- [保存到项目] → 按钮（Phase 4-A 暂存提示）
- [复制分享链接] → 复制 URL
- [质疑] → 输入框 + 重新分析

---

## 5. 技术设计

### 5.1 模块关系

```
M6 → M8 → POST /api/v1/agent/research (SSE) → M5

M5 新增 research/ 模块:
├── complexity.py         # FR-1: 问题复杂度评分
├── planner.py            # FR-2: LLM 问题分解 + KG 关联
├── agents/
│   ├── regulations.py    # FR-3: Agent_规范 (M3+M4)
│   └── web.py            # FR-3: Agent_Web
├── analyzer.py           # FR-4: 交叉分析 + 冲突检测
├── report_generator.py   # FR-5: 7 节报告生成
└── progress.py           # FR-6: SSE 进度事件
```

### 5.2 M5 API 扩展

```
POST /api/v1/agent/research
  Body: {"query": "...", "sub_questions": [...], "stream": true}
  Response: text/event-stream (SSE)

POST /api/v1/agent/research/{report_id}/question
  Body: {"conclusion_id": ..., "question": "..."}
  Response: {"report_id": "...", "updated_section": "..."}
```

### 5.3 复杂度检测集成

在 M5 `engine.py` 的 `chat()` 流程末尾，流式回答完成后：

```python
if not request.disable_suggestions:
    score = complexity_score(request.messages[-1].content)
    if score >= 5:
        response.suggestions.append({
            "type": "deep_research",
            "message": "涉及 3+ 船级社规范的复杂问题，建议使用 Deep Research",
            "action": "/api/v1/agent/research",
        })
```

---

## 6. 非目标（Phase 4-A 不做）

- ❌ Agent_标准 (ISO/ASTM/API/EN) — Phase 4-C
- ❌ Agent_案例 (事故数据库) — Phase 4-C
- ❌ Agent_法规 (IMO 通函) — Phase 4-C
- ❌ PDF/Excel 导出 — Phase 4-C
- ❌ 保存报告到 Projects — Phase 4-B
- ❌ 版本演进自动分析（需规范 changelog 数据） — Phase 4-C
- ❌ 规范对比矩阵自动生成（需 entity linking） — Phase 4-A 用 LLM 近似

---

## 7. 非功能需求

| 需求 | 目标 | 测量方式 |
|------|------|---------|
| 响应延迟 | 完整研究 < 90s | 计时 |
| 并行检索 | 2 Agent 真并行 | 日志 |
| Graceful degradation | 单 Agent 失败不崩溃 | 测试 |
| 缓存 | 相同问题 1h 内复用 | 测试 |
| 引用完整性 | 每个结论 ≥1 规范引用 | 人工审查 |
| 报告可读性 | 非技术人员能读懂 §1 | 人工审查 |

---

## 8. 成功指标

- **S1**: 用户对复杂问题选择 Deep Research 的比例 > 20%（vs 普通 Q&A）
- **S2**: Deep Research 报告中的引用准确率 > 90%
- **S3**: 完整研究流程 < 90 秒（不含排队）
- **S4**: 报告的 §2 对比矩阵包含至少 3 列（DNV/ABS/CCS）

---

## 9. 任务分解预览

| Task | 内容 | 模块 |
|------|------|------|
| 00104-01 | `complexity.py`: 问题复杂度评分 | M5 |
| 00104-02 | `planner.py`: LLM 问题分解 + M4 KG 关联 | M5 |
| 00104-03 | `agents/regulations.py`: Agent_规范 (M3+M4) | M5 |
| 00104-04 | `agents/web.py`: Agent_Web (DuckDuckGo/Tavily) | M5 |
| 00104-05 | `analyzer.py`: 交叉分析 + 冲突检测 | M5 |
| 00104-06 | `report_generator.py`: 7 节报告生成 | M5 |
| 00104-07 | `progress.py`: SSE 流式进度 + M8 路由 | M5/M8 |
| 00104-08 | M6 研究界面 (入口 + 进度 + 报告渲染) | M6 |
| 00104-09 | 测试 + 集成验证 | M5/M6 |

**依赖关系**: 01 → 02 → 03/04 → 05 → 06 → 07 → 08 → 09
（03/04 可并行，其他串行）

---

## 10. 开放问题

1. **复杂度评分阈值**: 5 分是否合适？需要 alpha 反馈调整
2. **报告模板**: 7 节是否涵盖所有海事场景？可能需要新造船/改造船/审计等子模板
3. **LLM 选择**: Planner + Analyzer + Reporter 是否共用同一个 LLM backend？
4. **引用格式**: 海事行业是否有标准引用格式？目前用 `DNV Pt.3 Ch.3 §6.2`
5. **Web Search Agent**: Phase 4-A 是否包含，还是留到 Phase 4-C？
