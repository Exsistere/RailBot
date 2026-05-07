"""
CheckPNRParamExtractor — deterministic mapper for CHECK_PNR_STATUS intent.

Reads pnr_number from immutable SemanticContext and maps it to tool params.
No LLM calls, no DB calls, no API calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.planner_extractors.base_extractor import BaseParamExtractor

if TYPE_CHECKING:
    from app.nlp.semantic_schema import SemanticContext


class CheckPNRParamExtractor(BaseParamExtractor):
    """Map SemanticContext -> params for CHECK_PNR_STATUS tool."""

    def extract(self, semantic_context: "SemanticContext") -> dict:
        if not semantic_context:
            return {"pnr_number": None}
        pnr = semantic_context.pnr_number.value if semantic_context.pnr_number else None
        return {"pnr_number": pnr}

