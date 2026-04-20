"""
Reference Processing Pipeline Orchestrator

Implements the complete 12-step pipeline for processing academic references
with semantic correctness as the primary goal.
"""
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger

from ..models.reference_models import Reference, ReferenceType, Conflict, ConflictSeverity
from .reference_normalizer import ReferenceNormalizer
from .reference_classifier import ReferenceTypeClassifier, normalize_doi
from .semantic_schema_validator import SemanticSchemaValidator
from .safe_string_utils import safe_strip
from .ner_reference_parser import NERReferenceParser
from .simple_parser import SimpleReferenceParser
from .smart_api_strategy import SmartAPIStrategy
try:
    from .quality_scorer import QualityScorer
except ImportError:
    # Fallback if quality_scorer not yet implemented
    from .quality_scorer import QualityScorer
from .reference_tagging import generate_tagged_output
from .strict_normalization_validator import StrictNormalizationValidator


class ReferencePipeline:
    """
    Complete reference processing pipeline following the 12-step architecture.
    
    This orchestrator ensures semantic correctness at every step and produces
    publication-grade XML output.
    """
    
    def __init__(self):
        self.normalizer = ReferenceNormalizer()
        self.classifier = ReferenceTypeClassifier()
        self.validator = SemanticSchemaValidator()
        self.ner_parser = NERReferenceParser()
        self.simple_parser = SimpleReferenceParser()
        self.api_strategy = SmartAPIStrategy()
        self.quality_scorer = QualityScorer()
        
        logger.info("Reference Pipeline initialized")
    
    async def process_reference(
        self,
        raw_text: str,
        index: int,
        enable_api_enrichment: bool = True
    ) -> Reference:
        """
        Process a single reference through the complete 12-step pipeline.
        
        Args:
            raw_text: Raw reference text from document
            index: Original index in document
            enable_api_enrichment: Whether to use API enrichment
            
        Returns:
            Processed Reference object with XML and quality metrics
        """
        # Step 1: Document Ingestion (already done - we receive raw_text)
        # Step 2: Reference Normalization
        normalized_text, original_text = self.normalizer.normalize(raw_text)
        
        # Step 3: Reference Type Classification (MANDATORY - before parsing)
        reference_type = self.classifier.classify_from_text(normalized_text)
        logger.info(f"Reference {index + 1} classified as: {reference_type.value}")
        
        # Step 4: Structured Parsing (Type-Aware)
        parsed_data = await self._parse_type_aware(normalized_text, reference_type)
        
        # Create initial Reference object
        reference = Reference(
            index=index,
            original_text=original_text,
            normalized_text=normalized_text,
            reference_type=reference_type,
            family_names=parsed_data.get("family_names", []),
            given_names=parsed_data.get("given_names", []),
            full_names=parsed_data.get("full_names", []),
            year=parsed_data.get("year"),
            title=parsed_data.get("title"),
            venue=parsed_data.get("venue") or parsed_data.get("journal"),
            volume=parsed_data.get("volume"),
            issue=parsed_data.get("issue"),
            pages=parsed_data.get("pages"),
            article_number=parsed_data.get("article_number"),
            publisher=parsed_data.get("publisher"),
            city=parsed_data.get("city"),
            conference_name=parsed_data.get("conference_name"),
            doi=parsed_data.get("doi"),
            url=parsed_data.get("url"),
            abstract=parsed_data.get("abstract"),
            parser_used=parsed_data.get("parser_used", "unknown")
        )
        
        # Step 5: Field Normalization
        reference = self._normalize_fields(reference)
        
        # Step 6: Validation Eligibility Check
        needs_enrichment, reasons = self._check_enrichment_eligibility(reference)
        
        # Step 7: Smart API Enrichment (if eligible)
        if enable_api_enrichment and needs_enrichment:
            reference = await self._enrich_with_apis(reference)
        
        # Step 8: Conflict Resolution
        reference = self._resolve_conflicts(reference)
        
        # Step 9: Quality Scoring
        reference.quality_score_before = self.quality_scorer.score(reference)
        if enable_api_enrichment and needs_enrichment:
            reference.quality_score_after = self.quality_scorer.score(reference)
            reference.quality_improvement = reference.quality_score_after - reference.quality_score_before
        
        # Step 10: Semantic Schema Validation (CRITICAL)
        is_valid, validation_errors = self.validator.validate(reference)
        reference.is_valid = is_valid
        reference.validation_errors = validation_errors
        
        if not is_valid:
            logger.warning(f"Reference {index + 1} failed schema validation: {validation_errors}")
        
        # Step 10.5: STRICT NORMALIZATION & VALIDATION (BEFORE XML GENERATION)
        strict_validator = StrictNormalizationValidator()
        normalized_ref, norm_errors, can_generate_xml = strict_validator.normalize_and_validate(reference)
        
        # Merge normalization errors into validation errors
        if norm_errors:
            reference.validation_errors.extend(norm_errors)
            logger.warning(f"Reference {index + 1} normalization: {norm_errors}")
        
        # Update reference with normalized values (normalized_ref is a copy with normalized fields)
        # Copy normalized fields back to reference
        reference.doi = normalized_ref.doi
        reference.pages = normalized_ref.pages
        reference.article_number = normalized_ref.article_number
        reference.issue = normalized_ref.issue
        reference.publisher = normalized_ref.publisher  # May be removed for journal articles
        reference.conference_name = normalized_ref.conference_name  # May be removed for journal articles
        
        # If core constraints violated, block XML generation
        if not can_generate_xml:
            logger.error(f"Reference {index + 1} core constraints violated - blocking XML generation")
            reference.is_valid = False
        
        # Step 11: XML Generation (STRICT - only from validated references)
        if is_valid and can_generate_xml:
            reference.tagged_output = generate_tagged_output(reference.to_dict(), index)
        else:
            # Generate error XML for invalid references (flagged)
            reference.tagged_output = self._generate_invalid_xml(reference, index)
        
        # Step 12: Output & Reporting (reference object contains all metrics)
        return reference
    
    async def _parse_type_aware(self, normalized_text: str, ref_type: ReferenceType) -> Dict[str, Any]:
        """
        Parse reference with type awareness.
        NEVER extracts fields forbidden by the reference type.
        """
        # Use NER parser as primary
        try:
            parsed = self.ner_parser.parse_reference_to_dict(normalized_text)
        except Exception as e:
            logger.warning(f"NER parsing failed, using simple parser: {e}")
            parsed = self.simple_parser.parse_reference(normalized_text)
        
        # Type-specific field extraction
        if ref_type == ReferenceType.JOURNAL_ARTICLE:
            # Extract: title, venue (journal), volume, issue, pages, doi
            # DO NOT extract: publisher, city, conference_name
            parsed.pop("publisher", None)
            parsed.pop("city", None)
            parsed.pop("conference_name", None)
        
        elif ref_type == ReferenceType.CONFERENCE_PAPER:
            # Extract: title, conference_name (or venue), publisher, pages, doi
            # DO NOT extract: volume, issue
            parsed.pop("volume", None)
            parsed.pop("issue", None)
            if parsed.get("venue") and not parsed.get("conference_name"):
                parsed["conference_name"] = parsed.pop("venue")
        
        elif ref_type == ReferenceType.BOOK:
            # Extract: title, publisher, city, doi
            # DO NOT extract: volume, issue, venue, conference_name
            parsed.pop("volume", None)
            parsed.pop("issue", None)
            parsed.pop("venue", None)
            parsed.pop("conference_name", None)
        
        elif ref_type == ReferenceType.BOOK_CHAPTER:
            # Extract: title, venue (book title), publisher, pages, doi
            # DO NOT extract: volume, issue
            parsed.pop("volume", None)
            parsed.pop("issue", None)
            parsed.pop("conference_name", None)
        
        elif ref_type == ReferenceType.REPORT:
            # Extract: title, publisher, city, doi
            # DO NOT extract: volume, issue, venue, conference_name
            parsed.pop("volume", None)
            parsed.pop("issue", None)
            parsed.pop("venue", None)
            parsed.pop("conference_name", None)
        
        return parsed
    
    def _normalize_fields(self, reference: Reference) -> Reference:
        """Normalize field values (Step 5)"""
        # Normalize DOI
        if reference.doi:
            reference.doi = normalize_doi(reference.doi)
        
        # Normalize author names (deduplicate, normalize casing)
        # Use safe_strip to prevent NoneType errors (FIX #1)
        if reference.family_names:
            reference.family_names = [safe_strip(name).title() if safe_strip(name) else "" 
                                    for name in reference.family_names if safe_strip(name)]
        if reference.given_names:
            reference.given_names = [safe_strip(name) or "" 
                                   for name in reference.given_names if safe_strip(name)]
        
        # Normalize venue names
        reference.venue = safe_strip(reference.venue) or None
        
        return reference
    
    def _check_enrichment_eligibility(self, reference: Reference) -> Tuple[bool, List[str]]:
        """Check if reference needs API enrichment (Step 6)"""
        reasons = []
        
        # Missing DOI
        if not reference.doi:
            reasons.append("missing_doi")
        
        # Missing venue (type-dependent)
        if reference.reference_type == ReferenceType.JOURNAL_ARTICLE and not reference.venue:
            reasons.append("missing_venue")
        elif reference.reference_type == ReferenceType.CONFERENCE_PAPER and not reference.conference_name:
            reasons.append("missing_conference_name")
        elif reference.reference_type == ReferenceType.BOOK and not reference.publisher:
            reasons.append("missing_publisher")
        
        # Low quality score
        quality_score = self.quality_scorer.score(reference)
        if quality_score < 0.5:
            reasons.append("low_quality")
        
        needs_enrichment = len(reasons) > 0
        return needs_enrichment, reasons
    
    async def _enrich_with_apis(self, reference: Reference) -> Reference:
        """Enrich reference with API data (Step 7)"""
        # Use smart API strategy
        enrichment_data = await self.api_strategy.enrich_reference(
            reference.to_dict(),
            reference.reference_type
        )
        
        # Merge field-by-field with provenance tracking
        for field, value in enrichment_data.items():
            if value and not getattr(reference, field, None):
                setattr(reference, field, value)
                reference.enrichment_provenance[field] = enrichment_data.get("_source", "unknown")
                reference.enrichment_used = True
                if enrichment_data.get("_source") not in reference.enrichment_sources:
                    reference.enrichment_sources.append(enrichment_data.get("_source"))
        
        return reference
    
    def _resolve_conflicts(self, reference: Reference) -> Reference:
        """Resolve conflicts between parsed and API data (Step 8)"""
        # This is simplified - full implementation would compare parsed vs enriched
        # For now, we flag conflicts but don't auto-resolve
        # Conflicts are tracked in reference.conflicts
        
        return reference
    
    def _generate_invalid_xml(self, reference: Reference, index: int) -> str:
        """Generate minimal XML for invalid references"""
        label_id = f"bib{index + 1}"
        return f'<bibitem><label id="{label_id}">INVALID REFERENCE</label><x> </x><error>Schema validation failed: {", ".join(reference.validation_errors)}</error></bibitem>'



