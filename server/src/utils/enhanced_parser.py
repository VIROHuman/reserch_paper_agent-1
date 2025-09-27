"""
Enhanced reference parser that integrates API clients for missing field completion
"""
import asyncio
import re
from typing import List, Dict, Any, Optional
from loguru import logger

from .simple_parser import SimpleReferenceParser
from .api_clients import CrossRefClient, OpenAlexClient, SemanticScholarClient, DOAJClient
from .smart_api_strategy import SmartAPIStrategy
from .doi_metadata_extractor import DOIMetadataExtractor, DOIMetadataConflictDetector
from .flagging_system import ReferenceFlaggingSystem


class EnhancedReferenceParser:
    """Enhanced parser that combines local parsing with API client enrichment"""
    
    def __init__(self):
        self.simple_parser = SimpleReferenceParser()
        
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
    
    async def _enhanced_initial_parsing(self, ref_text: str) -> Dict[str, Any]:
        """Enhanced initial parsing that combines multiple strategies"""
        try:
            # Enhanced parsing with multiple strategies
            # Start with simple parser as base
            parsed_ref = self.simple_parser.parse_reference(ref_text)
            
            # If simple parser didn't extract much, try alternative approaches
            if not parsed_ref.get("title") or len(parsed_ref.get("title", "")) < 10:
                # Try improved title extraction
                parsed_ref["title"] = self._extract_title_enhanced(ref_text)
            
            if not parsed_ref.get("journal") or len(parsed_ref.get("journal", "")) < 5:
                # Try improved journal extraction
                parsed_ref["journal"] = self._extract_journal_enhanced(ref_text)
            
            if not parsed_ref.get("family_names"):
                # Try improved author extraction
                authors = self._extract_authors_enhanced(ref_text)
                parsed_ref["family_names"] = [author["surname"] for author in authors]
                parsed_ref["given_names"] = [author["given"] for author in authors]
            
            # Try to extract publisher if missing
            if not parsed_ref.get("publisher"):
                parsed_ref["publisher"] = self._extract_publisher(ref_text)
            
            # Try to extract URL if missing
            if not parsed_ref.get("url"):
                parsed_ref["url"] = self._extract_url(ref_text)
            
            return parsed_ref
            
        except Exception as e:
            logger.error(f"Enhanced initial parsing error: {str(e)}")
            # Fallback to simple parser
            return self.simple_parser.parse_reference(ref_text)
    
    def _extract_title_enhanced(self, text: str) -> Optional[str]:
        """Enhanced title extraction with multiple strategies"""
        import re
        
        # Strategy 1: Title in quotes
        title_in_quotes = re.search(r'"([^"]{15,})"', text)
        if title_in_quotes:
            return title_in_quotes.group(1).strip()
        
        # Strategy 2: Title between authors and year
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        if year_match:
            before_year = text[:year_match.start()].strip()
            # Look for title patterns
            title_patterns = [
                r'[A-Z][^.]{15,}\.',  # Capital letter followed by long text ending with period
                r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+){2,}',  # Multiple capitalized words
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, before_year)
                if match:
                    title = match.group().strip()
                    if len(title) > 15 and not title.lower().startswith(('vol', 'pp', 'p.')):
                        return title
        
        return None
    
    def _extract_journal_enhanced(self, text: str) -> Optional[str]:
        """Enhanced journal extraction"""
        import re
        
        # Strategy 1: Italicized text
        italic_match = re.search(r'<i>([^<]+)</i>', text)
        if italic_match:
            return italic_match.group(1).strip()
        
        # Strategy 2: Common journal patterns
        journal_patterns = [
            r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*[,.]\s*\d{4}',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*vol',
            r'In:\s*([^,.]{8,})',
        ]
        
        for pattern in journal_patterns:
            match = re.search(pattern, text)
            if match:
                journal = match.group(1).strip()
                if len(journal) > 8:
                    return journal
        
        return None
    
    def _extract_authors_enhanced(self, text: str) -> List[Dict[str, str]]:
        """Enhanced author extraction with title word filtering"""
        import re
        
        authors = []
        
        # Strategy 1: Standard academic format "Last, First" - more specific
        pattern1 = r'(?:^|\s)([A-Z][a-z]{2,}),\s*([A-Z]\.(?:\s*[A-Z]\.)*)(?=\s|$)'
        matches1 = re.findall(pattern1, text)
        
        for surname, given in matches1:
            # Validate that this looks like a real author name
            if self._is_valid_author_name_enhanced(surname, given, text):
                authors.append({
                    "surname": surname.strip(),
                    "given": given.strip().replace('.', '').replace(' ', '')
                })
        
        # Strategy 2: "First Last" format - more specific
        if not authors:
            pattern2 = r'(?:^|\s)([A-Z]\.(?:\s*[A-Z]\.)*)\s+([A-Z][a-z]{2,})(?=\s|$)'
            matches2 = re.findall(pattern2, text)
            
            for given, surname in matches2:
                if self._is_valid_author_name_enhanced(surname, given, text):
                    authors.append({
                        "surname": surname.strip(),
                        "given": given.strip().replace('.', '').replace(' ', '')
                    })
        
        # Final validation: remove any authors that appear to be from the title
        authors = self._filter_title_words_enhanced(authors, text)
        
        return authors[:5]  # Limit to first 5 authors
    
    def _is_valid_author_name_enhanced(self, surname: str, given: str, full_text: str) -> bool:
        """Validate if a name candidate is actually an author name - enhanced version"""
        # Check minimum length requirements
        if len(surname) < 3 or len(given.strip('.')) < 1:
            return False
        
        # Common title words that should not be author names
        title_words = {
            'health', 'care', 'blockchain', 'revolution', 'sweeps', 'offering',
            'possibility', 'much', 'needed', 'data', 'solution', 'reaction',
            'chain', 'system', 'technology', 'digital', 'innovation', 'development',
            'research', 'study', 'analysis', 'approach', 'method', 'model',
            'framework', 'algorithm', 'network', 'platform', 'application',
            'management', 'service', 'process', 'implementation', 'evaluation'
        }
        
        # Don't accept common title words as surnames
        if surname.lower() in title_words:
            return False
        
        return True
    
    def _filter_title_words_enhanced(self, authors: List[Dict[str, str]], full_text: str) -> List[Dict[str, str]]:
        """Filter out author candidates that are likely title words - enhanced version"""
        filtered_authors = []
        
        # Extract potential title section (before year or journal indicators)
        year_match = re.search(r'\b(19|20)\d{2}\b', full_text)
        title_section = full_text[:year_match.start()] if year_match else full_text
        
        for author in authors:
            surname = author['surname']
            
            # Skip if surname appears in title section with title-like context
            if self._appears_in_title_context_enhanced(surname, title_section):
                continue
                
            filtered_authors.append(author)
        
        return filtered_authors
    
    def _appears_in_title_context_enhanced(self, surname: str, title_section: str) -> bool:
        """Check if a surname appears in title-like context - enhanced version"""
        import re
        
        # Look for patterns where the surname is part of a title phrase
        title_context_patterns = [
            r'[A-Z][a-z]*\s+' + re.escape(surname) + r'\s+[A-Z][a-z]*',  # Word Surname Word
            r'[A-Z][a-z]*\s+' + re.escape(surname) + r'[,:]',  # Word Surname, or Word Surname:
            r':\s*[A-Z][a-z]*\s+' + re.escape(surname),  # : Word Surname
            r'[A-Z][a-z]*\s+' + re.escape(surname) + r'\s+[A-Z][a-z]*\s+[A-Z]',  # Word Surname Word Word
        ]
        
        for pattern in title_context_patterns:
            if re.search(pattern, title_section, re.IGNORECASE):
                return True
        
        return False
    
    def _extract_publisher(self, text: str) -> Optional[str]:
        """Extract publisher information"""
        import re
        
        # Common publisher patterns
        publisher_patterns = [
            r'Published by\s+([^,.]{5,})',
            r'Publisher:\s*([^,.]{5,})',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Press',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Publishing',
        ]
        
        for pattern in publisher_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_url(self, text: str) -> Optional[str]:
        """Extract URL from reference"""
        import re
        
        # Look for URLs
        url_pattern = r'https?://[^\s,)]+'
        match = re.search(url_pattern, text)
        if match:
            return match.group().strip()
        
        return None
    
    async def parse_reference_enhanced(
        self, 
        ref_text: str, 
        enable_api_enrichment: bool = True
    ) -> Dict[str, Any]:
        try:
            # Use enhanced parsing strategy - combine multiple approaches
            parsed_ref = await self._enhanced_initial_parsing(ref_text)
            parser_used = "enhanced"
            
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
                
                # Calculate status and confidence
                status_info = self._calculate_status_and_confidence(enriched_ref, enriched_ref.get("flagging_analysis", {}))
                enriched_ref.update(status_info)
                
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
                
                # Calculate status and confidence
                status_info = self._calculate_status_and_confidence(parsed_ref, parsed_ref.get("flagging_analysis", {}))
                parsed_ref.update(status_info)
                
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
    
    def _calculate_status_and_confidence(self, parsed_ref: Dict[str, Any], flagging_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate Verified/Suspect/Unverified status and confidence"""
        try:
            # Extract key metrics
            has_timeout = any("timeout" in str(flag).lower() for flag in flagging_analysis.get("flags", []))
            has_conflicts = flagging_analysis.get("has_conflicts", False)
            has_domain_issues = any("domain" in str(flag).lower() for flag in flagging_analysis.get("flags", []))
            
            # Calculate confidence based on available fields
            confidence = 0.0
            field_count = 0
            
            if parsed_ref.get("title"):
                confidence += 0.2
                field_count += 1
            if parsed_ref.get("family_names"):
                confidence += 0.2
                field_count += 1
            if parsed_ref.get("year"):
                confidence += 0.15
                field_count += 1
            if parsed_ref.get("journal"):
                confidence += 0.15
                field_count += 1
            if parsed_ref.get("doi"):
                confidence += 0.2
                field_count += 1
            if parsed_ref.get("pages"):
                confidence += 0.1
                field_count += 1
            
            # Determine status based on requirements
            if has_timeout or has_conflicts or has_domain_issues:
                status = "Unverified"
                confidence = min(confidence, 0.3)  # Cap confidence for problematic cases
            elif confidence >= 0.8 and field_count >= 5:
                status = "Verified"
            elif confidence >= 0.6:
                status = "Suspect"
            else:
                status = "Unverified"
            
            # Generate reasons
            reasons = []
            if confidence < 0.6:
                reasons.append("low confidence")
            if has_timeout:
                reasons.append("timeout")
            if has_conflicts:
                reasons.append("source conflict")
            if has_domain_issues:
                reasons.append("domain mismatch")
            if field_count < 4:
                reasons.append("insufficient fields")
            
            # Determine matched fields
            matched_fields = []
            if parsed_ref.get("doi"):
                matched_fields.append("doi")
            if parsed_ref.get("journal"):
                matched_fields.append("journal")
            if parsed_ref.get("abstract"):
                matched_fields.append("abstract")
            if parsed_ref.get("url"):
                matched_fields.append("url")
            
            # Determine sources used
            sources_used = []
            if parsed_ref.get("api_enrichment_used"):
                sources_used.extend(parsed_ref.get("enrichment_sources", []))
            if parsed_ref.get("doi_metadata"):
                sources_used.append("DOI")
            
            return {
                "status": status,
                "confidence": round(confidence, 2),
                "sources_used": sources_used,
                "matched_fields": matched_fields,
                "reasons": reasons,
                "domain_check": "pass" if not has_domain_issues else "fail",
                "timeout": has_timeout
            }
            
        except Exception as e:
            logger.error(f"Error calculating status: {e}")
            return {
                "status": "Unverified",
                "confidence": 0.0,
                "sources_used": [],
                "matched_fields": [],
                "reasons": ["calculation error"],
                "domain_check": "unknown",
                "timeout": False
            }
