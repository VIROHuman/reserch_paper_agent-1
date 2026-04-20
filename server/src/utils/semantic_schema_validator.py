"""
Semantic Schema Validator (Step 10)

Validates references against their reference_type schema to ensure
semantic correctness before XML generation.
"""
import re
from typing import List, Tuple
from loguru import logger

from ..models.reference_models import Reference, ReferenceType
from .reference_classifier import ReferenceTagSchema


class SemanticSchemaValidator:
    """
    Validates references against semantic schemas based on reference type.
    
    This is a CRITICAL step that ensures references are semantically correct
    before XML generation. Invalid references are flagged, not auto-fixed.
    """
    
    def __init__(self):
        self.schema = ReferenceTagSchema()
    
    def validate(self, reference: Reference) -> Tuple[bool, List[str]]:
        """
        Validate a reference against its reference_type schema.
        
        Args:
            reference: Reference object to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        ref_type = reference.reference_type
        
        # Check 1: Reference type must not be UNKNOWN
        if ref_type == ReferenceType.UNKNOWN:
            errors.append("Reference type is UNKNOWN - cannot validate")
            return False, errors
        
        # Check 2: Required fields must be present
        required_fields = self._get_required_fields(ref_type)
        for field in required_fields:
            if not self._has_field(reference, field):
                errors.append(f"Required field '{field}' is missing for {ref_type.value}")
        
        # Check 3: Forbidden fields must not be present
        forbidden_fields = self._get_forbidden_fields(ref_type)
        for field in forbidden_fields:
            if self._has_field(reference, field):
                errors.append(f"Forbidden field '{field}' is present for {ref_type.value}")
        
        # Check 4: Type-specific field combinations
        type_errors = self._validate_type_specific_rules(reference, ref_type)
        errors.extend(type_errors)
        
        # Check 5: Field consistency
        consistency_errors = self._validate_field_consistency(reference, ref_type)
        errors.extend(consistency_errors)
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            logger.warning(f"Reference {reference.index} validation failed: {errors}")
        
        return is_valid, errors
    
    def _get_required_fields(self, ref_type: ReferenceType) -> List[str]:
        """Get required fields for a reference type"""
        required = {
            ReferenceType.JOURNAL_ARTICLE: ["title", "venue"],  # venue = journal
            ReferenceType.CONFERENCE_PAPER: ["title"],
            ReferenceType.BOOK: ["title"],
            ReferenceType.BOOK_CHAPTER: ["title"],
            ReferenceType.REPORT: ["title"],
        }
        return required.get(ref_type, [])
    
    def _get_forbidden_fields(self, ref_type: ReferenceType) -> List[str]:
        """Get forbidden fields for a reference type"""
        forbidden = {
            ReferenceType.JOURNAL_ARTICLE: ["publisher", "city", "conference_name"],
            ReferenceType.CONFERENCE_PAPER: ["volume", "issue", "venue"],  # venue should be conference_name
            ReferenceType.BOOK: ["volume", "issue", "article_number", "conference_name"],
            ReferenceType.BOOK_CHAPTER: ["volume", "issue", "article_number"],
            ReferenceType.REPORT: ["volume", "issue", "article_number", "conference_name"],
        }
        return forbidden.get(ref_type, [])
    
    def _has_field(self, reference: Reference, field: str) -> bool:
        """Check if reference has a field with a non-empty value"""
        value = getattr(reference, field, None)
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, list):
            return len(value) > 0
        return bool(value)
    
    def _validate_type_specific_rules(self, reference: Reference, ref_type: ReferenceType) -> List[str]:
        """Validate type-specific semantic rules"""
        errors = []
        
        if ref_type == ReferenceType.JOURNAL_ARTICLE:
            # Journal articles must have venue (journal name)
            if not reference.venue:
                errors.append("JOURNAL_ARTICLE must have venue (journal name)")
            # Journal articles should have volume OR issue OR pages
            if not (reference.volume or reference.issue or reference.pages or reference.article_number):
                errors.append("JOURNAL_ARTICLE should have volume, issue, pages, or article_number")
            # Journal articles cannot have publisher (unless it's a special case)
            if reference.publisher and not reference.venue:
                errors.append("JOURNAL_ARTICLE with publisher must also have venue")
        
        elif ref_type == ReferenceType.CONFERENCE_PAPER:
            # Conference papers should have conference_name or venue
            if not (reference.conference_name or reference.venue):
                errors.append("CONFERENCE_PAPER should have conference_name or venue")
            # Conference papers cannot have volume/issue
            if reference.volume or reference.issue:
                errors.append("CONFERENCE_PAPER cannot have volume or issue")
        
        elif ref_type == ReferenceType.BOOK:
            # Books should have publisher
            if not reference.publisher:
                errors.append("BOOK should have publisher")
            # Books cannot have volume/issue
            if reference.volume or reference.issue:
                errors.append("BOOK cannot have volume or issue")
        
        elif ref_type == ReferenceType.BOOK_CHAPTER:
            # Book chapters should have venue (book title)
            if not reference.venue:
                errors.append("BOOK_CHAPTER should have venue (book title)")
            # Book chapters should have pages
            if not reference.pages:
                errors.append("BOOK_CHAPTER should have pages")
            # Book chapters cannot have volume/issue
            if reference.volume or reference.issue:
                errors.append("BOOK_CHAPTER cannot have volume or issue")
        
        elif ref_type == ReferenceType.REPORT:
            # Reports should have publisher (institution)
            if not reference.publisher:
                errors.append("REPORT should have publisher (institution)")
            # Reports cannot have volume/issue
            if reference.volume or reference.issue:
                errors.append("REPORT cannot have volume or issue")
        
        return errors
    
    def _validate_field_consistency(self, reference: Reference, ref_type: ReferenceType) -> List[str]:
        """Validate field consistency and logical rules"""
        errors = []
        
        # DOI format validation
        if reference.doi:
            if reference.doi.startswith("http://") or reference.doi.startswith("https://"):
                errors.append("DOI should be normalized (no URL prefix)")
        
        # Year validation
        if reference.year:
            if reference.year < 1000 or reference.year > 2100:
                errors.append(f"Year {reference.year} is outside valid range")
        
        # Pages validation
        if reference.pages:
            # Pages should be in format "123-456" or "123"
            if not re.match(r'^\d+([-–—]\d+)?$', reference.pages):
                errors.append(f"Pages format invalid: '{reference.pages}'")
        
        # Authors validation
        if not reference.family_names and not reference.full_names:
            errors.append("Reference must have at least one author")
        
        # Title validation
        if reference.title:
            if len(reference.title.strip()) < 3:
                errors.append("Title is too short")
        
        return errors

