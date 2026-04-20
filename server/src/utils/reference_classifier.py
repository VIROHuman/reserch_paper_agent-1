"""
Reference Type Classifier for XML Generation

This module classifies references into semantic types and defines
allowed tag schemas for each type to ensure publication-grade XML output.
"""
import re
from typing import Dict, Any, Optional, Set, List, Tuple
from enum import Enum
from loguru import logger

from .safe_string_utils import safe_strip


class ReferenceType(Enum):
    """Reference type enumeration"""
    JOURNAL_ARTICLE = "journal_article"
    BOOK = "book"
    CONFERENCE_PAPER = "conference_paper"
    BOOK_CHAPTER = "book_chapter"
    REPORT = "report"
    THESIS = "thesis"  # Thesis/Dissertation
    UNKNOWN = "unknown"  # For invalid/unclassifiable references


class ReferenceTypeClassifier:
    """
    Classifies references into semantic types based on extracted fields.
    
    Classification rules (in priority order):
    1. JOURNAL_ARTICLE: Has journal + (volume OR issue OR pages)
    2. BOOK_CHAPTER: Has "In " prefix or editors field + pages
    3. CONFERENCE_PAPER: Has conference/event title (ebtl) + publisher
    4. BOOK: Has publisher + city, no journal
    5. REPORT: Has publisher but minimal other fields
    """
    
    # Keywords that indicate conference papers
    CONFERENCE_KEYWORDS = [
        r'\bproceedings\b',
        r'\bconference\b',
        r'\bsymposium\b',
        r'\bworkshop\b',
        r'\bmeeting\b',
        r'\bPICMET\b',
        r'\bISPIM\b',
        r'\bASEE\b',
    ]
    
    # Keywords that indicate book chapters
    BOOK_CHAPTER_KEYWORDS = [
        r'\bIn\b',  # "In Book Title"
        r'\bedited by\b',
        r'\beditor\b',
        r'\bEds?\b',
    ]
    
    # Keywords that indicate reports
    REPORT_KEYWORDS = [
        r'\breport\b',
        r'\btechnical report\b',
        r'\bworking paper\b',
        r'\boccasional paper\b',
        r'\bwhite paper\b',
    ]
    
    def classify_from_text(self, normalized_text: str) -> ReferenceType:
        """
        Classify reference type from normalized text (Step 3).
        Uses strong heuristics before parsing.
        
        Args:
            normalized_text: Normalized reference text
            
        Returns:
            ReferenceType enum value
        """
        text_lower = normalized_text.lower()
        
        # Rule 1: CONFERENCE_PAPER (highest priority - most specific)
        # Look for conference keywords
        conference_indicators = [
            r'\bproceedings\b',
            r'\bconference\b',
            r'\bsymposium\b',
            r'\bworkshop\b',
            r'\bmeeting\b',
            r'\bPICMET\b',
            r'\bISPIM\b',
            r'\bASEE\b',
            r'\bIEEE\s+.*\s+conference\b',
            r'\bACM\s+.*\s+conference\b',
        ]
        if any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in conference_indicators):
            return ReferenceType.CONFERENCE_PAPER
        
        # Rule 2: BOOK_CHAPTER
        # Look for "In " prefix or editor indicators
        book_chapter_indicators = [
            r'^\s*In\s+',  # Starts with "In "
            r'\bedited\s+by\b',
            r'\beditor\b',
            r'\bEds?\.?\s*$',  # Ends with "Ed." or "Eds."
            r'\bpp\.\s*\d+',  # Has "pp. 123" pattern
        ]
        if any(re.search(pattern, normalized_text, re.IGNORECASE) for pattern in book_chapter_indicators):
            return ReferenceType.BOOK_CHAPTER
        
        # Rule 3: THESIS (before REPORT - more specific)
        # Look for thesis/dissertation indicators
        thesis_indicators = [
            r'\bthesis\b',
            r'\bdissertation\b',
            r'\bPhD\b',
            r'\bPh\.D\.',
            r'\bMaster\s+thesis\b',
            r'\bDoctoral\s+dissertation\b',
            r'\bUniversity.*\d{4}',  # "University, 2011" pattern
            r'\b\w+\s+University,\s*\d{4}',  # "Zhejiang University, 2011"
        ]
        # Check if publisher contains "University" and no journal
        if re.search(r'\bUniversity\b', normalized_text, re.IGNORECASE):
            # Check it's not a journal article (no volume/issue patterns)
            has_journal_indicators = any(re.search(pattern, normalized_text, re.IGNORECASE) 
                                       for pattern in [
                                           r'\bvol\.?\s*\d+',
                                           r'\bvolume\s+\d+',
                                           r'\b\d+\s*\(\d+\)',
                                           r'\bno\.?\s*\d+',
                                       ])
            if not has_journal_indicators:
                return ReferenceType.THESIS
        
        if any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in thesis_indicators):
            return ReferenceType.THESIS
        
        # Rule 4: REPORT (enhanced with report codes and research organizations)
        # Look for report keywords, report codes, and research organizations
        report_indicators = [
            r'\breport\b',
            r'\btechnical\s+report\b',
            r'\bworking\s+paper\b',
            r'\boccasional\s+paper\b',
            r'\bwhite\s+paper\b',
            r'\bTR-\d+',  # Technical report number
            r'\bNKS-\d+',  # NKS report code
            r'\bIAEA-\w+',  # IAEA report code
            r'\bDOE/\w+',  # DOE report code
            r'\bANL-\d+',  # Argonne National Lab
            r'\bORNL-\w+',  # Oak Ridge National Lab
            r'\bPNNL-\w+',  # Pacific Northwest National Lab
            r'\bResearch\s+Report\b',
            r'\bSafety\s+Report\b',
            r'\bProgress\s+Report\b',
        ]
        
        # Research organizations that publish reports
        research_orgs = [
            r'\bDOE\b',  # Department of Energy
            r'\bNKS\b',  # Nordic Nuclear Safety Research
            r'\bIAEA\b',  # International Atomic Energy Agency
            r'\bOECD\b.*\bNEA\b',  # OECD Nuclear Energy Agency
            r'\bArgonne\s+National\s+Laboratory\b',
            r'\bOak\s+Ridge\s+National\s+Laboratory\b',
            r'\bPacific\s+Northwest\s+National\s+Laboratory\b',
            r'\bLawrence\s+Berkeley\s+National\s+Laboratory\b',
            r'\bSandia\s+National\s+Laboratories\b',
            r'\bLos\s+Alamos\s+National\s+Laboratory\b',
        ]
        
        # Check for report indicators
        if any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in report_indicators):
            return ReferenceType.REPORT
        
        # Check for research organizations (only if no journal indicators)
        has_journal_indicators = any(re.search(pattern, normalized_text, re.IGNORECASE) 
                                   for pattern in [
                                       r'\bvol\.?\s*\d+',
                                       r'\bvolume\s+\d+',
                                       r'\b\d+\s*\(\d+\)',
                                       r'\bno\.?\s*\d+',
                                   ])
        if not has_journal_indicators:
            if any(re.search(pattern, normalized_text, re.IGNORECASE) for pattern in research_orgs):
                return ReferenceType.REPORT
        
        # Rule 5: JOURNAL_ARTICLE
        # Look for volume/issue patterns: "vol. 15", "15(3)", "15:3", etc.
        journal_indicators = [
            r'\bvol\.?\s*\d+',  # "vol. 15" or "vol 15"
            r'\bvolume\s+\d+',
            r'\bv\.?\s*\d+',
            r'\b\d+\s*\(\d+\)',  # "15(3)" pattern
            r'\b\d+\s*:\s*\d+',  # "15:3" pattern
            r'\bno\.?\s*\d+',  # "no. 3" or "no 3"
            r'\bissue\s+\d+',
            r'\bpp\.\s*\d+[-–]\d+',  # "pp. 123-456"
            r'\bp\.\s*\d+[-–]\d+',  # "p. 123-456"
        ]
        if any(re.search(pattern, normalized_text, re.IGNORECASE) for pattern in journal_indicators):
            return ReferenceType.JOURNAL_ARTICLE
        
        # Rule 6: BOOK
        # Has publisher patterns but no journal indicators
        publisher_indicators = [
            r'\b(?:Published|Publisher|Pub\.|Press)\s+by\b',
            r'\b(?:Springer|Elsevier|Wiley|MIT|Harvard|Oxford|Cambridge)\s+Press\b',
            r'\b(?:New\s+York|London|Boston|Cambridge|Princeton):\s*',  # City: Publisher pattern
        ]
        if any(re.search(pattern, normalized_text, re.IGNORECASE) for pattern in publisher_indicators):
            # Check it's not a conference or report
            if not any(re.search(pattern, text_lower, re.IGNORECASE) 
                      for pattern in conference_indicators + report_indicators):
                return ReferenceType.BOOK
        
        # Rule 7: Fallback - minimal classification
        # If we see "Journal" or "J." in text, likely journal article
        if re.search(r'\bjournal\b|\bJ\.\s+[A-Z]', normalized_text, re.IGNORECASE):
            return ReferenceType.JOURNAL_ARTICLE
        
        # Default: UNKNOWN (will be flagged for review)
        logger.warning(f"Could not classify reference from text: '{normalized_text[:100]}...'")
        return ReferenceType.UNKNOWN
    
    def classify(self, parsed_ref: Dict[str, Any]) -> ReferenceType:
        """
        Classify a parsed reference into exactly one reference type.
        
        IMPORTANT: This should be called AFTER normalization to avoid NoneType errors.
        
        Args:
            parsed_ref: Normalized parsed reference dictionary
            
        Returns:
            ReferenceType enum value
        """
        # Use safe_strip to prevent NoneType errors
        journal = safe_strip(parsed_ref.get("journal")) or ""
        title = safe_strip(parsed_ref.get("title")) or ""
        publisher = safe_strip(parsed_ref.get("publisher")) or ""
        volume = safe_strip(parsed_ref.get("volume")) or ""
        issue = safe_strip(parsed_ref.get("issue")) or ""
        pages = safe_strip(parsed_ref.get("pages")) or ""
        url = safe_strip(parsed_ref.get("url")) or ""
        doi = safe_strip(parsed_ref.get("doi")) or ""
        
        # Check for book chapter indicators
        title_lower = title.lower()
        journal_lower = journal.lower() if journal else ""
        
        # Rule 1: JOURNAL_ARTICLE
        # Must have journal AND at least one of: volume, issue, pages
        if journal and (volume or issue or pages):
            return ReferenceType.JOURNAL_ARTICLE
        
        # Rule 2: BOOK_CHAPTER
        # Has "In " prefix or editors field, typically has pages
        if any(re.search(pattern, title_lower, re.IGNORECASE) for pattern in self.BOOK_CHAPTER_KEYWORDS):
            if pages or publisher:
                return ReferenceType.BOOK_CHAPTER
        
        # Rule 3: CONFERENCE_PAPER
        # Has conference keywords in title/journal OR has ebtl-like structure
        if any(re.search(pattern, title_lower + " " + journal_lower, re.IGNORECASE) 
               for pattern in self.CONFERENCE_KEYWORDS):
            if publisher or pages:
                return ReferenceType.CONFERENCE_PAPER
        
        # Rule 4: THESIS (before BOOK - more specific)
        # Publisher contains "University" and no journal
        if publisher and "university" in publisher.lower() and not journal:
            return ReferenceType.THESIS
        
        # Check title for thesis indicators
        if any(re.search(pattern, title_lower, re.IGNORECASE) for pattern in [
            r'\bthesis\b',
            r'\bdissertation\b',
            r'\bPhD\b',
            r'\bPh\.D\.',
        ]):
            return ReferenceType.THESIS
        
        # Rule 5: REPORT (check before BOOK - more specific)
        # Check for report codes in title (e.g., NKS-281, IAEA-TECDOC-1234)
        report_code_patterns = [
            r'\bNKS-\d+',
            r'\bIAEA-\w+',
            r'\bDOE/\w+',
            r'\bANL-\d+',
            r'\bORNL-\w+',
            r'\bPNNL-\w+',
            r'\bTR-\d+',
        ]
        if any(re.search(pattern, title, re.IGNORECASE) for pattern in report_code_patterns):
            return ReferenceType.REPORT
        
        # Check for report keywords in title or journal
        if any(re.search(pattern, title_lower, re.IGNORECASE) for pattern in self.REPORT_KEYWORDS):
            return ReferenceType.REPORT
        
        # Check journal for report indicators
        if journal:
            journal_lower = journal.lower()
            if any(keyword in journal_lower for keyword in ['research', 'report', 'safety']):
                return ReferenceType.REPORT
        
        # Check publisher for research organizations
        if publisher:
            publisher_lower = publisher.lower()
            research_orgs = ['doe', 'nks', 'iaea', 'oecd', 'nea', 'argonne', 'oak ridge', 'pacific northwest', 
                           'lawrence berkeley', 'sandia', 'los alamos', 'national laboratory', 'national lab']
            if any(org in publisher_lower for org in research_orgs):
                return ReferenceType.REPORT
        
        # Rule 6: BOOK
        # Has publisher + city, no journal
        if publisher and not journal:
            return ReferenceType.BOOK
        
        # Rule 7: Fallback classification
        # If we have journal but no volume/issue/pages, still classify as journal article
        if journal:
            return ReferenceType.JOURNAL_ARTICLE
        
        # If we have publisher but no other indicators, check for thesis first
        if publisher and "university" in publisher.lower():
            return ReferenceType.THESIS
        
        # Otherwise assume book
        if publisher:
            return ReferenceType.BOOK
        
        # Default: unknown (will be flagged as invalid)
        logger.warning(f"Could not classify reference: title='{title[:50]}...', journal='{journal}', publisher='{publisher}'")
        return ReferenceType.UNKNOWN


