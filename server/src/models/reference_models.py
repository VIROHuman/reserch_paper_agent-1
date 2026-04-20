"""
Strongly-typed Reference data model for the redesigned pipeline.

This model enforces reference-type semantics and tracks provenance throughout
the processing pipeline.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class ReferenceType(str, Enum):
    """Reference type enumeration - exactly one type per reference"""
    JOURNAL_ARTICLE = "journal_article"
    CONFERENCE_PAPER = "conference_paper"
    BOOK = "book"
    BOOK_CHAPTER = "book_chapter"
    REPORT = "report"
    THESIS = "thesis"  # Thesis/Dissertation
    UNKNOWN = "unknown"  # Invalid/unclassifiable - flagged for review


class ConflictSeverity(str, Enum):
    """Conflict severity levels"""
    LOW = "low"  # Minor differences (e.g., capitalization)
    MEDIUM = "medium"  # Significant differences (e.g., year off by 1)
    HIGH = "high"  # Major conflicts (e.g., different titles)


class Conflict(BaseModel):
    """Represents a conflict between parsed and API data"""
    field: str
    parsed_value: Any
    api_value: Any
    severity: ConflictSeverity
    resolution: str  # "parsed_preferred", "api_preferred", "flagged"
    source: str  # Which API provided conflicting data


class Reference(BaseModel):
    """
    Strongly-typed Reference object that enforces semantic correctness.
    
    This model is used throughout the pipeline and ensures that:
    - Reference type is set BEFORE parsing
    - Fields match the reference type schema
    - Provenance is tracked for all fields
    - Conflicts are explicit
    """
    
    # Identity & Ordering
    index: int = Field(..., description="Original index in document")
    original_text: str = Field(..., description="Raw reference text from document")
    normalized_text: str = Field(..., description="Normalized reference text")
    
    # Classification (MANDATORY - set in Step 3)
    reference_type: ReferenceType = Field(..., description="Classified reference type")
    
    # Authors
    family_names: List[str] = Field(default_factory=list, description="Author surnames")
    given_names: List[str] = Field(default_factory=list, description="Author given names")
    full_names: List[str] = Field(default_factory=list, description="Full author names")
    
    # Temporal
    year: Optional[int] = Field(None, description="Publication year")
    
    # Content (type-dependent)
    title: Optional[str] = Field(None, description="Article/Chapter/Paper/Book title")
    venue: Optional[str] = Field(None, description="Journal/Conference/Book title (type-dependent)")
    
    # Journal-specific fields
    volume: Optional[str] = Field(None, description="Journal volume")
    issue: Optional[str] = Field(None, description="Journal issue")
    pages: Optional[str] = Field(None, description="Page range")
    article_number: Optional[str] = Field(None, description="Article number (alternative to pages)")
    
    # Book-specific fields
    publisher: Optional[str] = Field(None, description="Publisher name")
    city: Optional[str] = Field(None, description="Publication city")
    edition: Optional[str] = Field(None, description="Edition number")
    
    # Conference-specific fields
    conference_name: Optional[str] = Field(None, description="Conference/Event name")
    
    # Identifiers
    doi: Optional[str] = Field(None, description="DOI (normalized, no URL)")
    url: Optional[str] = Field(None, description="URL")
    
    # Metadata
    abstract: Optional[str] = Field(None, description="Abstract")
    
    # Quality & Provenance
    quality_score_before: float = Field(0.0, description="Quality score before enrichment")
    quality_score_after: float = Field(0.0, description="Quality score after enrichment")
    quality_improvement: float = Field(0.0, description="Quality improvement delta")
    
    enrichment_provenance: Dict[str, str] = Field(
        default_factory=dict,
        description="Field → API source mapping (e.g., 'doi': 'crossref')"
    )
    conflicts: List[Conflict] = Field(
        default_factory=list,
        description="List of conflicts between parsed and API data"
    )
    validation_errors: List[str] = Field(
        default_factory=list,
        description="Schema validation errors"
    )
    is_valid: bool = Field(False, description="Whether reference passes schema validation")
    
    # Processing metadata
    parser_used: str = Field("unknown", description="Parser used (NER, simple, etc.)")
    enrichment_used: bool = Field(False, description="Whether API enrichment was used")
    enrichment_sources: List[str] = Field(
        default_factory=list,
        description="List of APIs used for enrichment"
    )
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return self.dict(exclude_none=True)
    
    def get_venue_for_type(self) -> Optional[str]:
        """
        Get the appropriate venue field based on reference type.
        Returns journal, conference_name, or venue depending on type.
        """
        if self.reference_type == ReferenceType.JOURNAL_ARTICLE:
            return self.venue  # Journal name
        elif self.reference_type == ReferenceType.CONFERENCE_PAPER:
            return self.conference_name or self.venue  # Conference name
        elif self.reference_type == ReferenceType.BOOK:
            return None  # Books don't have venues
        elif self.reference_type == ReferenceType.BOOK_CHAPTER:
            return self.venue  # Book title
        else:
            return self.venue  # Fallback

