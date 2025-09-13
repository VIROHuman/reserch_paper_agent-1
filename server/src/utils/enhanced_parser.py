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
        
        logger.info("✅ Enhanced reference parser initialized with Smart API Strategy and DOI extraction")
    
    async def parse_reference_enhanced(
        self, 
        ref_text: str, 
        use_ollama: bool = True,
        enable_api_enrichment: bool = True
    ) -> Dict[str, Any]:
        """Parse reference with API enrichment"""
        logger.info(f"🔍 ENHANCED PARSING START")
        logger.info(f"📝 Input text: {ref_text[:100]}{'...' if len(ref_text) > 100 else ''}")
        logger.info(f"🤖 Use Ollama: {use_ollama}")
        logger.info(f"🌐 API Enrichment: {enable_api_enrichment}")
        
        try:
            # First, parse with local parser
            logger.info(f"🔧 STEP 1: Local parsing")
            if use_ollama and self.ollama_parser.client:
                logger.info(f"🤖 Using Ollama parser")
                parsed_ref = self.ollama_parser.parse_reference(ref_text)
                parser_used = "ollama"
                logger.info(f"✅ Ollama parsing completed")
            else:
                logger.info(f"📝 Using simple parser")
                parsed_ref = self.simple_parser.parse_reference(ref_text)
                parser_used = "simple"
                logger.info(f"✅ Simple parsing completed")
            
            # Debug: Show initial parsing results
            logger.info(f"📊 INITIAL PARSING RESULTS:")
            logger.info(f"  Parser used: {parser_used}")
            logger.info(f"  Title: {parsed_ref.get('title', 'None')}")
            logger.info(f"  Authors: {parsed_ref.get('family_names', [])}")
            logger.info(f"  Year: {parsed_ref.get('year', 'None')}")
            logger.info(f"  Journal: {parsed_ref.get('journal', 'None')}")
            logger.info(f"  DOI: {parsed_ref.get('doi', 'None')}")
            logger.info(f"  Missing fields: {parsed_ref.get('missing_fields', [])}")
            
            # STEP 1.5: DOI Metadata Extraction and Conflict Detection
            doi_metadata = None
            conflict_analysis = None
            if parsed_ref.get('doi'):
                logger.info(f"🔍 DOI METADATA EXTRACTION: {parsed_ref.get('doi')}")
                try:
                    doi_metadata = await self.doi_extractor.extract_metadata(parsed_ref.get('doi'))
                    if doi_metadata and not doi_metadata.get('error'):
                        logger.info(f"✅ DOI metadata extracted from {doi_metadata.get('source_api', 'unknown')}")
                        
                        # Detect conflicts between online metadata and Ollama data
                        conflict_analysis = self.conflict_detector.detect_conflicts(doi_metadata, parsed_ref)
                        
                        if conflict_analysis.get('has_conflicts'):
                            logger.warning(f"⚠️ CONFLICTS DETECTED between online and Ollama data:")
                            for conflict in conflict_analysis.get('conflicts', []):
                                logger.warning(f"  {conflict['field']}: Online='{conflict['online_value']}' vs Ollama='{conflict['ollama_value']}' -> Preferred: {conflict['preferred']}")
                        else:
                            logger.info(f"✅ No conflicts detected between online and Ollama data")
                    else:
                        logger.warning(f"⚠️ DOI metadata extraction failed: {doi_metadata.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"❌ DOI metadata extraction error: {str(e)}")
            
            # Always try smart API enrichment for cross-checking and quality improvement
            if enable_api_enrichment:
                logger.info(f"🌐 STEP 2: Smart API enrichment for cross-checking and quality improvement")
                enriched_ref = await self.smart_api.enrich_reference_smart(
                    parsed_ref, 
                    ref_text,
                    force_enrichment=True  # Always enrich for cross-checking
                )
                enriched_ref["parser_used"] = parser_used
                enriched_ref["api_enrichment_used"] = True
                
                # Debug: Show final enriched results
                logger.info(f"📊 FINAL ENRICHED RESULTS:")
                logger.info(f"  Parser used: {enriched_ref.get('parser_used')}")
                logger.info(f"  API enrichment used: {enriched_ref.get('api_enrichment_used')}")
                logger.info(f"  Enrichment sources: {enriched_ref.get('enrichment_sources', [])}")
                logger.info(f"  Quality improvement: {enriched_ref.get('quality_improvement', 0):.2f}")
                logger.info(f"  Final quality score: {enriched_ref.get('final_quality_score', 0):.2f}")
                logger.info(f"  Title: {enriched_ref.get('title', 'None')}")
                logger.info(f"  Authors: {enriched_ref.get('family_names', [])}")
                logger.info(f"  Year: {enriched_ref.get('year', 'None')}")
                logger.info(f"  Journal: {enriched_ref.get('journal', 'None')}")
                logger.info(f"  DOI: {enriched_ref.get('doi', 'None')}")
                logger.info(f"  Publisher: {enriched_ref.get('publisher', 'None')}")
                logger.info(f"  URL: {enriched_ref.get('url', 'None')}")
                logger.info(f"  Abstract: {enriched_ref.get('abstract', 'None')[:100] if enriched_ref.get('abstract') else 'None'}")
                logger.info(f"  Missing fields: {enriched_ref.get('missing_fields', [])}")
                
                # Log author analysis
                author_analysis = enriched_ref.get('author_analysis', {})
                if author_analysis:
                    logger.info(f"👥 Final Author Analysis:")
                    logger.info(f"  Has authors: {author_analysis.get('has_authors', False)}")
                    logger.info(f"  Author count: {author_analysis.get('author_count', 0)}")
                    logger.info(f"  Completeness: {author_analysis.get('completeness_ratio', 0):.2f}")
                    logger.info(f"  Quality score: {author_analysis.get('quality_score', 0):.2f}")
                    if author_analysis.get('issues'):
                        logger.info(f"  Issues: {author_analysis['issues']}")
                
                # Add DOI metadata and conflict analysis to the result
                enriched_ref["doi_metadata"] = doi_metadata
                enriched_ref["conflict_analysis"] = conflict_analysis
                
                # If there are conflicts, prefer online data over Ollama data
                if conflict_analysis and conflict_analysis.get('has_conflicts'):
                    logger.info(f"🔄 APPLYING CONFLICT RESOLUTION: Preferring online data over Ollama data")
                    for field, value in conflict_analysis.get('preferred_data', {}).items():
                        if value:  # Only update if online data has a value
                            enriched_ref[field] = value
                            logger.info(f"  Updated {field}: {value}")
                
                return enriched_ref
            else:
                logger.info(f"⏭️  STEP 2: Skipping API enrichment (disabled)")
                parsed_ref["parser_used"] = parser_used
                parsed_ref["api_enrichment_used"] = False
                
                # Add DOI metadata and conflict analysis to the result even without API enrichment
                parsed_ref["doi_metadata"] = doi_metadata
                parsed_ref["conflict_analysis"] = conflict_analysis
                
                # If there are conflicts, prefer online data over Ollama data
                if conflict_analysis and conflict_analysis.get('has_conflicts'):
                    logger.info(f"🔄 APPLYING CONFLICT RESOLUTION: Preferring online data over Ollama data")
                    for field, value in conflict_analysis.get('preferred_data', {}).items():
                        if value:  # Only update if online data has a value
                            parsed_ref[field] = value
                            logger.info(f"  Updated {field}: {value}")
                
                return parsed_ref
                
        except Exception as e:
            logger.error(f"❌ Error in enhanced parsing: {e}")
            # Fallback to simple parsing
            logger.info(f"🔄 FALLBACK: Using simple parser")
            parsed_ref = self.simple_parser.parse_reference(ref_text)
            parsed_ref["parser_used"] = "simple"
            parsed_ref["api_enrichment_used"] = False
            parsed_ref["error"] = str(e)
            return parsed_ref
    
    async def _enrich_with_apis(self, parsed_ref: Dict[str, Any], original_text: str) -> Dict[str, Any]:
        """Enrich parsed reference using multiple API clients"""
        logger.info(f"🌐 API ENRICHMENT START")
        enriched_ref = parsed_ref.copy()
        enrichment_sources = []
        
        # Create search query from available information
        search_query = self._create_search_query(parsed_ref, original_text)
        
        if not search_query:
            logger.warning("❌ No search query could be created for API enrichment")
            return enriched_ref
        
        logger.info(f"🔍 Search query created: '{search_query}'")
        
        # Try multiple APIs in parallel
        api_names = ["CrossRef", "OpenAlex", "Semantic Scholar", "DOAJ"]
        api_tasks = [
            self._search_crossref(search_query, enriched_ref),
            self._search_openalex(search_query, enriched_ref),
            self._search_semantic_scholar(search_query, enriched_ref),
            self._search_doaj(search_query, enriched_ref)
        ]
        
        logger.info(f"🚀 Starting parallel API searches...")
        
        try:
            # Run all API searches in parallel
            results = await asyncio.gather(*api_tasks, return_exceptions=True)
            
            # Process results and merge information
            logger.info(f"📊 API SEARCH RESULTS:")
            for i, (api_name, result) in enumerate(zip(api_names, results)):
                if isinstance(result, Exception):
                    logger.warning(f"  ❌ {api_name}: Failed - {result}")
                    continue
                
                if result and result.get("sources"):
                    logger.info(f"  ✅ {api_name}: Found {len(result.get('data', {}).get('title', ''))} chars of data")
                    logger.info(f"      Sources: {result.get('sources')}")
                    logger.info(f"      Data preview: {str(result.get('data', {}))[:200]}...")
                    
                    enrichment_sources.extend(result["sources"])
                    
                    # Show what fields will be merged
                    logger.info(f"      Merging fields: {[k for k, v in result.get('data', {}).items() if v]}")
                    enriched_ref = self._merge_api_data(enriched_ref, result["data"])
                else:
                    logger.info(f"  ⚠️  {api_name}: No results found")
            
            # Update missing fields after enrichment
            enriched_ref["missing_fields"] = self._get_missing_fields(enriched_ref)
            enriched_ref["enrichment_sources"] = list(set(enrichment_sources))
            
            logger.info(f"✅ API enrichment completed. Sources: {enriched_ref.get('enrichment_sources', [])}")
            logger.info(f"📈 Enrichment summary: {len(enrichment_sources)} sources contributed data")
            
        except Exception as e:
            logger.error(f"❌ Error during API enrichment: {e}")
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
        """Search CrossRef API"""
        logger.info(f"🔍 CrossRef API: Searching for '{query}'")
        try:
            results = await self.crossref_client.search_reference(query, limit=3)
            logger.info(f"📊 CrossRef API: Found {len(results)} results")
            
            if results:
                for i, result in enumerate(results):
                    logger.info(f"  Result {i+1}: {result.title[:50] if hasattr(result, 'title') and result.title else 'No title'}...")
                
                best_match = self._find_best_match(parsed_ref, results)
                if best_match:
                    logger.info(f"✅ CrossRef API: Best match found - {best_match.title[:50] if hasattr(best_match, 'title') and best_match.title else 'No title'}...")
                    converted_data = self._convert_to_parsed_format(best_match)
                    logger.info(f"📋 CrossRef API: Converted data - {converted_data}")
                    return {
                        "data": converted_data,
                        "sources": ["crossref"]
                    }
                else:
                    logger.info(f"⚠️  CrossRef API: No suitable match found")
            else:
                logger.info(f"⚠️  CrossRef API: No results returned")
        except Exception as e:
            logger.warning(f"❌ CrossRef API: Search failed - {e}")
        
        return None
    
    async def _search_openalex(self, query: str, parsed_ref: Dict[str, Any]) -> Dict[str, Any]:
        """Search OpenAlex API"""
        logger.info(f"🔍 OpenAlex API: Searching for '{query}'")
        try:
            results = await self.openalex_client.search_reference(query, limit=3)
            logger.info(f"📊 OpenAlex API: Found {len(results)} results")
            
            if results:
                for i, result in enumerate(results):
                    logger.info(f"  Result {i+1}: {result.title[:50] if hasattr(result, 'title') and result.title else 'No title'}...")
                
                best_match = self._find_best_match(parsed_ref, results)
                if best_match:
                    logger.info(f"✅ OpenAlex API: Best match found - {best_match.title[:50] if hasattr(best_match, 'title') and best_match.title else 'No title'}...")
                    converted_data = self._convert_to_parsed_format(best_match)
                    logger.info(f"📋 OpenAlex API: Converted data - {converted_data}")
                    return {
                        "data": converted_data,
                        "sources": ["openalex"]
                    }
                else:
                    logger.info(f"⚠️  OpenAlex API: No suitable match found")
            else:
                logger.info(f"⚠️  OpenAlex API: No results returned")
        except Exception as e:
            logger.warning(f"❌ OpenAlex API: Search failed - {e}")
        
        return None
    
    async def _search_semantic_scholar(self, query: str, parsed_ref: Dict[str, Any]) -> Dict[str, Any]:
        """Search Semantic Scholar API"""
        logger.info(f"🔍 Semantic Scholar API: Searching for '{query}'")
        try:
            results = await self.semantic_client.search_reference(query, limit=3)
            logger.info(f"📊 Semantic Scholar API: Found {len(results)} results")
            
            if results:
                for i, result in enumerate(results):
                    logger.info(f"  Result {i+1}: {result.title[:50] if hasattr(result, 'title') and result.title else 'No title'}...")
                
                best_match = self._find_best_match(parsed_ref, results)
                if best_match:
                    logger.info(f"✅ Semantic Scholar API: Best match found - {best_match.title[:50] if hasattr(best_match, 'title') and best_match.title else 'No title'}...")
                    converted_data = self._convert_to_parsed_format(best_match)
                    logger.info(f"📋 Semantic Scholar API: Converted data - {converted_data}")
                    return {
                        "data": converted_data,
                        "sources": ["semantic_scholar"]
                    }
                else:
                    logger.info(f"⚠️  Semantic Scholar API: No suitable match found")
            else:
                logger.info(f"⚠️  Semantic Scholar API: No results returned")
        except Exception as e:
            logger.warning(f"❌ Semantic Scholar API: Search failed - {e}")
        
        return None
    
    async def _search_doaj(self, query: str, parsed_ref: Dict[str, Any]) -> Dict[str, Any]:
        """Search DOAJ API"""
        logger.info(f"🔍 DOAJ API: Searching for '{query}'")
        try:
            results = await self.doaj_client.search_reference(query, limit=3)
            logger.info(f"📊 DOAJ API: Found {len(results)} results")
            
            if results:
                for i, result in enumerate(results):
                    logger.info(f"  Result {i+1}: {result.title[:50] if hasattr(result, 'title') and result.title else 'No title'}...")
                
                best_match = self._find_best_match(parsed_ref, results)
                if best_match:
                    logger.info(f"✅ DOAJ API: Best match found - {best_match.title[:50] if hasattr(best_match, 'title') and best_match.title else 'No title'}...")
                    converted_data = self._convert_to_parsed_format(best_match)
                    logger.info(f"📋 DOAJ API: Converted data - {converted_data}")
                    return {
                        "data": converted_data,
                        "sources": ["doaj"]
                    }
                else:
                    logger.info(f"⚠️  DOAJ API: No suitable match found")
            else:
                logger.info(f"⚠️  DOAJ API: No results returned")
        except Exception as e:
            logger.warning(f"❌ DOAJ API: Search failed - {e}")
        
        return None
    
    def _find_best_match(self, parsed_ref: Dict[str, Any], api_results: List[Any]) -> Optional[Any]:
        """Find the best matching result from API responses"""
        if not api_results:
            logger.info(f"🔍 Matching: No API results to match against")
            return None
        
        logger.info(f"🔍 Matching: Comparing against {len(api_results)} API results")
        
        # Simple matching based on title similarity
        if parsed_ref.get("title"):
            logger.info(f"🔍 Matching: Using title similarity matching")
            logger.info(f"  Original title: '{parsed_ref.get('title')}'")
            
            best_similarity = 0.0
            best_match = None
            
            for i, result in enumerate(api_results):
                if hasattr(result, 'title') and result.title:
                    similarity = self._calculate_similarity(parsed_ref["title"], result.title)
                    logger.info(f"  Result {i+1}: '{result.title[:50]}...' - Similarity: {similarity:.2f}")
                    
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = result
            
            if best_similarity > 0.7:
                logger.info(f"✅ Matching: Best match found with similarity {best_similarity:.2f}")
                return best_match
            else:
                logger.info(f"⚠️  Matching: No good title match found (best: {best_similarity:.2f})")
        
        # If no good title match, return first result
        logger.info(f"🔍 Matching: Using first result as fallback")
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
        """Merge API data into original parsed reference"""
        logger.info(f"🔄 Merging: Starting data merge")
        logger.info(f"  Original data: {original}")
        logger.info(f"  API data: {api_data}")
        
        merged = original.copy()
        merged_fields = []
        
        # Only fill in missing fields, don't overwrite existing good data
        for field in ["title", "year", "journal", "doi", "pages", "publisher", "url", "abstract"]:
            if not merged.get(field) and api_data.get(field):
                logger.info(f"  ✅ Merging {field}: '{api_data[field]}'")
                merged[field] = api_data[field]
                merged_fields.append(field)
            elif merged.get(field):
                logger.info(f"  ⏭️  Skipping {field}: Already exists ('{merged[field]}')")
            else:
                logger.info(f"  ⚠️  Skipping {field}: Not available in API data")
        
        # For authors, only add if we don't have any
        if not merged.get("family_names") and api_data.get("family_names"):
            logger.info(f"  ✅ Merging authors: {api_data.get('family_names', [])}")
            merged["family_names"] = api_data["family_names"]
            merged["given_names"] = api_data["given_names"]
            merged_fields.append("authors")
        elif merged.get("family_names"):
            logger.info(f"  ⏭️  Skipping authors: Already exist ({merged.get('family_names', [])})")
        else:
            logger.info(f"  ⚠️  Skipping authors: Not available in API data")
        
        logger.info(f"🔄 Merging: Completed. Merged fields: {merged_fields}")
        logger.info(f"  Final merged data: {merged}")
        
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
        
        # Build authors section
        authors_xml = "<authors>"
        for i, (family, given) in enumerate(zip(parsed_ref.get("family_names", []), parsed_ref.get("given_names", []))):
            if family and given:
                authors_xml += f'<author><fnm>{given}</fnm><surname>{family}</surname></author>'
        authors_xml += "</authors>"
        
        # Build title section
        title_xml = ""
        if parsed_ref.get("title"):
            title_xml = f'<title><maintitle>{parsed_ref["title"]}</maintitle></title>'
        
        # Build year section
        year_xml = ""
        if parsed_ref.get("year"):
            year_xml = f'<date>{parsed_ref["year"]}</date>'
        
        # Build journal section
        journal_xml = ""
        if parsed_ref.get("journal"):
            journal_xml = f'<host><issue><series><title><maintitle>{parsed_ref["journal"]}</maintitle></title></series>{year_xml}</issue></host>'
        
        # Build pages section
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
        
        # Build DOI section
        doi_xml = ""
        if parsed_ref.get("doi"):
            doi_xml = f'<comment>DOI: {parsed_ref["doi"]}</comment>'
        
        # Build URL section
        url_xml = ""
        if parsed_ref.get("url"):
            url_xml = f'<comment>URL: {parsed_ref["url"]}</comment>'
        
        # Build publisher section
        publisher_xml = ""
        if parsed_ref.get("publisher"):
            publisher_xml = f'<comment>Publisher: {parsed_ref["publisher"]}</comment>'
        
        # Build abstract section
        abstract_xml = ""
        if parsed_ref.get("abstract"):
            abstract_xml = f'<comment>Abstract: {parsed_ref["abstract"][:200]}...</comment>'
        
        # Create label
        label = ""
        if parsed_ref.get("family_names"):
            if len(parsed_ref["family_names"]) == 1:
                label = f"{parsed_ref['family_names'][0]}, {parsed_ref.get('year', 'n.d.')}"
            else:
                label = f"{parsed_ref['family_names'][0]} et al., {parsed_ref.get('year', 'n.d.')}"
        
        # Combine everything
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
