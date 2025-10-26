"""
NER-based reference parser using the citation-parser-ENTITY model
This serves as the main stream parser for the system
"""
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
from collections import defaultdict
import json
import re
from loguru import logger

# Import the NER parser from the services directory
from ..services.reference_parcer_ollama import AdvancedNERParser, Author, ReferenceData


class NERReferenceParser:
    """
    Main reference parser using NER (Named Entity Recognition) 
    as the primary parsing method for academic references
    """
    
    def __init__(self, 
                 confidence_threshold: float = 0.3,  # Lowered from 0.5 to catch more authors
                 enable_entity_disambiguation: bool = True,
                 enable_confidence_weighting: bool = True,
                 use_llm_primary: bool = False):  # Disable LLM - use NER only for stability
        
        logger.info("Initializing NER Reference Parser as main stream parser (LLM disabled)")
        
        self.confidence_threshold = confidence_threshold
        self.enable_disambiguation = enable_entity_disambiguation
        self.enable_confidence_weighting = enable_confidence_weighting
        
        # Initialize the NER parser with error handling
        try:
            self.ner_parser = AdvancedNERParser(
                confidence_threshold=confidence_threshold,
                enable_entity_disambiguation=enable_entity_disambiguation,
                enable_confidence_weighting=enable_confidence_weighting,
                use_llm_primary=False  # Disable LLM for stability
            )
            self.ner_available = True
            logger.info("✅ NER Reference Parser initialized successfully (LLM disabled)")
        except Exception as e:
            logger.warning(f"⚠️ NER model initialization failed: {str(e)}")
            logger.info("🔄 Falling back to regex-based parsing")
            self.ner_parser = None
            self.ner_available = False
    
    def parse_reference_to_dict(self, raw_citation: str) -> dict:
        """
        Parse a single reference using NER as the primary method
        Returns a dictionary compatible with the existing API structure
        """
        try:
            logger.debug(f"Parsing reference: {raw_citation[:100]}...")
            
            if self.ner_available and self.ner_parser:
                # Use the NER parser to get structured data
                ner_result = self.ner_parser.parse_reference_to_dict(raw_citation)
                
                # Safety check: ensure ner_result is a valid dict
                if not ner_result or not isinstance(ner_result, dict):
                    logger.warning(f"NER parser returned invalid result: {ner_result}, using regex fallback")
                    result = self._regex_based_parsing(raw_citation)
                else:
                    result = self._convert_ner_to_api_format(ner_result, raw_citation)
                    logger.debug(f"NER parsing completed with quality score: {result.get('quality_score', 0):.2f}")
            else:
                # Use regex-based fallback parsing
                result = self._regex_based_parsing(raw_citation)
                logger.debug(f"Regex-based parsing completed with quality score: {result.get('quality_score', 0):.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Parsing failed for reference: {str(e)}")
            return self._create_fallback_result(raw_citation, str(e))
    
    def parse_batch(self, citations: List[str]) -> List[dict]:
        """
        Parse multiple references using NER
        """
        logger.info(f"Processing batch of {len(citations)} references with NER")
        results = []
        
        for i, citation in enumerate(citations):
            try:
                result = self.parse_reference_to_dict(citation)
                result['index'] = i
                results.append(result)
                
                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(citations)} references")
                    
            except Exception as e:
                logger.error(f"Failed to parse reference {i}: {str(e)}")
                results.append(self._create_fallback_result(citation, str(e), i))
        
        logger.info(f"Batch processing completed: {len(results)} results")
        return results
    
    def _convert_ner_to_api_format(self, ner_result: dict, raw_citation: str) -> dict:
        """
        Convert NER parser result to the expected API format
        """
        # Extract authors
        authors = ner_result.get('authors', [])
        family_names = []
        given_names = []
        
        for author in authors:
            if isinstance(author, dict):
                if author.get('surname'):
                    family_names.append(author['surname'])
                if author.get('first_name'):
                    given_names.append(author['first_name'])
            elif isinstance(author, str):
                # Fallback for string authors
                family_names.append(author)
            elif hasattr(author, 'surname'):
                # Handle Pydantic Author objects
                if author.surname:
                    family_names.append(author.surname)
                if author.first_name:
                    given_names.append(author.first_name)
        
        # Calculate quality metrics
        confidence_scores = ner_result.get('confidence_scores', {})
        overall_confidence = confidence_scores.get('overall', 0.0)
        
        # Determine missing fields
        missing_fields = []
        if not ner_result.get('title'):
            missing_fields.append('title')
        if not family_names:
            missing_fields.append('authors')
        if not ner_result.get('year'):
            missing_fields.append('year')
        if not ner_result.get('journal'):
            missing_fields.append('journal')
        if not ner_result.get('doi'):
            missing_fields.append('doi')
        
        # Create tagged output for display
        tagged_output = self._generate_tagged_output(ner_result)
        
        # Build flagging analysis
        flagging_analysis = {
            'missing_fields': missing_fields,
            'replaced_fields': [],  # NER doesn't replace, it extracts
            'conflicted_fields': [],  # NER resolves conflicts internally
            'partial_fields': [],  # Could be enhanced to detect partial extractions
            'data_sources_used': ['NER_MODEL']
        }
        
        return {
            'family_names': family_names,
            'given_names': given_names,
            'year': ner_result.get('year'),
            'title': ner_result.get('title'),
            'journal': ner_result.get('journal'),
            'volume': ner_result.get('volume'),
            'issue': ner_result.get('issue'),
            'pages': ner_result.get('pages'),
            'doi': ner_result.get('doi'),
            'url': ner_result.get('url'),
            'publisher': ner_result.get('publisher'),
            'abstract': ner_result.get('abstract'),
            'publication_type': ner_result.get('publication_type'),
            'raw_text': raw_citation,
            'parser_used': 'NER_MODEL',
            'api_enrichment_used': False,  # NER is local parsing
            'enrichment_sources': ['NER_MODEL'],
            'quality_score': overall_confidence,
            'quality_improvement': 0.0,  # No improvement from base parsing
            'final_quality_score': overall_confidence,
            'missing_fields': missing_fields,
            'tagged_output': tagged_output,
            'flagging_analysis': flagging_analysis,
            'confidence_scores': confidence_scores,
            'entity_count': ner_result.get('entity_count', {}),
            'ambiguity_flags': ner_result.get('ambiguity_flags', [])
        }
    
    def _generate_tagged_output(self, ner_result: dict) -> str:
        """
        Generate tagged output for display purposes
        """
        parts = []
        
        # Add title if present
        if ner_result.get('title'):
            parts.append(f"<title>{ner_result['title']}</title>")
        
        # Add authors
        authors = ner_result.get('authors', [])
        if authors:
            author_names = []
            for author in authors:
                if isinstance(author, dict):
                    name = author.get('full_name') or f"{author.get('first_name', '')} {author.get('surname', '')}".strip()
                    if name:
                        author_names.append(name)
                elif isinstance(author, str):
                    author_names.append(author)
            
            if author_names:
                parts.append(f"<authors>{', '.join(author_names)}</authors>")
        
        # Add journal
        if ner_result.get('journal'):
            parts.append(f"<journal>{ner_result['journal']}</journal>")
        
        # Add year
        if ner_result.get('year'):
            parts.append(f"<year>{ner_result['year']}</year>")
        
        # Add volume and issue
        if ner_result.get('volume'):
            parts.append(f"<volume>{ner_result['volume']}</volume>")
        if ner_result.get('issue'):
            parts.append(f"<issue>{ner_result['issue']}</issue>")
        
        # Add pages
        if ner_result.get('pages'):
            parts.append(f"<pages>{ner_result['pages']}</pages>")
        
        # Add DOI
        if ner_result.get('doi'):
            parts.append(f"<doi>{ner_result['doi']}</doi>")
        
        # Add URL
        if ner_result.get('url'):
            parts.append(f"<url>{ner_result['url']}</url>")
        
        return " | ".join(parts) if parts else "No structured data extracted"
    
    def _regex_based_parsing(self, raw_citation: str) -> dict:
        """
        Simple regex-based fallback parsing when NER is not available
        """
        import re
        
        result = {
            'family_names': [],
            'given_names': [],
            'year': None,
            'title': None,
            'journal': None,
            'volume': None,
            'issue': None,
            'pages': None,
            'doi': None,
            'url': None,
            'publisher': None,
            'abstract': None,
            'publication_type': None,
            'raw_text': raw_citation,
            'parser_used': 'REGEX_FALLBACK',
            'api_enrichment_used': False,
            'enrichment_sources': [],
            'quality_score': 0.3,
            'confidence_scores': {'overall': 0.3}
        }
        
        # Extract year
        year_match = re.search(r'\b(19|20)\d{2}\b', raw_citation)
        if year_match:
            result['year'] = int(year_match.group())
            result['confidence_scores']['year'] = 0.8
        
        # Extract DOI
        doi_match = re.search(r'10\.\d+/[^\s]+', raw_citation)
        if doi_match:
            result['doi'] = doi_match.group()
            result['confidence_scores']['doi'] = 0.9
        
        # Extract URL
        url_match = re.search(r'https?://[^\s]+', raw_citation)
        if url_match:
            result['url'] = url_match.group()
            result['confidence_scores']['url'] = 0.9
        
        # Simple author extraction (first few capitalized words)
        author_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        authors = re.findall(author_pattern, raw_citation)
        if authors:
            for author in authors[:5]:  # Limit to 5 authors
                if len(author.split()) >= 2:  # At least first and last name
                    name_parts = author.split()
                    result['family_names'].append(name_parts[-1])  # Last name
                    result['given_names'].append(name_parts[0])    # First name
        
        # Simple title extraction (text between authors and year)
        if result['year']:
            year_pos = raw_citation.find(str(result['year']))
            if year_pos > 0:
                # Look for title before year
                before_year = raw_citation[:year_pos].strip()
                # Find the last comma or period before year
                for sep in [',', '.']:
                    sep_pos = before_year.rfind(sep)
                    if sep_pos > 10:  # Reasonable title length
                        title = before_year[sep_pos+1:].strip()
                        if len(title) > 10:
                            result['title'] = title
                            break
        
        # Calculate overall confidence
        confidences = [v for k, v in result['confidence_scores'].items() if k != 'overall']
        if confidences:
            result['confidence_scores']['overall'] = float(sum(confidences) / len(confidences))
        
        return result

    def _create_fallback_result(self, raw_citation: str, error: str, index: int = 0) -> dict:
        """
        Create a fallback result when NER parsing fails
        """
        logger.warning(f"Creating fallback result for failed parsing: {error}")
        
        return {
            'index': index,
            'family_names': [],
            'given_names': [],
            'year': None,
            'title': None,
            'journal': None,
            'volume': None,
            'issue': None,
            'pages': None,
            'doi': None,
            'url': None,
            'publisher': None,
            'abstract': None,
            'publication_type': None,
            'raw_text': raw_citation,
            'parser_used': 'NER_MODEL_FALLBACK',
            'api_enrichment_used': False,
            'enrichment_sources': [],
            'quality_score': 0.0,
            'quality_improvement': 0.0,
            'final_quality_score': 0.0,
            'missing_fields': ['title', 'authors', 'year', 'journal', 'doi'],
            'tagged_output': f"<error>Parsing failed: {error}</error>",
            'flagging_analysis': {
                'missing_fields': ['title', 'authors', 'year', 'journal', 'doi'],
                'replaced_fields': [],
                'conflicted_fields': [],
                'partial_fields': [],
                'data_sources_used': []
            },
            'confidence_scores': {},
            'entity_count': {},
            'ambiguity_flags': ['parsing_failed'],
            'error': error
        }
    
    def get_parser_info(self) -> dict:
        """
        Get information about the parser capabilities
        """
        return {
            'parser_name': 'NER Reference Parser',
            'parser_type': 'Named Entity Recognition',
            'model': 'SIRIS-Lab/citation-parser-ENTITY',
            'confidence_threshold': self.confidence_threshold,
            'entity_disambiguation': self.enable_disambiguation,
            'confidence_weighting': self.enable_confidence_weighting,
            'supports_batch': True,
            'requires_internet': False,  # Local model
            'supports_languages': ['en'],
            'extraction_fields': [
                'title', 'authors', 'year', 'journal', 'volume', 
                'issue', 'pages', 'doi', 'url', 'publisher', 
                'publication_type', 'abstract'
            ]
        }


# Export the main parser class
__all__ = ['NERReferenceParser', 'Author', 'ReferenceData']
