"""
Smart API strategy for optimized reference enrichment
"""
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from dataclasses import dataclass
from enum import Enum

from .api_clients import CrossRefClient, OpenAlexClient, SemanticScholarClient, DOAJClient, PubMedClient, ArxivClient, circuit_breaker
from .text_normalizer import text_normalizer


class APIProvider(Enum):
    CROSSREF = "crossref"
    OPENALEX = "openalex"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    DOAJ = "doaj"
    PUBMED = "pubmed"
    ARXIV = "arxiv"


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
        self.pubmed_client = PubMedClient()
        self.arxiv_client = ArxivClient()
        
        # No domain filtering - support all research domains
        self.domain_whitelist = None  # Disabled
        self.domain_blacklist = None  # Disabled
        
        self.api_priority = [
            APIProvider.CROSSREF,
            APIProvider.OPENALEX,
            APIProvider.PUBMED,
            APIProvider.ARXIV,
            APIProvider.SEMANTIC_SCHOLAR,
            APIProvider.DOAJ
        ]
        
        self.min_quality_score = 0.7  # Higher threshold to avoid false positives
        self.min_confidence = 0.6     # Higher threshold to avoid false positives
        self.max_api_calls = 3        # Conservative number of API calls
        
        logger.info("Smart API Strategy initialized")
    
    async def enrich_reference_smart(
        self,
        parsed_ref: Dict[str, Any],
        original_text: str,
        force_enrichment: bool = True,
        aggressive_search: bool = False,
        fill_missing_fields: bool = False
    ) -> Dict[str, Any]:
        enriched_ref = parsed_ref.copy()
        enrichment_sources = []
        api_results = []
        
        search_query_strategies = self._create_optimized_search_query(parsed_ref, original_text)
        if not search_query_strategies:
            return enriched_ref
        
        # Ensure search_query_strategies is a list
        if isinstance(search_query_strategies, str):
            search_query_strategies = [search_query_strategies]
        
        initial_quality = self._calculate_data_quality(parsed_ref)
        needs_enrichment = self._needs_enrichment(parsed_ref, initial_quality, force_enrichment)
        author_analysis = self._analyze_authors(parsed_ref)
        
        # Enhanced logic for aggressive search and missing field filling
        if aggressive_search or fill_missing_fields:
            needs_enrichment = True
            logger.info(f"🔍 Aggressive search enabled - will search for missing data")
        
        if not needs_enrichment:
            enriched_ref["api_enrichment_used"] = False
            enriched_ref["enrichment_sources"] = []
            enriched_ref["quality_improvement"] = 0.0
            enriched_ref["final_quality_score"] = initial_quality.overall_confidence
            enriched_ref["author_analysis"] = author_analysis
            return enriched_ref
        
        current_quality = initial_quality  # Initialize current_quality
        
        # Smart filtering: decide which APIs to call based on existing data
        apis_to_call = self._select_apis_smart(parsed_ref, aggressive_search)
        logger.info(f"🎯 Selected {len(apis_to_call)} APIs to call: {[api.value for api in apis_to_call]}")
        
        # Try each query strategy until we get results
        api_results = []
        for query_idx, search_query in enumerate(search_query_strategies):
            logger.info(f"🔍 Trying query strategy {query_idx + 1}/{len(search_query_strategies)}: '{search_query[:80]}...'")
            
            # Parallel API calls for faster enrichment
            logger.info("🚀 Calling APIs in parallel...")
            api_tasks = [
                self._call_api_without_timeout(provider, search_query, parsed_ref)
                for provider in apis_to_call
            ]
            
            # Wait for all APIs to complete (no timeout)
            results = await asyncio.gather(*api_tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning(f"{apis_to_call[i].value} API error: {result}")
                    continue
                
                if result and result not in api_results:  # Avoid duplicates
                    api_results.append(result)
                    enrichment_sources.append(result.provider.value)
                    logger.info(f"✅ {result.provider.value}: Found match (confidence: {result.confidence:.2f})")
            
            # If we got results, stop trying other strategies
            if api_results:
                logger.info(f"✅ Got results from strategy {query_idx + 1}, stopping search")
                break
        
        # If still no results, try one more time with title-only
        if not api_results and parsed_ref.get("title"):
            title_query = parsed_ref.get("title")
            logger.info(f"🔄 Last attempt with title-only query: '{title_query[:80]}...'")
            api_tasks = [
                self._call_api_without_timeout(provider, title_query, parsed_ref)
                for provider in apis_to_call
            ]
            results = await asyncio.gather(*api_tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    continue
                
                if result and result not in api_results:
                    api_results.append(result)
                    enrichment_sources.append(result.provider.value)
                    logger.info(f"✅ {result.provider.value}: Found match (confidence: {result.confidence:.2f})")
        
        # Log final results count
        logger.info(f"📊 Total API results found: {len(api_results)}")
        
        # Apply multi-source adjudication if we have multiple results
        if len(api_results) > 1:
            logger.info(f"Applying multi-source adjudication for {len(api_results)} sources")
            enriched_ref = self._apply_multi_source_adjudication(enriched_ref, api_results, fill_missing_fields)
        elif len(api_results) == 1:
            # Single source - merge directly
            enriched_ref = self._merge_api_result(enriched_ref, api_results[0], fill_missing_fields)
        
        # Calculate final quality
        current_quality = self._calculate_data_quality(enriched_ref)
        
        final_quality = self._calculate_data_quality(enriched_ref)
        final_author_analysis = self._analyze_authors(enriched_ref)
        
        enriched_ref["api_enrichment_used"] = len(enrichment_sources) > 0
        enriched_ref["enrichment_sources"] = enrichment_sources
        enriched_ref["quality_improvement"] = final_quality.overall_confidence - initial_quality.overall_confidence
        enriched_ref["final_quality_score"] = final_quality.overall_confidence
        enriched_ref["author_analysis"] = final_author_analysis
        
        return enriched_ref
    
    def _create_optimized_search_query(self, parsed_ref: Dict[str, Any], original_text: str) -> Optional[str]:
        """Create optimized search query with better strategies and blocking keys"""
        query_strategies = []
        
        # Normalize data for better matching
        normalized_title = text_normalizer.normalize_title(parsed_ref.get("title", ""))
        normalized_authors = [text_normalizer.normalize_text(name) for name in parsed_ref.get("family_names", [])]
        normalized_journal = text_normalizer.normalize_journal_venue(parsed_ref.get("journal", ""))
        
        # Strategy 1: Title + First Author + Year (most reliable)
        if normalized_title.get('basic') and normalized_authors and parsed_ref.get("year"):
            query_strategies.append(f"{normalized_title['basic']} {normalized_authors[0]} {parsed_ref['year']}")
        
        # Strategy 2: Title + First Author
        if normalized_title.get('basic') and normalized_authors:
            query_strategies.append(f"{normalized_title['basic']} {normalized_authors[0]}")
        
        # Strategy 3: First Author + Year + Journal
        if normalized_authors and parsed_ref.get("year") and normalized_journal.get('basic'):
            query_strategies.append(f"{normalized_authors[0]} {parsed_ref['year']} {normalized_journal['basic']}")
        
        # Strategy 4: Normalized title only
        if normalized_title.get('basic'):
            query_strategies.append(normalized_title['basic'])
        
        # Strategy 5: Original text (fallback)
        if original_text and len(original_text) > 10:
            normalized_original = text_normalizer.normalize_text(original_text[:200])
            query_strategies.append(normalized_original)
        
        # Return all viable strategies
        viable_strategies = []
        for strategy in query_strategies:
            if strategy and len(strategy.strip()) > 5:
                viable_strategies.append(strategy.strip())
                logger.info(f"Adding query strategy: '{strategy[:100]}...'")
        
        return viable_strategies if viable_strategies else None
    
    def _calculate_data_quality(self, parsed_ref: Dict[str, Any]) -> QualityMetrics:
        """Calculate comprehensive data quality metrics with improved scoring"""
        
        # Enhanced title scoring with better validation
        title = parsed_ref.get("title", "")
        title_quality = 0.0
        if title:
            title_len = len(title.strip())
            # Check for title quality indicators
            has_capitalization = any(c.isupper() for c in title)
            has_lowercase = any(c.islower() for c in title)
            has_spaces = ' ' in title
            not_all_caps = not title.isupper()
            
            if title_len > 30 and has_capitalization and has_lowercase and has_spaces and not_all_caps:
                title_quality = 1.0
            elif title_len > 20 and has_capitalization and has_lowercase:
                title_quality = 0.9
            elif title_len > 15 and has_capitalization:
                title_quality = 0.8
            elif title_len > 10:
                title_quality = 0.6
            elif title_len > 5:
                title_quality = 0.4
        
        # Enhanced author quality calculation
        author_quality = 0.0
        author_analysis = self._analyze_authors(parsed_ref)
        
        if author_analysis["has_authors"]:
            completeness_score = author_analysis["completeness_ratio"]
            quality_score = author_analysis["quality_score"]
            author_count = author_analysis["author_count"]
            
            # Base quality from completeness and individual author quality
            base_quality = (completeness_score + quality_score) / 2.0
            
            # Bonus for multiple authors (indicates academic paper)
            if author_count > 1:
                base_quality = min(1.0, base_quality + 0.1)
            
            # Bonus for complete author information
            if completeness_score > 0.8:
                base_quality = min(1.0, base_quality + 0.1)
            
            author_quality = max(0.2, base_quality)
        
        # Enhanced year scoring with validation
        year = parsed_ref.get("year")
        year_quality = 0.0
        if year:
            try:
                year_int = int(str(year))
                if 1800 <= year_int <= 2030:
                    year_quality = 1.0
                elif 1700 <= year_int <= 2040:
                    year_quality = 0.8
            except (ValueError, TypeError):
                year_quality = 0.0
        
        # Enhanced journal scoring
        journal = parsed_ref.get("journal", "")
        journal_quality = 0.0
        if journal:
            journal_len = len(journal.strip())
            # Check for journal quality indicators
            has_capitalization = any(c.isupper() for c in journal)
            has_lowercase = any(c.islower() for c in journal)
            has_spaces = ' ' in journal
            
            if journal_len > 15 and has_capitalization and has_lowercase and has_spaces:
                journal_quality = 1.0
            elif journal_len > 10 and has_capitalization:
                journal_quality = 0.9
            elif journal_len > 8:
                journal_quality = 0.8
            elif journal_len > 5:
                journal_quality = 0.6
            elif journal_len > 3:
                journal_quality = 0.4
        
        # DOI gives significant bonus points
        doi_quality = 1.0 if parsed_ref.get("doi") else 0.0
        
        # Pages are nice to have but not critical
        pages_quality = 0.8 if parsed_ref.get("pages") else 0.0
        
        # Publisher gives bonus
        publisher_quality = 0.7 if parsed_ref.get("publisher") else 0.0
        
        # URL gives bonus
        url_quality = 0.6 if parsed_ref.get("url") else 0.0
        
        # Abstract gives bonus
        abstract_quality = 0.5 if parsed_ref.get("abstract") else 0.0
        
        # Updated weights - more balanced and accurate
        weights = {
            "title": 0.35,      # Most important - identifies the work
            "authors": 0.25,    # High importance - identifies creators
            "year": 0.15,       # Important for validation
            "journal": 0.15,    # Important for context
            "doi": 0.05,        # Bonus points
            "pages": 0.02,      # Nice to have
            "publisher": 0.015, # Bonus
            "url": 0.01,        # Bonus
            "abstract": 0.005   # Bonus
        }
        
        overall_confidence = (
            title_quality * weights["title"] +
            author_quality * weights["authors"] +
            year_quality * weights["year"] +
            journal_quality * weights["journal"] +
            doi_quality * weights["doi"] +
            pages_quality * weights["pages"] +
            publisher_quality * weights["publisher"] +
            url_quality * weights["url"] +
            abstract_quality * weights["abstract"]
        )
        
        # Ensure minimum quality score if we have basic info
        if title_quality > 0.5 and (author_quality > 0.3 or year_quality > 0.5):
            overall_confidence = max(overall_confidence, 0.5)
        elif title_quality > 0.3 and (author_quality > 0.2 or year_quality > 0.3):
            overall_confidence = max(overall_confidence, 0.3)
        
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
        
        # Conservative enrichment - higher threshold
        if quality.overall_confidence < 0.80:  # Higher threshold to avoid false positives
            logger.info(f"Quality below threshold: {quality.overall_confidence:.2f} < 0.80")
            return True
        
        # Check for missing or incomplete critical fields
        critical_issues = []
        
        # Title issues - conservative threshold
        title = parsed_ref.get("title", "")
        if not title or len(title) < 10:  # Conservative threshold
            critical_issues.append("title")
        
        # Author issues - conservative threshold
        family_names = parsed_ref.get("family_names", [])
        if not family_names or len(family_names) == 0:
            critical_issues.append("authors")
        elif len(family_names) == 1 and len(family_names[0]) < 4:  # Check quality
            critical_issues.append("authors")
        
        # Year issues - conservative threshold
        year = parsed_ref.get("year")
        if not year or not str(year).isdigit() or int(year) < 1800 or int(year) > 2030:
            critical_issues.append("year")
        
        if critical_issues:
            logger.info(f"Missing/incomplete critical fields: {critical_issues}")
            return True
        
        # Only enrich for DOI and journal if we have good base data
        if not parsed_ref.get("doi"):
            # Only try to get DOI if we have good title and authors
            if (parsed_ref.get("title") and len(parsed_ref.get("title", "")) > 15 and
                parsed_ref.get("family_names") and len(parsed_ref.get("family_names", [])) > 0):
                logger.info("Missing DOI but have good base data - enriching")
                return True
        
        # Enrich if missing journal but have good base data
        journal = parsed_ref.get("journal", "")
        if not journal or len(journal) < 5:  # Conservative threshold
            if (parsed_ref.get("title") and len(parsed_ref.get("title", "")) > 15 and
                parsed_ref.get("family_names") and len(parsed_ref.get("family_names", [])) > 0):
                logger.info("Missing/incomplete journal but have good base data - enriching")
                return True
        
        # Only enrich if we have very few fields filled AND they are high quality
        filled_fields = sum(1 for field in ["title", "family_names", "year", "journal", "doi"] 
                          if parsed_ref.get(field))
        if filled_fields < 2:  # Less than 2 critical fields
            logger.info(f"Only {filled_fields} critical fields filled - enriching")
            return True
        
        return False
    
    def _apply_multi_source_adjudication(self, enriched_ref: Dict[str, Any], api_results: List[APIResult], fill_missing_fields: bool = False) -> Dict[str, Any]:
        """Apply multi-source adjudication to resolve conflicts and choose best data"""
        if not api_results:
            return enriched_ref
        
        logger.info(f"Starting adjudication with {len(api_results)} sources")
        
        # Group results by provider for analysis
        provider_results = {}
        for result in api_results:
            provider_results[result.provider.value] = result
        
        # Adjudicate each field
        adjudicated_fields = {}
        conflicts = []
        
        # Fields to adjudicate
        fields_to_adjudicate = ['title', 'year', 'journal', 'doi', 'pages', 'publisher', 'url', 'abstract']
        
        for field in fields_to_adjudicate:
            field_values = {}
            field_confidences = {}
            
            # Collect values and confidences from all sources
            for provider, result in provider_results.items():
                if field in result.data and result.data[field]:
                    field_values[provider] = result.data[field]
                    field_confidences[provider] = result.confidence
            
            if not field_values:
                continue
            
            # Apply adjudication logic
            if len(field_values) == 1:
                # Single source - use its value
                provider = list(field_values.keys())[0]
                adjudicated_fields[field] = field_values[provider]
                logger.info(f"Field {field}: Single source ({provider})")
            else:
                # Multiple sources - apply adjudication rules
                adjudicated_value, conflict_info = self._adjudicate_field(field, field_values, field_confidences, provider_results)
                
                if adjudicated_value:
                    adjudicated_fields[field] = adjudicated_value
                
                if conflict_info:
                    conflicts.append(conflict_info)
        
        # Adjudicate authors separately (more complex)
        author_result = self._adjudicate_authors(provider_results)
        if author_result:
            adjudicated_fields.update(author_result)
        
        # Apply adjudicated results
        for field, value in adjudicated_fields.items():
            if not enriched_ref.get(field) or self._is_better_value(enriched_ref.get(field), value, field):
                enriched_ref[field] = value
                logger.info(f"Applied adjudicated {field}: {value}")
        
        # Store conflict information
        if conflicts:
            enriched_ref["adjudication_conflicts"] = conflicts
            logger.warning(f"Found {len(conflicts)} conflicts during adjudication")
        
        return enriched_ref
    
    def _adjudicate_field(self, field: str, field_values: Dict[str, Any], field_confidences: Dict[str, float], provider_results: Dict[str, APIResult]) -> Tuple[Any, Optional[Dict]]:
        """Adjudicate a single field across multiple sources"""
        # Check for exact matches first
        unique_values = set(str(v) for v in field_values.values())
        if len(unique_values) == 1:
            # All sources agree
            return list(field_values.values())[0], None
        
        # Check for DOI exact matches (highest priority)
        if field == 'doi':
            doi_matches = {k: v for k, v in field_values.items() if v and str(v).startswith('10.')}
            if doi_matches:
                # Prefer CrossRef for DOIs
                if 'crossref' in doi_matches:
                    return doi_matches['crossref'], None
                else:
                    # Use the DOI with highest confidence
                    best_provider = max(doi_matches.keys(), key=lambda k: field_confidences.get(k, 0))
                    return doi_matches[best_provider], None
        
        # Check for year exact matches
        if field == 'year':
            year_matches = {k: v for k, v in field_values.items() if v and str(v).isdigit()}
            if year_matches:
                # Count occurrences of each year
                year_counts = {}
                for provider, year in year_matches.items():
                    year_str = str(year)
                    if year_str not in year_counts:
                        year_counts[year_str] = []
                    year_counts[year_str].append(provider)
                
                # Find most common year
                most_common_year = max(year_counts.keys(), key=lambda y: len(year_counts[y]))
                if len(year_counts[most_common_year]) > 1:
                    # Multiple sources agree on year
                    return most_common_year, None
        
        # For other fields, use confidence-weighted selection
        # Prefer CrossRef for critical fields
        if field in ['title', 'journal'] and 'crossref' in field_values:
            crossref_confidence = field_confidences.get('crossref', 0)
            other_confidences = [field_confidences.get(k, 0) for k in field_values.keys() if k != 'crossref']
            
            if other_confidences and crossref_confidence >= max(other_confidences):
                return field_values['crossref'], None
        
        # Use highest confidence value
        best_provider = max(field_values.keys(), key=lambda k: field_confidences.get(k, 0))
        best_value = field_values[best_provider]
        best_confidence = field_confidences.get(best_provider, 0)
        
        # Check if there's significant disagreement
        other_confidences = [field_confidences.get(k, 0) for k in field_values.keys() if k != best_provider]
        if other_confidences and best_confidence < max(other_confidences) * 1.2:  # Less than 20% better
            conflict_info = {
                'field': field,
                'chosen_value': best_value,
                'chosen_provider': best_provider,
                'chosen_confidence': best_confidence,
                'alternatives': [(k, v, field_confidences.get(k, 0)) for k, v in field_values.items() if k != best_provider]
            }
            return best_value, conflict_info
        
        return best_value, None
    
    def _adjudicate_authors(self, provider_results: Dict[str, APIResult]) -> Optional[Dict[str, Any]]:
        """Adjudicate author information across sources"""
        author_data = {}
        
        for provider, result in provider_results.items():
            if result.data.get('family_names') and result.data.get('given_names'):
                author_data[provider] = {
                    'family_names': result.data['family_names'],
                    'given_names': result.data['given_names'],
                    'confidence': result.confidence
                }
        
        if not author_data:
            return None
        
        if len(author_data) == 1:
            # Single source
            provider = list(author_data.keys())[0]
            return {
                'family_names': author_data[provider]['family_names'],
                'given_names': author_data[provider]['given_names']
            }
        
        # Multiple sources - find consensus
        # Prefer CrossRef for authors
        if 'crossref' in author_data:
            crossref_authors = author_data['crossref']
            crossref_family = set(crossref_authors['family_names'])
            
            # Check if other sources have similar author sets
            consensus_count = 1  # CrossRef counts as 1
            for provider, data in author_data.items():
                if provider != 'crossref':
                    other_family = set(data['family_names'])
                    # Check for significant overlap
                    overlap = len(crossref_family & other_family)
                    if overlap >= len(crossref_family) * 0.6:  # At least 60% overlap
                        consensus_count += 1
            
            if consensus_count >= 2:  # At least 2 sources agree
                return {
                    'family_names': crossref_authors['family_names'],
                    'given_names': crossref_authors['given_names']
                }
        
        # No consensus - use highest confidence source
        best_provider = max(author_data.keys(), key=lambda k: author_data[k]['confidence'])
        best_data = author_data[best_provider]
        
        return {
            'family_names': best_data['family_names'],
            'given_names': best_data['given_names']
        }
    
    def _is_better_value(self, original: Any, new_value: Any, field: str) -> bool:
        """Determine if new value is better than original"""
        if not new_value:
            return False
        
        if not original:
            return True
        
        # For strings, prefer longer, more complete values
        if isinstance(original, str) and isinstance(new_value, str):
            # Special handling for different fields
            if field == 'title':
                return len(new_value) > len(original) * 1.1  # 10% longer
            elif field == 'journal':
                return len(new_value) > len(original) * 1.2  # 20% longer
            elif field in ['doi', 'url']:
                # Prefer more complete URLs/DOIs
                return len(new_value) > len(original)
            else:
                return len(new_value) > len(original) * 1.2  # 20% longer
        
        # For lists (authors), prefer more authors
        if isinstance(original, list) and isinstance(new_value, list):
            return len(new_value) > len(original)
        
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
    
    def _select_apis_smart(self, parsed_ref: Dict[str, Any], aggressive_search: bool) -> List[APIProvider]:
        """Smart API selection based on existing data and needs"""
        selected_apis = []
        
        has_doi = bool(parsed_ref.get("doi"))
        has_title = bool(parsed_ref.get("title") and len(parsed_ref.get("title", "")) > 10)
        has_authors = bool(parsed_ref.get("family_names") and len(parsed_ref.get("family_names", [])) > 0)
        has_year = bool(parsed_ref.get("year"))
        has_journal = bool(parsed_ref.get("journal") and len(parsed_ref.get("journal", "")) > 5)
        
        # If we have DOI, prioritize DOI-based APIs
        if has_doi:
            logger.info("📌 Has DOI - prioritizing CrossRef and OpenAlex")
            selected_apis.extend([APIProvider.CROSSREF, APIProvider.OPENALEX])
        
        # If we have good title + authors, use all APIs
        elif has_title and has_authors:
            logger.info("📚 Has title + authors - using all APIs")
            if aggressive_search:
                # Use all APIs for aggressive search
                selected_apis = self.api_priority.copy()
            else:
                # Use top 3 APIs
                selected_apis = self.api_priority[:3]
        
        # If we have title only, use title-friendly APIs
        elif has_title:
            logger.info("📖 Has title only - using title-search APIs")
            selected_apis.extend([
                APIProvider.CROSSREF,
                APIProvider.SEMANTIC_SCHOLAR,
                APIProvider.OPENALEX,
                APIProvider.ARXIV  # Include ArXiv for preprint detection
            ])
        
        # If we have authors + year, use author-friendly APIs
        elif has_authors and has_year:
            logger.info("👥 Has authors + year - using author-search APIs")
            selected_apis.extend([
                APIProvider.CROSSREF,
                APIProvider.OPENALEX,
                APIProvider.PUBMED,
                APIProvider.ARXIV  # Include ArXiv for preprint detection
            ])
        
        # Fallback: use top 2 APIs
        else:
            logger.info("⚠️ Limited data - using top 2 APIs only")
            selected_apis = self.api_priority[:2]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_apis = []
        for api in selected_apis:
            if api not in seen:
                seen.add(api)
                unique_apis.append(api)
        
        return unique_apis
    
    async def _call_api_without_timeout(self, provider: APIProvider, query: str, parsed_ref: Dict[str, Any]) -> Optional[APIResult]:
        """Call API without timeout - let circuit breaker handle failures"""
        start_time = asyncio.get_event_loop().time()
        results = None
        
        try:
            # Add small delay for Semantic Scholar to prevent rate limiting
            if provider == APIProvider.SEMANTIC_SCHOLAR:
                await asyncio.sleep(1.0)
            
            # Call the appropriate API WITHOUT timeout
            if provider == APIProvider.CROSSREF:
                results = await self.crossref_client.search_reference(query, limit=3)
            elif provider == APIProvider.OPENALEX:
                results = await self.openalex_client.search_reference(query, limit=3)
            elif provider == APIProvider.SEMANTIC_SCHOLAR:
                results = await self.semantic_client.search_reference(query, limit=3)
            elif provider == APIProvider.PUBMED:
                results = await self.pubmed_client.search_reference(query, limit=3)
            elif provider == APIProvider.ARXIV:
                results = await self.arxiv_client.search_reference(query, limit=3)
            elif provider == APIProvider.DOAJ:
                results = await self.doaj_client.search_reference(query, limit=3)
            else:
                return None
            
            response_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"⏱️ {provider.value}: Response time {response_time:.2f}s")
            
            if not results:
                logger.debug(f"{provider.value}: No results found")
                return None
            
            # Find best match and assess quality
            best_match = self._find_best_match_smart(parsed_ref, results)
            if not best_match:
                logger.debug(f"{provider.value}: No good match found")
                return None
            
            # Convert to our format
            converted_data = self._convert_to_parsed_format(best_match)
            
            # Calculate quality metrics
            quality_score = self._calculate_match_quality(parsed_ref, converted_data)
            confidence = self._calculate_confidence(converted_data)
            
            logger.info(f"✓ {provider.value}: Match found (quality: {quality_score:.2f}, confidence: {confidence:.2f})")
            
            return APIResult(
                provider=provider,
                data=converted_data,
                quality_score=quality_score,
                confidence=confidence,
                fields_found=[k for k, v in converted_data.items() if v],
                response_time=response_time
            )
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate limit" in error_msg.lower():
                logger.warning(f"🚫 {provider.value}: Rate limited - {error_msg}")
            else:
                logger.debug(f"{provider.value}: Error - {error_msg}")
            return None
    
    def _find_best_match_smart(self, parsed_ref: Dict[str, Any], api_results: List[Any]) -> Optional[Any]:
        """Robust matching with blocking keys, acceptance gates, and domain filtering"""
        if not api_results:
            return None
        
        # Create blocking key for efficient filtering
        blocking_key = self._create_blocking_key(parsed_ref)
        logger.info(f"Using blocking key: {blocking_key}")
        
        best_match = None
        best_score = 0.0
        candidates_checked = 0
        
        for result in api_results:
            if not hasattr(result, 'title') or not result.title:
                continue
            
            # Apply blocking filter first (most efficient) - but skip if blocking key is too restrictive
            # Only apply blocking if we have enough data, otherwise allow all candidates through
            has_sufficient_data = bool(parsed_ref.get("family_names") and parsed_ref.get("year"))
            if has_sufficient_data and not self._passes_blocking_filter(parsed_ref, result, blocking_key):
                continue
            
            candidates_checked += 1
            
            # Normalize titles for better comparison
            parsed_title_norm = text_normalizer.normalize_title(parsed_ref.get("title", ""))
            result_title_norm = text_normalizer.normalize_title(result.title)
            
            # Calculate title similarity using multiple methods
            title_sim = self._calculate_enhanced_similarity(
                parsed_title_norm, 
                result_title_norm
            )
            
            # Check if we have authors - if not, relax requirements
            has_authors = bool(parsed_ref.get("family_names"))
            
            # Require title similarity ≥ 0.50 (more relaxed to catch more matches)
            if title_sim < 0.50:
                continue
            
            # Check year agreement within ±2 (more flexible)
            year_match = False
            if parsed_ref.get("year") and hasattr(result, 'year') and result.year:
                try:
                    parsed_year = int(str(parsed_ref["year"]))
                    result_year = int(str(result.year))
                    year_match = abs(parsed_year - result_year) <= 2
                except (ValueError, TypeError):
                    year_match = False
            else:
                # If no year in parsed_ref, don't require year match
                year_match = True
            
            # Only check author match if authors exist
            author_match_score = 0.0
            if has_authors:
                author_match_score = self._calculate_author_match_score(parsed_ref, result)
                if author_match_score < 0.5:  # Require at least 50% author overlap
                    continue
            else:
                # No authors in original - don't require author match
                author_match_score = 1.0
            
            # Domain whitelist check
            if not self._check_domain_whitelist(result):
                logger.warning(f"Domain check failed for journal: {getattr(result, 'journal', 'unknown')}")
                continue
            
            # Calculate composite match score
            # Allow lower threshold when no authors (title-only matching)
            author_match_threshold = 0.6 if has_authors else 0.0
            composite_score = self._calculate_composite_score(title_sim, year_match, author_match_score > author_match_threshold, result)
            
            # Only consider matches with score ≥ 0.50 (more relaxed to catch more matches)
            min_score = 0.50
            if composite_score >= min_score and composite_score > best_score:
                best_score = composite_score
                best_match = result
        
        logger.info(f"Checked {candidates_checked} candidates, best match score: {best_score:.2f}")
        return best_match
    
    def _create_blocking_key(self, parsed_ref: Dict[str, Any]) -> str:
        """Create blocking key for efficient candidate filtering"""
        return text_normalizer.create_blocking_key(
            parsed_ref.get("family_names", []),
            parsed_ref.get("year", ""),
            parsed_ref.get("journal", "")
        )
    
    def _passes_blocking_filter(self, parsed_ref: Dict[str, Any], result: Any, blocking_key: str) -> bool:
        """Check if result passes blocking filter"""
        try:
            # Extract result data
            result_authors = []
            if hasattr(result, 'authors') and result.authors:
                for author in result.authors:
                    if hasattr(author, 'surname') and author.surname:
                        result_authors.append(author.surname)
                    elif hasattr(author, 'full_name') and author.full_name:
                        result_authors.append(author.full_name.split()[-1])
            
            result_year = str(result.year) if hasattr(result, 'year') and result.year else ""
            result_journal = result.journal if hasattr(result, 'journal') and result.journal else ""
            
            # Create result blocking key
            result_blocking_key = text_normalizer.create_blocking_key(
                result_authors, result_year, result_journal
            )
            
            # Check if blocking keys match (allows some flexibility)
            return self._blocking_keys_match(blocking_key, result_blocking_key)
            
        except Exception as e:
            logger.warning(f"Blocking filter error: {e}")
            return True  # If blocking fails, allow through
    
    def _blocking_keys_match(self, key1: str, key2: str) -> bool:
        """Check if two blocking keys match (with some flexibility)"""
        if not key1 or not key2:
            return True  # If either is empty, don't block
        
        # Exact match
        if key1 == key2:
            return True
        
        # Split keys and check components
        parts1 = key1.split('_')
        parts2 = key2.split('_')
        
        if len(parts1) != len(parts2):
            return False
        
        # Check each component with more flexibility
        for i, (p1, p2) in enumerate(zip(parts1, parts2)):
            if i == 0:  # Author name - skip if empty, otherwise must match
                if p1 and p2 and p1 != p2:
                    return False
                elif (not p1 or not p2):
                    # If either is empty, don't block
                    continue
            elif i == 1:  # Year - skip if empty, otherwise must match
                if p1 and p2 and p1 != p2:
                    return False
                elif (not p1 or not p2):
                    # If either is empty, don't block
                    continue
            elif i == 2:  # Venue - allow partial match or skip if empty
                if p1 and p2 and not self._venue_components_match(p1, p2):
                    return False
                elif (not p1 or not p2):
                    # If either is empty, don't block
                    continue
        
        return True
    
    def _venue_components_match(self, venue1: str, venue2: str) -> bool:
        """Check if venue components match with some flexibility"""
        if not venue1 or not venue2:
            return True
        
        # Normalize venues
        norm1 = text_normalizer.normalize_journal_venue(venue1)
        norm2 = text_normalizer.normalize_journal_venue(venue2)
        
        # Check if any key terms overlap
        terms1 = set(norm1.get('key_terms', '').split())
        terms2 = set(norm2.get('key_terms', '').split())
        
        if not terms1 or not terms2:
            return True  # If no terms, don't block
        
        overlap = len(terms1 & terms2)
        return overlap > 0  # At least one term must overlap
    
    def _calculate_enhanced_similarity(self, title1_norm: Dict[str, str], title2_norm: Dict[str, str]) -> float:
        """Calculate enhanced similarity using multiple normalization methods"""
        similarities = []
        
        # Basic similarity
        if title1_norm.get('basic') and title2_norm.get('basic'):
            similarities.append(text_normalizer.calculate_similarity(
                title1_norm['basic'], title2_norm['basic'], 'jaccard'
            ))
        
        # No stopwords similarity
        if title1_norm.get('no_stopwords') and title2_norm.get('no_stopwords'):
            similarities.append(text_normalizer.calculate_similarity(
                title1_norm['no_stopwords'], title2_norm['no_stopwords'], 'jaccard'
            ))
        
        # Token-sorted similarity (order-independent)
        if title1_norm.get('token_sorted') and title2_norm.get('token_sorted'):
            similarities.append(text_normalizer.calculate_similarity(
                title1_norm['token_sorted'], title2_norm['token_sorted'], 'jaccard'
            ))
        
        # N-gram similarity
        if title1_norm.get('bigrams') and title2_norm.get('bigrams'):
            bigram_sim = len(title1_norm['bigrams'] & title2_norm['bigrams']) / max(
                len(title1_norm['bigrams'] | title2_norm['bigrams']), 1
            )
            similarities.append(bigram_sim)
        
        return max(similarities) if similarities else 0.0
    
    def _calculate_author_match_score(self, parsed_ref: Dict[str, Any], result: Any) -> float:
        """Calculate detailed author match score"""
        if not parsed_ref.get("family_names") or not hasattr(result, 'authors') or not result.authors:
            return 0.0
        
        # Normalize original authors
        original_authors = [text_normalizer.normalize_text(name) for name in parsed_ref["family_names"]]
        
        # Extract and normalize result authors
        result_authors = []
        for author in result.authors:
            if hasattr(author, 'surname') and author.surname:
                result_authors.append(text_normalizer.normalize_text(author.surname))
            elif hasattr(author, 'full_name') and author.full_name:
                surname = author.full_name.split()[-1]
                result_authors.append(text_normalizer.normalize_text(surname))
        
        if not result_authors:
            return 0.0
        
        # Calculate overlap
        original_set = set(original_authors)
        result_set = set(result_authors)
        
        intersection = len(original_set & result_set)
        union = len(original_set | result_set)
        
        # Return Jaccard similarity
        return intersection / union if union > 0 else 0.0
    
    def _check_domain_whitelist(self, result) -> bool:
        """Check if result passes domain whitelist - disabled for general research support"""
        # No domain filtering - accept all research domains
        return True
    
    def _calculate_composite_score(self, title_sim: float, year_match: bool, author_match: bool, result) -> float:
        """Calculate composite match score ∈ [0, 1]"""
        score = 0.0
        
        # Title similarity - always weighted (50% weight when other fields missing)
        weight_adjustment = 1.0
        title_weight = 0.4
        
        # If no year or author info, give title more weight
        if not year_match and not author_match:
            title_weight = 0.6
            weight_adjustment = 1.4  # Scale up remaining weights
        
        score += title_sim * title_weight
        
        # Year match (25% weight, scaled if author missing)
        if year_match:
            score += 0.25 * weight_adjustment
        
        # Author match (25% weight, scaled if year missing)
        if author_match:
            score += 0.25 * weight_adjustment
        
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
    
    def _merge_api_result(self, original: Dict[str, Any], api_result: APIResult, fill_missing_fields: bool = False) -> Dict[str, Any]:
        """Robust merge with acceptance gates and score-based rules"""
        merged = original.copy()
        merged_fields = []
        
        # Calculate match score for merge decisions
        match_score = self._calculate_merge_score(original, api_result)
        
        # Enhanced logic for filling missing fields
        if fill_missing_fields:
            logger.info(f"🔍 Fill missing fields mode - will fill any missing data")
            # Fill all missing fields regardless of match score
            for field in ["title", "year", "journal", "doi", "pages", "publisher", "url", "abstract", "volume", "issue"]:
                if not merged.get(field) and api_result.data.get(field):
                    merged[field] = api_result.data[field]
                    merged_fields.append(field)
                    logger.info(f"✅ Filled missing {field}: '{api_result.data[field]}'")
            
            # Handle authors specially
            if not merged.get("family_names") and api_result.data.get("family_names"):
                merged["family_names"] = api_result.data["family_names"]
                merged["given_names"] = api_result.data.get("given_names", [])
                merged_fields.append("authors")
                logger.info(f"✅ Filled missing authors: {api_result.data['family_names']}")
            
            return merged
        
        # Apply merge rules based on score
        if match_score < 0.60:
            # No merges allowed
            logger.warning(f"Match score {match_score:.2f} < 0.60 - no merges allowed")
            return merged
        
        elif 0.60 <= match_score < 0.80:
            # Conservative merge: DOI, URL, and non-critical fields
            logger.info(f"Conservative merge (score {match_score:.2f}): DOI/URL and non-critical fields")
            for field in ["doi", "url", "pages", "publisher", "abstract"]:
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
