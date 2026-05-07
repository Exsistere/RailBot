"""
Shared Context Module — Central working memory for collaborative multi-tool agent system.

This module implements a unified shared context that flows through the entire
workflow, enabling tools to collaborate through cross-tool memory sharing.

Components:
  - SharedContext: Central immutable/shared structured object (semantic memory)
  - SharedContextExtractor: LLM-based query understanding (one call per query)
  - Merger: Safe merging of tool memory_updates into SharedContext
"""

from app.shared_context.models import SharedContext, MemoryUpdate
from app.shared_context.extractor import SharedContextExtractor
from app.shared_context.merger import merge_shared_context

__all__ = [
    "SharedContext",
    "MemoryUpdate",
    "SharedContextExtractor",
    "merge_shared_context",
]
