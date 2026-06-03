"""
Tests for the LLM-based entity/relation extractor (M4 Task 00080-03).

Tests cover:
  1. Prompt template rendering with document text
  2. Normalization of clean JSON output
  3. Normalization of markdown-wrapped JSON
  4. Normalization of garbled output with regex extraction
  5. Normalization of invalid/unparseable output
  6. Token-aware batching behavior

WHAT: Validates that the LLMExtractor correctly formats prompts, parses LLM
      responses with three-layer normalization, and batches chunks by token
      count rather than a fixed count.
WHY: LLM output is inherently unstable — it may return clean JSON, markdown-
     wrapped JSON, or explanatory text with embedded JSON. The extractor must
     handle all cases robustly. Token-aware batching prevents context overflow.
"""

from unittest.mock import AsyncMock, patch

import pytest

from contracts.document import Chunk, DocumentMetadata
from contracts.knowledge_graph import Entity, Relation
from m4_kg.core.config import ExtractionConfig, LLMBackend
from m4_kg.extraction.llm_extractor import LLMExtractor
from m4_kg.extraction.prompt_templates import EXTRACTION_PROMPT_EN


# ---------------------------------------------------------------------------
# Mock LLM response helper
# ---------------------------------------------------------------------------

_MOCK_JSON = """\
{
  "entities": [
    {"id": "e1", "name": "EH36", "type": "steel_grade", "properties": {"yield_strength": "355MPa"}},
    {"id": "e2", "name": "Pt.4 Ch.3", "type": "regulation_clause", "properties": {"society": "DNV"}}
  ],
  "relations": [
    {"source": "e1", "target": "e2", "type": "constrains", "properties": {"condition": "t <= 50mm"}}
  ]
}"""


def _make_mock_llm_response(
    response_text: str = _MOCK_JSON,
) -> AsyncMock:
    """Create an AsyncMock that returns a simulated LLM chat completion.

    WHAT: Builds a mock AsyncOpenAI client whose chat.completions.create
          method returns the given text as the LLM response.
    WHY: Tests must not depend on real LLM APIs. This mock lets us control
         exactly what the "LLM" returns for each test case.
    """
    mock_message = AsyncMock()
    mock_message.content = response_text

    mock_choice = AsyncMock()
    mock_choice.message = mock_message

    mock_completion = AsyncMock()
    mock_completion.choices = [mock_choice]

    mock_create = AsyncMock(return_value=mock_completion)

    mock_chat = AsyncMock()
    mock_chat.completions.create = mock_create

    mock_client = AsyncMock()
    mock_client.chat = mock_chat

    return mock_client


# ---------------------------------------------------------------------------
# Helper to build test Chunk objects
# ---------------------------------------------------------------------------

def _make_chunk(
    chunk_id: str = "chunk-001",
    text: str = "Test text content.",
) -> Chunk:
    """Create a minimal Chunk for testing.

    WHAT: Builds a Chunk dataclass instance with only the fields that the
          LLMExtractor actually reads (chunk_id and text).
    WHY: Avoids boilerplate in every test; only meaningful fields need
         to be customized.
    """
    return Chunk(
        chunk_id=chunk_id,
        text=text,
        metadata=DocumentMetadata(source_filename="test.pdf"),
        chunk_type="clause",
        position_in_document=0,
    )


# ===================================================================
# Test 1: Prompt formatting
# ===================================================================


class TestPromptFormatting:
    """Tests that the prompt template renders correctly with document text."""

    def test_prompt_template_renders_document_text(self):
        """Verify EXTRACTION_PROMPT_EN contains the document text after formatting.

        WHAT: Format the prompt template with sample document text and check
              that both the instructions and the text appear in the result.
        WHY: The prompt template is the contract between the extractor and the
             LLM. If it doesn't render correctly, the LLM will receive garbled
             or missing context.
        """
        doc_text = "DH36 steel plates require preheat temperature of 150C per Pt.4 Ch.3."
        prompt = EXTRACTION_PROMPT_EN.format(document_text=doc_text)

        # The prompt must contain the document text
        assert doc_text in prompt

        # The prompt must contain the entity type definitions
        assert "steel_grade" in prompt
        assert "regulation_clause" in prompt
        assert "equipment" in prompt
        assert "system_type" in prompt
        assert "parameter" in prompt
        assert "ship_type" in prompt

        # The prompt must contain the relation type definitions
        assert "requires" in prompt
        assert "applies_to" in prompt
        assert "prohibits" in prompt
        assert "replaces" in prompt
        assert "references" in prompt
        assert "constrains" in prompt

        # The prompt must specify JSON output format
        assert '"entities"' in prompt
        assert '"relations"' in prompt


# ===================================================================
# Test 2: Normalize valid JSON
# ===================================================================


