"""
M5 QA Engine - Marine & Offshore Expert System.

The brain of the system: receives user questions, selects pipeline mode
based on user tier, orchestrates retrieval (M3 semantic + M4 knowledge graph),
and generates answers with source citations via LLM.

Three operating modes:
  - simple:    M3 retrieval → LLM generation (Basic tier, 4K context)
  - pipeline:  M3+M4 parallel → fusion + citations → LLM (Pro tier, 8K context)
  - self_rag:  Iterative retrieval with quality checks (Enterprise tier, 16K context)
"""

from m5_qa.core.config import LLMBackend, QAConfig
from m5_qa.core.engine import QAEngine

__all__ = ["QAEngine", "QAConfig", "LLMBackend"]
__version__ = "0.1.0"
