"""
Semantic extractor: LLM-based entity extraction.

SemanticExtractor makes exactly ONE LLM call per user query to extract
generalized railway entities (stations, dates, classes, quotas, etc.).

This is the ONLY component responsible for LLM-based semantic understanding.
All downstream extractors are deterministic only.

CACHING HOOK:
- Placeholder methods _get_cached and _set_cached for future implementation.
- Currently no caching; future: could implement query hashing + Redis/DB lookup.
"""

import logging
from typing import Optional, Protocol, Callable

from app.nlp.semantic_schema import SemanticContext

logger = logging.getLogger(__name__)


class LLMClientLike(Protocol):
    def generate_json(self, prompt: str, system_prompt: str = "") -> dict: ...


class SemanticExtractor:
    """
    Extracts generalized semantic entities from user query via LLM.
    
    RESPONSIBILITIES:
    - Make ONE LLM call per query
    - Extract railway entities (stations, dates, classes, quotas, etc.)
    - Parse LLM response into SemanticContext
    - Handle LLM failures gracefully (return empty context)
    - Support optional caching (placeholder for now)
    
    NOT RESPONSIBILITIES:
    - Normalization (handled by canonicalize_semantic_context)
    - Tool-specific extraction (handled by intent-specific extractors)
    - Router/planner logic (handled by planner node)
    
    Usage:
        extractor = SemanticExtractor(llm_client_module, parser_func)
        semantic_context = extractor.extract("Delhi to Mumbai on June 15", intent_hint="SEARCH_TRAINS")
    """
    
    def __init__(
        self,
        llm_client: LLMClientLike,
        parser: Callable[[dict], SemanticContext],
        cache_enabled: bool = False,
    ):
        """
        Initialize semantic extractor.
        
        Args:
            llm_client: LLM client-like object/module (app.services.llm.client).
                        Must have generate_json(prompt, system_prompt) method.
            parser: Parser function parse_semantic_extraction(data: dict) -> SemanticContext
            cache_enabled: Enable caching hook (placeholder, no-op for now)
        """
        self.llm_client = llm_client
        self.parser_func = parser
        self.cache_enabled = cache_enabled
    
    def extract(
        self,
        query: str,
        intent_hint: Optional[str] = None
    ) -> SemanticContext:
        """
        Extract semantic entities from user query.
        
        Makes exactly ONE LLM call to extract railway entities.
        
        Args:
            query: User query text (e.g., "I want to go from Delhi to Mumbai on June 15")
            intent_hint: Optional intent classification result (e.g., "SEARCH_TRAINS")
                        Helps LLM focus extraction on relevant entities
        
        Returns:
            SemanticContext with extracted entities (immutable)
            On LLM failure, returns empty SemanticContext (all fields None)
        
        Flow:
            1. Check cache (if enabled) → return cached context if found
            2. Call LLM with semantic extraction prompt
            3. Parse LLM response into SemanticContext
            4. Store in cache (if enabled)
            5. Return SemanticContext
        """
        # Try cache lookup
        if self.cache_enabled:
            query_hash = self._compute_query_hash(query)
            cached = self._get_cached(query_hash)
            if cached is not None:
                logger.debug(f"Semantic extraction cache hit for query: {query[:50]}...")
                return cached
        
        try:
            # Call LLM
            logger.debug(f"Calling LLM for semantic extraction: {query[:50]}...")
            llm_response_dict = self._call_llm(query, intent_hint)
            
            # Parse response
            semantic_context = self._parse_response(llm_response_dict)
            
            # Cache if enabled
            if self.cache_enabled:
                self._set_cached(query_hash, semantic_context)
            
            return semantic_context
        
        except Exception as e:
            logger.warning(
                f"Semantic extraction LLM call failed: {e}. "
                f"Returning empty semantic context."
            )
            return SemanticContext.empty()
    
    def _call_llm(self, query: str, intent_hint: Optional[str] = None) -> dict:
        """
        Call LLM for semantic extraction.
        
        Args:
            query: User query text
            intent_hint: Optional intent hint for LLM
        
        Returns:
            Dict response from LLM (JSON)
        
        Raises:
            Exception: If LLM call fails
        """
        # Import prompts here to avoid circular imports
        from app.services.llm.prompts import (
            SEMANTIC_EXTRACTION_SYSTEM_PROMPT,
            SEMANTIC_EXTRACTION_USER_PROMPT_TEMPLATE,
        )
        from datetime import datetime
        
        # Build user prompt
        today = datetime.now().strftime("%Y-%m-%d")
        user_prompt = SEMANTIC_EXTRACTION_USER_PROMPT_TEMPLATE.format(
            query=query,
            today=today,
            intent_hint=intent_hint or "UNKNOWN"
        )
        
        # Call LLM using module-level function
        response_dict = self.llm_client.generate_json(
            prompt=user_prompt,
            system_prompt=SEMANTIC_EXTRACTION_SYSTEM_PROMPT,
        )
        
        return response_dict
    
    def _parse_response(self, llm_response_dict: dict) -> SemanticContext:
        """
        Parse LLM JSON response into SemanticContext.
        
        Args:
            llm_response_dict: Dict from LLM (already parsed from JSON)
        
        Returns:
            Parsed SemanticContext
        
        Raises:
            Exception: If parsing fails (caught by caller)
        """
        # Use parser function to convert dict to SemanticContext
        # Parser handles validation, normalization, etc.
        semantic_context = self.parser_func(llm_response_dict)
        
        return semantic_context
    
    def _compute_query_hash(self, query: str) -> str:
        """
        Compute hash of query for caching key.
        
        Placeholder for future caching implementation.
        
        Args:
            query: User query text
        
        Returns:
            Hash string
        """
        import hashlib
        return hashlib.sha256(query.encode()).hexdigest()
    
    def _get_cached(self, query_hash: str) -> Optional[SemanticContext]:
        """
        Retrieve cached semantic context by query hash.
        
        Placeholder method. No actual caching implemented.
        Future: Could implement Redis/DB lookup here.
        
        Args:
            query_hash: Query hash key
        
        Returns:
            Cached SemanticContext or None if not found
        """
        # Placeholder: No caching yet
        return None
    
    def _set_cached(self, query_hash: str, context: SemanticContext) -> None:
        """
        Store semantic context in cache by query hash.
        
        Placeholder method. No actual caching implemented.
        Future: Could implement Redis/DB storage here.
        
        Args:
            query_hash: Query hash key
            context: SemanticContext to cache
        """
        # Placeholder: No caching yet
        pass
