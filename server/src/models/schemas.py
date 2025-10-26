from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class Author(BaseModel):
    first_name: Optional[str] = Field(None, alias="fnm")
    surname: Optional[str] = Field(None, alias="surname")
    full_name: Optional[str] = None


class ReferenceData(BaseModel):
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
    publication_type: Optional[str] = None
    raw_text: Optional[str] = None


class ValidationResult(BaseModel):
    is_valid: bool
    missing_fields: List[str] = []
    confidence_score: float = 0.0
    suggestions: Dict[str, Any] = {}
    warnings: List[str] = []


class ReferenceValidationRequest(BaseModel):
    references: List[str] = Field(..., description="List of reference texts to validate")
    validate_all: bool = Field(True, description="Whether to validate all references or stop at first error")


class ReferenceValidationResponse(BaseModel):
    processed_count: int
    total_count: int
    results: List[Dict[str, Any]] = []
    errors: List[str] = []


class TaggingRequest(BaseModel):
    references: List[ReferenceData] = Field(..., description="List of validated reference data")
    style: str = Field("elsevier", description="Tagging style: elsevier, sage, or custom")


class TaggingResponse(BaseModel):
    tagged_references: List[str] = []
    errors: List[str] = []


class PDFUploadRequest(BaseModel):
    process_references: bool = True
    validate_all: bool = True
    paper_type: str = "auto"
    use_ml: bool = True


class PDFProcessingResponse(BaseModel):
    success: bool
    message: str
    data: Dict[str, Any]
    file_info: Dict[str, str]
    references_found: int
    processing_results: List[Dict[str, Any]]


class FieldAnalysis(BaseModel):
    """Analysis of a specific field"""
    value: Optional[Any] = None
    source: str
    confidence: float
    status: str
    original_value: Optional[Any] = None
    replacement_reason: Optional[str] = None
    conflict_details: Optional[Dict[str, Any]] = None


class FlaggingSummary(BaseModel):
    """Summary of flagging information"""
    missing_fields: List[str] = []
    replaced_fields: List[str] = []
    conflicted_fields: List[str] = []
    partial_fields: List[str] = []
    data_sources_used: List[str] = []


class FlaggingAnalysis(BaseModel):
    """Comprehensive flagging analysis"""
    extraction_status: str
    overall_confidence: float
    quality_score: float
    field_analysis: Dict[str, FieldAnalysis] = {}
    summary: FlaggingSummary
    processing_notes: List[str] = []
    recovery_suggestions: List[str] = []


class ComparisonAnalysis(BaseModel):
    """Detailed comparison between online and LLM data"""
    has_conflicts: bool = False
    conflicts: List[Dict[str, Any]] = []
    field_comparisons: Dict[str, Dict[str, Any]] = {}
    similarity_scores: Dict[str, float] = {}
    confidence_scores: Dict[str, float] = {}
    resolution_strategy: str = "online_preferred"


class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class JobStatus(BaseModel):
    """Job status for async processing"""
    job_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: int = 0
    current_step: str = ""
    message: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class JobSubmissionResponse(BaseModel):
    """Response for job submission"""
    success: bool
    message: str
    job_id: str
    status: str
    estimated_completion_time: Optional[int] = None  # seconds


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


class ArxivResponse(BaseModel):
    """ArXiv API response structure"""
    arxiv_id: str
    title: str
    authors: List[Dict[str, Any]] = []
    published: Optional[str] = None
    summary: Optional[str] = None
    categories: List[str] = []
    url: Optional[str] = None


class PubMedResponse(BaseModel):
    """PubMed API response structure"""
    pmid: str
    title: str
    authors: List[Dict[str, Any]] = []
    journal: Optional[str] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None
    publication_type: Optional[str] = None