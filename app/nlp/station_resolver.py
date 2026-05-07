"""
Resolvers for canonical entity normalization.

Centralized responsibility for all entity normalization:
- Station names → station codes
- Train class names → standard abbreviations
- Quota names → standard abbreviations

All normalization happens HERE, not in prompts or extractors.

This enables:
1. Single source of truth for entity mappings
2. Easy future extension (DB lookups, API calls)
3. Consistent normalization across all tools
4. Easy mocking/testing
"""

from typing import Optional, Dict


class StationResolver:
    """
    Resolves station names/aliases to canonical station codes.
    
    Supports:
    - Case-insensitive lookup ("mumbai" or "MUMBAI" → "CSTM")
    - Common aliases ("Mumbai Central" → "CSTM")
    - Returns None if unresolved (downstream handles)
    
    Usage:
        resolver = StationResolver(station_mapping)
        code = resolver("mumbai")  # → "CSTM"
    """
    
    def __init__(self, station_mapping: Dict[str, str]):
        """
        Initialize resolver with station mapping dict.
        
        Args:
            station_mapping: Dict mapping normalized station names/aliases to codes.
                            Keys should be lowercase for case-insensitive matching.
                            Values should be uppercase station codes (e.g., "CSTM").
        """
        self.station_mapping = station_mapping
    
    def __call__(self, station_text: Optional[str]) -> Optional[str]:
        """
        Resolve station text to canonical station code.
        
        Args:
            station_text: Station name or alias (e.g., "mumbai", "Mumbai Central")
        
        Returns:
            Canonical station code (e.g., "CSTM") or None if unresolved
        """
        if not station_text:
            return None
        
        candidate = station_text.strip()
        if not candidate:
            return None

        # Lookup in mapping (alias -> code)
        normalized = candidate.lower()
        resolved = self.station_mapping.get(normalized)
        if resolved:
            return resolved

        # Pass-through: if LLM already returned a code-like value (e.g., NDLS),
        # keep it so canonicalization doesn't discard it.
        # Station codes are typically 2-5 alphanumeric uppercase strings.
        if candidate.isalnum() and 2 <= len(candidate) <= 5:
            return candidate.upper()

        return None


class TrainClassResolver:
    """
    Resolves train class names to canonical abbreviations.
    
    Supports:
    - Case-insensitive lookup ("sleeper" or "SLEEPER" → "SL")
    - Common aliases ("3AC" → "3A")
    - Returns None if unresolved
    
    Canonical classes: SL, 3A, 2A, 1A, CC, EC, 2S
    """
    
    def __init__(self, class_mapping: Dict[str, str]):
        """
        Initialize resolver with class mapping dict.
        
        Args:
            class_mapping: Dict mapping normalized class names/aliases to codes.
                          Keys should be lowercase.
                          Values should be uppercase (e.g., "SL", "3A").
        """
        self.class_mapping = class_mapping
    
    def __call__(self, class_text: Optional[str]) -> Optional[str]:
        """
        Resolve class text to canonical abbreviation.
        
        Args:
            class_text: Class name or alias (e.g., "sleeper", "3AC")
        
        Returns:
            Canonical class code (e.g., "SL") or None if unresolved
        """
        if not class_text:
            return None
        
        # Normalize
        normalized = class_text.strip().lower()
        
        # Lookup
        return self.class_mapping.get(normalized, None)


class QuotaResolver:
    """
    Resolves quota names to canonical abbreviations.
    
    Supports:
    - Case-insensitive lookup ("tatkal" → "TQ")
    - Common aliases ("Tatkal" → "TQ")
    - Returns None if unresolved
    
    Canonical quotas: GN (General), TQ (Tatkal), PT (Premium Tatkal), LD (Ladies)
    """
    
    def __init__(self, quota_mapping: Dict[str, str]):
        """
        Initialize resolver with quota mapping dict.
        
        Args:
            quota_mapping: Dict mapping normalized quota names to codes.
                          Keys should be lowercase.
                          Values should be uppercase (e.g., "GN", "TQ").
        """
        self.quota_mapping = quota_mapping
    
    def __call__(self, quota_text: Optional[str]) -> Optional[str]:
        """
        Resolve quota text to canonical abbreviation.
        
        Args:
            quota_text: Quota name or alias (e.g., "tatkal", "Tatkal")
        
        Returns:
            Canonical quota code (e.g., "TQ") or None if unresolved
        """
        if not quota_text:
            return None
        
        # Normalize
        normalized = quota_text.strip().lower()
        
        # Lookup
        return self.quota_mapping.get(normalized, None)


# Default mappings (used in dependencies.py)
DEFAULT_STATION_MAPPING: Dict[str, str] = {
    # North India
    "new delhi": "NDLS",
    "delhi": "NDLS",
    "delhi central": "NDLS",
    "new delhi central": "NDLS",
    
    # Mumbai/Maharashtra
    "mumbai": "CSTM",
    "mumbai central": "CSTM",
    "mumbai cst": "CSTM",
    "cst": "CSTM",
    "bombay": "CSTM",
    "bombay central": "CSTM",
    
    "surat": "ST",
    "surat station": "ST",

    # Add more stations as needed
}

DEFAULT_TRAIN_CLASS_MAPPING: Dict[str, str] = {
    # Sleeper
    "sleeper": "SL",
    "sl": "SL",
    
    # AC classes
    "3ac": "3A",
    "3a": "3A",
    "third ac": "3A",
    "third": "3A",
    
    "2ac": "2A",
    "2a": "2A",
    "second ac": "2A",
    
    "1ac": "1A",
    "1a": "1A",
    "first ac": "1A",
    "first": "1A",
    
    # Chair cars
    "cc": "CC",
    "chair": "CC",
    "chair car": "CC",
    
    # Executive chair
    "ec": "EC",
    "executive": "EC",
    "executive chair": "EC",
    
    # 2nd sitting
    "2s": "2S",
    "second sitting": "2S",
    "sitting": "2S",
}

DEFAULT_QUOTA_MAPPING: Dict[str, str] = {
    # General
    "gn": "GN",
    "general": "GN",
    
    # Tatkal
    "tq": "TQ",
    "tatkal": "TQ",
    
    # Premium Tatkal
    "pt": "PT",
    "premium tatkal": "PT",
    "premium": "PT",
    
    # Ladies
    "ld": "LD",
    "ladies": "LD",
}
