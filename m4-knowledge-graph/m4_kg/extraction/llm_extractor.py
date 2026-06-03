"""
LLM-based entity and relation extractor for the M4 Knowledge Graph engine.

WHAT:
  This module provides the LLMExtractor class which uses an LLM (via
  OpenAI-compatible API) to extract entities and relations from document
  chunks. It includes:

  - Token-aware batching: groups chunks by estimated token count (not fixed
    count) to stay within the LLM context limit.
  - Three-layer output normalization: json.loads -> regex extraction -> empty.
  - Concurrency control: asyncio.Semaphore limits simultaneous LLM requests.
  - Graceful degradation: LLM failures return empty results (rule extractor
    covers the gap via fallback in the merger stage).

WHY:
  LLM-based extraction captures nuanced entities and relations that regex-
  based rules miss (~30% of cases). The token-aware batching prevents context
  overflow (a fixed batch of 20 chunks could exceed 6000 tokens). Three-layer
  parsing handles the inherently unstable LLM output format. Concurrency
  control prevents overwhelming local LLM servers with too many parallel
  requests.

Key design decisions:
  - Uses the `openai` package (AsyncOpenAI) for ALL LLM backends because
    Ollama, DeepSeek, OpenAI, and Claude-compatible proxies all expose
    OpenAI-compatible chat completions APIs.
  - Entities get md5("name:type") IDs (same as rule extractor) for consistent
    merging in the merger stage.
  - Relations get confidence=0.9 (lower than rule extractor's 1.0) to allow
    the merger to prefer LLM results where available but trust rules where not.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any

from contracts.document import Chunk
from contracts.knowledge_graph import Entity, Relation
from m4_kg.core.config import ExtractionConfig
from m4_kg.extraction.prompt_templates import EXTRACTION_PROMPT_EN

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON extraction via brace counting
# WHAT: Finds the first JSON object {...} in a string by counting brace depth.
# WHY: Used as the second layer of _normalize_output() when json.loads fails.
#      A regex with fixed nesting depth cannot handle arbitrarily deep JSON.
#      Brace counting finds the outermost {...} regardless of depth.
# ---------------------------------------------------------------------------


def _extract_json_block(text: str) -> str | None:
    """Find the first balanced {...} JSON object in text using brace counting.

    WHAT:
      Scans the text for the first '{' character, then counts opening and
      closing braces until they balance, and returns that substring.

    WHY:
      LLM output often wraps JSON in markdown fences or explanatory text.
      A simple regex can't handle arbitrary JSON nesting depth (e.g.,
      {"entities": [{"properties": {"key": "val"}}]} has 3+ levels).
      Brace counting handles any depth correctly.

    Args:
        text: Raw text that may contain a JSON object.

    Returns:
        The extracted JSON substring from first '{' to matching '}', or None
        if no balanced braces are found.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        ch = text[i]

        if escape_next:
            escape_next = False
            continue

        if ch == "\\" and in_string:
            escape_next = True
            continue

        if ch == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    # Unbalanced braces — return None
    return None


