"""
Quality Scorer (Step 9)

Computes quality scores for references before and after enrichment.
Tracks quality improvement delta for explainability.
"""
from typing import Dict, Any
from loguru import logger

from ..models.reference_models import Reference, ReferenceType


class QualityScorer:
    """
    Computes quality scores for references.
    
    Quality is based on:
    - Presence of required fields
    - Completeness of metadata
    - Field confidence scores
    """
    
    # Field weights for quality scoring
    FIELD_WEIGHTS = {
        "title": 0.20,
        "authors": 0.20,
        "year": 0.10,
        "doi": 0.30,
        "venue": 0.20,  # Journal, conference, or book title
    }
    
    def score(self, reference: Reference) -> float:
        """
        Compute quality score for a reference.
        
        Args:
            reference: Reference object to score
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        score = 0.0
        
        # Title (required for all types)
        if reference.title and len(reference.title.strip()) > 3:
            score += self.FIELD_WEIGHTS["title"]
        
        # Authors (required for all types)
        if reference.family_names or reference.full_names:
            score += self.FIELD_WEIGHTS["authors"]
        
        # Year
        if reference.year and 1000 <= reference.year <= 2100:
            score += self.FIELD_WEIGHTS["year"]
        
        # DOI (highly valuable)
        if reference.doi and reference.doi.strip():
            score += self.FIELD_WEIGHTS["doi"]
        
        # Venue (type-dependent)
        venue_score = self._score_venue(reference)
        score += venue_score * self.FIELD_WEIGHTS["venue"]
        
        # Type-specific bonuses
        type_bonus = self._score_type_specific(reference)
        score += type_bonus
        
        return min(score, 1.0)
    
    def _score_venue(self, reference: Reference) -> float:
        """Score venue completeness based on reference type"""
        ref_type = reference.reference_type
        
        if ref_type == ReferenceType.JOURNAL_ARTICLE:
            return 1.0 if reference.venue else 0.0
        elif ref_type == ReferenceType.CONFERENCE_PAPER:
            return 1.0 if (reference.conference_name or reference.venue) else 0.0
        elif ref_type == ReferenceType.BOOK:
            return 1.0 if reference.publisher else 0.5  # Publisher is venue-like
        elif ref_type == ReferenceType.BOOK_CHAPTER:
            return 1.0 if reference.venue else 0.0  # Book title
        elif ref_type == ReferenceType.REPORT:
            return 1.0 if reference.publisher else 0.5  # Institution is venue-like
        else:
            return 0.0
    
    def _score_type_specific(self, reference: Reference) -> float:
        """Score type-specific fields"""
        bonus = 0.0
        ref_type = reference.reference_type
        
        if ref_type == ReferenceType.JOURNAL_ARTICLE:
            # Volume or issue or pages
            if reference.volume or reference.issue:
                bonus += 0.05
            if reference.pages or reference.article_number:
                bonus += 0.05
        
        elif ref_type == ReferenceType.CONFERENCE_PAPER:
            # Pages
            if reference.pages:
                bonus += 0.05
            # Publisher (conference organizer)
            if reference.publisher:
                bonus += 0.05
        
        elif ref_type == ReferenceType.BOOK:
            # City
            if reference.city:
                bonus += 0.05
            # Edition
            if reference.edition:
                bonus += 0.05
        
        elif ref_type == ReferenceType.BOOK_CHAPTER:
            # Pages (required)
            if reference.pages:
                bonus += 0.10
        
        return min(bonus, 0.20)  # Cap bonus at 0.20


