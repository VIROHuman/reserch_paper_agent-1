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
        self.crossref_client = CrossRefClient()
        self.openalex_client = OpenAlexClient()
        self.semantic_client = SemanticScholarClient()
        self.doaj_client = DOAJClient()
        
        # No domain filtering - support all research domains
        self.domain_whitelist = None  # Disabled
        self.domain_blacklist = None  # Disabled
        
        self.api_priority = [
            APIProvider.CROSSREF,
            APIProvider.OPENALEX,
            APIProvider.SEMANTIC_SCHOLAR,
            APIProvider.DOAJ
        ]
        
        self.min_quality_score = 0.7
        self.min_confidence = 0.6
        self.max_api_calls = 3  # Restored original value
        
        logger.info("Smart API Strategy initialized")
    
    async def enrich_reference_smart(
        self, 
        parsed_ref: Dict[str, Any], 
        original_text: str,
        force_enrichment: bool = True
    ) -> Dict[str, Any]:
        enriched_ref = parsed_ref.copy()
        enrichment_sources = []
        api_results = []
        
        search_query = self._create_optimized_search_query(parsed_ref, original_text)
        if not search_query:
            return enriched_ref
        
        initial_quality = self._calculate_data_quality(parsed_ref)
        needs_enrichment = self._needs_enrichment(parsed_ref, initial_quality, force_enrichment)
        author_analysis = self._analyze_authors(parsed_ref)
        
        if not needs_enrichment:
            enriched_ref["api_enrichment_used"] = False
            enriched_ref["enrichment_sources"] = []
            enriched_ref["quality_improvement"] = 0.0
            enriched_ref["final_quality_score"] = initial_quality.overall_confidence
            enriched_ref["author_analysis"] = author_analysis
            return enriched_ref
        
        timeout_occurred = False
        current_quality = initial_quality  # Initialize current_quality
        for i, provider in enumerate(self.api_priority):
            if len(api_results) >= self.max_api_calls:
                break
            
            # Add delay between API calls to prevent rate limiting
            if i > 0:
                await asyncio.sleep(0.5)
            
            try:
                result = await self._call_api_with_timeout(provider, search_query, parsed_ref)
                if result:
                    # Check if this result came after a timeout - if so, don't merge
                    if timeout_occurred:
                        logger.warning(f"⚠️ Skipping merge from {provider.value} due to previous timeout")
                        continue
                    
                    api_results.append(result)
                    enriched_ref = self._merge_api_result(enriched_ref, result)
                    enrichment_sources.append(provider.value)
                    
                    current_quality = self._calculate_data_quality(enriched_ref)
                    if current_quality.overall_confidence >= self.min_confidence:
                        break
                else:
                    # Check if this was a timeout (result is None but no exception)
                    timeout_occurred = True
                    logger.warning(f"⚠️ Timeout detected for {provider.value} - no more merges this cycle")
                    
                    
            except Exception as e:
                logger.warning(f"{provider.value} API error: {e}")
                continue
        
        final_quality = self._calculate_data_quality(enriched_ref)
        final_author_analysis = self._analyze_authors(enriched_ref)
        
        enriched_ref["api_enrichment_used"] = len(enrichment_sources) > 0
        enriched_ref["enrichment_sources"] = enrichment_sources
        enriched_ref["quality_improvement"] = final_quality.overall_confidence - initial_quality.overall_confidence
        enriched_ref["final_quality_score"] = final_quality.overall_confidence
        enriched_ref["author_analysis"] = final_author_analysis
        
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
                logger.info(f"Using query strategy: '{strategy[:100]}...'")
                return strategy.strip()
        
        return None
    
    def _calculate_data_quality(self, parsed_ref: Dict[str, Any]) -> QualityMetrics:
        """Calculate comprehensive data quality metrics with improved scoring"""
        
        # More lenient title scoring - partial credit for shorter titles
        title = parsed_ref.get("title", "")
        if title and len(title) > 20:
            title_quality = 1.0
        elif title and len(title) > 10:
            title_quality = 0.8
        elif title and len(title) > 5:
            title_quality = 0.6
        else:
            title_quality = 0.0
        
        # Improved author quality calculation
        author_quality = 0.0
        author_analysis = self._analyze_authors(parsed_ref)
        
        if author_analysis["has_authors"]:
            completeness_score = author_analysis["completeness_ratio"]
            quality_score = author_analysis["quality_score"]
            # Give partial credit even for incomplete authors
            author_quality = max(0.3, (completeness_score + quality_score) / 2.0)
        
        # More lenient year scoring
        year = parsed_ref.get("year")
        if year and str(year).isdigit() and 1800 <= int(year) <= 2030:
            year_quality = 1.0
        else:
            year_quality = 0.0
        
        # More lenient journal scoring
        journal = parsed_ref.get("journal", "")
        if journal and len(journal) > 10:
            journal_quality = 1.0
        elif journal and len(journal) > 5:
            journal_quality = 0.8
        elif journal and len(journal) > 3:
            journal_quality = 0.6
        else:
            journal_quality = 0.0
        
        # DOI gives bonus points
        doi_quality = 1.0 if parsed_ref.get("doi") else 0.0
        
        # Pages are nice to have but not critical
        pages_quality = 0.8 if parsed_ref.get("pages") else 0.0
        
        # Publisher gives bonus
        publisher_quality = 0.7 if parsed_ref.get("publisher") else 0.0
        
        # URL gives bonus
        url_quality = 0.6 if parsed_ref.get("url") else 0.0
        
        # Updated weights - more balanced
        weights = {
            "title": 0.30,      # Increased - most important
            "authors": 0.25,    # High importance
            "year": 0.15,       # Important for validation
            "journal": 0.15,    # Important for context
            "doi": 0.08,        # Bonus points
            "pages": 0.03,      # Nice to have
            "publisher": 0.02,  # Bonus
            "url": 0.02         # Bonus
        }
        
        overall_confidence = (
            title_quality * weights["title"] +
            author_quality * weights["authors"] +
            year_quality * weights["year"] +
            journal_quality * weights["journal"] +
            doi_quality * weights["doi"] +
            pages_quality * weights["pages"] +
            publisher_quality * weights["publisher"] +
            url_quality * weights["url"]
        )
        
        # Ensure minimum quality score if we have basic info
        if title_quality > 0 and (author_quality > 0 or year_quality > 0):
            overall_confidence = max(overall_confidence, 0.4)
        
        return QualityMetrics(
            title_similarity=title_quality,
            author_match_ratio=author_quality,
            year_match=bool(year_quality),
            journal_similarity=journal_quality,
            doi_match=bool(doi_quality),
            overall_confidence=overall_confidence
        )
    
    def _needs_enrichment(self, parsed_ref: Dict[str, Any], quality: QualityMetrics, force_enrichment: bool) -> bool:
        """Determine if enrichment is needed - more aggressive enrichment"""
        if force_enrichment:
            return True
        
        # More aggressive enrichment - lower threshold
        if quality.overall_confidence < 0.85:  # Higher threshold for enrichment
            logger.info(f"Quality below threshold: {quality.overall_confidence:.2f} < 0.85")
            return True
        
        # Check for missing or incomplete critical fields
        critical_issues = []
        
        # Title issues
        title = parsed_ref.get("title", "")
        if not title or len(title) < 10:
            critical_issues.append("title")
        
        # Author issues
        if not parsed_ref.get("family_names"):
            critical_issues.append("authors")
        
        # Year issues
        if not parsed_ref.get("year"):
            critical_issues.append("year")
        
        if critical_issues:
            logger.info(f"Missing/incomplete critical fields: {critical_issues}")
            return True
        
        # Enrich if missing DOI (valuable for validation)
        if not parsed_ref.get("doi"):
            logger.info("Missing DOI - enriching")
            return True
        
        # Enrich if missing journal or journal is too short
        journal = parsed_ref.get("journal", "")
        if not journal or len(journal) < 5:
            logger.info("Missing/incomplete journal - enriching")
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
        
        if given_names:
            analysis["completeness_ratio"] = min(len(given_names) / len(family_names), 1.0)
            analysis["missing_given_names"] = max(0, len(family_names) - len(given_names))
        else:
            analysis["completeness_ratio"] = 0.0
            analysis["missing_given_names"] = len(family_names)
            analysis["issues"].append("No given names found")
        
        quality_issues = 0
        for i, (family, given) in enumerate(zip(family_names, given_names or [])):
            if not family or len(family.strip()) < 2:
                quality_issues += 1
                analysis["issues"].append(f"Author {i+1}: Invalid family name '{family}'")
            
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
        """Call API with timeout, retry logic, and rate limiting"""
        start_time = asyncio.get_event_loop().time()
        results = None  # Initialize results to avoid UnboundLocalError
        
        try:
            # Add small delay for Semantic Scholar to prevent rate limiting
            if provider == APIProvider.SEMANTIC_SCHOLAR:
                await asyncio.sleep(1.0)
            
            # Call the appropriate API with original timeouts
            if provider == APIProvider.CROSSREF:
                results = await asyncio.wait_for(
                    self.crossref_client.search_reference(query, limit=2),
                    timeout=15.0
                )
            elif provider == APIProvider.OPENALEX:
                results = await asyncio.wait_for(
                    self.openalex_client.search_reference(query, limit=2),
                    timeout=15.0
                )
            elif provider == APIProvider.SEMANTIC_SCHOLAR:
                results = await asyncio.wait_for(
                    self.semantic_client.search_reference(query, limit=2),
                    timeout=15.0
                )
            elif provider == APIProvider.DOAJ:
                results = await asyncio.wait_for(
                    self.doaj_client.search_reference(query, limit=2),
                    timeout=15.0
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
            logger.warning(f"⏰ {provider.value}: Timeout after 15s")
            return None
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate limit" in error_msg.lower():
                logger.warning(f"🚫 {provider.value}: Rate limited - {error_msg}")
            else:
                logger.warning(f"❌ {provider.value}: Error - {error_msg}")
            return None
    
    def _find_best_match_smart(self, parsed_ref: Dict[str, Any], api_results: List[Any]) -> Optional[Any]:
        """Robust matching with acceptance gates and domain filtering"""
        if not api_results:
            return None
        
        best_match = None
        best_score = 0.0
        
        for result in api_results:
            if not hasattr(result, 'title') or not result.title:
                continue
            
            # Calculate title similarity (token Jaccard or cosine TF-IDF)
            title_sim = self._calculate_similarity(
                parsed_ref.get("title", ""), 
                result.title
            )
            
            # Require title similarity ≥ 0.65
            if title_sim < 0.65:
                continue
            
            # Check year agreement within ±1
            year_match = False
            if parsed_ref.get("year") and hasattr(result, 'year') and result.year:
                try:
                    parsed_year = int(str(parsed_ref["year"]))
                    result_year = int(str(result.year))
                    year_match = abs(parsed_year - result_year) <= 1
                except (ValueError, TypeError):
                    year_match = False
            
            if not year_match:
                continue
            
            # Check author match - require at least one exact last-name match
            author_match = False
            if parsed_ref.get("family_names") and hasattr(result, 'authors') and result.authors:
                original_authors = [name.lower().strip() for name in parsed_ref["family_names"]]
                result_authors = []
                for author in result.authors:
                    if hasattr(author, 'surname') and author.surname:
                        result_authors.append(author.surname.lower().strip())
                    elif hasattr(author, 'full_name') and author.full_name:
                        result_authors.append(author.full_name.split()[-1].lower().strip())
                
                if result_authors:
                    author_match = len(set(original_authors) & set(result_authors)) > 0
            
            if not author_match:
                continue
            
            # Domain whitelist check
            if not self._check_domain_whitelist(result):
                logger.warning(f"Domain check failed for journal: {getattr(result, 'journal', 'unknown')}")
                continue
            
            # Calculate composite match score
            composite_score = self._calculate_composite_score(title_sim, year_match, author_match, result)
            
            # Only consider matches with score ≥ 0.60
            if composite_score >= 0.60 and composite_score > best_score:
                best_score = composite_score
                best_match = result
        
        logger.info(f"Best match score: {best_score:.2f}")
        return best_match
    
    def _check_domain_whitelist(self, result) -> bool:
        """Check if result passes domain whitelist - disabled for general research support"""
        # No domain filtering - accept all research domains
        return True
    
    def _calculate_composite_score(self, title_sim: float, year_match: bool, author_match: bool, result) -> float:
        """Calculate composite match score ∈ [0, 1]"""
        score = 0.0
        
        # Title similarity (40% weight)
        score += title_sim * 0.4
        
        # Year match (25% weight)
        if year_match:
            score += 0.25
        
        # Author match (25% weight)
        if author_match:
            score += 0.25
        
        # DOI presence bonus (10% weight)
        if hasattr(result, 'doi') and result.doi:
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_merge_score(self, original: Dict[str, Any], api_result: APIResult) -> float:
        """Calculate merge score for decision making"""
        # Use the same logic as composite score
        title_sim = self._calculate_similarity(
            original.get("title", ""), 
            api_result.data.get("title", "")
        )
        
        # Year match
        year_match = False
        if original.get("year") and api_result.data.get("year"):
            try:
                orig_year = int(str(original["year"]))
                api_year = int(str(api_result.data["year"]))
                year_match = abs(orig_year - api_year) <= 1
            except (ValueError, TypeError):
                year_match = False
        
        # Author match
        author_match = False
        if original.get("family_names") and api_result.data.get("family_names"):
            orig_authors = set(name.lower().strip() for name in original["family_names"])
            api_authors = set(name.lower().strip() for name in api_result.data["family_names"])
            author_match = len(orig_authors & api_authors) > 0
        
        return self._calculate_composite_score(title_sim, year_match, author_match, api_result)
    
    def _can_overwrite_critical_field(self, original: Dict[str, Any], api_result: APIResult) -> bool:
        """Check if critical fields can be overwritten (both sources must agree)"""
        # For now, we only have one source, so we're conservative
        # In a multi-source scenario, this would check for agreement
        return False  # Conservative approach - don't overwrite critical fields
    
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
        """Robust merge with acceptance gates and score-based rules"""
        merged = original.copy()
        merged_fields = []
        
        # Calculate match score for merge decisions
        match_score = self._calculate_merge_score(original, api_result)
        
        # Apply merge rules based on score
        if match_score < 0.60:
            # No merges allowed
            logger.warning(f"Match score {match_score:.2f} < 0.60 - no merges allowed")
            return merged
        
        elif 0.60 <= match_score < 0.80:
            # Conservative merge: only DOI and external URL additions
            logger.info(f"Conservative merge (score {match_score:.2f}): DOI/URL only")
            for field in ["doi", "url"]:
                if not merged.get(field) and api_result.data.get(field):
                    merged[field] = api_result.data[field]
                    merged_fields.append(field)
                    logger.info(f"Added {field}: '{api_result.data[field]}'")
        
        elif match_score >= 0.80:
            # Aggressive merge: allow replacing critical fields
            logger.info(f"Aggressive merge (score {match_score:.2f}): full merge allowed")
            for field in ["title", "year", "journal", "doi", "pages", "publisher", "url", "abstract", "volume", "issue"]:
                original_value = merged.get(field)
                api_value = api_result.data.get(field)
                
                if api_value:
                    if not original_value:
                        # Fill missing field
                        merged[field] = api_value
                        merged_fields.append(field)
                        logger.info(f"Filled missing {field}: '{api_value}'")
                    elif field in ["title", "journal", "authors"] and self._can_overwrite_critical_field(original, api_result):
                        # Only overwrite critical fields if both sources agree
                        merged[field] = api_value
                        merged_fields.append(field)
                        logger.info(f"Overwrote {field}: '{original_value}' → '{api_value}'")
                    elif field not in ["title", "journal", "authors"]:
                        # Safe to overwrite non-critical fields
                        merged[field] = api_value
                        merged_fields.append(field)
                        logger.info(f"Updated {field}: '{original_value}' → '{api_value}'")
                    else:
                        logger.info(f"Kept original {field}: '{original_value}'")
        
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
                logger.info(f"Added authors: {api_family_names}")
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
                    logger.info(f" Improved authors: {original_family} → {api_family_names}")
                elif len(api_family_names) > len(original_family):
                    # API has more authors
                    merged["family_names"] = api_family_names
                    merged["given_names"] = api_given_names
                    merged_fields.append("authors")
                    logger.info(f"Added more authors: {len(original_family)} → {len(api_family_names)}")
                else:
                    logger.info(f"Kept original authors: {original_family}")
        
        logger.info(f"Merged {len(merged_fields)} fields: {merged_fields}")
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