class LLMExtractor:
    """Extract entities and relations from document chunks using LLM.

    WHAT:
      Asynchronously processes document chunks through an LLM to extract
      structured knowledge (entities and relations) for the knowledge graph.
      Chunks are batched by token count, each batch is sent to the LLM via
      OpenAI-compatible API, and results are normalized and merged.

    WHY:
      LLM extraction captures semantic relationships that rule-based regex
      cannot detect (e.g., "preheat temperature 150C constrains EH36").
      This provides the deep extraction layer that complements the fast
      rule-based extraction covering 70% of simple patterns.

    Attributes:
        _config: ExtractionConfig controlling batch size, concurrency, etc.
        _semaphore: asyncio.Semaphore limiting concurrent LLM API calls.
        _client: Lazy-initialized AsyncOpenAI client for LLM calls.
    """

    def __init__(
        self,
        config: ExtractionConfig | None = None,
    ) -> None:
        """Initialize the LLM extractor.

        WHAT: Sets up the extractor with an optional ExtractionConfig.
              If no config is provided, defaults are used (rule-only mode
              since llm=None in the default config).

        WHY: The config is optional to support the simple constructor in
             tests. Production code should pass a config with an LLM backend.

        Args:
            config: ExtractionConfig with LLM backend settings and batching
                    parameters. If None, default config is used.
        """
        self._config = config or ExtractionConfig()

        # Concurrency limiter: asyncio.Semaphore restricts the number of
        # simultaneous LLM API calls to prevent overwhelming local models
        # or hitting cloud API rate limits.
        # WHY: Local models (Ollama/vLLM) have limited inference capacity;
        #      cloud APIs have rate limits. The semaphore is the simplest
        #      and most effective concurrency control mechanism.
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent)

        # Lazy-initialized client: created on first _call_llm() invocation.
        # WHY: The AsyncOpenAI client requires an API key and base_url that
        #      may be set via config at runtime. Deferring initialization
        #      avoids creating a client that's never used.
        self._client: Any = None

    # ===================================================================
    # Public API
    # ===================================================================

    async def extract(
        self, chunks: list[Chunk]
    ) -> tuple[list[Entity], list[Relation]]:
        """Extract entities and relations from document chunks using LLM.

        WHAT:
          Main entry point. Batches chunks by token count, sends each batch
          to the LLM, normalizes each response, and merges all results.

        WHY:
          This is the primary public API. It coordinates the full pipeline:
          batching -> prompt formatting -> LLM call -> normalization -> merging.

        Args:
            chunks: List of Chunk objects from parsed document text.

        Returns:
            Tuple of (entities, relations) extracted across all batches.
            Returns empty lists if no LLM is configured or if all calls fail.
        """
        # No LLM configured → return empty, rule extractor will handle all
        # WHY: Supports deployment modes without LLM backend (cost saving,
        #      offline mode, etc.). The merger stage uses rules-only results.
        if not chunks or self._config.llm is None:
            return [], []

        try:
            # Step 1: Batch chunks by estimated token count
            batches = self._batch_by_tokens(chunks)

            # Step 2: Process each batch concurrently (up to max_concurrent)
            results: list[tuple[list[Entity], list[Relation]]] = (
                await asyncio.gather(
                    *[self._process_batch(batch) for batch in batches],
                )
            )

            # Step 3: Merge results from all batches
            return self._merge_batch_results(results)

        except Exception:
            # Catch-all: if anything goes wrong during LLM extraction,
            # return empty results. The merger stage will use rule-based
            # results as fallback when fallback_to_rules is True.
            # WHY: LLM failures should never crash the extraction pipeline.
            #      Rule-based extraction provides reliable baseline coverage.
            _logger.exception("LLM extraction failed; returning empty results")
            return [], []

    # ===================================================================
    # Token-aware batching
    # ===================================================================

    def _batch_by_tokens(self, chunks: list[Chunk]) -> list[list[Chunk]]:
        """Group chunks into batches that fit within the token budget.

        WHAT:
          Iterates through chunks, accumulating them into batches such that
          each batch's total estimated token count does not exceed
          max_tokens_per_batch. Uses the rough estimate of 1 token ≈ 4 chars.

        WHY:
          Fixed-size batching (e.g. "always 20 chunks per batch") fails when
          chunks are long — 20 x 2000-char chunks = 40000 chars ≈ 10000 tokens,
          far exceeding the 6000 token budget. Token-aware batching is adaptive:
          it packs many short chunks or few long chunks, always staying within
          the context window.

        Args:
            chunks: List of Chunk objects to batch.

        Returns:
            List of batches, each being a list of Chunk objects whose total
            estimated token count is <= max_tokens_per_batch.
        """
        max_tokens = self._config.max_tokens_per_batch

        batches: list[list[Chunk]] = []
        current_batch: list[Chunk] = []
        current_tokens: int = 0

        for chunk in chunks:
            chunk_tokens = self._estimate_tokens(chunk.text)

            # If adding this chunk would exceed the budget and we already
            # have chunks in the current batch, start a new batch.
            # WHY: We never split an individual chunk across batches because
            #      an entity might span sentence boundaries within a chunk.
            #      Keeping chunks whole preserves entity context.
            if current_tokens + chunk_tokens > max_tokens and current_batch:
                batches.append(current_batch)
                current_batch = [chunk]
                current_tokens = chunk_tokens
            else:
                current_batch.append(chunk)
                current_tokens += chunk_tokens

        # Don't forget the last partially-filled batch
        if current_batch:
            batches.append(current_batch)

        return batches

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Estimate token count for text using rough character ratio.

        WHAT:
          Returns len(text) // 4 as an approximate token count.

        WHY:
          1 token ≈ 4 characters for English text is a widely-used heuristic
          that is fast (no tokenizer needed), language-agnostic, and accurate
          enough for batching purposes. The goal is to avoid context overflow,
          not to count tokens precisely. A slight underestimate is safe because
          it keeps batches smaller than the max budget.

        Args:
            text: Input text string.

        Returns:
            Estimated token count (never less than 1 for non-empty text).
        """
        if not text:
            return 0
        return max(1, len(text) // 4)

    # ===================================================================
    # Batch processing
    # ===================================================================

    async def _process_batch(
        self, batch: list[Chunk]
    ) -> tuple[list[Entity], list[Relation]]:
        """Process a single batch through the LLM pipeline.

        WHAT:
          Formats the batch chunks into a prompt, sends it to the LLM,
          and normalizes the response into Entity and Relation lists.

        WHY:
          Each batch is an independent LLM call. The results from all
          batches are merged later by _merge_batch_results().

        Args:
            batch: List of Chunk objects representing one token-budget batch.

        Returns:
            Tuple of (entities, relations) extracted from this batch.
            Returns empty lists on LLM failure.
        """
        try:
            # Format chunks into a single document text string for the prompt
            document_text = self._format_batch(batch)

            # Build the prompt by inserting document text into the template
            prompt = EXTRACTION_PROMPT_EN.format(document_text=document_text)

            # Call LLM with semaphore-based concurrency control
            async with self._semaphore:
                raw = await self._call_llm(prompt)

            # Normalize the LLM response into structured data
            return self._normalize_output(raw)

        except Exception:
            # Log the failure and return empty — the merger stage will
            # use rule-based results to fill the gap.
            # WHY: One failing batch should not block other batches or
            #      crash the entire extraction. We log and continue.
            _logger.exception(
                "LLM batch processing failed (batch size=%d)", len(batch)
            )
            return [], []

    def _format_batch(self, batch: list[Chunk]) -> str:
        """Format a batch of chunks into a single document text block.

        WHAT:
          Joins chunk texts with double newlines as separators, and
          truncates to max_chunks_per_doc if needed.

        WHY:
          The LLM prompt needs a single text block. Simple concatenation
          with clear separators preserves chunk boundaries so the LLM
          can still associate entities with specific chunks.

        Args:
            batch: List of Chunk objects to format.

        Returns:
            A single string containing all chunk texts joined by double
            newlines.
        """
        # Truncate to max_chunks_per_doc if the batch exceeds it
        # WHY: Prevents unbounded prompt size when processing very large
        #      documents. The limit is per-batch, not per-document.
        limit = self._config.max_chunks_per_doc
        truncated = batch[:limit] if len(batch) > limit else batch

        return "\n\n".join(chunk.text for chunk in truncated)

    # ===================================================================
    # LLM call
    # ===================================================================

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM via OpenAI-compatible API.

        WHAT:
          Sends a chat completion request to the configured LLM backend
          using the openai AsyncOpenAI client. The client is initialized
          lazily on first call.

        WHY:
          The openai package is used for ALL backends (Ollama, DeepSeek,
          OpenAI, Claude via proxy) because they all expose OpenAI-compatible
          chat completions endpoints. This avoids vendor lock-in and allows
          the user to switch backends via config.

        Args:
            prompt: The formatted extraction prompt to send to the LLM.

        Returns:
            The LLM's response text (expected to contain JSON, but may
            include markdown fences or explanatory text).

        Raises:
            RuntimeError: If no LLM backend is configured.
            Various openai errors: Propagated from the API call (caught by
                                   the caller).
        """
        if self._config.llm is None:
            raise RuntimeError("No LLM backend configured for extraction")

        # Lazy initialization of the AsyncOpenAI client
        # WHY: The API key and base_url come from config which may be set
        #      at deploy time. Creating the client early would require dummy
        #      values for unit tests.
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=self._config.llm.api_key or "not-needed",
                base_url=self._config.llm.base_url,
            )

        # Send chat completion request
        # WHY: Using chat completions (not legacy completions) because:
        #      1. It's the standard for modern LLM APIs.
        #      2. All supported backends (Ollama, DeepSeek, OpenAI, Claude)
        #         support the /v1/chat/completions endpoint.
        response = await self._client.chat.completions.create(
            model=self._config.llm.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a marine engineering knowledge extraction assistant. Extract entities and relations from document text and return ONLY valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,  # Deterministic output for extraction
            max_tokens=4096,  # Sufficient for JSON with ~50 entities+relations
        )

        return response.choices[0].message.content or ""

    # ===================================================================
    # Output normalization (three-layer parsing)
    # ===================================================================

    def _normalize_output(
        self, raw: str
    ) -> tuple[list[Entity], list[Relation]]:
        """Parse LLM output into Entity and Relation lists.

        WHAT:
          Three-layer parsing strategy for handling unstable LLM output:
          1. Try json.loads() directly — works for clean JSON.
          2. If that fails, use regex to find the first {...} block and
             parse that — handles markdown fences and explanatory text.
          3. If that also fails, return empty lists — safety net.

        WHY:
          LLM output format is inherently unstable. Some models wrap JSON
          in markdown fences despite instructions. Others prepend/appended
          explanatory text. Some return completely wrong output. Each layer
          handles a progressively more garbled response.

        Args:
            raw: Raw LLM response text.

        Returns:
            Tuple of (entities, relations) parsed from the response.
            Returns empty lists if all parsing layers fail.
        """
        if not raw or not raw.strip():
            return [], []

        # ---- Layer 1: Direct json.loads ----
        # Try parsing the entire response as JSON first.
        # This handles the happy path where the LLM returns clean JSON.
        try:
            data = json.loads(raw.strip())
            return self._parse_json_data(data)
        except json.JSONDecodeError:
            pass

        # ---- Layer 2: Brace-counting extraction ----
        # The LLM may have wrapped JSON in markdown fences or added
        # explanatory text. Use brace counting to find the first {...}
        # block — handles arbitrary nesting depth correctly.
        # WHY: Brace counting is more robust than regex for nested JSON
        #      because it handles any depth (e.g. properties inside
        #      entities inside arrays inside the outer object).
        json_block = _extract_json_block(raw)
        if json_block is not None:
            try:
                data = json.loads(json_block)
                return self._parse_json_data(data)
            except json.JSONDecodeError:
                pass

        # ---- Layer 3: Return empty ----
        # Completely unparseable output. Return empty results.
        # The rule-based extractor provides fallback coverage.
        _logger.warning(
            "Failed to parse LLM output (all 3 normalization layers failed); "
            "first 200 chars: %s",
            raw[:200],
        )
        return [], []

    def _parse_json_data(
        self, data: dict[str, Any]
    ) -> tuple[list[Entity], list[Relation]]:
        """Convert parsed JSON dict into Entity and Relation lists.

        WHAT:
          Validates the JSON structure (must have "entities" and "relations"
          keys containing lists), then converts each entry to the appropriate
          dataclass type.

        WHY:
          Separates the JSON parsing concern from the entity/relation
          construction concern. The three-layer parsing in _normalize_output
          only needs to produce a dict; this method handles type conversion.

        Args:
            data: Parsed JSON dict with expected keys "entities" and "relations".

        Returns:
            Tuple of (entities, relations) constructed from the JSON data.
            Returns empty lists if the JSON structure is invalid.
        """
        entities: list[Entity] = []
        relations: list[Relation] = []

        # Validate structure: both keys must exist and be lists
        raw_entities = data.get("entities")
        raw_relations = data.get("relations")
        if not isinstance(raw_entities, list):
            raw_entities = []
        if not isinstance(raw_relations, list):
            raw_relations = []

        # Build a set of entity IDs from the LLM output for relation validation
        # WHY: Some LLM-generated relations may reference entity IDs that
        #      are not in the entities list. We skip those relations to
        #      maintain graph consistency.
        valid_entity_ids: set[str] = set()

        # Convert entity dicts to Entity objects
        for item in raw_entities:
            if not isinstance(item, dict):
                continue
            # Use LLM-provided 'id' as entity_id, fall back to md5 hash
            eid = item.get("id", "")
            ename = str(item.get("name", ""))
            etype = str(item.get("type", "unknown"))
            eprops = item.get("properties", {})

            if not isinstance(eprops, dict):
                eprops = {}

            # Deterministic fallback ID when LLM doesn't provide one
            # WHY: Matches the rule extractor's ID generation for consistent
            #      merging in the merger stage.
            if not eid:
                eid = self._make_entity_id(ename, etype)

            valid_entity_ids.add(eid)

            entities.append(Entity(
                entity_id=eid,
                name=ename,
                entity_type=etype,
                properties=eprops,
                source_doc_id=None,  # Will be stamped by the engine layer
            ))

        # Convert relation dicts to Relation objects
        for item in raw_relations:
            if not isinstance(item, dict):
                continue

            src = str(item.get("source", ""))
            tgt = str(item.get("target", ""))
            rtype = str(item.get("type", "references"))
            rprops = item.get("properties", {})

            if not isinstance(rprops, dict):
                rprops = {}

            # Skip relations referencing entities not in the entities list
            # WHY: Prevents dangling edges in the graph. The LLM may generate
            #      relations to entity IDs it did not include in entities.
            if src not in valid_entity_ids or tgt not in valid_entity_ids:
                _logger.debug(
                    "Skipping relation %s -> %s (%s): target or source not in entities",
                    src, tgt, rtype,
                )
                continue

            # Generate deterministic relation ID
            rid = self._make_relation_id(src, tgt, rtype)

            relations.append(Relation(
                relation_id=rid,
                source_entity_id=src,
                target_entity_id=tgt,
                relation_type=rtype,
                properties=rprops,
                confidence=0.9,  # LLM results have lower confidence than rules (1.0)
            ))

        return entities, relations

    # ===================================================================
    # Result merging
    # ===================================================================

    def _merge_batch_results(
        self,
        results: list[tuple[list[Entity], list[Relation]]],
    ) -> tuple[list[Entity], list[Relation]]:
        """Merge entity and relation lists from multiple batches.

        WHAT:
          Concatenates entities and relations from all batches, deduplicating
          entities by entity_id (keeping first occurrence) and relations by
          relation_id.

        WHY:
          Multiple batches process different parts of a document and may
          independently extract the same entities (e.g. "EH36" mentioned
          in multiple sections). Deduplication ensures each entity appears
          only once in the final output.

        Args:
            results: List of (entities, relations) tuples from each batch.

        Returns:
            Merged and deduplicated tuple of (entities, relations).
        """
        all_entities: list[Entity] = []
        all_relations: list[Relation] = []

        seen_entity_ids: set[str] = set()
        seen_relation_ids: set[str] = set()

        for entities, relations in results:
            for e in entities:
                if e.entity_id not in seen_entity_ids:
                    seen_entity_ids.add(e.entity_id)
                    all_entities.append(e)

            for r in relations:
                if r.relation_id not in seen_relation_ids:
                    seen_relation_ids.add(r.relation_id)
                    all_relations.append(r)

        return all_entities, all_relations

    # ===================================================================
    # ID generation (matches rule extractor for consistent merging)
    # ===================================================================

    @staticmethod
    def _make_entity_id(name: str, entity_type: str) -> str:
        """Generate a deterministic entity ID from name and type.

        WHAT: Computes MD5 hash of "name:entity_type" string.
        WHY: Must match the rule extractor's ID generation exactly so that
             the merger stage can correctly deduplicate entities from both
             sources.
        """
        raw = f"{name}:{entity_type}"
        return hashlib.md5(raw.encode()).hexdigest()

    @staticmethod
    def _make_relation_id(
        source_id: str, target_id: str, relation_type: str
    ) -> str:
        """Generate a deterministic relation ID.

        WHAT: Computes MD5 hash of "source_id:target_id:relation_type".
        WHY: Matches rule extractor's ID generation for consistent
             deduplication in the merger stage.
        """
        raw = f"{source_id}:{target_id}:{relation_type}"
        return hashlib.md5(raw.encode()).hexdigest()
