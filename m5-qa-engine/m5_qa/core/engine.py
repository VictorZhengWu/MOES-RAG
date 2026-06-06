"""
M5 QA Engine — QAEngine (main brain of the Marine & Offshore Expert System).

WHAT: QAEngine implements QAEngineProtocol and serves as the central orchestrator
      for the entire RAG QA pipeline. It:
      1. Routes queries to the appropriate pipeline (simple/pipeline/self_rag)
         based on user tier and Premium quota availability.
      2. Coordinates the LLM client, prompt manager, retrieval client,
         conversation manager, context compressor, and metrics collector.
      3. Produces OpenAI-compatible chat completion responses (ChatResponse).
      4. Supports both non-streaming (chat) and streaming (chat_stream) modes.
      5. Exposes conversation management and health check APIs.

WHY: The QA engine is the "brain" of the system — all user-facing chat requests
     flow through it. It encapsulates the complexity of mode routing, pipeline
     orchestration, and response building behind a clean protocol interface.
     This allows the API gateway (M8) and web portals (M6/M7) to interact
     with the QA engine without knowing implementation details.
"""

from __future__ import annotations

import datetime
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from contracts.qa_engine import (
    ChatRequest,
    ChatResponse,
    Choice,
    Citation,
    ConversationSummary,
    Message,
    QAEngineProtocol,
    Usage,
)

from m5_qa.context.retriever import RetrievalClient
from m5_qa.conversation.compressor import ContextCompressor
from m5_qa.conversation.manager import ConversationManager
from m5_qa.core.config import LLMBackend, QAConfig
from m5_qa.core.router import ModeRouter
from m5_qa.core.tier import USER_TIERS
from m5_qa.generation.llm_client import LLMClient, estimate_tokens
from m5_qa.generation.prompt_manager import PromptManager
from m5_qa.generation.streaming import sse_chunk, sse_done
from m5_qa.monitoring.logger import StructuredLogger
from m5_qa.monitoring.metrics import MetricsCollector
from m5_qa.pipelines.pipeline import execute_pipeline
from m5_qa.pipelines.self_rag import execute_self_rag
from m5_qa.pipelines.simple import execute_simple


