"""Document index backend implementations.

Exports:
    BaseDocumentIndex     -- abstract base (contracts compliance + lifecycle)
    MeilisearchIndex      -- Meilisearch BM25 (Personal mode default)
    ElasticsearchIndex    -- Elasticsearch 8.x (SaaS)
"""
from .base import BaseDocumentIndex
from .elasticsearch_index import ElasticsearchIndex
from .meilisearch_index import MeilisearchIndex

__all__ = ["BaseDocumentIndex", "MeilisearchIndex", "ElasticsearchIndex"]
