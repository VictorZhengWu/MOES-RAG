"""
Prompt templates for LLM-based entity/relation extraction (M4 Task 00080-03).

WHAT:
  Contains English and Chinese prompt templates that instruct the LLM how to
  extract entities and relations from marine engineering document text.
  Both templates specify entity types, relation types, and output format.

WHY:
  Centralizing prompts in a separate module allows:
    - Easy updates to the prompt wording without touching extraction logic.
    - Bilingual support (EN/CN) for processing documents in both languages.
    - Clear separation of concerns: prompts are configuration, not logic.
"""

# ---------------------------------------------------------------------------
# English prompt template
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT_EN = """\
Extract entities and relations from the following marine engineering document text.

## Entity Types
- regulation_clause: normative rule (e.g., "DNV Pt.4 Ch.3 S2.1")
- steel_grade: steel material grade (e.g., "EH36", "AH32")
- equipment: specific equipment model (e.g., "DNV Type-A valve")
- system_type: ship system category (e.g., "bilge system", "ballast system")
- parameter: quantitative requirement (e.g., "preheat temperature 150C", "plate thickness less than 50mm")
- ship_type: vessel classification (e.g., "bulk carrier", "oil tanker")

## Relation Types
- requires: entity A mandates entity B
- applies_to: entity A is applicable to entity B
- prohibits: entity A forbids entity B
- replaces: entity A supersedes entity B
- references: entity A cites entity B
- constrains: entity A limits value of entity B

## Output Format
Return ONLY valid JSON (no markdown fences, no explanations):
{{
  "entities": [
    {{"id": "e1", "name": "...", "type": "steel_grade", "properties": {{...}}}},
    ...
  ],
  "relations": [
    {{"source": "e1", "target": "e2", "type": "constrains", "properties": {{"condition": "t less than 50mm"}}}},
    ...
  ]
}}

## Text
{document_text}"""

# ---------------------------------------------------------------------------
# Chinese prompt template
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT_CN = """\
从以下海洋工程文档文本中提取实体和关系。

## 实体类型
- regulation_clause: 规范性规则（例如："DNV Pt.4 Ch.3 S2.1"）
- steel_grade: 钢材等级（例如："EH36", "AH32"）
- equipment: 特定设备型号（例如："DNV Type-A 阀门"）
- system_type: 船舶系统类别（例如："舱底系统", "压载系统"）
- parameter: 定量要求（例如："预热温度 150C", "板厚小于 50mm"）
- ship_type: 船舶分类（例如："散货船", "油轮"）

## 关系类型
- requires: 实体A强制要求实体B
- applies_to: 实体A适用于实体B
- prohibits: 实体A禁止实体B
- replaces: 实体A取代实体B
- references: 实体A引用实体B
- constrains: 实体A限制实体B的值

## 输出格式
只返回有效的JSON（不要markdown代码块，不要解释）：
{{
  "entities": [
    {{"id": "e1", "name": "...", "type": "steel_grade", "properties": {{...}}}},
    ...
  ],
  "relations": [
    {{"source": "e1", "target": "e2", "type": "constrains", "properties": {{"condition": "t 小于 50mm"}}}},
    ...
  ]
}}

## 文本
{document_text}"""
