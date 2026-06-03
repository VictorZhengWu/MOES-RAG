"""
Tests for m5_qa.monitoring.metrics — MetricsCollector.

WHAT: Unit tests for the MetricsCollector class that records query execution
      metrics and produces aggregated summaries.

WHY: TDD ensures the collector correctly tracks latency, mode, and tier across
     multiple queries, and that edge cases (empty records) are handled properly.
"""

import time

import pytest

from m5_qa.monitoring.metrics import MetricsCollector, QueryMetrics


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMetricsCollector:
    """
    WHAT: Test suite for MetricsCollector — query recording and aggregation.
    WHY: The collector is the central monitoring point for all QA engine
         queries. It must correctly count queries, compute average latency,
         and break down usage by pipeline mode.
    """

    def test_record_and_summary(self):
        """
        WHAT: Record 3 queries and verify the summary has total_queries=3.
        WHY: The primary use case is tracking query volume with correct counts.
        """
        # Arrange: create collector and record 3 queries with different modes
        collector = MetricsCollector()
        collector.record_query(mode="simple", latency_ms=150.0, tier="basic")
        collector.record_query(mode="pipeline", latency_ms=320.0, tier="pro")
        collector.record_query(mode="self_rag", latency_ms=1200.0, tier="enterprise")

        # Act: get the aggregated summary
        summary = collector.get_summary()

        # Assert: total count is 3, average latency is computed correctly
        assert summary["total_queries"] == 3
        expected_avg = (150.0 + 320.0 + 1200.0) / 3
        assert summary["avg_latency_ms"] == round(expected_avg, 1)
        # Each mode should appear exactly once in by_mode distribution
        assert summary["by_mode"] == {
            "simple": 1,
            "pipeline": 1,
            "self_rag": 1,
        }

    def test_empty_summary(self):
        """
        WHAT: Verify get_summary returns total_queries=0 when no records exist.
        WHY: Before any queries are served, the metrics endpoint should return
             a valid (but empty) summary rather than crashing or returning None.
        """
        collector = MetricsCollector()

        summary = collector.get_summary()

        assert summary == {"total_queries": 0}

    def test_mode_distribution(self):
        """
        WHAT: Record 2 simple + 1 self_rag and verify by_mode counts are correct.
        WHY: Mode distribution helps operators understand pipeline usage patterns
             and optimize resource allocation. The counts must be exact.
        """
        collector = MetricsCollector()
        collector.record_query(mode="simple", latency_ms=100.0, tier="basic")
        collector.record_query(mode="simple", latency_ms=200.0, tier="basic")
        collector.record_query(mode="self_rag", latency_ms=800.0, tier="enterprise")

        summary = collector.get_summary()

        assert summary["total_queries"] == 3
        assert summary["by_mode"]["simple"] == 2
        assert summary["by_mode"]["self_rag"] == 1
        # pipeline was never used, should not be in the dict
        assert "pipeline" not in summary["by_mode"]

    def test_query_metrics_dataclass(self):
        """
        WHAT: Verify QueryMetrics dataclass stores all fields correctly.
        WHY: The dataclass is the internal record format. Field values must
             be exactly as provided by the record_query caller.
        """
        now = time.time()
        metrics = QueryMetrics(
            mode="pipeline",
            latency_ms=500.0,
            tier="pro",
            timestamp=now,
        )

        assert metrics.mode == "pipeline"
        assert metrics.latency_ms == 500.0
        assert metrics.tier == "pro"
        assert metrics.timestamp == now
