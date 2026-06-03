"""
M5 QA Engine — Monitoring module.

WHAT: Provides runtime observability for the QA engine through:
      - MetricsCollector: records per-query latency, mode, and tier statistics
      - StructuredLogger: JSON-structured logging for query traceability

WHY: Production systems need visibility into usage patterns, performance
     bottlenecks, and error rates. This module provides the foundation
     for dashboards, alerting, and performance tuning.
"""

from m5_qa.monitoring.metrics import MetricsCollector, QueryMetrics
from m5_qa.monitoring.logger import StructuredLogger

__all__ = [
    "MetricsCollector",
    "QueryMetrics",
    "StructuredLogger",
]
