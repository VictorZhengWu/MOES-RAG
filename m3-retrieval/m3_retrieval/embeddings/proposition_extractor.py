"""
Proposition Extractor — LLM-based atomic fact extraction.

WHAT: Given document chunks, uses an LLM to extract self-contained atomic
      facts (propositions). Each proposition is a single sentence that can
      independently answer a specific question.

      Example:
        Input:  "EH36 requires preheat to 150°C when t≤50mm. Interpass
                 must be maintained at 150-200°C for all positions."
        Output: ["EH36 steel requires preheat to 150°C when plate
                 thickness is 50mm or less",
                 "EH36 steel requires interpass temperature between
                 150°C and 200°C for all welding positions"]

WHY: Current retrieval returns 200-word chunks. The LLM must scan each
     chunk to find the answer. Propositions are pre-extracted into
     atomic facts — retrieval can directly return the relevant fact
     instead of making the LLM search for it. This shifts the LLM
     cost from QUERY TIME (every question) to INDEX TIME (once per doc).

     The pattern follows M4's entity extraction: LLM at index time,
     free retrieval at query time.

Cost: ~$0.005 per 10 chunks (1 LLM call). A 50-page doc (~200 chunks)
      costs ~$0.10 to propositionalize. One-time cost, permanent benefit.
"""

from __future__ import annotations

import asyncio
import json
import re

import httpx


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT: str = """For each sentence in the text below, extract self-contained atomic facts that could answer a specific technical question.

## Rules
- One fact per line
- Include the technical subject explicitly (e.g. "EH36 steel" not "it")
- Include numeric values with units (e.g. "150°C" not "high temperature")
- Skip headings, introductions, tables of contents, and generic statements
- If a sentence contains multiple independent facts, split them
- Each fact must be understandable WITHOUT reading the original text
- Answer in the same language as the input text

## Example
Input: "EH36 requires preheat to 150°C and interpass at 150-200°C for all positions."
Output:
EH36 steel requires preheat temperature of 150°C
EH36 steel requires interpass temperature between 150°C and 200°C for all welding positions

## Text
{chunk_text}

## Facts (one per line, no numbering, no markdown)"""


# ---------------------------------------------------------------------------
# PropositionExtractor
# ---------------------------------------------------------------------------


class PropositionExtractor:
    """
    Extract atomic facts from document chunks using an LLM.

    WHAT: Sends chunks in batches to an LLM (OpenAI-compatible API),
          parses the response into individual propositions, and deduplicates.

    WHY: The LLM is the only reliable way to decompose complex technical
         text into self-contained facts. Regex cannot handle the myriad
         ways regulations express requirements ("shall be at least 150°C"
         vs "minimum preheat temperature: 150°C" vs "preheat ≥ 150°C").
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "DeepSeek-V3",
        api_key: str | None = None,
        batch_size: int = 10,
        max_concurrent: int = 2,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key or "not-needed"
        self._batch_size = batch_size
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def extract(self, texts: list[str]) -> list[str]:
        """
        Extract propositions from a list of chunk texts.

        Returns a deduplicated list of atomic fact strings.
        Empty input returns empty list. LLM failure returns empty list
        (graceful degradation — chunks are still available).
        """
        if not texts:
            return []

        # Batch texts
        batches: list[list[str]] = []
        for i in range(0, len(texts), self._batch_size):
            batches.append(texts[i : i + self._batch_size])

        # Process batches concurrently
        tasks = [self._extract_batch(b) for b in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect and deduplicate
        all_props: list[str] = []
        seen: set[str] = set()
        for result in results:
            if isinstance(result, Exception):
                continue
            for prop in result:
                normalized = prop.strip().lower()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    all_props.append(prop.strip())

        return all_props

    async def _extract_batch(self, texts: list[str]) -> list[str]:
        """Extract propositions from one batch of chunk texts."""
        async with self._semaphore:
            try:
                chunk_text = "\n\n".join(texts)
                prompt = EXTRACTION_PROMPT.format(chunk_text=chunk_text)

                headers: dict[str, str] = {
                    "Content-Type": "application/json",
                }
                if self._api_key and self._api_key != "not-needed":
                    headers["Authorization"] = f"Bearer {self._api_key}"

                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{self._base_url}/chat/completions",
                        json={
                            "model": self._model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": 2000,
                            "temperature": 0.3,  # Low temp for factual extraction
                        },
                        headers=headers,
                    )

                    if resp.status_code != 200:
                        import logging
                        logging.getLogger("m3_retrieval").warning(
                            "Proposition extraction LLM call failed: HTTP %s", resp.status_code
                        )
                        return []

                    data = resp.json()
                    content: str = data["choices"][0]["message"]["content"]

                # Parse lines into individual facts
                return _parse_propositions(content)

            except Exception as exc:
                import logging
                logging.getLogger("m3_retrieval").warning(
                    "Proposition extraction failed: %s", exc
                )
                return []


def _parse_propositions(llm_output: str) -> list[str]:
    """
    Parse LLM output into clean proposition strings.

    WHAT: Handles various LLM output formats:
      - Plain lines (expected format)
      - Numbered lines ("1. EH36 requires...")
      - Bullet points ("- EH36 requires...")
      - JSON arrays (fallback parsing)

    Returns cleaned, non-empty lines.
    """
    lines: list[str] = []
    for line in llm_output.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Remove common list markers
        line = re.sub(r"^\s*(?:\d+[.)]\s*|[-•*]\s*)", "", line)
        # Remove quotes if the LLM wrapped them
        line = line.strip('"').strip("'")
        if len(line) > 10:  # Skip very short fragments
            lines.append(line)
    return lines