class TestNormalizeValidJson:
    """Tests that clean JSON output is parsed correctly."""

    @pytest.mark.asyncio
    async def test_normalize_valid_json_parsed(self):
        """Clean JSON from LLM should be parsed into entities and relations.

        WHAT: Provide clean JSON to _normalize_output and verify it returns
              correctly structured Entity and Relation objects.
        WHY: This is the happy path — the most common case when using a
             well-tuned LLM that follows the output format instructions.
        """
        extractor = LLMExtractor()

        entities, relations = extractor._normalize_output(_MOCK_JSON)

        # Verify entities
        assert len(entities) == 2
        assert entities[0].name == "EH36"
        assert entities[0].entity_type == "steel_grade"
        assert entities[0].properties == {"yield_strength": "355MPa"}
        assert entities[1].name == "Pt.4 Ch.3"
        assert entities[1].entity_type == "regulation_clause"
        assert entities[1].properties == {"society": "DNV"}

        # Verify relations
        assert len(relations) == 1
        assert relations[0].source_entity_id == "e1"
        assert relations[0].target_entity_id == "e2"
        assert relations[0].relation_type == "constrains"
        assert relations[0].properties == {"condition": "t <= 50mm"}
        # Verify confidence defaults to 0.9 for LLM-extracted relations
        assert relations[0].confidence == 0.9


# ===================================================================
# Test 3: Normalize markdown-wrapped JSON
# ===================================================================


class TestNormalizeMarkdownWrappedJson:
    """Tests that markdown-fenced JSON is stripped and parsed."""

    @pytest.mark.asyncio
    async def test_normalize_markdown_wrapped_json(self):
        """JSON inside triple-backtick fences should be parsed correctly.

        WHAT: Provide JSON wrapped in ```json...``` markdown fences to
              _normalize_output and verify it is parsed correctly.
        WHY: Many LLMs (especially open-source models) wrap JSON output in
             markdown code fences despite being told not to. The extractor
             must strip these fences before parsing.
        """
        md_json = '```json\n' + _MOCK_JSON + '\n```'

        extractor = LLMExtractor()
        entities, relations = extractor._normalize_output(md_json)

        assert len(entities) == 2
        assert entities[0].name == "EH36"
        assert len(relations) == 1
        assert relations[0].relation_type == "constrains"


# ===================================================================
# Test 4: Normalize garbled output (regex extraction)
# ===================================================================


class TestNormalizeGarbledOutput:
    """Tests that garbled LLM output with embedded JSON is regex-extracted."""

    @pytest.mark.asyncio
    async def test_normalize_garbled_output_regex(self):
        """JSON surrounded by explanatory text should be extracted via regex.

        WHAT: Provide LLM output that contains explanatory text before and
              after the JSON object. Verify that the regex-based second layer
              of normalization extracts the JSON block.
        WHY: Some LLMs prepend or append natural language commentary despite
             being told "return ONLY valid JSON". The regex fallback catches
             the JSON object embedded within the commentary.
        """
        garbled = (
            'Here are the entities I found:\n'
            + _MOCK_JSON
            + '\nYes I found 5 entities in this text.'
        )

        extractor = LLMExtractor()
        entities, relations = extractor._normalize_output(garbled)

        assert len(entities) == 2
        assert entities[0].name == "EH36"
        assert entities[1].name == "Pt.4 Ch.3"
        assert len(relations) == 1


# ===================================================================
# Test 5: Normalize invalid output
# ===================================================================


class TestNormalizeInvalid:
    """Tests that completely unparseable LLM output returns empty results."""

    @pytest.mark.asyncio
    async def test_normalize_invalid_returns_empty(self):
        """Completely unparseable output should return empty lists.

        WHAT: Provide text with no JSON-like structure to _normalize_output
              and verify it returns empty entity and relation lists.
        WHY: The third layer of normalization is the safety net. When both
             json.loads and regex extraction fail, the extractor must not
             crash or return garbage — it returns empty results, and the
             rule-based extractor provides fallback coverage.
        """
        invalid = "Sorry, I can't do that. Please provide a valid marine engineering document."

        extractor = LLMExtractor()
        entities, relations = extractor._normalize_output(invalid)

        assert entities == []
        assert relations == []


# ===================================================================
# Test 6: Token-aware batching
# ===================================================================


