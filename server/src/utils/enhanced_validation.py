"""
Enhanced reference validation with cross-checking and hallucination detection
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from loguru import logger
import asyncio
from difflib import SequenceMatcher

from ..models.schemas import ReferenceData, ValidationResult, Author
from ..utils.api_clients import CrossRefClient, OpenAlexClient, SemanticScholarClient, DOAJClient


@dataclass
class CrossCheckResult:
    """Result of cross-checking a reference across multiple APIs"""
    field: str
    original_value: Optional[str]
    found_values: Dict[str, Any]  # API name -> found value
    confidence_scores: Dict[str, float]  # API name -> confidence score
    consensus_value: Optional[str]
    consensus_confidence: float
    is_hallucinated: bool
    hallucination_reason: Optional[str]
    missing_from_apis: List[str]  # APIs that couldn't find this field


@dataclass
class EnhancedValidationResult:
    """Enhanced validation result with cross-checking information"""
    is_valid: bool
    missing_fields: List[str]
    confidence_score: float
    suggestions: Dict[str, Any]
    warnings: List[str]
    cross_check_results: Dict[str, CrossCheckResult]
    hallucination_detected: bool
    hallucination_details: List[str]
    api_coverage: Dict[str, bool]  # API name -> whether it found the reference


class EnhancedReferenceValidator:
    """Enhanced validator with cross-checking and hallucination detection"""
    
    def __init__(self):
        self.required_fields = ["title", "authors", "year"]
        self.important_fields = ["journal", "volume", "issue", "pages", "doi"]
        self.optional_fields = ["publisher", "url", "abstract"]
        
        # Initialize API clients
        self.crossref_client = CrossRefClient()
        self.openalex_client = OpenAlexClient()
        self.semantic_client = SemanticScholarClient()
        self.doaj_client = DOAJClient()
        
        # Hallucination detection thresholds
        self.min_confidence_threshold = 0.3
        self.consensus_threshold = 0.6
        self.api_agreement_threshold = 0.7
    
    async def validate_reference_enhanced(
        self, 
        reference: ReferenceData, 
        original_text: str = "",
        enable_cross_checking: bool = True
    ) -> EnhancedValidationResult:
        """Enhanced validation with cross-checking and hallucination detection"""
        
        # Basic validation first
        basic_validation = self._basic_validate_reference(reference, original_text)
        
        if not enable_cross_checking:
            return self._convert_to_enhanced_result(basic_validation, {}, {}, {})
        
        # Cross-check missing fields
        cross_check_results = {}
        hallucination_details = []
        api_coverage = {}
        
        if basic_validation.missing_fields:
            cross_check_results = await self._cross_check_missing_fields(
                reference, original_text, basic_validation.missing_fields
            )
            
            # Detect hallucinations
            hallucination_details = self._detect_hallucinations(cross_check_results)
            
            # Check API coverage
            api_coverage = await self._check_api_coverage(reference, original_text)
        
        # Determine if reference is valid after cross-checking
        is_valid = len(basic_validation.missing_fields) == 0 or any(
            result.consensus_confidence > self.min_confidence_threshold 
            for result in cross_check_results.values()
        )
        
        hallucination_detected = len(hallucination_details) > 0
        
        return EnhancedValidationResult(
            is_valid=is_valid,
            missing_fields=basic_validation.missing_fields,
            confidence_score=basic_validation.confidence_score,
            suggestions=basic_validation.suggestions,
            warnings=basic_validation.warnings + hallucination_details,
            cross_check_results=cross_check_results,
            hallucination_detected=hallucination_detected,
            hallucination_details=hallucination_details,
            api_coverage=api_coverage
        )
    
    def _basic_validate_reference(self, reference: ReferenceData, original_text: str) -> ValidationResult:
        """Basic validation without cross-checking"""
        missing_fields = []
        warnings = []
        suggestions = {}
        confidence_score = 0.0
        
        # Check required fields
        if not reference.title or not reference.title.strip():
            missing_fields.append("title")
        else:
            confidence_score += 0.3
        
        if not reference.authors or len(reference.authors) == 0:
            missing_fields.append("authors")
        else:
            # Validate author completeness
            incomplete_authors = []
            for author in reference.authors:
                if not author.surname or not author.surname.strip():
                    incomplete_authors.append("surname")
                if not author.first_name or not author.first_name.strip():
                    incomplete_authors.append("first_name")
            
            if incomplete_authors:
                warnings.append(f"Incomplete author information: {', '.join(set(incomplete_authors))}")
            confidence_score += 0.3
        
        if not reference.year:
            missing_fields.append("year")
        else:
            # Validate year range
            if reference.year < 1900 or reference.year > 2024:
                warnings.append(f"Year {reference.year} seems unusual")
            confidence_score += 0.2
        
        # Check important fields
        important_missing = []
        if not reference.journal or not reference.journal.strip():
            important_missing.append("journal")
        else:
            confidence_score += 0.1
        
        if not reference.volume:
            important_missing.append("volume")
        else:
            confidence_score += 0.05
        
        if not reference.issue:
            important_missing.append("issue")
        else:
            confidence_score += 0.05
        
        if not reference.pages:
            important_missing.append("pages")
        else:
            confidence_score += 0.05
        
        if not reference.doi:
            important_missing.append("doi")
        else:
            confidence_score += 0.1
        
        # Generate suggestions for missing fields
        if missing_fields or important_missing:
            suggestions = self._generate_suggestions(reference, original_text, missing_fields + important_missing)
        
        # Determine if reference is valid
        is_valid = len(missing_fields) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            missing_fields=missing_fields + important_missing,
            confidence_score=min(confidence_score, 1.0),
            suggestions=suggestions,
            warnings=warnings
        )
    
    async def _cross_check_missing_fields(
        self, 
        reference: ReferenceData, 
        original_text: str, 
        missing_fields: List[str]
    ) -> Dict[str, CrossCheckResult]:
        """Cross-check missing fields across multiple APIs"""
        logger.info(f"🔍 CROSS-CHECKING MISSING FIELDS: {missing_fields}")
        
        # Build search query
        search_query = self._build_search_query(reference, original_text)
        logger.info(f"🔍 SEARCH QUERY: '{search_query}'")
        
        # Search across all APIs
        api_results = {}
        apis = {
            "crossref": self.crossref_client,
            "openalex": self.openalex_client,
            "semantic_scholar": self.semantic_client,
            "doaj": self.doaj_client
        }
        
        for api_name, client in apis.items():
            logger.info(f"🔍 Searching {api_name.upper()}...")
            try:
                results = await client.search_reference(search_query, limit=3)
                api_results[api_name] = results
                logger.info(f"✅ {api_name.upper()} returned {len(results)} results")
            except Exception as e:
                logger.warning(f"❌ Error searching {api_name}: {str(e)}")
                api_results[api_name] = []
        
        # Cross-check each missing field
        cross_check_results = {}
        
        for field in missing_fields:
            logger.info(f"🔍 Cross-checking field: {field}")
            cross_check_results[field] = await self._cross_check_field(
                field, reference, api_results, apis
            )
            logger.info(f"✅ Field {field} cross-check complete")
        
        return cross_check_results
    
    async def _cross_check_field(
        self, 
        field: str, 
        original_reference: ReferenceData, 
        api_results: Dict[str, List[ReferenceData]],
        apis: Dict[str, Any]
    ) -> CrossCheckResult:
        """Cross-check a specific field across APIs"""
        
        found_values = {}
        confidence_scores = {}
        missing_from_apis = []
        
        for api_name, results in api_results.items():
            if not results:
                missing_from_apis.append(api_name)
                continue
            
            # Find best match for this field
            best_match = None
            best_score = 0.0
            
            for candidate in results:
                score = self._calculate_field_similarity(field, original_reference, candidate)
                if score > best_score:
                    best_score = score
                    best_match = candidate
            
            if best_match and best_score > 0.1:  # Minimum threshold
                field_value = self._extract_field_value(field, best_match)
                if field_value:
                    found_values[api_name] = field_value
                    confidence_scores[api_name] = best_score
            else:
                missing_from_apis.append(api_name)
        
        # Calculate consensus
        consensus_value, consensus_confidence = self._calculate_consensus(
            field, found_values, confidence_scores
        )
        
        # Detect hallucination
        is_hallucinated, hallucination_reason = self._detect_field_hallucination(
            field, found_values, confidence_scores, consensus_confidence
        )
        
        return CrossCheckResult(
            field=field,
            original_value=self._extract_field_value(field, original_reference),
            found_values=found_values,
            confidence_scores=confidence_scores,
            consensus_value=consensus_value,
            consensus_confidence=consensus_confidence,
            is_hallucinated=is_hallucinated,
            hallucination_reason=hallucination_reason,
            missing_from_apis=missing_from_apis
        )
    
    def _calculate_field_similarity(
        self, 
        field: str, 
        original: ReferenceData, 
        candidate: ReferenceData
    ) -> float:
        """Calculate similarity score for a specific field"""
        
        if field == "title":
            return self._text_similarity(original.title, candidate.title)
        elif field == "authors":
            return self._authors_similarity(original.authors, candidate.authors)
        elif field == "year":
            return 1.0 if original.year == candidate.year else 0.0
        elif field == "journal":
            return self._text_similarity(original.journal, candidate.journal)
        elif field == "volume":
            return self._text_similarity(original.volume, candidate.volume)
        elif field == "issue":
            return self._text_similarity(original.issue, candidate.issue)
        elif field == "pages":
            return self._text_similarity(original.pages, candidate.pages)
        elif field == "doi":
            return 1.0 if original.doi == candidate.doi else 0.0
        else:
            return 0.0
    
    def _text_similarity(self, text1: Optional[str], text2: Optional[str]) -> float:
        """Calculate text similarity using SequenceMatcher"""
        if not text1 or not text2:
            return 0.0
        
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _authors_similarity(self, authors1: List[Author], authors2: List[Author]) -> float:
        """Calculate similarity between author lists"""
        if not authors1 or not authors2:
            return 0.0
        
        # Simple similarity based on surname matching
        surnames1 = {author.surname.lower() for author in authors1 if author.surname}
        surnames2 = {author.surname.lower() for author in authors2 if author.surname}
        
        if not surnames1 or not surnames2:
            return 0.0
        
        intersection = len(surnames1.intersection(surnames2))
        union = len(surnames1.union(surnames2))
        
        return intersection / union if union > 0 else 0.0
    
    def _extract_field_value(self, field: str, reference: ReferenceData) -> Optional[str]:
        """Extract field value from reference data"""
        if field == "title":
            return reference.title
        elif field == "authors":
            return ", ".join([f"{a.first_name} {a.surname}" for a in reference.authors if a.first_name and a.surname])
        elif field == "year":
            return str(reference.year) if reference.year else None
        elif field == "journal":
            return reference.journal
        elif field == "volume":
            return reference.volume
        elif field == "issue":
            return reference.issue
        elif field == "pages":
            return reference.pages
        elif field == "doi":
            return reference.doi
        else:
            return None
    
    def _calculate_consensus(
        self, 
        field: str, 
        found_values: Dict[str, Any], 
        confidence_scores: Dict[str, float]
    ) -> Tuple[Optional[str], float]:
        """Calculate consensus value and confidence"""
        
        if not found_values:
            return None, 0.0
        
        # Weight by confidence scores
        weighted_values = {}
        total_weight = 0.0
        
        for api_name, value in found_values.items():
            weight = confidence_scores.get(api_name, 0.0)
            if value not in weighted_values:
                weighted_values[value] = 0.0
            weighted_values[value] += weight
            total_weight += weight
        
        if total_weight == 0:
            return None, 0.0
        
        # Find most weighted value
        best_value = max(weighted_values.items(), key=lambda x: x[1])
        consensus_confidence = best_value[1] / total_weight
        
        return best_value[0], consensus_confidence
    
    def _detect_field_hallucination(
        self, 
        field: str, 
        found_values: Dict[str, Any], 
        confidence_scores: Dict[str, float],
        consensus_confidence: float
    ) -> Tuple[bool, Optional[str]]:
        """Detect if a field value is likely hallucinated"""
        
        if not found_values:
            return True, "No APIs found this field"
        
        if consensus_confidence < self.min_confidence_threshold:
            return True, f"Low consensus confidence: {consensus_confidence:.2f}"
        
        # Check for API disagreement
        if len(found_values) > 1:
            values = list(found_values.values())
            if len(set(values)) > 1:  # Different values found
                agreement_ratio = len(set(values)) / len(values)
                if agreement_ratio < self.api_agreement_threshold:
                    return True, f"Low API agreement: {agreement_ratio:.2f}"
        
        return False, None
    
    def _detect_hallucinations(self, cross_check_results: Dict[str, CrossCheckResult]) -> List[str]:
        """Detect overall hallucinations in cross-check results"""
        hallucination_details = []
        
        for field, result in cross_check_results.items():
            if result.is_hallucinated:
                hallucination_details.append(
                    f"Field '{field}': {result.hallucination_reason}"
                )
        
        return hallucination_details
    
    async def _check_api_coverage(self, reference: ReferenceData, original_text: str) -> Dict[str, bool]:
        """Check which APIs can find the reference"""
        search_query = self._build_search_query(reference, original_text)
        api_coverage = {}
        
        apis = {
            "crossref": self.crossref_client,
            "openalex": self.openalex_client,
            "semantic_scholar": self.semantic_client,
            "doaj": self.doaj_client
        }
        
        for api_name, client in apis.items():
            try:
                results = await client.search_reference(search_query, limit=1)
                api_coverage[api_name] = len(results) > 0
            except Exception as e:
                logger.warning(f"Error checking {api_name} coverage: {str(e)}")
                api_coverage[api_name] = False
        
        return api_coverage
    
    def _build_search_query(self, reference: ReferenceData, original_text: str) -> str:
        """Build search query from reference data"""
        query_parts = []
        
        if reference.title:
            query_parts.append(reference.title)
        
        if reference.authors:
            author_names = [f"{a.first_name} {a.surname}" for a in reference.authors if a.first_name and a.surname]
            if author_names:
                query_parts.append(" ".join(author_names[:2]))
        
        if reference.year:
            query_parts.append(str(reference.year))
        
        if reference.journal:
            query_parts.append(reference.journal)
        
        return " ".join(query_parts) if query_parts else original_text
    
    def _generate_suggestions(
        self, 
        reference: ReferenceData, 
        original_text: str, 
        missing_fields: List[str]
    ) -> Dict[str, Any]:
        """Generate suggestions for missing fields"""
        suggestions = {}
        
        for field in missing_fields:
            suggestions[field] = {
                "status": "missing",
                "message": f"Field '{field}' is missing and could not be reliably found",
                "confidence": 0.0
            }
        
        return suggestions
    
    def _convert_to_enhanced_result(
        self, 
        basic_result: ValidationResult, 
        cross_check_results: Dict[str, CrossCheckResult],
        hallucination_details: List[str],
        api_coverage: Dict[str, bool]
    ) -> EnhancedValidationResult:
        """Convert basic validation result to enhanced result"""
        return EnhancedValidationResult(
            is_valid=basic_result.is_valid,
            missing_fields=basic_result.missing_fields,
            confidence_score=basic_result.confidence_score,
            suggestions=basic_result.suggestions,
            warnings=basic_result.warnings + hallucination_details,
            cross_check_results=cross_check_results,
            hallucination_detected=len(hallucination_details) > 0,
            hallucination_details=hallucination_details,
            api_coverage=api_coverage
        )
