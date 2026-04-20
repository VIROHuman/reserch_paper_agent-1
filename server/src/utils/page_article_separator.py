"""
Page Range and Article Number Separation

Correctly separates page ranges from article numbers in reference strings.
Handles cases where BOTH pages and article numbers exist together.

Publisher-specific rules:
- Elsevier (10.1016/*): Single numeric tokens are article numbers
- Frontiers (10.3389/*): Always uses article numbers
"""
import re
from typing import Tuple, Optional
from loguru import logger

# Publisher DOI prefixes that use article numbers
ELSEVIER_PREFIX = "10.1016"
FRONTIERS_PREFIX = "10.3389"
ELSEVIER_OTHER_PREFIXES = ["10.1016", "10.1017", "10.1021"]  # Common Elsevier prefixes

# Article number patterns (e-numbers, article IDs)
ARTICLE_NUMBER_PATTERNS = [
    r'\be\d+\.?\b',  # e8, e2401195, e8.
    r'\barticle\s*#?\s*(\d+)',  # article #123
    r'\bart\.?\s*(\d+)',  # art. 123
]

# Page range pattern (numeric ranges)
PAGE_RANGE_PATTERN = re.compile(r'(\d{1,5})[-–—](\d{1,5})')
SINGLE_PAGE_PATTERN = re.compile(r'^\d{1,5}$')
# Article number pattern: long numeric strings (5+ digits) are likely article numbers
ARTICLE_NUMBER_NUMERIC_PATTERN = re.compile(r'^\d{5,}$')  # 5+ digits = article number


def is_elsevier_doi(doi: Optional[str]) -> bool:
    """Check if DOI is from Elsevier"""
    if not doi:
        return False
    return doi.startswith(ELSEVIER_PREFIX) or any(doi.startswith(prefix) for prefix in ELSEVIER_OTHER_PREFIXES)


def is_frontiers_doi(doi: Optional[str]) -> bool:
    """Check if DOI is from Frontiers"""
    if not doi:
        return False
    return doi.startswith(FRONTIERS_PREFIX)


def separate_pages_and_article_number(
    pages_string: str, 
    doi: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Separate page ranges from article numbers in a pages string.
    
    Handles cases like:
    - "1061-1077, e8" -> pages="1061-1077", article_number="e8"
    - "e2401195" -> pages=None, article_number="e2401195"
    - "1061-1077" -> pages="1061-1077", article_number=None
    - "1061-1077 e8" -> pages="1061-1077", article_number="e8"
    
    Args:
        pages_string: Raw pages string (may contain pages, article numbers, or both)
        
    Returns:
        Tuple of (pages_string, article_number_string)
        - pages_string: Normalized page range (e.g., "1061-1077") or None
        - article_number_string: Article number (e.g., "e8") or None
    """
    if not pages_string or not pages_string.strip():
        return None, None
    
    pages_string = pages_string.strip()
    
    # Remove common prefixes
    pages_string = re.sub(r'^(pp\.?|p\.?|pages?)\s*', '', pages_string, flags=re.IGNORECASE)
    pages_string = pages_string.strip()
    
    # Check for article number patterns first
    article_number = None
    
    # Pattern 1: e-number at the end (most common)
    e_number_match = re.search(r'\be\d+\.?$', pages_string, re.IGNORECASE)
    if e_number_match:
        article_number = e_number_match.group().rstrip('.')
        # Remove article number from pages string
        pages_string = pages_string[:e_number_match.start()].strip()
        # Remove trailing comma or space
        pages_string = re.sub(r'[,;]\s*$', '', pages_string).strip()
    
    # Pattern 2: e-number in the middle (e.g., "1061-1077, e8")
    if not article_number:
        e_number_match = re.search(r'\be\d+\.?', pages_string, re.IGNORECASE)
        if e_number_match:
            article_number = e_number_match.group().rstrip('.')
            # Split on the article number
            parts = re.split(r'\be\d+\.?', pages_string, flags=re.IGNORECASE, maxsplit=1)
            pages_string = parts[0].strip()
            # Remove trailing comma or space
            pages_string = re.sub(r'[,;]\s*$', '', pages_string).strip()
    
    # Pattern 3: Article number patterns
    if not article_number:
        for pattern in ARTICLE_NUMBER_PATTERNS:
            match = re.search(pattern, pages_string, re.IGNORECASE)
            if match:
                if match.groups():
                    article_number = match.group(1)
                else:
                    article_number = match.group().strip()
                # Remove article number from pages string
                pages_string = re.sub(pattern, '', pages_string, flags=re.IGNORECASE).strip()
                pages_string = re.sub(r'[,;]\s*$', '', pages_string).strip()
                break
    
    # Now extract page range from remaining string
    pages = None
    
    if pages_string:
        # Check for page range pattern (has hyphen)
        range_match = PAGE_RANGE_PATTERN.search(pages_string)
        if range_match:
            first_page = range_match.group(1)
            last_page = range_match.group(2)
            
            # Validate: last page should be >= first page
            try:
                first_num = int(first_page)
                last_num = int(last_page)
                if last_num >= first_num:
                    pages = f"{first_page}-{last_page}"
                else:
                    logger.warning(f"Invalid page range: {first_page}-{last_page} (last < first)")
            except ValueError:
                logger.warning(f"Non-numeric page range: {first_page}-{last_page}")
        elif SINGLE_PAGE_PATTERN.match(pages_string):
            # Single numeric token - check if it's an article number based on publisher
            # CRITICAL: For Elsevier and Frontiers, single numeric tokens are article numbers
            if is_elsevier_doi(doi) or is_frontiers_doi(doi):
                # Publisher uses article numbers - single token is article number
                if not article_number:
                    article_number = pages_string
                pages = None
                logger.info(f"Detected article number for {doi[:20]}: '{pages_string}' (single token, publisher uses article numbers)")
            elif ARTICLE_NUMBER_NUMERIC_PATTERN.match(pages_string):
                # Long numeric string (5+ digits) is likely article number
                if not article_number:
                    article_number = pages_string
                pages = None
                logger.info(f"Detected article number pattern (long numeric): '{pages_string}'")
            else:
                # Short numeric string (1-4 digits) - treat as page number
                pages = pages_string
        else:
            # Check if it looks like a malformed article number (e.g., "40258-018")
            if re.match(r'^\d{5,}-\d{3,}$', pages_string):
                # This is likely an article number, not pages
                if not article_number:
                    article_number = pages_string
                pages = None
                logger.info(f"Detected malformed article number pattern: {pages_string}")
            else:
                logger.warning(f"Could not parse pages string: {pages_string}")
    
    return pages, article_number


def extract_first_last_page(pages_string: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract first-page and last-page from a normalized page range string.
    
    Args:
        pages_string: Normalized page range (e.g., "1061-1077" or "123")
        
    Returns:
        Tuple of (first_page, last_page)
        - For ranges: ("1061", "1077")
        - For single pages: ("123", None)
        - For invalid: (None, None)
    """
    if not pages_string:
        return None, None
    
    pages_string = pages_string.strip()
    
    # Check for range
    if '-' in pages_string or '–' in pages_string or '—' in pages_string:
        parts = re.split(r'[-–—]', pages_string, 1)
        if len(parts) == 2:
            first_page = parts[0].strip()
            last_page = parts[1].strip()
            
            # Validate both are numeric
            if SINGLE_PAGE_PATTERN.match(first_page) and SINGLE_PAGE_PATTERN.match(last_page):
                return first_page, last_page
    
    # Single page
    if SINGLE_PAGE_PATTERN.match(pages_string):
        return pages_string, None
    
    return None, None