class TestTokenBatching:
    """Tests that chunks are batched by token count, not fixed count."""

    @pytest.mark.asyncio
    async def test_token_batching_splits_long_chunks(self):
        """15 long chunks should split into multiple token-based batches.

        WHAT: Create 15 chunks each containing ~2000 characters (≈500 tokens),
              then verify that _batch_by_tokens splits them into multiple
              batches based on the 6000-token budget per batch.
        WHY: Fixed-size batching (e.g. 20 chunks per batch) can overflow the
             LLM context window when chunks are long. Token-aware batching
             ensures each batch stays within the token budget regardless of
             individual chunk length.
        """
        # Each chunk is ~2000 chars → ~500 tokens (1 token ≈ 4 chars)
        long_text = "DH36 EH36 AH32 regulations requirements specifications " * 100  # ~5000 chars but we'll truncate
        # More precisely: ~2000 chars per chunk
        long_text = "X" * 2000

        chunks = [_make_chunk(chunk_id=f"chunk-{i:03d}", text=long_text) for i in range(15)]

        config = ExtractionConfig(max_tokens_per_batch=6000)
        extractor = LLMExtractor(config=config)

        batches = extractor._batch_by_tokens(chunks)

        # With 6000 token budget and ~500 tokens/chunk, each batch should
        # hold about 12 chunks max. 15 chunks → at least 2 batches.
        assert len(batches) >= 2, (
            f"Expected at least 2 batches for 15 long chunks, got {len(batches)}"
        )

        # Each batch must not exceed the token budget
        for batch in batches:
            batch_tokens = sum(len(c.text) // 4 for c in batch)
            assert batch_tokens <= 6000, (
                f"Batch token count {batch_tokens} exceeds budget of 6000"
            )

        # All chunks should be accounted for
        total_in_batches = sum(len(b) for b in batches)
        assert total_in_batches == len(chunks), (
            f"Expected {len(chunks)} chunks in batches, got {total_in_batches}"
        )

    @pytest.mark.asyncio
    async def test_short_chunks_single_batch(self):
        """Short chunks that fit within budget should stay in one batch.

        WHAT: Create 5 short chunks (each ~100 chars ≈ 25 tokens) and verify
              they all end up in a single batch.
        WHY: For small documents, batching should not fragment unnecessarily.
             A single LLM call is more efficient and produces better results
             than splitting across multiple small batches.
        """
        short_text = "Short text for testing batching behavior."
        chunks = [_make_chunk(chunk_id=f"chunk-{i:03d}", text=short_text) for i in range(5)]

        config = ExtractionConfig(max_tokens_per_batch=6000)
        extractor = LLMExtractor(config=config)

        batches = extractor._batch_by_tokens(chunks)

        assert len(batches) == 1
        assert len(batches[0]) == 5


# ===================================================================
# Test 7: Full extract pipeline with mocked LLM
# ===================================================================


class TestExtractPipeline:
    """Integration-style tests for the full extract() pipeline.

    WHAT: Tests the complete async extract() method end-to-end with a
          mocked LLM backend, verifying the full flow from chunks to
          entity/relation lists.
    """

    @pytest.mark.asyncio
    async def test_extract_with_mock_llm(self):
        """Full extract pipeline with mocked LLM returns expected results.

        WHAT: Create an LLMExtractor with a mocked _call_llm, invoke extract()
              with test chunks, and verify the merged results.
        WHY: End-to-end validation ensures the pipeline stages (batching →
              prompt formatting → LLM call → normalization → merging) all
              work together correctly.
        """
        # Arange: build mock LLM client that returns preset JSON
        mock_client = _make_mock_llm_response()

        config = ExtractionConfig(
            llm=LLMBackend(provider="openai", model="gpt-4o", api_key="sk-test"),
            max_tokens_per_batch=6000,
            max_concurrent=1,
        )
        extractor = LLMExtractor(config=config)

        # Patch _call_llm to return our mock response
        async def mock_call(prompt: str) -> str:
            return _MOCK_JSON

        extractor._call_llm = mock_call

        # Act: run extraction on a few chunks
        chunks = [
            _make_chunk("c1", "EH36 steel plates for Pt.4 Ch.3 bulk carrier requirements."),
            _make_chunk("c2", "Preheat temperature 150C, thickness less than 50mm."),
        ]
        entities, relations = await extractor.extract(chunks)

        # Assert: results should match the mock JSON
        assert len(entities) >= 2
        entity_names = {e.name for e in entities}
        assert "EH36" in entity_names
        assert "Pt.4 Ch.3" in entity_names
        assert len(relations) >= 1

    @pytest.mark.asyncio
    async def test_extract_llm_failure_returns_empty(self):
        """LLM failure should return empty results (not crash).

        WHAT: When the LLM call raises an exception, extract() should catch
              it and return empty entity/relation lists.
        WHY: The extractor must be resilient to LLM failures. The pipeline
             should not crash — it returns empty results, and the rule-based
             extractor provides fallback coverage via the merger stage.
        """
        config = ExtractionConfig(
            llm=LLMBackend(provider="openai", model="gpt-4o", api_key="sk-test"),
            max_tokens_per_batch=6000,
            max_concurrent=1,
            fallback_to_rules=True,
        )
        extractor = LLMExtractor(config=config)

        # Simulate LLM failure
        async def mock_failing_call(prompt: str) -> str:
            raise RuntimeError("LLM API connection refused")

        extractor._call_llm = mock_failing_call

        chunks = [_make_chunk("c1", "Test content.")]
        entities, relations = await extractor.extract(chunks)

        # Should return empty list on failure, not crash
        assert entities == []
        assert relations == []
