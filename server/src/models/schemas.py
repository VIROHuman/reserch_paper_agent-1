"""
Pydantic models for request/response data
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class Author(BaseModel):
    """Author information"""
    first_name: Optional[str] = Field(None, alias="fnm")
    surname: Optional[str] = Field(None, alias="surname")
    full_name: Optional[str] = None


class ReferenceData(BaseModel):
    """Reference data structure"""
    title: Optional[str] = None
    authors: List[Author] = []
    year: Optional[int] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    publisher: Optional[str] = None
    publication_type: Optional[str] = None  # journal, conference, book, etc.
    raw_text: Optional[str] = None  # Original reference text


class ValidationResult(BaseModel):
    """Result of reference validation"""
    is_valid: bool
    missing_fields: List[str] = []
    confidence_score: float = 0.0
    suggestions: Dict[str, Any] = {}
    warnings: List[str] = []


class ReferenceValidationRequest(BaseModel):
    """Request for reference validation"""
    references: List[str] = Field(..., description="List of reference texts to validate")
    validate_all: bool = Field(True, description="Whether to validate all references or stop at first error")


class ReferenceValidationResponse(BaseModel):
    """Response for reference validation"""
    processed_count: int
    total_count: int
    results: List[Dict[str, Any]] = []
    errors: List[str] = []


class TaggingRequest(BaseModel):
    """Request for reference tagging"""
    references: List[ReferenceData] = Field(..., description="List of validated reference data")
    style: str = Field("elsevier", description="Tagging style: elsevier, sage, or custom")


class TaggingResponse(BaseModel):
    """Response for reference tagging"""
    tagged_references: List[str] = []
    errors: List[str] = []


class APIResponse(BaseModel):
    """Generic API response"""
    success: bool
    message: str
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class CrossRefResponse(BaseModel):
    """CrossRef API response structure"""
    status: str
    message_type: str
    message: Dict[str, Any]


class OpenAlexResponse(BaseModel):
    """OpenAlex API response structure"""
    id: str
    title: str
    publication_year: Optional[int] = None
    authors: List[Dict[str, Any]] = []
    primary_location: Optional[Dict[str, Any]] = None
    doi: Optional[str] = None
    open_access: Optional[Dict[str, Any]] = None


class SemanticScholarResponse(BaseModel):
    """Semantic Scholar API response structure"""
    paperId: str
    title: str
    year: Optional[int] = None
    authors: List[Dict[str, Any]] = []
    venue: Optional[str] = None
    journal: Optional[Dict[str, Any]] = None
    doi: Optional[str] = None
    openAccessPdf: Optional[Dict[str, Any]] = None