class ReferenceTagSchema:
    """
    Defines allowed tag schemas for each reference type.
    Prevents semantic errors by enforcing strict tag usage rules.
    """
    
    # Allowed tags for each reference type
    SCHEMAS = {
        ReferenceType.JOURNAL_ARTICLE: {
            "required_tags": {"atl", "stl"},  # Article title, Source/Journal title
            "allowed_tags": {
                "atl",      # Article title (REQUIRED)
                "stl",      # Source/Journal title (REQUIRED)
                "vol",      # Volume
                "iss",      # Issue
                "first-page", "last-page",  # Pages
                "atlno",    # Article number (alternative to pages)
                "doi",      # DOI
                "url",      # URL
            },
            "forbidden_tags": {"btl", "ebtl", "pub", "city", "edn"}  # Book tags not allowed
        },
        
        ReferenceType.BOOK: {
            "required_tags": {"btl"},  # Book title
            "allowed_tags": {
                "btl",      # Book title (REQUIRED)
                "pub",      # Publisher
                "city",     # City
                "edn",      # Edition
                "doi",      # DOI
                "url",      # URL
                "first-page", "last-page",  # Pages (for book sections)
            },
            "forbidden_tags": {"atl", "stl", "vol", "iss", "ebtl"}  # Journal tags not allowed
        },
        
        ReferenceType.CONFERENCE_PAPER: {
            "required_tags": {"atl"},  # Paper title
            "allowed_tags": {
                "atl",      # Paper title (REQUIRED)
                "ebtl",     # Event/Conference title
                "pub",      # Publisher (conference organizer)
                "first-page", "last-page",  # Pages
                "doi",      # DOI
                "url",      # URL
            },
            "forbidden_tags": {"btl", "stl", "vol", "iss", "city"}  # Journal/book tags not allowed
        },
        
        ReferenceType.BOOK_CHAPTER: {
            "required_tags": {"atl"},  # Chapter title
            "allowed_tags": {
                "atl",      # Chapter title (REQUIRED)
                "ebtl",     # Book title (in which chapter appears)
                "pub",      # Publisher
                "city",     # City
                "first-page", "last-page",  # Pages
                "doi",      # DOI
                "url",      # URL
            },
            "forbidden_tags": {"btl", "stl", "vol", "iss"}  # Journal tags not allowed
        },
        
        ReferenceType.REPORT: {
            "required_tags": {"atl"},  # Report title (use atl, not btl)
            "allowed_tags": {
                "atl",      # Report title (REQUIRED)
                "pub",      # Publisher/Institution (REQUIRED for reports)
                "msc3",     # Miscellaneous (for report numbers, dates)
                "doi",      # DOI
                "url",      # URL
                # Pages are OPTIONAL for reports (not required)
                "first-page", "last-page",  # Pages (optional)
            },
            "forbidden_tags": {"btl", "stl", "vol", "iss", "ebtl", "city"}  # Journal/book tags not allowed
        },
        
        ReferenceType.THESIS: {
            "required_tags": {"atl"},  # Thesis title
            "allowed_tags": {
                "atl",      # Thesis title (REQUIRED)
                "pub",      # University/Institution (REQUIRED)
                "doi",      # DOI (if available)
                "url",      # URL (if available)
            },
            "forbidden_tags": {"btl", "stl", "vol", "iss", "ebtl", "first-page", "last-page", "atlno", "city"}  # Journal/book tags not allowed
        },
        
        ReferenceType.UNKNOWN: {
            "required_tags": set(),
            "allowed_tags": set(),  # No tags allowed - will be flagged
            "forbidden_tags": set()
        }
    }
    
    @classmethod
    def get_allowed_tags(cls, ref_type: ReferenceType) -> Set[str]:
        """Get allowed tags for a reference type"""
        return cls.SCHEMAS.get(ref_type, {}).get("allowed_tags", set())
    
    @classmethod
    def get_required_tags(cls, ref_type: ReferenceType) -> Set[str]:
        """Get required tags for a reference type"""
        return cls.SCHEMAS.get(ref_type, {}).get("required_tags", set())
    
    @classmethod
    def get_forbidden_tags(cls, ref_type: ReferenceType) -> Set[str]:
        """Get forbidden tags for a reference type"""
        return cls.SCHEMAS.get(ref_type, {}).get("forbidden_tags", set())
    
    @classmethod
    def is_tag_allowed(cls, ref_type: ReferenceType, tag: str) -> bool:
        """Check if a tag is allowed for a reference type"""
        allowed = cls.get_allowed_tags(ref_type)
        return tag in allowed
    
    @classmethod
    def validate_schema(cls, ref_type: ReferenceType, used_tags: Set[str]) -> Tuple[bool, List[str]]:
        """
        Validate that used tags conform to the schema.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        if ref_type == ReferenceType.UNKNOWN:
            errors.append("Reference type is UNKNOWN - cannot generate valid XML")
            return False, errors
        
        allowed_tags = cls.get_allowed_tags(ref_type)
        forbidden_tags = cls.get_forbidden_tags(ref_type)
        required_tags = cls.get_required_tags(ref_type)
        
        # Check for forbidden tags
        for tag in used_tags:
            if tag in forbidden_tags:
                errors.append(f"Tag '<{tag}>' is forbidden for {ref_type.value}")
            elif tag not in allowed_tags:
                errors.append(f"Tag '<{tag}>' is not allowed for {ref_type.value}")
        
        # Check for missing required tags
        for tag in required_tags:
            if tag not in used_tags:
                errors.append(f"Required tag '<{tag}>' is missing for {ref_type.value}")
        
        return len(errors) == 0, errors


def normalize_journal_title(journal: Optional[str], api_journal: Optional[str] = None) -> str:
    """
    Normalize journal title, preferring API-provided casing.
    
    Args:
        journal: Journal title from parsing
        api_journal: Journal title from API (preferred for casing)
        
    Returns:
        Normalized journal title
    """
    from .safe_string_utils import safe_strip
    
    # Prefer API journal title if available (better casing)
    if api_journal:
        return safe_strip(api_journal) or ""
    
    if journal:
        return safe_strip(journal) or ""
    
    return ""


def normalize_doi(doi: str) -> str:
    """
    Normalize DOI format with strict validation and aggressive cleaning.
    Handles malformed DOIs with spaces and incorrect prefixes.
    Ensures consistent DOI representation (e.g., removes http://dx.doi.org/ prefix).
    REJECTS invalid DOIs (e.g., article numbers mislabeled as DOIs).
    
    Args:
        doi: Raw DOI string
        
    Returns:
        Normalized DOI (e.g., "10.1038/s41591-023-02456-7") or empty string if invalid
    """
    from .safe_string_utils import safe_strip, is_valid_doi
    
    if not doi:
        return ""
    
    original_doi = doi
    doi = safe_strip(doi) or ""
    if not doi:
        return ""
    
    # AGGRESSIVE CLEANING: Handle malformed prefixes like ": //doi. org/" or ": //doi.org/"
    # Check for malformed patterns (with spaces) before cleaning
    if ": //doi" in doi.lower() or ": //doi" in doi.lower():
        # Extract DOI part starting from "10." (may still have spaces)
        doi_match = re.search(r'10\.\s*\d+/', doi)
        if doi_match:
            doi = doi[doi_match.start():]
        else:
            # Try to find "10." anywhere
            ten_pos = doi.find("10.")
            if ten_pos != -1:
                doi = doi[ten_pos:]
    
    # Remove all spaces (handles malformed DOIs with spaces)
    doi = doi.replace(" ", "")
    
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
    
    for prefix in prefixes:
        if doi.lower().startswith(prefix.lower()):
            doi = doi[len(prefix):]
            break
    
    doi = safe_strip(doi) or ""
    
    # Remove trailing punctuation
    doi = doi.rstrip('.,;:')
    
    # STRICT VALIDATION: Reject if not valid DOI format
    if not is_valid_doi(doi):
        logger.warning(f"Invalid DOI format rejected: '{original_doi}' → cleaned: '{doi}'")
        return ""  # Return empty string for invalid DOIs
    
    return doi

