"""
Header normalization utilities for the SEATS application.

Provides functions for normalizing and matching column headers.
"""

import re
from typing import List, Optional, Dict, Tuple
from fuzzywuzzy import fuzz, process
import logging

logger = logging.getLogger(__name__)


def normalize_header(header: str) -> str:
    """
    Normalize a single header string.
    
    Args:
        header: Raw header string
        
    Returns:
        Normalized header string
    """
    if not header or not isinstance(header, str):
        return ""
    
    # Strip whitespace
    normalized = header.strip()
    
    # Convert to uppercase
    normalized = normalized.upper()
    
    # Replace spaces and special characters with underscores
    normalized = re.sub(r"[\s\-\.]+", "_", normalized)
    
    # Remove non-alphanumeric characters except underscores
    normalized = re.sub(r"[^A-Z0-9_]", "", normalized)
    
    # Remove multiple consecutive underscores
    normalized = re.sub(r"_+", "_", normalized)
    
    # Remove leading/trailing underscores
    normalized = normalized.strip("_")
    
    return normalized


def normalize_header_list(headers: List[str]) -> List[str]:
    """
    Normalize a list of headers.
    
    Args:
        headers: List of raw header strings
        
    Returns:
        List of normalized header strings
    """
    return [normalize_header(h) for h in headers]


def find_best_match(
    header: str,
    candidates: List[str],
    threshold: int = 80
) -> Optional[str]:
    """
    Find the best matching header from candidates using fuzzy matching.
    
    Args:
        header: Header to match
        candidates: List of candidate headers
        threshold: Minimum match score (0-100)
        
    Returns:
        Best matching candidate or None if no match above threshold
    """
    if not header or not candidates:
        return None
    
    # Normalize input
    normalized_header = normalize_header(header)
    
    # First try exact match
    if normalized_header in candidates:
        return normalized_header
    
    # Normalize candidates for comparison
    normalized_candidates = {normalize_header(c): c for c in candidates}
    
    if normalized_header in normalized_candidates:
        return normalized_candidates[normalized_header]
    
    # Fuzzy match
    try:
        result = process.extractOne(
            normalized_header,
            list(normalized_candidates.keys()),
            scorer=fuzz.ratio
        )
        
        if result and result[1] >= threshold:
            matched_normalized = result[0]
            return normalized_candidates.get(matched_normalized, matched_normalized)
        
    except Exception as e:
        logger.warning(f"Fuzzy matching failed: {e}")
    
    return None


def find_all_matches(
    header: str,
    candidates: List[str],
    threshold: int = 60,
    limit: int = 5
) -> List[Tuple[str, int]]:
    """
    Find all matching headers above threshold.
    
    Args:
        header: Header to match
        candidates: List of candidate headers
        threshold: Minimum match score (0-100)
        limit: Maximum number of matches to return
        
    Returns:
        List of (candidate, score) tuples
    """
    if not header or not candidates:
        return []
    
    normalized_header = normalize_header(header)
    
    try:
        results = process.extract(
            normalized_header,
            candidates,
            scorer=fuzz.ratio,
            limit=limit
        )
        
        return [(match, score) for match, score in results if score >= threshold]
        
    except Exception as e:
        logger.warning(f"Fuzzy matching failed: {e}")
        return []


def create_header_mapping(
    source_headers: List[str],
    target_headers: List[str],
    threshold: int = 80
) -> Dict[str, Optional[str]]:
    """
    Create a mapping from source headers to target headers.
    
    Args:
        source_headers: Source column headers
        target_headers: Expected target headers
        threshold: Minimum match score
        
    Returns:
        Dictionary mapping source headers to target headers
    """
    mapping = {}
    used_targets = set()
    
    for source in source_headers:
        best_match = None
        best_score = 0
        
        for target in target_headers:
            if target in used_targets:
                continue
            
            normalized_source = normalize_header(source)
            normalized_target = normalize_header(target)
            
            # Exact match
            if normalized_source == normalized_target:
                best_match = target
                best_score = 100
                break
            
            # Fuzzy match
            score = fuzz.ratio(normalized_source, normalized_target)
            if score > best_score and score >= threshold:
                best_match = target
                best_score = score
        
        if best_match:
            mapping[source] = best_match
            used_targets.add(best_match)
        else:
            mapping[source] = None
    
    return mapping


def validate_header_format(header: str) -> bool:
    """
    Validate that a header follows expected format.
    
    Args:
        header: Header to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not header or not isinstance(header, str):
        return False
    
    # Check length
    if len(header) > 100:
        return False
    
    # Check for invalid characters
    if re.search(r"[\x00-\x1f\x7f]", header):
        return False
    
    return True


def standardize_header(header: str, style: str = "upper_snake") -> str:
    """
    Standardize header to a specific style.
    
    Args:
        header: Header to standardize
        style: Target style (upper_snake, lower_snake, camel, pascal)
        
    Returns:
        Standardized header
    """
    # First normalize
    normalized = normalize_header(header)
    
    if style == "upper_snake":
        return normalized
    
    elif style == "lower_snake":
        return normalized.lower()
    
    elif style == "camel":
        parts = normalized.lower().split("_")
        return parts[0] + "".join(p.capitalize() for p in parts[1:])
    
    elif style == "pascal":
        parts = normalized.lower().split("_")
        return "".join(p.capitalize() for p in parts)
    
    else:
        return normalized


__all__ = [
    "normalize_header",
    "normalize_header_list",
    "find_best_match",
    "find_all_matches",
    "create_header_mapping",
    "validate_header_format",
    "standardize_header"
]
