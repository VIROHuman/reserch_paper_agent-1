"""
Comprehensive flagging system for reference extraction tracking
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class FieldStatus(Enum):
    """Status of individual fields"""
    EXTRACTED = "extracted"           
    REPLACED = "replaced"            
    MISSING = "missing"               
    CONFLICTED = "conflicted"         
    PARTIAL = "partial"                 


class ExtractionStatus(Enum):
    """Overall reference extraction status"""
    COMPLETE = "complete"             
    PARTIAL = "partial"              
    FAILED = "failed"                 
    SKIPPED = "skipped"              


class DataSource(Enum):
    """Data source attribution"""
    OLLAMA = "ollama"                
    SIMPLE_PARSER = "simple_parser"  
    CROSSREF = "crossref"            
    OPENALEX = "openalex"            
    SEMANTIC_SCHOLAR = "semantic_scholar" 
    DOAJ = "doaj"                    
    DOI_METADATA = "doi_metadata"    
    UNKNOWN = "unknown"              


@dataclass
class FieldInfo:
    """Information about a specific field"""
    value: Any
    source: DataSource
    confidence: float
    status: FieldStatus
    original_value: Optional[Any] = None
    replacement_reason: Optional[str] = None
    conflict_details: Optional[Dict[str, Any]] = None


@dataclass
class ReferenceFlags:
    """Comprehensive flagging information for a reference"""
    extraction_status: ExtractionStatus
    overall_confidence: float
    field_flags: Dict[str, FieldInfo]
    missing_fields: List[str]
    replaced_fields: List[str]
    conflicted_fields: List[str]
    partial_fields: List[str]
    data_sources_used: List[DataSource]
    quality_score: float
    processing_notes: List[str]
    recovery_suggestions: List[str]


class ReferenceFlaggingSystem:
    """Comprehensive flagging system for reference extraction"""
    
    def __init__(self):
        self.critical_fields = ["title", "family_names", "year"]
        
        self.important_fields = ["journal", "doi", "pages", "publisher"]
        
        self.optional_fields = ["abstract", "url", "volume", "issue"]
        
        self.field_weights = {
            "title": 0.25,
            "family_names": 0.20,
            "year": 0.15,
            "journal": 0.15,
            "doi": 0.10,
            "pages": 0.05,
            "publisher": 0.05,
            "abstract": 0.03,
            "url": 0.02
        }
        
        logger.info("Reference Flagging System initialized")
    
    def analyze_reference_extraction(
        self,
        original_parsed: Dict[str, Any],
        final_result: Dict[str, Any],
        api_enrichment_data: Optional[Dict[str, Any]] = None,
        doi_metadata: Optional[Dict[str, Any]] = None,
        conflict_analysis: Optional[Dict[str, Any]] = None
    ) -> ReferenceFlags:
        field_flags = {}
        missing_fields = []
        replaced_fields = []
        conflicted_fields = []
        partial_fields = []
        data_sources_used = []
        processing_notes = []
        recovery_suggestions = []
        
        primary_source = self._determine_primary_source(final_result)
        data_sources_used.append(primary_source)
        
        all_fields = set(list(original_parsed.keys()) + list(final_result.keys()))
        if api_enrichment_data:
            all_fields.update(api_enrichment_data.keys())
        if doi_metadata:
            all_fields.update(doi_metadata.keys())
        
        for field in all_fields:
            field_info = self._analyze_field_extraction(
                field,
                original_parsed,
                final_result,
                api_enrichment_data,
                doi_metadata,
                conflict_analysis
            )
            
            if field_info:
                field_flags[field] = field_info
                
                if field_info.status == FieldStatus.MISSING:
                    missing_fields.append(field)
                elif field_info.status == FieldStatus.REPLACED:
                    replaced_fields.append(field)
                elif field_info.status == FieldStatus.CONFLICTED:
                    conflicted_fields.append(field)
                elif field_info.status == FieldStatus.PARTIAL:
                    partial_fields.append(field)
                
                if field_info.source not in data_sources_used:
                    data_sources_used.append(field_info.source)
        
        extraction_status = self._determine_extraction_status(
            missing_fields, partial_fields, final_result
        )
        
        overall_confidence = self._calculate_overall_confidence(field_flags)
        quality_score = self._calculate_quality_score(field_flags, final_result)
        
        processing_notes = self._generate_processing_notes(
            extraction_status, missing_fields, replaced_fields, conflicted_fields
        )
        recovery_suggestions = self._generate_recovery_suggestions(
            missing_fields, partial_fields, conflicted_fields
        )
        
        flags = ReferenceFlags(
            extraction_status=extraction_status,
            overall_confidence=overall_confidence,
            field_flags=field_flags,
            missing_fields=missing_fields,
            replaced_fields=replaced_fields,
            conflicted_fields=conflicted_fields,
            partial_fields=partial_fields,
            data_sources_used=data_sources_used,
            quality_score=quality_score,
            processing_notes=processing_notes,
            recovery_suggestions=recovery_suggestions
        )
        
        return flags
    
    def _determine_primary_source(self, final_result: Dict[str, Any]) -> DataSource:
        """Determine the primary data source based on parsing method used"""
        parser_used = final_result.get("parser_used", "unknown")
        
        if parser_used == "ollama":
            return DataSource.OLLAMA
        elif parser_used == "simple":
            return DataSource.SIMPLE_PARSER
        else:
            return DataSource.UNKNOWN
    
    def _analyze_field_extraction(
        self,
        field: str,
        original_parsed: Dict[str, Any],
        final_result: Dict[str, Any],
        api_enrichment_data: Optional[Dict[str, Any]],
        doi_metadata: Optional[Dict[str, Any]],
        conflict_analysis: Optional[Dict[str, Any]]
    ) -> Optional[FieldInfo]:
        """Analyze how a specific field was extracted and processed"""
        
        original_value = original_parsed.get(field)
        final_value = final_result.get(field)
        
        if not final_value:
            return FieldInfo(
                value=None,
                source=DataSource.UNKNOWN,
                confidence=0.0,
                status=FieldStatus.MISSING
            )
        
        source, status, confidence = self._determine_field_source_and_status(
            field, original_value, final_value, api_enrichment_data, doi_metadata, conflict_analysis
        )
        
        conflict_details = None
        if conflict_analysis and field in [c.get("field") for c in conflict_analysis.get("conflicts", [])]:
            conflict_details = self._extract_conflict_details(field, conflict_analysis)
            if not conflict_details:
                status = FieldStatus.CONFLICTED
        
        replacement_reason = None
        if status == FieldStatus.REPLACED and original_value != final_value:
            replacement_reason = f"Replaced by {source.value} data for better quality/completeness"
        
        return FieldInfo(
            value=final_value,
            source=source,
            confidence=confidence,
            status=status,
            original_value=original_value,
            replacement_reason=replacement_reason,
            conflict_details=conflict_details
        )
    
    def _determine_field_source_and_status(
        self,
        field: str,
        original_value: Any,
        final_value: Any,
        api_enrichment_data: Optional[Dict[str, Any]],
        doi_metadata: Optional[Dict[str, Any]],
        conflict_analysis: Optional[Dict[str, Any]]
    ) -> Tuple[DataSource, FieldStatus, float]:
        """Determine the source, status, and confidence for a field"""
        
        if doi_metadata and field in doi_metadata and doi_metadata[field]:
            doi_value = doi_metadata[field]
            if doi_value != original_value:
                return DataSource.DOI_METADATA, FieldStatus.REPLACED, 0.95
            else:
                return DataSource.DOI_METADATA, FieldStatus.EXTRACTED, 0.95
        
        if api_enrichment_data and field in api_enrichment_data and api_enrichment_data[field]:
            api_value = api_enrichment_data[field]
            if api_value != original_value:
                source = self._determine_api_source(api_enrichment_data)
                return source, FieldStatus.REPLACED, 0.85
            else:
                source = self._determine_api_source(api_enrichment_data)
                return source, FieldStatus.EXTRACTED, 0.85
        
        if original_value == final_value:
            parser_used = self._get_parser_from_context()
            if parser_used == "ollama":
                return DataSource.OLLAMA, FieldStatus.EXTRACTED, 0.75
            else:
                return DataSource.SIMPLE_PARSER, FieldStatus.EXTRACTED, 0.70
        
        return DataSource.UNKNOWN, FieldStatus.EXTRACTED, 0.50
    
    def _determine_api_source(self, api_enrichment_data: Dict[str, Any]) -> DataSource:
        """Determine which LLM was the source of enrichment data"""
        enrichment_sources = api_enrichment_data.get("enrichment_sources", [])
        
        if "crossref" in enrichment_sources:
            return DataSource.CROSSREF
        elif "openalex" in enrichment_sources:
            return DataSource.OPENALEX
        elif "semantic_scholar" in enrichment_sources:
            return DataSource.SEMANTIC_SCHOLAR
        elif "doaj" in enrichment_sources:
            return DataSource.DOAJ
        else:
            return DataSource.UNKNOWN
    
    def _get_parser_from_context(self) -> str:
        """Get the parser type from context (this would be passed in real implementation)"""
        return "ollama"  
    
    def _extract_conflict_details(self, field: str, conflict_analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract conflict details for a specific field"""
        conflicts = conflict_analysis.get("conflicts", [])
        for conflict in conflicts:
            if conflict.get("field") == field:
                return {
                    "online_value": conflict.get("online_value"),
                    "ollama_value": conflict.get("ollama_value"),
                    "preferred": conflict.get("preferred"),
                    "confidence_scores": conflict_analysis.get("confidence_scores", {})
                }
        return None
    
    def _determine_extraction_status(
        self,
        missing_fields: List[str],
        partial_fields: List[str],
        final_result: Dict[str, Any]
    ) -> ExtractionStatus:
        """Determine the overall extraction status"""
        
        missing_critical = [field for field in self.critical_fields if field in missing_fields]
        
        if missing_critical:
            if len(missing_critical) >= 2:  
                return ExtractionStatus.FAILED
            else:
                return ExtractionStatus.PARTIAL
        
        if partial_fields:
            return ExtractionStatus.PARTIAL
        
        has_all_critical = all(
            final_result.get(field) for field in self.critical_fields
        )
        
        if has_all_critical:
            return ExtractionStatus.COMPLETE
        else:
            return ExtractionStatus.PARTIAL
    
    def _calculate_overall_confidence(self, field_flags: Dict[str, FieldInfo]) -> float:
        """Calculate overall confidence based on field-level confidence scores"""
        if not field_flags:
            return 0.0
        
        weighted_confidence = 0.0
        total_weight = 0.0
        
        for field, field_info in field_flags.items():
            weight = self.field_weights.get(field, 0.01)
            weighted_confidence += field_info.confidence * weight
            total_weight += weight
        
        return weighted_confidence / total_weight if total_weight > 0 else 0.0
    
    def _calculate_quality_score(self, field_flags: Dict[str, FieldInfo], final_result: Dict[str, Any]) -> float:
        """Calculate overall quality score based on completeness and field status"""
        score = 0.0
        max_score = 0.0
        
        for field, weight in self.field_weights.items():
            max_score += weight
            
            if field in field_flags:
                field_info = field_flags[field]
                
                if field_info.status == FieldStatus.EXTRACTED:
                    score += weight * 1.0
                elif field_info.status == FieldStatus.REPLACED:
                    score += weight * 0.9  
                elif field_info.status == FieldStatus.PARTIAL:
                    score += weight * 0.6
                elif field_info.status == FieldStatus.CONFLICTED:
                    score += weight * 0.5   
        
        if final_result.get("doi"):
            score += 0.05
        
        if final_result.get("abstract"):
            score += 0.03
        
        return min(score / max_score if max_score > 0 else 0.0, 1.0)
    
    def _generate_processing_notes(
        self,
        extraction_status: ExtractionStatus,
        missing_fields: List[str],
        replaced_fields: List[str],
        conflicted_fields: List[str]
    ) -> List[str]:
        """Generate human-readable processing notes"""
        notes = []
        
        notes.append(f"Reference extraction status: {extraction_status.value}")
        
        if missing_fields:
            notes.append(f"Missing fields: {', '.join(missing_fields)}")
        
        if replaced_fields:
            notes.append(f"Fields replaced by online data: {', '.join(replaced_fields)}")
        
        if conflicted_fields:
            notes.append(f"Conflicted fields requiring review: {', '.join(conflicted_fields)}")
        
        if extraction_status == ExtractionStatus.COMPLETE:
            notes.append("High-quality extraction with all critical fields present")
        elif extraction_status == ExtractionStatus.PARTIAL:
            notes.append("Partial extraction - some fields may need manual review")
        elif extraction_status == ExtractionStatus.FAILED:
            notes.append("Extraction failed - manual intervention required")
        
        return notes
    
    def _generate_recovery_suggestions(
        self,
        missing_fields: List[str],
        partial_fields: List[str],
        conflicted_fields: List[str]
    ) -> List[str]:
        """Generate suggestions for improving extraction quality"""
        suggestions = []
        
        if "doi" in missing_fields:
            suggestions.append("Try searching for DOI using title and author information")
        
        if "family_names" in missing_fields:
            suggestions.append("Reference may have unusual author format - manual review recommended")
        
        if "year" in missing_fields:
            suggestions.append("Year information may be embedded in text - try different parsing approach")
        
        if "journal" in missing_fields:
            suggestions.append("Journal name may be abbreviated - check full journal name")
        
        if partial_fields:
            suggestions.append("Some fields are partially extracted - consider manual completion")
        
        if conflicted_fields:
            suggestions.append("Review conflicted fields to determine correct values")
            suggestions.append("Consider using online data as authoritative source")
        
        if not suggestions:
            suggestions.append("Reference extraction completed successfully")
        
        return suggestions
    
    def format_flags_for_api(self, flags: ReferenceFlags) -> Dict[str, Any]:
        """Format flags for API response"""
        return {
            "extraction_status": flags.extraction_status.value,
            "overall_confidence": flags.overall_confidence,
            "quality_score": flags.quality_score,
            "field_analysis": {
                field: {
                    "value": field_info.value,
                    "source": field_info.source.value,
                    "confidence": field_info.confidence,
                    "status": field_info.status.value,
                    "original_value": field_info.original_value,
                    "replacement_reason": field_info.replacement_reason,
                    "conflict_details": field_info.conflict_details
                }
                for field, field_info in flags.field_flags.items()
            },
            "summary": {
                "missing_fields": flags.missing_fields,
                "replaced_fields": flags.replaced_fields,
                "conflicted_fields": flags.conflicted_fields,
                "partial_fields": flags.partial_fields,
                "data_sources_used": [source.value for source in flags.data_sources_used]
            },
            "processing_notes": flags.processing_notes,
            "recovery_suggestions": flags.recovery_suggestions
        }
