"""
Strict Normalization and Validation Layer (Pre-XML Generation)

This module performs strict normalization and validation of reference fields
BEFORE XML generation to ensure publication-grade output.

Validations:
- Normalize page ranges into valid numeric first-page and last-page
- Reject or correct malformed page strings
- Enforce canonical DOI format
- Resolve conflicts between month-based and numeric issue values
- Prevent XML emission if core journal constraints are violated
"""
import re
from typing import Tuple, Optional, List, Dict, Any
from loguru import logger

from ..models.reference_models import Reference, ReferenceType


class StrictNormalizationValidator:
    """
    Strict normalization and validation layer that runs BEFORE XML generation.
    
    This ensures all fields are in canonical format and validates core constraints
    that would prevent valid XML generation.
    """
    
    # DOI pattern: 10.xxxx/xxxx (no punctuation except dots and slashes)
    DOI_PATTERN = re.compile(r'^10\.\d{4,}/[^\s]+$')
    
    # Page range patterns
    PAGE_RANGE_PATTERN = re.compile(r'^(\d+)[-–—](\d+)$')
    SINGLE_PAGE_PATTERN = re.compile(r'^\d+$')
    
    # Issue patterns
    NUMERIC_ISSUE_PATTERN = re.compile(r'^\d+$')
    MONTH_ISSUE_PATTERN = re.compile(r'^(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$', re.IGNORECASE)
    
    def normalize_and_validate(self, reference: Reference) -> Tuple[Reference, List[str], bool]:
        """
        Normalize and validate reference fields before XML generation.
        
        Args:
            reference: Reference object to normalize and validate
            
        Returns:
            Tuple of (normalized_reference, errors, can_generate_xml)
            - normalized_reference: Reference with normalized fields
            - errors: List of normalization/validation errors
            - can_generate_xml: Whether XML can be safely generated
        """
        errors = []
        can_generate_xml = True
        
        # Create a copy to avoid mutating original
        normalized_ref = reference.copy(deep=True)
        
        # 1. Normalize and validate DOI
        doi_errors, doi_valid = self._normalize_doi(normalized_ref)
        errors.extend(doi_errors)
        if not doi_valid and normalized_ref.doi:
            logger.warning(f"Reference {normalized_ref.index}: Invalid DOI format: {normalized_ref.doi}")
        
        # 2. Normalize and validate page ranges
        page_errors, pages_valid = self._normalize_pages(normalized_ref)
        errors.extend(page_errors)
        if not pages_valid:
            logger.warning(f"Reference {normalized_ref.index}: Invalid page format: {normalized_ref.pages}")
        
        # 3. Resolve issue conflicts (month vs numeric)
        issue_errors, issue_resolved = self._resolve_issue_conflict(normalized_ref)
        errors.extend(issue_errors)
        
        # 4. Validate core journal constraints
        journal_errors, journal_valid = self._validate_journal_constraints(normalized_ref)
        errors.extend(journal_errors)
        if not journal_valid:
            can_generate_xml = False
            logger.error(f"Reference {normalized_ref.index}: Core journal constraints violated - XML generation blocked")
        
        # 5. Normalize article numbers
        article_no_errors = self._normalize_article_number(normalized_ref)
        errors.extend(article_no_errors)
        
        # 6. Validate volume/issue consistency
        volume_issue_errors = self._validate_volume_issue_consistency(normalized_ref)
        errors.extend(volume_issue_errors)
        
        return normalized_ref, errors, can_generate_xml
    
    def _normalize_doi(self, reference: Reference) -> Tuple[List[str], bool]:
        """
        Normalize DOI to canonical format: 10.xxxx/xxxx (no punctuation except dots/slashes).
        
        Returns:
            (errors, is_valid)
        """
        errors = []
        
        if not reference.doi:
            return errors, True
        
        original_doi = reference.doi
        doi = original_doi.strip()
        
        # Remove common DOI prefixes
        prefixes = [
            "http://dx.doi.org/",
            "https://dx.doi.org/",
            "http://doi.org/",
            "https://doi.org/",
            "doi:",
            "DOI:",
        ]
        
        for prefix in prefixes:
            if doi.lower().startswith(prefix.lower()):
                doi = doi[len(prefix):].strip()
                break
        
        # Remove any remaining punctuation except dots and slashes
        # DOI format: 10.xxxx/xxxx
        # Allow: digits, dots, slashes, hyphens (in suffix)
        # Remove: spaces, commas, parentheses, etc.
        doi = re.sub(r'[^\d./-]', '', doi)
        
        # Validate DOI format
        if not self.DOI_PATTERN.match(doi):
            errors.append(f"DOI format invalid: '{original_doi}' → '{doi}' (expected format: 10.xxxx/xxxx)")
            # Try to fix common issues
            fixed_doi = self._attempt_doi_fix(doi)
            if fixed_doi and self.DOI_PATTERN.match(fixed_doi):
                doi = fixed_doi
                errors.append(f"DOI auto-corrected to: '{doi}'")
            else:
                return errors, False
        
        reference.doi = doi
        return errors, True
    
    def _attempt_doi_fix(self, doi: str) -> Optional[str]:
        """Attempt to fix common DOI format issues"""
        # Remove leading/trailing punctuation
        doi = doi.strip('.,;:()[]{}')
        
        # Ensure starts with "10."
        if not doi.startswith('10.'):
            # Try to find "10." in the string
            match = re.search(r'10\.\d+', doi)
            if match:
                doi = doi[match.start():]
        
        # Ensure has a slash
        if '/' not in doi:
            # Try to insert slash after prefix
            match = re.match(r'(10\.\d{4,})(.+)', doi)
            if match:
                doi = f"{match.group(1)}/{match.group(2)}"
        
        return doi if self.DOI_PATTERN.match(doi) else None
    
    def _normalize_pages(self, reference: Reference) -> Tuple[List[str], bool]:
        """
        Normalize page ranges into valid numeric first-page and last-page.
        Separate article numbers from page ranges.
        
        Returns:
            (errors, is_valid)
        """
        from .page_article_separator import separate_pages_and_article_number
        
        errors = []
        
        if not reference.pages:
            return errors, True
        
        original_pages = reference.pages
        pages_string = original_pages.strip()
        
        # Separate pages and article numbers
        pages, article_number = separate_pages_and_article_number(pages_string)
        
        # Set article number if found
        if article_number:
            reference.article_number = article_number
            errors.append(f"Extracted article number from pages string: '{article_number}'")
        
        # Normalize page range
        if pages:
            # Validate page range format
            if '-' in pages or '–' in pages or '—' in pages:
                # Split on any dash type
                parts = re.split(r'[-–—]', pages, 1)
                if len(parts) == 2:
                    first_page = parts[0].strip()
                    last_page = parts[1].strip()
                    
                    # Validate both are numeric
                    if not self.SINGLE_PAGE_PATTERN.match(first_page):
                        errors.append(f"Invalid first page: '{first_page}' (must be numeric)")
                        reference.pages = None
                        return errors, False
                    
                    if not self.SINGLE_PAGE_PATTERN.match(last_page):
                        errors.append(f"Invalid last page: '{last_page}' (must be numeric)")
                        reference.pages = None
                        return errors, False
                    
                    # Validate last_page >= first_page
                    try:
                        first_num = int(first_page)
                        last_num = int(last_page)
                        if last_num < first_num:
                            errors.append(f"Invalid page range: '{first_page}-{last_page}' (last page < first page)")
                            reference.pages = None
                            return errors, False
                        
                        # Store normalized pages
                        reference.pages = f"{first_num}-{last_num}"
                        return errors, True
                    except ValueError:
                        errors.append(f"Page range contains non-numeric values: '{original_pages}'")
                        reference.pages = None
                        return errors, False
                else:
                    errors.append(f"Invalid page range format: '{original_pages}'")
                    reference.pages = None
                    return errors, False
            else:
                # Single page
                if self.SINGLE_PAGE_PATTERN.match(pages):
                    reference.pages = pages
                    return errors, True
                else:
                    errors.append(f"Invalid page format: '{original_pages}' (must be numeric or range)")
                    reference.pages = None
                    return errors, False
        else:
            # No pages found - might be article number only
            if article_number:
                reference.pages = None
                return errors, True
            else:
                # Invalid format
                errors.append(f"Could not parse pages/article number from: '{original_pages}'")
                reference.pages = None
                return errors, False
    
    def _resolve_issue_conflict(self, reference: Reference) -> Tuple[List[str], bool]:
        """
        Resolve conflicts between month-based and numeric issue values.
        
        Returns:
            (errors, was_resolved)
        """
        errors = []
        resolved = False
        
        if not reference.issue:
            return errors, False
        
        issue = reference.issue.strip()
        
        # Check if issue contains both month and number
        # Pattern: "3 (January)" or "January (3)" or "3, January"
        month_match = self.MONTH_ISSUE_PATTERN.search(issue)
        number_match = self.NUMERIC_ISSUE_PATTERN.search(issue)
        
        if month_match and number_match:
            # Conflict: both month and number present
            # Prefer numeric value for consistency
            numeric_value = number_match.group(0)
            reference.issue = numeric_value
            errors.append(f"Issue conflict resolved: '{issue}' → '{numeric_value}' (preferred numeric over month)")
            resolved = True
        elif month_match and not number_match:
            # Only month present - convert to numeric if possible
            month_to_number = self._month_to_number(month_match.group(0))
            if month_to_number:
                reference.issue = str(month_to_number)
                errors.append(f"Issue converted from month: '{issue}' → '{month_to_number}'")
                resolved = True
            else:
                # Keep month as-is in issue field (Reference model doesn't have issue_month)
                # This is acceptable for XML generation
                errors.append(f"Issue contains month name: '{issue}' (keeping as-is)")
                resolved = True
        
        return errors, resolved
    
    def _month_to_number(self, month: str) -> Optional[int]:
        """Convert month name to number (1-12)"""
        month_map = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12,
        }
        return month_map.get(month.lower())
    
    def _validate_journal_constraints(self, reference: Reference) -> Tuple[List[str], bool]:
        """
        Validate core journal constraints that would prevent valid XML generation.
        
        Returns:
            (errors, is_valid)
        """
        errors = []
        
        if reference.reference_type != ReferenceType.JOURNAL_ARTICLE:
            # Only validate journal articles
            return errors, True
        
        # Constraint 1: Journal articles MUST have venue (journal name)
        if not reference.venue or not reference.venue.strip():
            errors.append("JOURNAL_ARTICLE must have venue (journal name) - XML generation blocked")
            return errors, False
        
        # Constraint 2: Journal articles MUST have title
        if not reference.title or not reference.title.strip():
            errors.append("JOURNAL_ARTICLE must have title - XML generation blocked")
            return errors, False
        
        # Constraint 3: Journal articles MUST have at least one author
        if not reference.family_names and not reference.full_names:
            errors.append("JOURNAL_ARTICLE must have at least one author - XML generation blocked")
            return errors, False
        
        # Constraint 4: Journal articles should have volume OR issue OR pages OR article_number OR DOI
        has_identifying_info = bool(
            reference.volume or
            reference.issue or
            reference.pages or
            reference.article_number or
            reference.doi
        )
        if not has_identifying_info:
            errors.append("JOURNAL_ARTICLE should have volume, issue, pages, article_number, or DOI - XML generation blocked")
            return errors, False
        
        # Constraint 5: Journal articles CANNOT have publisher (unless it's a special case)
        if reference.publisher and reference.publisher.strip():
            # This is a violation - publisher not allowed for journal articles
            errors.append(f"JOURNAL_ARTICLE cannot have publisher: '{reference.publisher}' - removing")
            reference.publisher = None
        
        # Constraint 6: Journal articles CANNOT have conference_name
        if reference.conference_name and reference.conference_name.strip():
            errors.append(f"JOURNAL_ARTICLE cannot have conference_name: '{reference.conference_name}' - removing")
            reference.conference_name = None
        
        return errors, True
    
    def _normalize_article_number(self, reference: Reference) -> List[str]:
        """Normalize article number format"""
        errors = []
        
        if not reference.article_number:
            return errors
        
        article_no = reference.article_number.strip()
        
        # Article numbers are typically numeric strings
        # Remove any non-numeric characters except hyphens
        normalized = re.sub(r'[^\d-]', '', article_no)
        
        if normalized != article_no:
            errors.append(f"Article number normalized: '{article_no}' → '{normalized}'")
            reference.article_number = normalized
        
        return errors
    
    def _validate_volume_issue_consistency(self, reference: Reference) -> List[str]:
        """Validate volume and issue consistency"""
        errors = []
        
        if reference.reference_type != ReferenceType.JOURNAL_ARTICLE:
            return errors
        
        # If both volume and issue exist, validate they're reasonable
        if reference.volume and reference.issue:
            try:
                volume_num = int(reference.volume)
                issue_num = int(reference.issue) if self.NUMERIC_ISSUE_PATTERN.match(reference.issue) else None
                
                if issue_num is not None:
                    # Issue should typically be <= 12 (monthly) or reasonable range
                    if issue_num > 20:
                        errors.append(f"Unusual issue number: {issue_num} (may be incorrect)")
                    
                    # Volume should be positive
                    if volume_num <= 0:
                        errors.append(f"Invalid volume number: {volume_num} (must be positive)")
            except ValueError:
                pass  # Non-numeric values handled elsewhere
        
        return errors
    
    def extract_page_range(self, pages: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract first-page and last-page from page range string.
        
        Args:
            pages: Page range string (e.g., "123-456", "123")
            
        Returns:
            Tuple of (first_page, last_page) or (page, None) for single page
        """
        if not pages:
            return None, None
        
        pages = pages.strip()
        
        # Remove prefixes
        pages = re.sub(r'^(pp\.?|p\.?|pages?)\s*', '', pages, flags=re.IGNORECASE)
        pages = pages.strip()
        
        # Check for range
        if '-' in pages or '–' in pages or '—' in pages:
            parts = re.split(r'[-–—]', pages, 1)
            if len(parts) == 2:
                first_page = parts[0].strip()
                last_page = parts[1].strip()
                
                # Validate both are numeric
                if self.SINGLE_PAGE_PATTERN.match(first_page) and self.SINGLE_PAGE_PATTERN.match(last_page):
                    return first_page, last_page
        
        # Single page
        if self.SINGLE_PAGE_PATTERN.match(pages):
            return pages, None
        
        return None, None

