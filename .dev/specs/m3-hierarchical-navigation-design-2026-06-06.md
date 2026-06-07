# Phase 3 — 层级化导航式 RAG

> **日期**：2026-06-06 | **RAG 技术**：层级化/导航式 RAG (#4)
> **改动范围**：M3（pipeline.py, query_analyzer.py） | **改动量**：小

---

## 1. 背景

船级社规范具有天然树形结构：

```
DNV Pt.4 Ch.3 §2.1 — 焊接预热要求
     │     │     │
    Part  Ch.  Section
```

当前 M3 把 `chapter_section` 作为 filter 传入 ChromaDB，但只做一次检索——如果 filter 太精确导致 0 结果，直接返回空，不尝试更宽的范围。

## 2. 设计：刚性回退

用户问"Ch.3 §2.1 焊接预热"时：

```
尝试 1: filter chapter_section="Pt.4 Ch.3 §2.1" → 检索 →
         结果 ≥ min_results (3)?  → YES: 返回
                                 → NO: 回退到 Level 2

尝试 2: filter chapter_section="Pt.4 Ch.3" → 检索 →
         结果 ≥ 3?  → YES: 返回
                    → NO: 回退到 Level 3

尝试 3: no chapter_section filter → 检索 → 返回（永不空）
```

回退函数 `_strip_section(chapter_section)`:
```
"Pt.4 Ch.3 §2.1" → "Pt.4 Ch.3"
"Pt.4 Ch.3"      → "Pt.4"
"Pt.4"           → None (remove filter entirely)
```

## 3. 改动清单

| 文件 | 改动 |
|------|------|
| `m3_retrieval/core/pipeline.py` | `_build_filters` 返回三层 filter 列表而非单个 |
| `m3_retrieval/core/pipeline.py` | `retrieve()` 中加回退循环 |
| `m3_retrieval/stages/query_analyzer.py` | 加 `_strip_section()` 辅助函数 |
| `m3_retrieval/tests/test_pipeline.py` | 加 3 个回退测试 |

## 4. 回退算法

```python
HIERARCHY_FALLBACK_LEVELS = [
    "full",     # "Pt.4 Ch.3 §2.1"
    "chapter",  # "Pt.4 Ch.3"
    "part",     # "Pt.4"  
    None,       # remove filter
]

async def retrieve_with_fallback(request, pipeline):
    """Retrieve with tiered chapter filter."""
    qa = analyze_query(request.query)

    if not qa.chapter_section:
        # No chapter info → single retrieval
        return await pipeline._execute(request, qa, filters=None)

    levels = _build_fallback_filters(qa.chapter_section)

    for level_filter in levels:
        result = await pipeline._execute(request, qa, filters=level_filter)
        if len(result) >= MIN_RESULTS:
            return result

    return result  # Last resort (no filter)
```

## 5. 测试

1. `test_full_match_enough_results` — "Pt.4 Ch.3 §2.1" 有足够结果 → 不回退
2. `test_fallback_to_chapter` — §2.1 无结果 → 回退到 Ch.3
3. `test_fallback_to_none` — 所有 level 无结果 → 全文字段

---

*设计结束。开始实现。*
