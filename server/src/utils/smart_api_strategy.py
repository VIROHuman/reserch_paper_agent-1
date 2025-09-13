"""
Smart API strategy for optimized reference enrichment
"""
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from dataclasses import dataclass
from enum import Enum

from .api_clients import CrossRefClient, OpenAlexClient, SemanticScholarClient, DOAJClient


class APIProvider(Enum):
    CROSSREF = "crossref"
    OPENALEX = "openalex"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    DOAJ = "doaj"


@dataclass
class APIResult:
    provider: APIProvider
    data: Dict[str, Any]
    quality_score: float
    confidence: float
    fields_found: List[str]
    response_time: float


@dataclass
class QualityMetrics:
    title_similarity: float
    author_match_ratio: float
    year_match: bool
    journal_similarity: float
    doi_match: bool
    overall_confidence: float


class SmartAPIStrategy:
    """Smart API strategy with priority ordering and early exit"""
    
    def __init__(self):
        # Initialize API clients
        self.crossref_client = CrossRefClient()
        self.openalex_client = OpenAlexClient()
        self.semantic_client = SemanticScholarClient()
        self.doaj_client = DOAJClient()
        
        # API priority order (most reliable first)
        self.api_priority = [
            APIProvider.CROSSREF,
            APIProvider.OPENALEX,
            APIProvider.SEMANTIC_SCHOLAR,
            APIProvider.DOAJ
        ]
        
        # Quality thresholds
        self.min_quality_score = 0.7
        self.min_confidence = 0.6
        self.max_api_calls = 3  # Stop after 3 successful API calls
        
        logger.info("✅ Smart API Strategy initialized")
    
    async def enrich_reference_smart(
        self, 
        parsed_ref: Dict[str, Any], 
        original_text: str,
        force_enrichment: bool = True
    ) -> Dict[str, Any]:
        """Smart enrichment with priority ordering and early exit"""
        logger.info(f"🧠 SMART API ENRICHMENT START")
        logger.info(f"📝 Input: {original_text[:100]}...")
        logger.info(f"🔍 Force enrichment: {force_enrichment}")
        
        enriched_ref = parsed_ref.copy()
        enrichment_sources = []
        api_results = []
        
        # Create search query
        search_query = self._create_optimized_search_query(parsed_ref, original_text)
        if not search_query:
            logger.warning("❌ No search query could be created")
            return enriched_ref
        
        logger.info(f"🔍 Optimized search query: '{search_query}'")
        
        # Calculate initial data quality
        initial_quality = self._calculate_data_quality(parsed_ref)
        logger.info(f"📊 Initial data quality: {initial_quality.overall_confidence:.2f}")
        
        # Determine if we need enrichment
        needs_enrichment = self._needs_enrichment(parsed_ref, initial_quality, force_enrichment)
        author_analysis = self._analyze_authors(parsed_ref)
        
        # Log author analysis
        logger.info(f"👥 Author Analysis:")
        logger.info(f"  Has authors: {author_analysis['has_authors']}")
        logger.info(f"  Author count: {author_analysis['author_count']}")
        logger.info(f"  Completeness: {author_analysis['completeness_ratio']:.2f}")
        logger.info(f"  Quality score: {author_analysis['quality_score']:.2f}")
        if author_analysis['issues']:
            logger.info(f"  Issues: {author_analysis['issues']}")
        
        if not needs_enrichment:
            logger.info("⏭️  No enrichment needed - data quality is sufficient")
            return enriched_ref
        
        # Try APIs in priority order with early exit
        for i, provider in enumerate(self.api_priority):
            if len(api_results) >= self.max_api_calls:
                logger.info(f"🛑 Reached max API calls limit ({self.max_api_calls})")
                break
            
            logger.info(f"🔍 Trying {provider.value} (priority {i+1})")
            
            try:
                result = await self._call_api_with_timeout(provider, search_query, parsed_ref)
                if result:
                    api_results.append(result)
                    logger.info(f"✅ {provider.value}: Quality {result.quality_score:.2f}, Confidence {result.confidence:.2f}")
                    
                    # Merge the result
                    enriched_ref = self._merge_api_result(enriched_ref, result)
                    enrichment_sources.append(provider.value)
                    
                    # Check if we have sufficient data quality now
                    current_quality = self._calculate_data_quality(enriched_ref)
                    if current_quality.overall_confidence >= self.min_confidence:
                        logger.info(f"🎯 Sufficient data quality reached: {current_quality.overall_confidence:.2f}")
                        break
                else:
                    logger.info(f"⚠️  {provider.value}: No results or failed")
                    
            except Exception as e:
                logger.warning(f"❌ {provider.value}: Error - {e}")
                continue
        
        # Final quality assessment
        final_quality = self._calculate_data_quality(enriched_ref)
        final_author_analysis = self._analyze_authors(enriched_ref)
        
        enriched_ref["enrichment_sources"] = enrichment_sources
        enriched_ref["quality_improvement"] = final_quality.overall_confidence - initial_quality.overall_confidence
        enriched_ref["final_quality_score"] = final_quality.overall_confidence
        enriched_ref["author_analysis"] = final_author_analysis
        
        logger.info(f"✅ Smart enrichment completed")
        logger.info(f"  Sources used: {enrichment_sources}")
        logger.info(f"  Quality improvement: {enriched_ref['quality_improvement']:.2f}")
        logger.info(f"  Final quality: {final_quality.overall_confidence:.2f}")
        
        return enriched_ref
    
    def _create_optimized_search_query(self, parsed_ref: Dict[str, Any], original_text: str) -> Optional[str]:
        """Create optimized search query with better strategies"""
        query_strategies = []
        
        # Strategy 1: Title + First Author + Year (most reliable)
        if parsed_ref.get("title") and parsed_ref.get("family_names") and parsed_ref.get("year"):
            query_strategies.append(f"{parsed_ref['title']} {parsed_ref['family_names'][0]} {parsed_ref['year']}")
        
        # Strategy 2: Title + First Author
        if parsed_ref.get("title") and parsed_ref.get("family_names"):
            query_strategies.append(f"{parsed_ref['title']} {parsed_ref['family_names'][0]}")
        
        # Strategy 3: First Author + Year + Journal
        if parsed_ref.get("family_names") and parsed_ref.get("year") and parsed_ref.get("journal"):
            query_strategies.append(f"{parsed_ref['family_names'][0]} {parsed_ref['year']} {parsed_ref['journal']}")
        
        # Strategy 4: Title only
        if parsed_ref.get("title"):
            query_strategies.append(parsed_ref["title"])
        
        # Strategy 5: Original text (fallback)
        if original_text and len(original_text) > 10:
            query_strategies.append(original_text[:200])
        
        # Return the best strategy (first one that exists)
        for strategy in query_strategies:
            if strategy and len(strategy.strip()) > 5:
                logger.info(f"🔍 Using query strategy: '{strategy[:100]}...'")
                return strategy.strip()
        
        return None
    
    def _calculate_data_quality(self, parsed_ref: Dict[str, Any]) -> QualityMetrics:
        """Calculate comprehensive data quality metrics"""
        # Title quality
        title_quality = 1.0 if parsed_ref.get("title") and len(parsed_ref["title"]) > 10 else 0.0
        
        # Author quality - enhanced analysis
        author_quality = 0.0
        author_analysis = self._analyze_authors(parsed_ref)
        
        if author_analysis["has_authors"]:
            # Score based on completeness and quality
            completeness_score = author_analysis["completeness_ratio"]
            quality_score = author_analysis["quality_score"]
            author_quality = (completeness_score + quality_score) / 2.0
        
        # Year quality
        year_quality = 1.0 if parsed_ref.get("year") and str(parsed_ref["year"]).isdigit() else 0.0
        
        # Journal quality
        journal_quality = 1.0 if parsed_ref.get("journal") and len(parsed_ref["journal"]) > 5 else 0.0
        
        # DOI quality
        doi_quality = 1.0 if parsed_ref.get("doi") else 0.0
        
        # Pages quality
        pages_quality = 1.0 if parsed_ref.get("pages") else 0.0
        
        # Calculate overall confidence
        weights = {
            "title": 0.25,
            "authors": 0.25,
            "year": 0.15,
            "journal": 0.15,
            "doi": 0.10,
            "pages": 0.10
        }
        
        overall_confidence = (
            title_quality * weights["title"] +
            author_quality * weights["authors"] +
            year_quality * weights["year"] +
            journal_quality * weights["journal"] +
            doi_quality * weights["doi"] +
            pages_quality * weights["pages"]
        )
        
        return QualityMetrics(
            title_similarity=title_quality,
            author_match_ratio=author_quality,
            year_match=bool(year_quality),
            journal_similarity=journal_quality,
            doi_match=bool(doi_quality),
            overall_confidence=overall_confidence
        )
    
    def _needs_enrichment(self, parsed_ref: Dict[str, Any], quality: QualityMetrics, force_enrichment: bool) -> bool:
        """Determine if enrichment is needed"""
        if force_enrichment:
            return True
        
        # Check for missing critical fields
        critical_fields = ["title", "family_names", "year"]
        missing_critical = [field for field in critical_fields if not parsed_ref.get(field)]
        
        if missing_critical:
            logger.info(f"🔍 Missing critical fields: {missing_critical}")
            return True
        
        # Check quality threshold
        if quality.overall_confidence < self.min_confidence:
            logger.info(f"🔍 Quality below threshold: {quality.overall_confidence:.2f} < {self.min_confidence}")
            return True
        
        return False
    
    def _analyze_authors(self, parsed_ref: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze author data quality and completeness"""
        family_names = parsed_ref.get("family_names", [])
        given_names = parsed_ref.get("given_names", [])
        
        analysis = {
            "has_authors": bool(family_names),
            "author_count": len(family_names),
            "completeness_ratio": 0.0,
            "quality_score": 0.0,
            "missing_given_names": 0,
            "incomplete_authors": 0,
            "issues": []
        }
        
        if not family_names:
            analysis["issues"].append("No authors found")
            return analysis
        
        # Check completeness (family names vs given names)
        if given_names:
            analysis["completeness_ratio"] = min(len(given_names) / len(family_names), 1.0)
            analysis["missing_given_names"] = max(0, len(family_names) - len(given_names))
        else:
            analysis["completeness_ratio"] = 0.0
            analysis["missing_given_names"] = len(family_names)
            analysis["issues"].append("No given names found")
        
        # Check quality of author names
        quality_issues = 0
        for i, (family, given) in enumerate(zip(family_names, given_names or [])):
            # Check if family name is meaningful
            if not family or len(family.strip()) < 2:
                quality_issues += 1
                analysis["issues"].append(f"Author {i+1}: Invalid family name '{family}'")
            
            # Check if given name is meaningful (if present)
            if given and len(given.strip()) < 1:
                quality_issues += 1
                analysis["issues"].append(f"Author {i+1}: Invalid given name '{given}'")
        
        analysis["incomplete_authors"] = quality_issues
        analysis["quality_score"] = max(0.0, 1.0 - (quality_issues / len(family_names)))
        
        # Add specific issues
        if analysis["missing_given_names"] > 0:
            analysis["issues"].append(f"Missing {analysis['missing_given_names']} given names")
        
        if analysis["completeness_ratio"] < 0.5:
            analysis["issues"].append("Less than 50% of authors have given names")
        
        return analysis
    
    async def _call_api_with_timeout(self, provider: APIProvider, query: str, parsed_ref: Dict[str, Any]) -> Optional[APIResult]:
        """Call API with timeout and quality assessment"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Call the appropriate API
            if provider == APIProvider.CROSSREF:
                results = await asyncio.wait_for(
                    self.crossref_client.search_reference(query, limit=3),
                    timeout=8.0
                )
            elif provider == APIProvider.OPENALEX:
                results = await asyncio.wait_for(
                    self.openalex_client.search_reference(query, limit=3),
                    timeout=8.0
                )
            elif provider == APIProvider.SEMANTIC_SCHOLAR:
                results = await asyncio.wait_for(
                    self.semantic_client.search_reference(query, limit=3),
                    timeout=8.0
                )
            elif provider == APIProvider.DOAJ:
                results = await asyncio.wait_for(
                    self.doaj_client.search_reference(query, limit=3),
                    timeout=8.0
                )
            else:
                return None
            
            response_time = asyncio.get_event_loop().time() - start_time
            
            if not results:
                return None
            
            # Find best match and assess quality
            best_match = self._find_best_match_smart(parsed_ref, results)
            if not best_match:
                return None
            
            # Convert to our format
            converted_data = self._convert_to_parsed_format(best_match)
            
            # Calculate quality metrics
            quality_score = self._calculate_match_quality(parsed_ref, converted_data)
            confidence = self._calculate_confidence(converted_data)
            
            return APIResult(
                provider=provider,
                data=converted_data,
                quality_score=quality_score,
                confidence=confidence,
                fields_found=[k for k, v in converted_data.items() if v],
                response_time=response_time
            )
            
        except asyncio.TimeoutError:
            logger.warning(f"⏰ {provider.value}: Timeout after 8s")
            return None
        except Exception as e:
            logger.warning(f"❌ {provider.value}: Error - {e}")
            return None
    
    def _find_best_match_smart(self, parsed_ref: Dict[str, Any], api_results: List[Any]) -> Optional[Any]:
        """Smart matching with multiple criteria"""
        if not api_results:
            return None
        
        best_match = None
        best_score = 0.0
        
        for result in api_results:
            if not hasattr(result, 'title') or not result.title:
                continue
            
            # Calculate similarity score
            title_sim = self._calculate_similarity(
                parsed_ref.get("title", ""), 
                result.title
            )
            
            # Check year match
            year_match = 0.0
            if parsed_ref.get("year") and hasattr(result, 'year') and result.year:
                if str(parsed_ref["year"]) == str(result.year):
                    year_match = 1.0
            
            # Check author match
            author_match = 0.0
            if parsed_ref.get("family_names") and hasattr(result, 'authors') and result.authors:
                original_authors = [name.lower() for name in parsed_ref["family_names"]]
                result_authors = []
                for author in result.authors:
                    if hasattr(author, 'surname') and author.surname:
                        result_authors.append(author.surname.lower())
                    elif hasattr(author, 'full_name') and author.full_name:
                        result_authors.append(author.full_name.split()[-1].lower())
                
                if result_authors:
                    common_authors = set(original_authors) & set(result_authors)
                    author_match = len(common_authors) / max(len(original_authors), len(result_authors))
            
            # Combined score
            total_score = (title_sim * 0.5 + year_match * 0.3 + author_match * 0.2)
            
            if total_score > best_score:
                best_score = total_score
                best_match = result
        
        logger.info(f"🔍 Best match score: {best_score:.2f}")
        return best_match if best_score > 0.3 else api_results[0]  # Fallback to first result
    
    def _calculate_match_quality(self, original: Dict[str, Any], api_data: Dict[str, Any]) -> float:
        """Calculate quality score for API match"""
        score = 0.0
        total_weight = 0.0
        
        # Title similarity
        if original.get("title") and api_data.get("title"):
            title_sim = self._calculate_similarity(original["title"], api_data["title"])
            score += title_sim * 0.3
            total_weight += 0.3
        
        # Author match
        if original.get("family_names") and api_data.get("family_names"):
            orig_authors = set(name.lower() for name in original["family_names"])
            api_authors = set(name.lower() for name in api_data["family_names"])
            if orig_authors and api_authors:
                author_sim = len(orig_authors & api_authors) / len(orig_authors | api_authors)
                score += author_sim * 0.3
                total_weight += 0.3
        
        # Year match
        if original.get("year") and api_data.get("year"):
            if str(original["year"]) == str(api_data["year"]):
                score += 0.2
            total_weight += 0.2
        
        # Journal similarity
        if original.get("journal") and api_data.get("journal"):
            journal_sim = self._calculate_similarity(original["journal"], api_data["journal"])
            score += journal_sim * 0.2
            total_weight += 0.2
        
        return score / total_weight if total_weight > 0 else 0.0
    
    def _calculate_confidence(self, data: Dict[str, Any]) -> float:
        """Calculate confidence based on data completeness"""
        fields = ["title", "family_names", "year", "journal", "doi", "pages"]
        present_fields = sum(1 for field in fields if data.get(field))
        return present_fields / len(fields)
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using Jaccard similarity"""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
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
                    name_parts = author.full_name.split()
                    if len(name_parts) >= 2:
                        result["family_names"].append(name_parts[-1])
                        result["given_names"].append(name_parts[0])
        
        # Extract other fields
        for field in ["title", "year", "journal", "doi", "pages", "publisher", "url", "abstract"]:
            if hasattr(api_result, field) and getattr(api_result, field):
                value = getattr(api_result, field)
                if field == "year":
                    result[field] = str(value)
                else:
                    result[field] = value
        
        return result
    
    def _merge_api_result(self, original: Dict[str, Any], api_result: APIResult) -> Dict[str, Any]:
        """Merge API result into original data with quality consideration"""
        merged = original.copy()
        merged_fields = []
        
        # Only merge if API data is better quality or fills missing fields
        for field in ["title", "year", "journal", "doi", "pages", "publisher", "url", "abstract"]:
            original_value = merged.get(field)
            api_value = api_result.data.get(field)
            
            if api_value:
                if not original_value:
                    # Fill missing field
                    merged[field] = api_value
                    merged_fields.append(field)
                    logger.info(f"  ✅ Filled missing {field}: '{api_value}'")
                elif self._is_better_value(original_value, api_value, field):
                    # Replace with better value
                    merged[field] = api_value
                    merged_fields.append(field)
                    logger.info(f"  🔄 Improved {field}: '{original_value}' → '{api_value}'")
                else:
                    logger.info(f"  ⏭️  Kept original {field}: '{original_value}'")
        
        # Handle authors specially - enhanced logic
        api_family_names = api_result.data.get("family_names", [])
        api_given_names = api_result.data.get("given_names", [])
        
        if api_family_names:
            original_family = merged.get("family_names", [])
            original_given = merged.get("given_names", [])
            
            if not original_family:
                # No original authors - add all API authors
                merged["family_names"] = api_family_names
                merged["given_names"] = api_given_names
                merged_fields.append("authors")
                logger.info(f"  ✅ Added authors: {api_family_names}")
            else:
                # Check if API authors are better/more complete
                original_analysis = self._analyze_authors(merged)
                temp_merged = merged.copy()
                temp_merged["family_names"] = api_family_names
                temp_merged["given_names"] = api_given_names
                api_analysis = self._analyze_authors(temp_merged)
                
                if api_analysis["quality_score"] > original_analysis["quality_score"]:
                    merged["family_names"] = api_family_names
                    merged["given_names"] = api_given_names
                    merged_fields.append("authors")
                    logger.info(f"  🔄 Improved authors: {original_family} → {api_family_names}")
                elif len(api_family_names) > len(original_family):
                    # API has more authors
                    merged["family_names"] = api_family_names
                    merged["given_names"] = api_given_names
                    merged_fields.append("authors")
                    logger.info(f"  ➕ Added more authors: {len(original_family)} → {len(api_family_names)}")
                else:
                    logger.info(f"  ⏭️  Kept original authors: {original_family}")
        
        logger.info(f"🔄 Merged {len(merged_fields)} fields: {merged_fields}")
        return merged
    
    def _is_better_value(self, original: Any, api_value: Any, field: str) -> bool:
        """Determine if API value is better than original"""
        if not api_value:
            return False
        
        # For strings, prefer longer, more complete values
        if isinstance(original, str) and isinstance(api_value, str):
            return len(api_value) > len(original) * 1.2  # 20% longer
        
        # For lists, prefer more items
        if isinstance(original, list) and isinstance(api_value, list):
            return len(api_value) > len(original)
        
        return False
