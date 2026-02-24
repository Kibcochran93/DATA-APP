"""
Header normalization utilities for the SEATS application.
"""
import re
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher

def normalize_header(header: str) -> str:
    """
    Normalize a single header string.
    
    Args:
        header: Header string to normalize
        
    Returns:
        Normalized header string
    """
    # Strip numeric prefixes (^\d+\s*)
    header = re.sub(r'^\d+\s*', '', header)
    # Remove trailing asterisks, hashes
    header = header.rstrip('*#')
    # Convert to UPPER_CASE_WITH_UNDERSCORES
    header = header.upper().replace(' ', '_')
    return header

def normalize_header_list(headers: List[str]) -> List[str]:
    """
    Normalize a list of header strings.
    
    Args:
        headers: List of header strings to normalize
        
    Returns:
        List of normalized header strings
    """
    return [normalize_header(h) for h in headers]

def find_best_match(target: str, candidates: List[str], threshold: float = 0.6) -> Optional[str]:
    """
    Find the best matching string from a list of candidates.
    
    Args:
        target: String to match
        candidates: List of candidate strings
        threshold: Minimum similarity score (0-1)
        
    Returns:
        Best matching string or None if no match above threshold
    """
    if not candidates:
        return None
        
    # Normalize target
    target = normalize_header(target)
    candidates = [normalize_header(c) for c in candidates]
    
    # Find best match
    best_score = 0
    best_match = None
    
    for candidate in candidates:
        score = SequenceMatcher(None, target, candidate).ratio()
        if score > best_score:
            best_score = score
            best_match = candidate
            
    return best_match if best_score >= threshold else None

def suggest_header_mappings(headers: List[str], expected_headers: List[str], threshold: float = 0.6) -> Dict[str, Tuple[str, float]]:
    """
    Suggest mappings between actual and expected headers.
    
    Args:
        headers: List of actual headers
        expected_headers: List of expected headers
        threshold: Minimum similarity score (0-1)
        
    Returns:
        Dictionary mapping actual headers to (suggested_match, score) tuples
    """
    suggestions = {}
    
    for header in headers:
        match = find_best_match(header, expected_headers, threshold)
        if match:
            score = SequenceMatcher(None, normalize_header(header), normalize_header(match)).ratio()
            suggestions[header] = (match, score)
            
    return suggestions

# Remove any duplicate logic from header_normalizer.py
# All header normalization should be done using normalize_header() 