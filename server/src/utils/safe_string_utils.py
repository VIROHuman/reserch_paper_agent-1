"""
Safe string utilities to prevent NoneType errors
"""
import re
from typing import Optional, Any


def safe_strip(value: Optional[str]) -> Optional[str]:
    """
    Safely strip a string value, returning None if value is None or not a string.
    
    Args:
        value: String value to strip (can be None)
        
    Returns:
        Stripped string or None
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    return value.strip() or None


def safe_get_str(value: Any, default: str = "") -> str:
    """
    Safely get string value with default.
    
    Args:
        value: Value to convert to string
        default: Default value if None or empty
        
    Returns:
        String value or default
    """
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    return str(value).strip() or default


# Strict DOI validation regex
DOI_REGEX = re.compile(r'^10\.\d{4,9}/[-._;()/:A-Z0-9]+$', re.IGNORECASE)


def is_valid_doi(candidate: Optional[str]) -> bool:
    """
    Validate DOI format using strict regex.
    Handles malformed DOIs with spaces and incorrect prefixes.
    
    Args:
        candidate: Potential DOI string
        
    Returns:
        True if valid DOI format, False otherwise
    """
    if not candidate:
        return False
    
    candidate = safe_strip(candidate)
    if not candidate:
        return False
    
    # AGGRESSIVE CLEANING: Handle malformed prefixes like ": //doi. org/" or ": //doi.org/"
    # Check for malformed patterns (with spaces) before cleaning
    if ": //doi" in candidate.lower() or ": //doi" in candidate.lower():
        # Extract DOI part starting from "10." (may still have spaces)
        doi_match = re.search(r'10\.\s*\d+/', candidate)
        if doi_match:
            candidate = candidate[doi_match.start():]
        else:
            # Try to find "10." anywhere
            ten_pos = candidate.find("10.")
            if ten_pos != -1:
                candidate = candidate[ten_pos:]
    
    # Remove all spaces (handles malformed DOIs with spaces)
    candidate = candidate.replace(" ", "")
    
    # Remove common DOI prefixes
    prefixes = [
        "http://dx.doi.org/",
        "https://dx.doi.org/",
        "http://doi.org/",
        "https://doi.org/",
        "doi:",
        "DOI:",
        "://doi.org/",  # Handle malformed ": //doi. org/" after space removal
    ]
    
    # Normalize prefix removal
    for prefix in prefixes:
        if candidate.lower().startswith(prefix.lower()):
            candidate = candidate[len(prefix):].strip()
            break
    
    # Remove trailing punctuation
    candidate = candidate.rstrip('.,;:')
    
    # Validate against strict regex
    return bool(DOI_REGEX.match(candidate))


def looks_like_article_number(value: Optional[str]) -> bool:
    """
    Check if value looks like an article number (e-number).
    
    Patterns:
    - e2401195
    - e2401195.
    - 13(27) (2024) e2401195
    - Starts with 'e' followed by digits
    
    Args:
        value: Potential article number
        
    Returns:
        True if looks like article number
    """
    if not value:
        return False
    
    value = safe_strip(value)
    if not value:
        return False
    
    # Check for e-number pattern: e followed by digits
    e_number_pattern = re.compile(r'^e\d+\.?$', re.IGNORECASE)
    if e_number_pattern.match(value):
        return True
    
    # Check if contains e-number pattern
    if re.search(r'\be\d+\.?', value, re.IGNORECASE):
        return True
    
    return False

