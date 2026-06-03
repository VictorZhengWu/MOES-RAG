"""
M5 QA Engine — Metrics Collector.

WHAT: Records per-query execution metrics (mode, latency, tier) and produces
      aggregated summaries for monitoring dashboards and performance analysis.

WHY: Operators need to understand usage patterns (which pipeline modes are
     most used), performance characteristics (average latency), and quality
     of service (tier distribution). The MetricsCollector provides an in-memory
     aggregation layer that can be extended to push metrics to external systems
     (Prometheus, Grafana, etc.) in later phases.
"""

import time
from dataclasses import dataclass, field


@dataclass
class QueryMetrics:
    """
    WHAT: A single query execution record with mode, latency, tier, and timestamp.

    WHY: Each query through the QA engine is recorded with its execution
         characteristics. This data feeds into aggregated summaries for
         monitoring dashboards and performance analysis. The timestamp enables
         time-series analysis (e.g., latency trends over the last hour).

    Attributes:
        mode: Pipeline mode used ("simple", "pipeline", "self_rag").
        latency_ms: End-to-end query latency in milliseconds.
        tier: User tier at time of query ("basic", "pro", "enterprise").
        timestamp: Unix epoch timestamp when the query was recorded.
    """

    mode: str
    """Pipeline mode: 'simple', 'pipeline', or 'self_rag'."""

    latency_ms: float
    """End-to-end query latency in milliseconds."""

    tier: str = "basic"
    """User tier level: 'basic', 'pro', or 'enterprise'."""

    timestamp: float = field(default_factory=time.time)
    """Unix epoch timestamp when the metric was recorded."""


class MetricsCollector:
    """
    WHAT: In-memory collector for query execution metrics with aggregation.

    Records each query as a QueryMetrics dataclass and provides get_summary()
    for aggregated statistics including total query count, average latency,
    and mode distribution.

    WHY: This is the lightweight, zero-dependency observability foundation.
         The in-memory list is sufficient for single-server deployments.
         For cluster deployments in Phase 3, this can be backed by a
         time-series database (Prometheus) or a message queue (Kafka)
         without changing the record_query() API.

    Usage:
        collector = MetricsCollector()
        collector.record_query(mode="simple", latency_ms=150.0, tier="basic")
        summary = collector.get_summary()
        # {'total_queries': 1, 'avg_latency_ms': 150.0, 'by_mode': {'simple': 1}}
    """

    def __init__(self):
        """
        WHAT: Initialize an empty metrics collector.
        WHY: The collector starts with zero records and accumulates data as
             queries are processed. No external configuration is needed.
        """
        self._records: list[QueryMetrics] = []

    def record_query(
        self,
        mode: str,
        latency_ms: float,
        tier: str = "basic",
    ) -> None:
        """
        WHAT: Record one query execution metric.
        WHY: Called by the QA engine after each query completes, regardless
             of success or failure. This ensures complete visibility into
             all query traffic, not just successful ones.

        Args:
            mode: Pipeline mode used ("simple", "pipeline", "self_rag").
            latency_ms: End-to-end query latency in milliseconds.
            tier: User tier level ("basic", "pro", "enterprise").
                  Defaults to "basic" for anonymous users.
        """
        record = QueryMetrics(
            mode=mode,
            latency_ms=latency_ms,
            tier=tier,
        )
        self._records.append(record)

    def get_summary(self) -> dict:
        """
        WHAT: Compute aggregated statistics from all recorded queries.

        Returns:
            dict with keys:
              - "total_queries" (int): Total number of recorded queries.
              - "avg_latency_ms" (float): Average latency rounded to 1 decimal.
                Only present if total_queries > 0.
              - "by_mode" (dict[str, int]): Count of queries per pipeline mode.
                Only present if total_queries > 0.

        WHY: Aggregated stats are more useful than raw records for dashboards.
             The summary is computed on-demand (not cached) so it always reflects
             the latest data. For high-throughput deployments, consider adding
             a caching layer in Phase 3.
        """
        if not self._records:
            return {"total_queries": 0}

        # Compute average latency from all recorded queries
        total_latency = sum(r.latency_ms for r in self._records)
        avg_latency = total_latency / len(self._records)

        # Compute mode distribution (count per pipeline mode)
        modes: dict[str, int] = {}
        for r in self._records:
            modes[r.mode] = modes.get(r.mode, 0) + 1

        return {
            "total_queries": len(self._records),
            "avg_latency_ms": round(avg_latency, 1),
            "by_mode": modes,
        }