class QAEngine:
    """
    WHAT: The central QA engine for the Marine & Offshore Expert System.

    Implements QAEngineProtocol to provide:
      - chat(): Non-streaming chat completion (OpenAI-compatible).
      - chat_stream(): Streaming chat completion via Server-Sent Events.
      - list_conversations(), get_conversation(), delete_conversation():
        Conversation history management.
      - list_models(): Available LLM model listing.
      - health_check(): Component health status.

    Dependencies (wired in __init__):
      - ModeRouter: Routes queries to simple/pipeline/self_rag based on tier.
      - LLMClient: Unified LLM client for all backends (OpenAI-compatible API).
      - PromptManager: DB-backed prompt template store with i18n support.
      - RetrievalClient: Coordinates M3 (semantic) + M4 (graph) retrieval.
      - ConversationManager: SQLite-backed conversation/message/quotas store.
      - ContextCompressor: Truncates conversation history to fit token budget.
      - MetricsCollector: Records per-query latency, mode, and tier stats.

    WHY: All user-facing chat requests must flow through a single, consistent
         entry point. This design ensures consistent routing, response formatting,
         monitoring, and error handling across all deployment modes.
    """

    def __init__(self, config: QAConfig | None = None):
        """
        WHAT: Initialize the QA engine with all subsystem dependencies.

        Wires up the complete dependency graph: mode router, LLM client,
        prompt manager, retrieval client, conversation manager, context
        compressor, and metrics collector. All components are created
        with the same configuration and database path.

        Args:
            config: QAConfig with LLM backend, db_path, and pipeline thresholds.
                    If None, a default QAConfig is used (Ollama + in-memory DB).

        WHY: Centralized initialization ensures all components share the same
             configuration (same DB, same LLM backend). Constructing in __init__
             rather than lazily ensures failures are detected at startup, not
             at the first user request.
        """
        self._config = config or QAConfig()

        # Mode router: determines pipeline mode from tier + premium status
        self._router = ModeRouter()

        # LLM client: unified interface for Ollama/DeepSeek/OpenAI/Claude
        self._llm_client = LLMClient(
            self._config.llm if self._config.llm is not None else LLMBackend()
        )

        # Prompt manager: DB-backed i18n prompt templates
        self._prompt_manager = PromptManager(self._config.db_path)

        # Retrieval client: coordinates M3 (semantic) and M4 (graph) search.
        # Engines are injected later via set_retrieval_engines() or remain
        # None for graceful degradation during testing/early development.
        self._retriever = RetrievalClient()

        # Conversation manager: M5-owned SQLite for conversations + quotas.
        # NOT routed through M2 — conversation management is M5 business logic.
        self._conversations = ConversationManager(self._config.db_path)

        # Context compressor: truncates history to fit LLM context window.
        self._compressor = ContextCompressor()

        # Metrics collector: records per-query stats for monitoring dashboards.
        self._metrics = MetricsCollector()

    # ------------------------------------------------------------------
    # Core Chat API
    # ------------------------------------------------------------------

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        WHAT: Process a non-streaming chat completion request and return
              an OpenAI-compatible ChatResponse with RAG citations.

        Pipeline flow:
          1. Extract user message and user ID from the request.
          2. Determine pipeline mode based on user tier and Premium quota.
          3. Execute the selected pipeline (simple/pipeline/self_rag).
          4. Build an OpenAI-compatible ChatResponse with citations and usage.
          5. Record metrics (latency, mode, tier) and log the query.

        Args:
            request: ChatRequest with model, messages, and optional filters.

        Returns:
            ChatResponse with assistant answer, citations, and token usage.

        WHY: This is the primary API entry point — all non-streaming chat
             interactions from M6 (User Portal), M7 (Admin Portal), and
             external API consumers (M8) go through this method.
        """
        t0 = time.perf_counter()

        # Step 1: Extract user message content from the last message in the
        # conversation. If no messages exist (edge case), use empty string.
        user_msg = request.messages[-1].content if request.messages else ""
        user_id = request.user or "anonymous"

        # Step 2: Determine the user's tier level and default pipeline mode.
        # Currently hardcoded to "basic" — future: lookup from user DB/M7 admin.
        # The router resolves the tier string to a UserTier object with
        # context_window size and default_mode ("simple"/"pipeline"/"self_rag").
        tier_level = getattr(request, "tier", None) or self._config.default_tier
        _, tier = self._router.select_mode(user_id, tier_level)
        mode = tier.default_mode

        # Step 3: Check Premium quota — if available, upgrade to self_rag mode.
        # Premium provides temporary access to the highest-quality pipeline
        # (self_rag) regardless of the user's base tier. One credit is consumed.
        # Enterprise users have unlimited premium (-1 limit), so this always
        # returns True but their default_mode is already self_rag.
        if user_id != "anonymous":
            today = datetime.date.today().isoformat()
            premium_ok = await self._conversations.consume_premium(user_id, today)
            if premium_ok:
                mode = "self_rag"

        # Step 4: If web search is enabled, fetch web results to supplement
        # the retrieval context. Web results are appended to the user's query
        # so the LLM sees them alongside M3/M4 retrieved chunks.
        web_context: str = ""
        if getattr(request, "web_search_enabled", False):
            try:
                from m5_qa.context.web_search import create_web_search_engine, format_web_results

                engine = create_web_search_engine(
                    engine=self._config.web_search_engine,
                    api_key=self._config.web_search_api_key,
                    searxng_url=self._config.web_search_searxng_url,
                    google_cx=self._config.web_search_google_cx,
                )
                web_results = await engine.search(user_msg)
                web_context = format_web_results(web_results)
            except Exception:
                pass  # Web search is supplementary — never block the pipeline

        if web_context:
            user_msg = f"{user_msg}\n\n[Web Search Results]\n{web_context}"

        # Step 5: Execute the selected pipeline mode.
        # Each pipeline function is an async function that takes query, llm_client,
        # retriever, prompt_manager, tier, and optional parameters.
        if mode == "simple":
            result = await execute_simple(
                query=user_msg,
                llm_client=self._llm_client,
                retriever=self._retriever,
                prompt_manager=self._prompt_manager,
                tier=tier_level,
            )
        elif mode == "pipeline":
            result = await execute_pipeline(
                query=user_msg,
                llm_client=self._llm_client,
                retriever=self._retriever,
                prompt_manager=self._prompt_manager,
                tier=tier_level,
            )
        else:  # self_rag
            result = await execute_self_rag(
                query=user_msg,
                llm_client=self._llm_client,
                retriever=self._retriever,
                prompt_manager=self._prompt_manager,
                tier=tier_level,
                score_threshold=self._config.retrieval_score_threshold,
                max_iterations=self._config.max_self_rag_iterations,
            )

        # Step 5: Build the OpenAI-compatible ChatResponse.
        # The response format matches the OpenAI /v1/chat/completions schema
        # with an additional 'citations' field for RAG source traceability.
        response = ChatResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
            model=request.model or (
                self._config.llm.model if self._config.llm else "m5-qa"
            ),
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content=result["answer"]),
                    finish_reason="stop",
                )
            ],
            citations=result.get("citations", []),
            usage=Usage(
                prompt_tokens=estimate_tokens(user_msg),
                completion_tokens=estimate_tokens(result["answer"]),
                total_tokens=estimate_tokens(user_msg)
                + estimate_tokens(result["answer"]),
            ),
        )

        # Step 6: Record metrics and log the query for observability.
        latency_ms = (time.perf_counter() - t0) * 1000
        self._metrics.record_query(
            mode=mode,
            latency_ms=latency_ms,
            tier=tier_level,
        )
        StructuredLogger.log_query(
            user_id=user_id,
            query=user_msg,
            mode=mode,
            latency_ms=latency_ms,
            token_count=response.usage.total_tokens if response.usage else 0,
        )

        return response

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """
        WHAT: Process a streaming chat completion request and yield SSE
              (Server-Sent Events) chunks for real-time display.

        The flow is similar to chat() but uses LLMClient.complete_stream()
        instead of complete(), yielding SSE-formatted text deltas followed
        by a [DONE] termination marker.

        Args:
            request: ChatRequest with model, messages, and stream=True.

        Yields:
            str: SSE event chunks in `data: {json}\n\n` format, terminated
                 by `data: [DONE]\n\n`.

        WHY: Streaming provides a better UX for long answers — users see
             text appearing in real-time rather than waiting for the full
             response. The SSE format is consumed by the M6 frontend's
             EventSource API.
        """
        user_msg = request.messages[-1].content if request.messages else ""
        user_id = request.user or "anonymous"

        # Resolve tier and mode (same logic as chat())
        tier_level = getattr(request, "tier", None) or self._config.default_tier
        _, tier = self._router.select_mode(user_id, tier_level)
        mode = tier.default_mode

        if user_id != "anonymous":
            today = datetime.date.today().isoformat()
            premium_ok = await self._conversations.consume_premium(user_id, today)
            if premium_ok:
                mode = "self_rag"

        # Step 1: Retrieve real context FIRST (non-streaming).
        # Streaming is about LLM token delivery, NOT about skipping retrieval.
        # Without real context, the LLM generates from its own knowledge only.
        if mode == "simple":
            ctx = await self._retriever.simple_retrieve(user_msg)
            graph_text = "(not available in simple mode)"
        else:
            ctx = await self._retriever.parallel_retrieve(
                user_msg, kg_depth=tier.traversal_depth if hasattr(tier, "traversal_depth") else 3
            )
            graph_text = "(no graph insights)" if not ctx.graph or not ctx.graph.entities else (
                "\n".join(f"- {e.name} ({e.entity_type})" for e in ctx.graph.entities[:20])
            )

        # Step 2: Token budget + context fusion
        from m5_qa.context.token_budget import allocate_budget
        from m5_qa.context.fusion import fuse_context
        budget = allocate_budget(tier_level, user_msg)
        context_text = fuse_context(ctx, budget.retrieval_limit)

        # Step 3: Build prompt with REAL retrieval context
        system_template = await self._prompt_manager.get_prompt("system_en", "en")
        system_prompt = self._prompt_manager.fill_template(
            system_template,
            retrieved_context=context_text,
            graph_context=graph_text,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]

        # Step 4: Stream tokens from the LLM
        async for content in self._llm_client.complete_stream(messages):
            chunk = await sse_chunk(content)
            yield chunk

        # Step 5: Push citations as final SSE event before [DONE]
        from m5_qa.context.citation_builder import build_citations
        citations = build_citations(ctx.chunks)
        yield await sse_chunk("", finish_reason="stop")
        if citations:
            yield await sse_citations(citations)

        # Step 6: Signal stream completion
        done = await sse_done()
        yield done

    # ------------------------------------------------------------------
    # Model Listing
    # ------------------------------------------------------------------

    async def list_models(self) -> list[dict[str, Any]]:
        """
        WHAT: Return the list of available LLM models for this engine instance.

        Returns:
            A list of dicts, each with at minimum "id" and "object" keys,
            following the OpenAI /v1/models response format.

        WHY: OpenAI-compatible clients (including M6/M7 frontend and external
             API consumers) call /v1/models to discover available models.
             This endpoint must exist for API compatibility.
        """
        model_id = self._config.llm.model if self._config.llm else "m5-qa"
        return [
            {
                "id": model_id,
                "object": "model",
            }
        ]

    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """
        WHAT: Return the health status of the QA engine and its components.

        Returns:
            dict with keys:
              - "status": "ok" if the engine is running.
              - "components": dict with sub-component statuses (llm, db).

        WHY: Load balancers, monitoring systems, and the M7 admin dashboard
             need to verify the engine is operational. This provides a simple
             health check without requiring external dependencies.
        """
        return {
            "status": "ok",
            "components": {
                "llm": "configured",
                "db": self._config.db_path,
            },
        }

    # ------------------------------------------------------------------
    # Conversation Management (delegates to ConversationManager)
    # ------------------------------------------------------------------

    async def list_conversations(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[ConversationSummary]:
        """
        WHAT: List a user's conversation history, newest first.
        WHY: Delegates to ConversationManager which queries the M5 SQLite DB.
        """
        return await self._conversations.list_conversations(
            user_id=user_id, limit=limit, offset=offset
        )

    async def get_conversation(
        self, conversation_id: str, user_id: str
    ) -> list[Message]:
        """
        WHAT: Retrieve all messages for a conversation.
        WHY: Delegates to ConversationManager with user_id verification
             to prevent cross-user conversation access.
        """
        return await self._conversations.get_conversation(
            conversation_id=conversation_id, user_id=user_id
        )

    async def delete_conversation(
        self, conversation_id: str, user_id: str
    ) -> bool:
        """
        WHAT: Delete a conversation and all its messages.
        WHY: Delegates to ConversationManager with user_id verification
             to prevent cross-user conversation access.
        """
        return await self._conversations.delete_conversation(
            conversation_id=conversation_id, user_id=user_id
        )

    async def rename_conversation(
        self, conversation_id: str, title: str
    ) -> bool:
        """
        WHAT: Rename a conversation by updating its title.
        WHY: Delegates to ConversationManager.rename_conversation().
        """
        return await self._conversations.rename_conversation(
            conversation_id=conversation_id, title=title
        )
