"""
Quality scoring configuration for reference parsing
"""

# Quality scoring weights (should sum to 1.0)
QUALITY_WEIGHTS = {
    "title": 0.30,      # Most important - identifies the work
    "authors": 0.25,    # High importance - identifies creators
    "year": 0.15,       # Important for validation and context
    "journal": 0.15,    # Important for context and validation
    "doi": 0.08,        # Bonus points - provides unique identifier
    "pages": 0.03,      # Nice to have - location within publication
    "publisher": 0.02,  # Bonus - publication context
    "url": 0.02         # Bonus - accessibility
}

# Minimum quality thresholds
MIN_QUALITY_THRESHOLDS = {
    "enrichment_trigger": 0.80,    # Trigger API enrichment below this score
    "acceptable_quality": 0.55,    # Consider acceptable above this score
    "minimum_quality": 0.30        # Minimum score even with basic info
}

# Field length requirements (more lenient)
FIELD_LENGTH_REQUIREMENTS = {
    "title": {
        "excellent": 20,    # Full points
        "good": 10,         # High points
        "acceptable": 5     # Partial points
    },
    "journal": {
        "excellent": 10,    # Full points
        "good": 5,          # Partial points
        "acceptable": 3     # Minimum
    },
    "author_given_names": {
        "complete": 0.8,    # 80% of authors have given names
        "partial": 0.5,     # 50% of authors have given names
        "minimum": 0.2      # 20% of authors have given names
    }
}

# API enrichment strategy
API_ENRICHMENT_CONFIG = {
    "max_api_calls": 3,           # Maximum API calls per reference
    "timeout_per_call": 10,       # Seconds per API call
    "retry_attempts": 2,          # Retry failed API calls
    "aggressive_enrichment": True, # Always try to enrich if possible
    "preferred_sources": ["crossref", "openalex", "semantic_scholar"]  # Order of preference
}

# Parsing strategy configuration
PARSING_CONFIG = {
    "use_enhanced_parsing": True, # Use enhanced parsing strategies
    "fallback_to_simple": True,   # Fallback to simple parser if enhanced fails
    "combine_strategies": True,   # Combine multiple parsing strategies
    "use_grobid": True            # Use GROBID for PDF parsing (primary method)
}

# Quality improvement bonuses
QUALITY_BONUSES = {
    "doi_present": 0.08,
    "pages_present": 0.05,
    "publisher_present": 0.03,
    "url_present": 0.02,
    "abstract_present": 0.02,
    "multiple_authors": 0.05,     # Bonus for 2+ authors
    "complete_author_names": 0.03 # Bonus for complete given names
}
