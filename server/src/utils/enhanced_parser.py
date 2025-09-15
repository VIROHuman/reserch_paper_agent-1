"""
Enhanced reference parser that integrates API clients for missing field completion
"""
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger

from .simple_parser import SimpleReferenceParser
from .ollama_parser import OllamaReferenceParser
from .api_clients import CrossRefClient, OpenAlexClient, SemanticScholarClient, DOAJClient
from .smart_api_strategy import SmartAPIStrategy
from .doi_metadata_extractor import DOIMetadataExtractor, DOIMetadataConflictDetector
from .flagging_system import ReferenceFlaggingSystem


class EnhancedReferenceParser:
    """Enhanced parser that combines local parsing with API client enrichment"""
    
    def __init__(self):
        self.simple_parser = SimpleReferenceParser()
        self.ollama_parser = OllamaReferenceParser()
        
        # Initialize smart API strategy
        self.smart_api = SmartAPIStrategy()
        
        # Keep individual clients for backward compatibility
        self.crossref_client = self.smart_api.crossref_client
        self.openalex_client = self.smart_api.openalex_client
        self.semantic_client = self.smart_api.semantic_client
        self.doaj_client = self.smart_api.doaj_client
        
        # Initialize DOI metadata extractor and conflict detector
        self.doi_extractor = DOIMetadataExtractor()
        self.conflict_detector = DOIMetadataConflictDetector()
        
        # Initialize flagging system
        self.flagging_system = ReferenceFlaggingSystem()
        
        logger.info("Enhanced reference parser initialized with Smart API Strategy, DOI extraction, and Flagging System")
    
    async def parse_reference_enhanced(
        self, 
        ref_text: str, 
        use_ollama: bool = True,
        enable_api_enrichment: bool = True
    ) -> Dict[str, Any]:
        try:
            if use_ollama and self.ollama_parser.client:
                parsed_ref = self.ollama_parser.parse_reference(ref_text)
                parser_used = "ollama"
            else:
                parsed_ref = self.simple_parser.parse_reference(ref_text)
                parser_used = "simple"
            
            doi_metadata = None
            conflict_analysis = None
            if parsed_ref.get('doi'):
                try:
                    doi_metadata = await self.doi_extractor.extract_metadata(parsed_ref.get('doi'))
                    if doi_metadata and not doi_metadata.get('error'):
                        conflict_analysis = self.conflict_detector.detect_conflicts(doi_metadata, parsed_ref)
                except Exception as e:
                    logger.error(f"DOI metadata extraction error: {str(e)}")
            
            if enable_api_enrichment:
                enriched_ref = await self.smart_api.enrich_reference_smart(
                    parsed_ref, 
                    ref_text,
                    force_enrichment=True
                )
                enriched_ref["parser_used"] = parser_used
                enriched_ref["api_enrichment_used"] = True
                
                enriched_ref["doi_metadata"] = doi_metadata
                enriched_ref["conflict_analysis"] = conflict_analysis
                
                if conflict_analysis and conflict_analysis.get('has_conflicts'):
                    for field, value in conflict_analysis.get('preferred_data', {}).items():
                        if value:
                            enriched_ref[field] = value
                
                flags = self.flagging_system.analyze_reference_extraction(
                    original_parsed=parsed_ref,
                    final_result=enriched_ref,
                    api_enrichment_data=enriched_ref if enriched_ref.get("api_enrichment_used") else None,
                    doi_metadata=doi_metadata,
                    conflict_analysis=conflict_analysis
                )
                
                enriched_ref["flagging_analysis"] = self.flagging_system.format_flags_for_api(flags)
                
                return enriched_ref
            else:
                parsed_ref["parser_used"] = parser_used
                parsed_ref["api_enrichment_used"] = False
                
                parsed_ref["doi_metadata"] = doi_metadata
                parsed_ref["conflict_analysis"] = conflict_analysis
                
                if conflict_analysis and conflict_analysis.get('has_conflicts'):
                    for field, value in conflict_analysis.get('preferred_data', {}).items():
                        if value:
                            parsed_ref[field] = value
                
                flags = self.flagging_system.analyze_reference_extraction(
                    original_parsed=parsed_ref.copy(),
                    final_result=parsed_ref,
                    api_enrichment_data=None,
                    doi_metadata=doi_metadata,
                    conflict_analysis=conflict_analysis
                )
                
                parsed_ref["flagging_analysis"] = self.flagging_system.format_flags_for_api(flags)
                
                return parsed_ref
                
        except Exception as e:
            logger.error(f"Error in enhanced parsing: {e}")
            parsed_ref = self.simple_parser.parse_reference(ref_text)
            parsed_ref["parser_used"] = "simple"
            parsed_ref["api_enrichment_used"] = False
            parsed_ref["error"] = str(e)
            return parsed_ref
    
    async def _enrich_with_apis(self, parsed_ref: Dict[str, Any], original_text: str) -> Dict[str, Any]:
        enriched_ref = parsed_ref.copy()
        enrichment_sources = []
        
        search_query = self._create_search_query(parsed_ref, original_text)
        
        if not search_query:
            return enriched_ref
        
        api_names = ["CrossRef", "OpenAlex", "Semantic Scholar", "DOAJ"]
        api_tasks = [
            self._search_crossref(search_query, enriched_ref),
            self._search_openalex(search_query, enriched_ref),
            self._search_semantic_scholar(search_query, enriched_ref),
            self._search_doaj(search_query, enriched_ref)
        ]
        
        try:
            results = await asyncio.gather(*api_tasks, return_exceptions=True)
            
            for i, (api_name, result) in enumerate(zip(api_names, results)):
                if isinstance(result, Exception):
                    continue
                
                if result and result.get("sources"):
                    enrichment_sources.extend(result["sources"])
                    enriched_ref = self._merge_api_data(enriched_ref, result["data"])
            
            enriched_ref["missing_fields"] = self._get_missing_fields(enriched_ref)
            enriched_ref["enrichment_sources"] = list(set(enrichment_sources))
            
        except Exception as e:
            logger.error(f"Error during API enrichment: {e}")
            enriched_ref["enrichment_error"] = str(e)
        
        return enriched_ref
    
    def _create_search_query(self, parsed_ref: Dict[str, Any], original_text: str) -> str:
        """Create search query from parsed reference data"""
        query_parts = []
        
        # Use title if available
        if parsed_ref.get("title"):
            query_parts.append(parsed_ref["title"])
        
        # Add first author if available
        if parsed_ref.get("family_names"):
            query_parts.append(parsed_ref["family_names"][0])
        
        # Add year if available
        if parsed_ref.get("year"):
            query_parts.append(parsed_ref["year"])
        
        # If we have good query parts, use them
        if len(query_parts) >= 2:
            return " ".join(query_parts)
        
        # Fallback to using original text (truncated)
        if original_text and len(original_text) > 10:
            return original_text[:200]  # Truncate to avoid too long queries
        
        return None
    
    async def _search_crossref(self, query: str, parsed_ref: Dict[str, Any]) -> Dict[str, Any]:
        try:
            results = await self.crossref_client.search_reference(query, limit=3)
            
            if results:
                best_match = self._find_best_match(parsed_ref, results)
                if best_match:
                    converted_data = self._convert_to_parsed_format(best_match)
                    return {
                        "data": converted_data,
                        "sources": ["crossref"]
                    }
        except Exception as e:
            logger.warning(f"CrossRef API search failed: {e}")
        
        return None
    
    async def _search_openalex(self, query: str, parsed_ref: Dict[str, Any]) -> Dict[str, Any]:
        try:
            results = await self.openalex_client.search_reference(query, limit=3)
            
            if results:
                best_match = self._find_best_match(parsed_ref, results)
                if best_match:
                    converted_data = self._convert_to_parsed_format(best_match)
                    return {
                        "data": converted_data,
                        "sources": ["openalex"]
                    }
        except Exception as e:
            logger.warning(f"OpenAlex API search failed: {e}")
        
        return None
    
    async def _search_semantic_scholar(self, query: str, parsed_ref: Dict[str, Any]) -> Dict[str, Any]:
        try:
            results = await self.semantic_client.search_reference(query, limit=3)
            
            if results:
                best_match = self._find_best_match(parsed_ref, results)
                if best_match:
                    converted_data = self._convert_to_parsed_format(best_match)
                    return {
                        "data": converted_data,
                        "sources": ["semantic_scholar"]
                    }
        except Exception as e:
            logger.warning(f"Semantic Scholar API search failed: {e}")
        
        return None
    
    async def _search_doaj(self, query: str, parsed_ref: Dict[str, Any]) -> Dict[str, Any]:
        try:
            results = await self.doaj_client.search_reference(query, limit=3)
            
            if results:
                best_match = self._find_best_match(parsed_ref, results)
                if best_match:
                    converted_data = self._convert_to_parsed_format(best_match)
                    return {
                        "data": converted_data,
                        "sources": ["doaj"]
                    }
        except Exception as e:
            logger.warning(f"DOAJ API search failed: {e}")
        
        return None
    
    def _find_best_match(self, parsed_ref: Dict[str, Any], api_results: List[Any]) -> Optional[Any]:
        if not api_results:
            return None
        
        if parsed_ref.get("title"):
            best_similarity = 0.0
            best_match = None
            
            for result in api_results:
                if hasattr(result, 'title') and result.title:
                    similarity = self._calculate_similarity(parsed_ref["title"], result.title)
                    
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = result
            
            if best_similarity > 0.7:
                return best_match
        
        return api_results[0]
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity"""
        if not text1 or not text2:
            return 0.0
        
        text1_lower = text1.lower()
        text2_lower = text2.lower()
        
        # Simple word overlap similarity
        words1 = set(text1_lower.split())
        words2 = set(text2_lower.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _convert_to_parsed_format(self, api_result) -> Dict[str, Any]:
        """Convert API result to parsed reference format"""
        result = {
            "family_names": [],
            "given_names": [],
            "year": None,
            "title": None,
            "journal": None,
            "doi": None,
            "pages": None,
            "publisher": None,
            "url": None,
            "abstract": None
        }
        
        # Extract authors
        if hasattr(api_result, 'authors') and api_result.authors:
            for author in api_result.authors:
                if hasattr(author, 'surname') and hasattr(author, 'first_name'):
                    result["family_names"].append(author.surname or "")
                    result["given_names"].append(author.first_name or "")
                elif hasattr(author, 'full_name') and author.full_name:
                    # Try to split full name
                    name_parts = author.full_name.split()
                    if len(name_parts) >= 2:
                        result["family_names"].append(name_parts[-1])
                        result["given_names"].append(name_parts[0])
        
        # Extract other fields
        if hasattr(api_result, 'title') and api_result.title:
            result["title"] = api_result.title
        
        if hasattr(api_result, 'year') and api_result.year:
            result["year"] = str(api_result.year)
        
        if hasattr(api_result, 'journal') and api_result.journal:
            result["journal"] = api_result.journal
        
        if hasattr(api_result, 'doi') and api_result.doi:
            result["doi"] = api_result.doi
        
        if hasattr(api_result, 'pages') and api_result.pages:
            result["pages"] = api_result.pages
        
        if hasattr(api_result, 'publisher') and api_result.publisher:
            result["publisher"] = api_result.publisher
        
        if hasattr(api_result, 'url') and api_result.url:
            result["url"] = api_result.url
        
        if hasattr(api_result, 'abstract') and api_result.abstract:
            result["abstract"] = api_result.abstract
        
        return result
    
    def _merge_api_data(self, original: Dict[str, Any], api_data: Dict[str, Any]) -> Dict[str, Any]:
        merged = original.copy()
        
        for field in ["title", "year", "journal", "doi", "pages", "publisher", "url", "abstract"]:
            if not merged.get(field) and api_data.get(field):
                merged[field] = api_data[field]
        
        if not merged.get("family_names") and api_data.get("family_names"):
            merged["family_names"] = api_data["family_names"]
            merged["given_names"] = api_data["given_names"]
        
        return merged
    
    def _get_missing_fields(self, result: Dict[str, Any]) -> List[str]:
        """Determine which required fields are missing"""
        missing = []
        required_fields = ["family_names", "year", "title"]
        
        for field in required_fields:
            if not result.get(field) or (isinstance(result[field], list) and len(result[field]) == 0):
                missing.append(field)
        
        return missing
    
    def generate_tagged_output(self, parsed_ref: Dict[str, Any], index: int) -> str:
        """Generate XML-like tagged output with enhanced information"""
        ref_id = f"ref{index + 1}"
        
        authors_xml = "<authors>"
        for i, (family, given) in enumerate(zip(parsed_ref.get("family_names", []), parsed_ref.get("given_names", []))):
            if family and given:
                authors_xml += f'<author><fnm>{given}</fnm><surname>{family}</surname></author>'
        authors_xml += "</authors>"
        
        title_xml = ""
        if parsed_ref.get("title"):
            title_xml = f'<title><maintitle>{parsed_ref["title"]}</maintitle></title>'
        
        year_xml = ""
        if parsed_ref.get("year"):
            year_xml = f'<date>{parsed_ref["year"]}</date>'
        
        journal_xml = ""
        if parsed_ref.get("journal"):
            journal_xml = f'<host><issue><series><title><maintitle>{parsed_ref["journal"]}</maintitle></title></series>{year_xml}</issue></host>'
        
        pages_xml = ""
        if parsed_ref.get("pages"):
            if '-' in parsed_ref["pages"] or '–' in parsed_ref["pages"]:
                import re
                page_parts = re.split(r'[-–]', parsed_ref["pages"])
                if len(page_parts) == 2:
                    pages_xml = f'<pages><fpage>{page_parts[0]}</fpage><lpage>{page_parts[1]}</lpage></pages>'
                else:
                    pages_xml = f'<pages>{parsed_ref["pages"]}</pages>'
            else:
                pages_xml = f'<pages><fpage>{parsed_ref["pages"]}</fpage></pages>'
        
        doi_xml = ""
        if parsed_ref.get("doi"):
            doi_xml = f'<comment>DOI: {parsed_ref["doi"]}</comment>'
        
        url_xml = ""
        if parsed_ref.get("url"):
            url_xml = f'<comment>URL: {parsed_ref["url"]}</comment>'
        
        publisher_xml = ""
        if parsed_ref.get("publisher"):
            publisher_xml = f'<comment>Publisher: {parsed_ref["publisher"]}</comment>'
        
        abstract_xml = ""
        if parsed_ref.get("abstract"):
            abstract_xml = f'<comment>Abstract: {parsed_ref["abstract"][:200]}...</comment>'
        
        label = ""
        if parsed_ref.get("family_names"):
            if len(parsed_ref["family_names"]) == 1:
                label = f"{parsed_ref['family_names'][0]}, {parsed_ref.get('year', 'n.d.')}"
            else:
                label = f"{parsed_ref['family_names'][0]} et al., {parsed_ref.get('year', 'n.d.')}"
        
        tagged_output = f'<reference id="{ref_id}">'
        if label:
            tagged_output += f'<label>{label}</label>'
        tagged_output += authors_xml
        tagged_output += title_xml
        tagged_output += journal_xml
        tagged_output += pages_xml
        tagged_output += doi_xml
        tagged_output += url_xml
        tagged_output += publisher_xml
        tagged_output += abstract_xml
        tagged_output += '</reference>'
        
        return tagged_output
