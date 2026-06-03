"""
M5 QA Engine — Structured Logger.

WHAT: Provides structured JSON logging for query events in the QA engine.
      Each log entry is a single-line JSON object for easy ingestion by
      log aggregation systems (ELK, Loki, CloudWatch, etc.).

WHY: Unstructured text logs are difficult to query and aggregate. JSON-structured
     logs enable precise filtering (e.g., "show all self_rag queries with
     latency > 1000ms") and automated alerting. The single-line format is
     required by most log shippers for correct parsing.
"""

import json
import logging


# Module-level logger instance — used by QAEngine and pipeline functions.
# WHY: A shared logger ensures consistent log format across all M5 components
#      and avoids the overhead of creating a new logger for each query.
_logger = logging.getLogger("m5_qa")


class StructuredLogger:
    """
    WHAT: Static helper for emitting structured JSON log entries.

    All methods are static because the logger has no state — it's a thin
    formatting wrapper around Python's logging module. This keeps the
    API simple: callers don't need to instantiate or manage a logger object.

    WHY: Structured logging is critical for production observability.
         JSON format enables:
         - Filtering by user_id, mode, or latency thresholds
         - Aggregation in log analysis tools (ELK, Loki)
         - Automated alerting on error events
         - Audit trails for compliance (who asked what, when)
    """

    @staticmethod
    def log_query(
        user_id: str,
        query: str,
        mode: str,
        latency_ms: float,
        token_count: int,
    ) -> None:
        """
        WHAT: Log a completed query event as a single-line JSON object.

        Only the first 100 characters of the query are logged (query_preview)
        to keep log entries compact while still providing enough context for
        debugging and audit purposes.

        Args:
            user_id: The user who submitted the query.
            query: The full query text (only first 100 chars are logged).
            mode: Pipeline mode used ("simple", "pipeline", "self_rag").
            latency_ms: End-to-end query latency in milliseconds.
            token_count: Total tokens consumed (prompt + completion).

        WHY: Each query must be traceable for debugging, performance analysis,
             and compliance auditing. The query_preview truncation prevents
             log bloat from very long queries while retaining enough context
             to identify the query topic.
        """
        _logger.info(
            json.dumps(
                {
                    "event": "query",
                    "user_id": user_id,
                    "mode": mode,
                    "latency_ms": round(latency_ms, 1),
                    "token_count": token_count,
                    "query_preview": query[:100],
                },
                ensure_ascii=False,
            )
        )

    @staticmethod
    def log_error(
        user_id: str,
        query: str,
        error: str,
        mode: str = "unknown",
    ) -> None:
        """
        WHAT: Log a query that resulted in an error.

        Args:
            user_id: The user who submitted the query.
            query: The full query text (first 100 chars logged).
            error: The error message or exception string.
            mode: Pipeline mode attempted (default "unknown" if failure
                  occurred before mode selection).

        WHY: Error logs are essential for detecting and diagnosing production
             issues. Including the mode helps identify whether errors are
             concentrated in a specific pipeline (e.g., self_rag LLM timeouts).
        """
        _logger.error(
            json.dumps(
                {
                    "event": "query_error",
                    "user_id": user_id,
                    "mode": mode,
                    "error": error,
                    "query_preview": query[:100],
                },
                ensure_ascii=False,
            )
        )
