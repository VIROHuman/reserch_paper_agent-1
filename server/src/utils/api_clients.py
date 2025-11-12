import httpx
import requests
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

from ..config import settings
from ..models.schemas import CrossRefResponse, OpenAlexResponse, SemanticScholarResponse, ReferenceData, Author


class CircuitBreaker:
    """Circuit breaker to temporarily disable failing APIs"""
    
    def __init__(self, failure_threshold: int = 3, timeout_duration: int = 300):
        self.failure_threshold = failure_threshold
        self.timeout_duration = timeout_duration  # seconds to wait before retrying
        self.failures = {}  # API name -> failure count
        self.disabled_until = {}  # API name -> datetime when to re-enable
    
    def record_failure(self, api_name: str):
        """Record a failure for an API - DISABLED"""
        # Circuit breaker disabled - do nothing
        pass
    
    def record_success(self, api_name: str):
        """Record a success for an API (resets failure count)"""
        if api_name in self.failures:
            self.failures[api_name] = 0
        if api_name in self.disabled_until:
            del self.disabled_until[api_name]
    
    def is_available(self, api_name: str) -> bool:
        """Check if an API is available - ALWAYS TRUE (circuit breaker disabled)"""
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status for all APIs"""
        return {
            "failures": self.failures.copy(),
            "disabled_apis": {
                api: (disabled_until - datetime.now()).total_seconds()
                for api, disabled_until in self.disabled_until.items()
            }
        }


# Global circuit breaker instance
circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_duration=300)


class CrossRefClient:
    
    def __init__(self):
        self.base_url = settings.crossref_base_url
        self.headers = {
            "User-Agent": "ResearchPaperAgent/1.0 (mailto:user@example.com)",
            "Accept": "application/json"
        }
        if settings.crossref_api_key:
            self.headers["Authorization"] = f"Bearer {settings.crossref_api_key}"
    
    async def search_reference(self, query: str, limit: int = 5) -> List[ReferenceData]:
        api_name = "CrossRef"
        
        # Check circuit breaker
        if not circuit_breaker.is_available(api_name):
            logger.debug(f"{api_name}: Skipped (circuit breaker open)")
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "query": query,
                    "rows": limit,
                    "sort": "relevance"
                }
                
                response = await client.get(
                    f"{self.base_url}/works",
                    headers=self.headers,
                    params=params,
                    timeout=None  # No timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = self._parse_crossref_response(data)
                    circuit_breaker.record_success(api_name)
                    return results
                
                circuit_breaker.record_failure(api_name)
                return []
                
        except Exception as e:
            logger.debug(f"{api_name}: Error - {str(e)}")
            circuit_breaker.record_failure(api_name)
            return []
    
    def _parse_crossref_response(self, data: Dict[str, Any]) -> List[ReferenceData]:
        """Parse CrossRef API response"""
        references = []
        
        if "message" in data and "items" in data["message"]:
            for item in data["message"]["items"]:
                try:
                    # Extract authors
                    authors = []
                    if "author" in item:
                        for author in item["author"]:
                            given = author.get("given", "")
                            family = author.get("family", "")
                            # Debug: Log what CrossRef is returning
                            logger.debug(f"CrossRef Author - given='{given}', family='{family}'")
                            authors.append(Author(
                                first_name=given,
                                surname=family,
                                full_name=f"{given} {family}".strip()
                            ))
                    
                    # Extract publication year and month
                    year = None
                    issue_month = None
                    date_parts = None
                    if item.get("published-print", {}).get("date-parts"):
                        date_parts = item.get("published-print", {}).get("date-parts", [[None]])[0]
                    elif item.get("published-online", {}).get("date-parts"):
                        date_parts = item.get("published-online", {}).get("date-parts", [[None]])[0]
                    
                    if date_parts:
                        year = date_parts[0] if len(date_parts) > 0 else None
                        if len(date_parts) > 1 and date_parts[1]:
                            # Convert month number to month name
                            month_num = int(date_parts[1])
                            month_names = ["January", "February", "March", "April", "May", "June",
                                         "July", "August", "September", "October", "November", "December"]
                            if 1 <= month_num <= 12:
                                issue_month = month_names[month_num - 1]
                    
                    # Extract publication details
                    reference = ReferenceData(
                        title=item.get("title", [""])[0] if item.get("title") else None,
                        authors=authors,
                        year=year,
                        journal=item.get("container-title", [""])[0] if item.get("container-title") else None,
                        volume=item.get("volume"),
                        issue=item.get("issue"),
                        issue_month=issue_month,
                        pages=item.get("page"),
                        doi=item.get("DOI"),
                        publisher=item.get("publisher"),
                        publication_type=item.get("type", "journal-article")
                    )
                    references.append(reference)
                    
                except Exception as e:
                    logger.warning(f"Error parsing CrossRef item: {str(e)}")
                    continue
        
        return references
    
    async def get_doi_metadata(self, doi: str) -> Dict[str, Any]:
        try:
            normalized_doi = self._normalize_doi(doi)
            if not normalized_doi:
                return {"error": "Invalid DOI format"}
            
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/works/{normalized_doi}"
                
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=None  # No timeout
                )
                response.raise_for_status()
                
                data = response.json()
                
                if "message" not in data:
                    return {"error": "No message in CrossRef response"}
                
                metadata = self._parse_crossref_doi_metadata(data["message"])
                return metadata
                
        except Exception as e:
            logger.error(f"CrossRef DOI API error: {str(e)}")
            return {"error": str(e)}
    
    def _normalize_doi(self, doi: str) -> str:
        """Normalize DOI: strip spaces, ensure lowercase, remove prefixes"""
        if not doi:
            return ""
        
        doi = doi.strip()
        
        if doi.startswith("https://doi.org/"):
            doi = doi[16:]
        elif doi.startswith("http://doi.org/"):
            doi = doi[15:]
        elif doi.startswith("doi.org/"):
            doi = doi[8:]
        
        if not doi.startswith("10."):
            logger.warning(f"Invalid DOI format: {doi}")
            return ""
        
        doi = doi.lower()
        
        return doi
    
    def _parse_crossref_doi_metadata(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Parse CrossRef DOI metadata into standardized format"""
        try:
            # Extract authors
            authors = []
            if "author" in item:
                for author in item["author"]:
                    given = author.get("given", "")
                    family = author.get("family", "")
                    full_name = f"{given} {family}".strip()
                    if full_name:
                        authors.append(full_name)
            
            # Extract publication year and month
            year = None
            issue_month = None
            date_parts = None
            if "published-print" in item and "date-parts" in item["published-print"]:
                date_parts = item["published-print"]["date-parts"][0]
            elif "published-online" in item and "date-parts" in item["published-online"]:
                date_parts = item["published-online"]["date-parts"][0]
            elif "published" in item and "date-parts" in item["published"]:
                date_parts = item["published"]["date-parts"][0]
            
            if date_parts:
                year = date_parts[0] if len(date_parts) > 0 else None
                if len(date_parts) > 1 and date_parts[1]:
                    # Convert month number to month name
                    month_num = int(date_parts[1])
                    month_names = ["January", "February", "March", "April", "May", "June",
                                 "July", "August", "September", "October", "November", "December"]
                    if 1 <= month_num <= 12:
                        issue_month = month_names[month_num - 1]
            
            # Extract title
            title = None
            if "title" in item and item["title"]:
                title = item["title"][0] if isinstance(item["title"], list) else item["title"]
            
            # Extract journal/conference
            journal = None
            if "container-title" in item and item["container-title"]:
                journal = item["container-title"][0] if isinstance(item["container-title"], list) else item["container-title"]
            
            # Extract abstract
            abstract = None
            if "abstract" in item:
                abstract = item["abstract"]
            
            # Extract citation count
            citation_count = None
            if "is-referenced-by-count" in item:
                citation_count = item["is-referenced-by-count"]
            
            return {
                "doi": item.get("DOI", "").lower(),
                "title": title,
                "authors": authors,
                "journal": journal,
                "publisher": item.get("publisher"),
                "year": year,
                "volume": item.get("volume"),
                "issue": item.get("issue"),
                "issue_month": issue_month,
                "pages": item.get("page"),
                "abstract": abstract,
                "url": f"https://doi.org/{item.get('DOI', '').lower()}" if item.get("DOI") else None,
                "citation_count": citation_count,
                "source_api": "CrossRef"
            }
            
        except Exception as e:
            logger.error(f"Error parsing CrossRef DOI metadata: {str(e)}")
            return {"error": str(e)}


class OpenAlexClient:
    """Client for OpenAlex API"""
    
    def __init__(self):
        self.base_url = settings.openalex_base_url
        self.headers = {
            "User-Agent": "ResearchPaperAgent/1.0 (mailto:user@example.com)",
            "Accept": "application/json"
        }
    
    async def search_reference(self, query: str, limit: int = 5) -> List[ReferenceData]:
        api_name = "OpenAlex"
        
        # Check circuit breaker
        if not circuit_breaker.is_available(api_name):
            logger.debug(f"{api_name}: Skipped (circuit breaker open)")
            return []
        
        client = None
        try:
            # Create client with explicit timeout settings to prevent hangs
            client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),  # 30s total, 10s connect
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
            
            params = {
                "search": query,
                "per_page": limit,
                "sort": "relevance_score:desc"
            }
            
            response = await client.get(
                f"{self.base_url}/works",
                headers=self.headers,
                params=params
            )
            
            # Check status before parsing JSON
            if response.status_code != 200:
                logger.debug(f"{api_name}: HTTP {response.status_code}")
                circuit_breaker.record_failure(api_name)
                return []
            
            # Parse JSON with error handling
            try:
                data = response.json()
            except Exception as json_error:
                logger.warning(f"{api_name}: Failed to parse JSON response: {str(json_error)}")
                circuit_breaker.record_failure(api_name)
                return []
            
            # Parse response with error handling
            try:
                results = self._parse_openalex_response(data)
                circuit_breaker.record_success(api_name)
                return results
            except Exception as parse_error:
                logger.warning(f"{api_name}: Error parsing response: {str(parse_error)}")
                circuit_breaker.record_failure(api_name)
                return []
                
        except httpx.TimeoutException:
            logger.warning(f"{api_name}: Request timed out")
            circuit_breaker.record_failure(api_name)
            return []
        except httpx.RequestError as e:
            logger.debug(f"{api_name}: Request error - {str(e)}")
            circuit_breaker.record_failure(api_name)
            return []
        except Exception as e:
            logger.debug(f"{api_name}: Error - {str(e)}")
            circuit_breaker.record_failure(api_name)
            return []
        finally:
            # Ensure client is properly closed
            if client:
                try:
                    await client.aclose()
                except Exception:
                    pass
    
    def _parse_openalex_response(self, data: Dict[str, Any]) -> List[ReferenceData]:
        """Parse OpenAlex API response"""
        references = []
        
        if not isinstance(data, dict):
            logger.warning("OpenAlex: Invalid response format")
            return references
        
        if "results" not in data:
            logger.debug("OpenAlex: No results in response")
            return references
        
        results = data.get("results", [])
        if not isinstance(results, list):
            logger.warning("OpenAlex: Results is not a list")
            return references
        
        # Limit processing to prevent hangs on very large result sets
        max_items = 50
        if len(results) > max_items:
            logger.debug(f"OpenAlex: Too many results ({len(results)}), processing first {max_items}")
            results = results[:max_items]
        
        for item in results:
            try:
                if not isinstance(item, dict):
                    continue
                
                # Extract authors with error handling
                authors = []
                if "authorships" in item and isinstance(item["authorships"], list):
                    # Limit authors to prevent processing issues
                    authorships = item["authorships"][:20]  # Max 20 authors per paper
                    for authorship in authorships:
                        try:
                            if not isinstance(authorship, dict):
                                continue
                            author = authorship.get("author", {})
                            if not isinstance(author, dict):
                                continue
                            
                            display_name = author.get("display_name", "")
                            if display_name and isinstance(display_name, str):
                                name_parts = display_name.split()
                                if len(name_parts) >= 2:
                                    # Last word is surname, everything else is first_name (including middle names)
                                    first_name = " ".join(name_parts[:-1])
                                    surname = name_parts[-1]
                                else:
                                    first_name = None
                                    surname = display_name if name_parts else None
                            else:
                                first_name = None
                                surname = None
                            
                            authors.append(Author(
                                first_name=first_name,
                                surname=surname,
                                full_name=display_name
                            ))
                        except Exception as author_error:
                            logger.debug(f"OpenAlex: Error parsing author: {str(author_error)}")
                            continue

                # Extract abstract with error handling
                abstract_text = None
                try:
                    abstract_index = item.get("abstract_inverted_index")
                    if abstract_index and isinstance(abstract_index, dict):
                        abstract_text = self._convert_abstract_index_to_text(abstract_index)
                except Exception as abstract_error:
                    logger.debug(f"OpenAlex: Error processing abstract: {str(abstract_error)}")
                    abstract_text = None
                
                # Safely extract nested fields
                journal = None
                try:
                    primary_location = item.get("primary_location", {})
                    if isinstance(primary_location, dict):
                        source = primary_location.get("source", {})
                        if isinstance(source, dict):
                            journal = source.get("display_name")
                except Exception:
                    pass
                
                reference = ReferenceData(
                    title=item.get("title"),
                    authors=authors,
                    year=item.get("publication_year"),
                    journal=journal,
                    doi=item.get("doi"),
                    url=item.get("id"),
                    abstract=abstract_text,
                    publication_type=item.get("type", "journal-article")
                )
                references.append(reference)
                
            except Exception as e:
                logger.warning(f"OpenAlex: Error parsing item: {str(e)}")
                continue
        
        return references
    
    def _convert_abstract_index_to_text(self, abstract_index: Dict[str, List[int]]) -> str:
        """Convert OpenAlex abstract_inverted_index to readable text"""
        if not abstract_index:
            return ""
        
        try:
            # Limit processing to prevent hangs on very large abstracts
            max_words = 10000  # Reasonable limit
            word_count = sum(len(positions) for positions in abstract_index.values())
            
            if word_count > max_words:
                logger.debug(f"OpenAlex: Abstract too large ({word_count} words), truncating")
                # Process only first N words
                word_positions = []
                processed = 0
                for word, positions in abstract_index.items():
                    if processed >= max_words:
                        break
                    for pos in positions:
                        if processed >= max_words:
                            break
                        word_positions.append((pos, word))
                        processed += 1
            else:
                word_positions = []
                for word, positions in abstract_index.items():
                    for pos in positions:
                        word_positions.append((pos, word))
            
            # Sort by position
            word_positions.sort(key=lambda x: x[0])
            
            # Join words
            return " ".join([word for _, word in word_positions])
        except Exception as e:
            logger.warning(f"OpenAlex: Error converting abstract: {str(e)}")
            return ""
    
    async def get_doi_metadata(self, doi: str) -> Dict[str, Any]:
        try:
            normalized_doi = self._normalize_doi(doi)
            if not normalized_doi:
                return {"error": "Invalid DOI format"}
            
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/works/doi:{normalized_doi}"
                
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=None  # No timeout
                )
                response.raise_for_status()
                
                data = response.json()
                metadata = self._parse_openalex_doi_metadata(data)
                return metadata
                
        except Exception as e:
            logger.error(f"OpenAlex DOI API error: {str(e)}")
            return {"error": str(e)}
    
    def _normalize_doi(self, doi: str) -> str:
        """Normalize DOI: strip spaces, ensure lowercase, remove prefixes"""
        if not doi:
            return ""
        
        doi = doi.strip()
        
        if doi.startswith("https://doi.org/"):
            doi = doi[16:]
        elif doi.startswith("http://doi.org/"):
            doi = doi[15:]
        elif doi.startswith("doi.org/"):
            doi = doi[8:]
        
        if not doi.startswith("10."):
            logger.warning(f"Invalid DOI format: {doi}")
            return ""

        doi = doi.lower()
        
        return doi
    
    def _parse_openalex_doi_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse OpenAlex DOI metadata into standardized format"""
        try:
            # Extract authors
            authors = []
            if "authorships" in data:
                for authorship in data["authorships"]:
                    author = authorship.get("author", {})
                    display_name = author.get("display_name")
                    if display_name:
                        authors.append(display_name)
            
            # Extract abstract
            abstract = None
            if "abstract_inverted_index" in data:
                abstract = self._convert_abstract_index_to_text(data["abstract_inverted_index"])
            
            # Extract journal/conference
            journal = None
            if "primary_location" in data and "source" in data["primary_location"]:
                journal = data["primary_location"]["source"].get("display_name")
            
            # Extract citation count
            citation_count = None
            if "cited_by_count" in data:
                citation_count = data["cited_by_count"]
            
            return {
                "doi": data.get("doi", "").lower(),
                "title": data.get("title"),
                "authors": authors,
                "journal": journal,
                "publisher": data.get("primary_location", {}).get("source", {}).get("publisher"),
                "year": data.get("publication_year"),
                "volume": data.get("biblio", {}).get("volume"),
                "issue": data.get("biblio", {}).get("issue"),
                "pages": data.get("biblio", {}).get("first_page"),
                "abstract": abstract,
                "url": data.get("id"),
                "citation_count": citation_count,
                "source_api": "OpenAlex"
            }
            
        except Exception as e:
            logger.error(f"Error parsing OpenAlex DOI metadata: {str(e)}")
            return {"error": str(e)}


class SemanticScholarClient:
    """Client for Semantic Scholar API"""
    
    def __init__(self):
        self.base_url = settings.semantic_scholar_base_url
        self.headers = {
            "User-Agent": "ResearchPaperAgent/1.0 (mailto:user@example.com)",
            "Accept": "application/json"
        }
        if settings.semantic_scholar_api_key:
            self.headers["x-api-key"] = settings.semantic_scholar_api_key
    
    async def search_reference(self, query: str, limit: int = 5) -> List[ReferenceData]:
        """Search for reference using Semantic Scholar API"""
        api_name = "SemanticScholar"
        
        # Check circuit breaker
        if not circuit_breaker.is_available(api_name):
            logger.debug(f"{api_name}: Skipped (circuit breaker open)")
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "query": query,
                    "limit": limit,
                    "sort": "relevance"
                }
                
                response = await client.get(
                    f"{self.base_url}/paper/search",
                    headers=self.headers,
                    params=params,
                    timeout=None  # No timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = self._parse_semantic_scholar_response(data)
                    circuit_breaker.record_success(api_name)
                    return results
                
                circuit_breaker.record_failure(api_name)
                return []
                
        except Exception as e:
            logger.debug(f"{api_name}: Error - {str(e)}")
            circuit_breaker.record_failure(api_name)
            return []
    
    def _parse_semantic_scholar_response(self, data: Dict[str, Any]) -> List[ReferenceData]:
        """Parse Semantic Scholar API response"""
        references = []
        
        if "data" in data:
            for item in data["data"]:
                try:
                    # Extract authors
                    authors = []
                    if "authors" in item:
                        for author in item["authors"]:
                            author_name = author.get("name", "")
                            if author_name:
                                name_parts = author_name.split()
                                if len(name_parts) >= 2:
                                    # Last word is surname, everything else is first_name (including middle names)
                                    first_name = " ".join(name_parts[:-1])
                                    surname = name_parts[-1]
                                else:
                                    first_name = None
                                    surname = author_name
                            else:
                                first_name = None
                                surname = None
                            authors.append(Author(
                                first_name=first_name,
                                surname=surname,
                                full_name=author_name
                            ))
                    
                    # Extract publication details
                    reference = ReferenceData(
                        title=item.get("title"),
                        authors=authors,
                        year=item.get("year"),
                        journal=item.get("venue") or (item.get("journal", {}).get("name") if item.get("journal") else None),
                        doi=item.get("doi"),
                        url=item.get("openAccessPdf", {}).get("url") if item.get("openAccessPdf") else None,
                        publication_type="journal-article"  # Semantic Scholar primarily has academic papers
                    )
                    references.append(reference)
                    
                except Exception as e:
                    logger.warning(f"Error parsing Semantic Scholar item: {str(e)}")
                    continue
        
        return references


class DOAJClient:
    """Client for DOAJ (Directory of Open Access Journals) API"""
    
    def __init__(self):
        self.base_url = "https://doaj.org/api"
        self.headers = {
            "User-Agent": "ResearchPaperAgent/1.0 (mailto:user@example.com)",
            "Accept": "application/json"
        }
    
    async def search_reference(self, query: str, limit: int = 5) -> List[ReferenceData]:
        """Search for reference using DOAJ API"""
        api_name = "DOAJ"
        
        # Check circuit breaker
        if not circuit_breaker.is_available(api_name):
            logger.debug(f"{api_name}: Skipped (circuit breaker open)")
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                encoded_query = query.replace(" ", "%20")
                
                response = await client.get(
                    f"{self.base_url}/search/articles/{encoded_query}",
                    headers=self.headers,
                    timeout=None  # No timeout
                )
                response.raise_for_status()
                
                data = response.json()
                results = self._parse_doaj_response(data)
                circuit_breaker.record_success(api_name)
                return results
                
        except Exception as e:
            logger.debug(f"{api_name}: Error - {str(e)}")
            circuit_breaker.record_failure(api_name)
            return []
    
    def _parse_doaj_response(self, data: Dict[str, Any]) -> List[ReferenceData]:
        """Parse DOAJ API response"""
        references = []
        
        if "results" in data:
            for item in data["results"]:
                try:
                    # Extract authors
                    authors = []
                    if "bibjson" in item and "author" in item["bibjson"]:
                        for author in item["bibjson"]["author"]:
                            author_name = author.get("name", "")
                            name_parts = author_name.split() if author_name else []
                            if len(name_parts) >= 2:
                                # Last word is surname, everything else is first_name (including middle names)
                                first_name = " ".join(name_parts[:-1])
                                surname = name_parts[-1]
                            elif len(name_parts) == 1:
                                first_name = None
                                surname = name_parts[0]
                            else:
                                first_name = None
                                surname = None
                            authors.append(Author(
                                first_name=first_name,
                                surname=surname,
                                full_name=author_name
                            ))
                    
                    # Extract publication details
                    bibjson = item.get("bibjson", {})
                    reference = ReferenceData(
                        title=bibjson.get("title"),
                        authors=authors,
                        year=bibjson.get("year"),
                        journal=bibjson.get("journal", {}).get("title") if bibjson.get("journal") else None,
                        volume=bibjson.get("journal", {}).get("volume") if bibjson.get("journal") else None,
                        issue=bibjson.get("journal", {}).get("number") if bibjson.get("journal") else None,
                        pages=bibjson.get("start_page") and bibjson.get("end_page") and 
                              f"{bibjson.get('start_page')}-{bibjson.get('end_page')}" or 
                              bibjson.get("start_page"),
                        doi=bibjson.get("identifier", [{}])[0].get("id") if bibjson.get("identifier") else None,
                        url=bibjson.get("link", [{}])[0].get("url") if bibjson.get("link") else None,
                        abstract=bibjson.get("abstract"),
                        publisher=bibjson.get("publisher"),
                        publication_type="journal-article"  # DOAJ primarily has journal articles
                    )
                    references.append(reference)
                    
                except Exception as e:
                    logger.warning(f"Error parsing DOAJ item: {str(e)}")
                    continue
        
        return references


class ArxivClient:
    """Client for ArXiv API (no API key required)"""
    
    def __init__(self):
        self.base_url = "https://export.arxiv.org/api/query"
        self.headers = {
            "User-Agent": "ResearchPaperAgent/1.0"
        }
    
    async def search_reference(self, query: str, limit: int = 5) -> List[ReferenceData]:
        """Search ArXiv for references"""
        api_name = "ArXiv"
        
        # Check circuit breaker
        if not circuit_breaker.is_available(api_name):
            logger.debug(f"{api_name}: Skipped (circuit breaker open)")
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "search_query": f"ti:{query} OR all:{query}",
                    "start": 0,
                    "max_results": limit,
                    "sortBy": "relevance",
                    "sortOrder": "descending"
                }
                
                response = await client.get(
                    self.base_url,
                    headers=self.headers,
                    params=params,
                    timeout=None  # No timeout
                )
                
                if response.status_code == 200:
                    results = self._parse_arxiv_response(response.text)
                    circuit_breaker.record_success(api_name)
                    return results
                
                circuit_breaker.record_failure(api_name)
                return []
                
        except Exception as e:
            logger.debug(f"{api_name}: Error - {str(e)}")
            circuit_breaker.record_failure(api_name)
            return []
    
    def _parse_arxiv_response(self, xml_content: str) -> List[ReferenceData]:
        """Parse ArXiv XML response"""
        import xml.etree.ElementTree as ET
        references = []
        
        try:
            root = ET.fromstring(xml_content)
            
            for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
                try:
                    # Extract title
                    title_elem = entry.find('.//{http://www.w3.org/2005/Atom}title')
                    title = title_elem.text.strip() if title_elem is not None else None
                    
                    # Extract authors
                    authors = []
                    for author in entry.findall('.//{http://www.w3.org/2005/Atom}author'):
                        name_elem = author.find('.//{http://www.w3.org/2005/Atom}name')
                        if name_elem is not None:
                            full_name = name_elem.text.strip()
                            name_parts = full_name.split()
                            if len(name_parts) >= 2:
                                # Last word is surname, everything else is first_name (including middle names)
                                first_name = " ".join(name_parts[:-1])
                                surname = name_parts[-1]
                            elif len(name_parts) == 1:
                                first_name = None
                                surname = name_parts[0]
                            else:
                                first_name = None
                                surname = None
                            
                            authors.append(Author(
                                first_name=first_name,
                                surname=surname,
                                full_name=full_name
                            ))
                    
                    # Extract publication date
                    published_elem = entry.find('.//{http://www.w3.org/2005/Atom}published')
                    year = None
                    if published_elem is not None:
                        try:
                            year = int(published_elem.text[:4])
                        except (ValueError, TypeError):
                            pass
                    
                    # Extract abstract
                    summary_elem = entry.find('.//{http://www.w3.org/2005/Atom}summary')
                    abstract = summary_elem.text.strip() if summary_elem is not None else None
                    
                    # Extract ArXiv ID
                    arxiv_id_elem = entry.find('.//{http://www.w3.org/2005/Atom}id')
                    arxiv_id = None
                    arxiv_url = None
                    if arxiv_id_elem is not None:
                        arxiv_url = arxiv_id_elem.text
                        # Extract ArXiv ID from URL
                        if 'arxiv.org/abs/' in arxiv_url:
                            arxiv_id = arxiv_url.split('arxiv.org/abs/')[-1]
                    
                    # Extract categories
                    categories = []
                    for category in entry.findall('.//{http://www.w3.org/2005/Atom}category'):
                        term = category.get('term')
                        if term:
                            categories.append(term)
                    
                    # Determine publication type based on categories
                    publication_type = "preprint"
                    if categories:
                        # Check if it's a journal paper that was also posted to ArXiv
                        journal_indicators = ['journal', 'published', 'accepted']
                        if any(indicator in str(categories).lower() for indicator in journal_indicators):
                            publication_type = "journal-article"
                    
                    reference = ReferenceData(
                        title=title,
                        authors=authors,
                        year=year,
                        journal=f"arXiv:{arxiv_id}" if arxiv_id else "arXiv",
                        doi=None,  # ArXiv doesn't have DOIs
                        url=arxiv_url,
                        abstract=abstract,
                        publication_type=publication_type,
                        raw_text=f"arXiv:{arxiv_id}" if arxiv_id else None
                    )
                    references.append(reference)
                    
                except Exception as e:
                    logger.warning(f"Error parsing ArXiv entry: {str(e)}")
                    continue
            
        except Exception as e:
            logger.warning(f"Error parsing ArXiv XML: {str(e)}")
        
        return references
    
    async def get_arxiv_metadata(self, arxiv_id: str) -> Dict[str, Any]:
        """Get metadata for a specific ArXiv paper"""
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "id_list": arxiv_id,
                    "max_results": 1
                }
                
                response = await client.get(
                    self.base_url,
                    headers=self.headers,
                    params=params,
                    timeout=None
                )
                
                if response.status_code == 200:
                    results = self._parse_arxiv_response(response.text)
                    if results:
                        ref = results[0]
                        return {
                            "arxiv_id": arxiv_id,
                            "title": ref.title,
                            "authors": [{"full_name": author.full_name} for author in ref.authors],
                            "year": ref.year,
                            "abstract": ref.abstract,
                            "url": ref.url,
                            "publication_type": ref.publication_type,
                            "source_api": "ArXiv"
                        }
                
                return {"error": "ArXiv paper not found"}
                
        except Exception as e:
            logger.error(f"ArXiv metadata API error: {str(e)}")
            return {"error": str(e)}


class PubMedClient:
    """Client for PubMed/NCBI E-utilities API (no API key required)"""
    
    def __init__(self):
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.headers = {
            "User-Agent": "ResearchPaperAgent/1.0"
        }
    
    async def search_reference(self, query: str, limit: int = 5) -> List[ReferenceData]:
        """Search PubMed for references"""
        api_name = "PubMed"
        
        # Check circuit breaker
        if not circuit_breaker.is_available(api_name):
            logger.debug(f"{api_name}: Skipped (circuit breaker open)")
            return []
        
        try:
            # Step 1: Search for PMIDs
            pmids = await self._search_pmids(query, limit)
            if not pmids:
                logger.debug(f"{api_name}: No results found for query")
                circuit_breaker.record_failure(api_name)
                return []
            
            # Step 2: Fetch details for PMIDs
            references = await self._fetch_details(pmids)
            circuit_breaker.record_success(api_name)
            return references
            
        except Exception as e:
            logger.debug(f"{api_name}: Error - {str(e)}")
            circuit_breaker.record_failure(api_name)
            return []
    
    async def _search_pmids(self, query: str, limit: int) -> List[str]:
        """Search PubMed and get PMIDs"""
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "db": "pubmed",
                    "term": query,
                    "retmax": limit,
                    "retmode": "json"
                }
                
                response = await client.get(
                    f"{self.base_url}/esearch.fcgi",
                    headers=self.headers,
                    params=params,
                    timeout=None  # No timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("esearchresult", {}).get("idlist", [])
                return []
                
        except Exception as e:
            logger.debug(f"PubMed search error: {str(e)}")
            return []
    
    async def _fetch_details(self, pmids: List[str]) -> List[ReferenceData]:
        """Fetch detailed information for PMIDs"""
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "db": "pubmed",
                    "id": ",".join(pmids),
                    "retmode": "xml"
                }
                
                response = await client.get(
                    f"{self.base_url}/efetch.fcgi",
                    headers=self.headers,
                    params=params,
                    timeout=None  # No timeout
                )
                
                if response.status_code == 200:
                    return self._parse_pubmed_xml(response.text)
                return []
                
        except Exception as e:
            logger.debug(f"PubMed fetch error: {str(e)}")
            return []
    
    def _parse_pubmed_xml(self, xml_content: str) -> List[ReferenceData]:
        """Parse PubMed XML response"""
        import xml.etree.ElementTree as ET
        references = []
        
        try:
            root = ET.fromstring(xml_content)
            
            for article in root.findall('.//PubmedArticle'):
                try:
                    # Extract authors
                    authors = []
                    author_list = article.find('.//AuthorList')
                    if author_list is not None:
                        for author in author_list.findall('Author'):
                            last_name = author.find('LastName')
                            fore_name = author.find('ForeName')
                            if last_name is not None:
                                authors.append(Author(
                                    surname=last_name.text,
                                    first_name=fore_name.text if fore_name is not None else None,
                                    full_name=f"{fore_name.text if fore_name is not None else ''} {last_name.text}".strip()
                                ))
                    
                    # Extract title
                    title_elem = article.find('.//ArticleTitle')
                    title = title_elem.text if title_elem is not None else None
                    
                    # Extract journal
                    journal_elem = article.find('.//Journal/Title')
                    journal = journal_elem.text if journal_elem is not None else None
                    
                    # Extract year
                    year_elem = article.find('.//PubDate/Year')
                    year = int(year_elem.text) if year_elem is not None and year_elem.text else None
                    
                    # Extract DOI
                    doi = None
                    for article_id in article.findall('.//ArticleId'):
                        if article_id.get('IdType') == 'doi':
                            doi = article_id.text
                            break
                    
                    # Extract abstract
                    abstract_elem = article.find('.//Abstract/AbstractText')
                    abstract = abstract_elem.text if abstract_elem is not None else None
                    
                    # Extract pages
                    pages_elem = article.find('.//MedlinePgn')
                    pages = pages_elem.text if pages_elem is not None else None
                    
                    # Extract volume
                    volume_elem = article.find('.//Volume')
                    volume = volume_elem.text if volume_elem is not None else None
                    
                    # Extract issue
                    issue_elem = article.find('.//Issue')
                    issue = issue_elem.text if issue_elem is not None else None
                    
                    # Extract PMID
                    pmid_elem = article.find('.//PMID')
                    pmid = pmid_elem.text if pmid_elem is not None else None
                    
                    # Extract publication type
                    pub_type_elem = article.find('.//PublicationType')
                    pub_type = pub_type_elem.text if pub_type_elem is not None else "journal-article"
                    
                    reference = ReferenceData(
                        title=title,
                        authors=authors,
                        year=year,
                        journal=journal,
                        doi=doi,
                        abstract=abstract,
                        pages=pages,
                        volume=volume,
                        issue=issue,
                        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
                        publication_type=pub_type,
                        raw_text=f"PMID: {pmid}" if pmid else None
                    )
                    references.append(reference)
                    
                except Exception as e:
                    logger.warning(f"Error parsing PubMed article: {str(e)}")
                    continue
            
        except Exception as e:
            logger.warning(f"Error parsing PubMed XML: {str(e)}")
        
        return references
    
    async def get_pmid_metadata(self, pmid: str) -> Dict[str, Any]:
        """Get metadata for a specific PMID"""
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "db": "pubmed",
                    "id": pmid,
                    "retmode": "xml"
                }
                
                response = await client.get(
                    f"{self.base_url}/efetch.fcgi",
                    headers=self.headers,
                    params=params,
                    timeout=None
                )
                
                if response.status_code == 200:
                    results = self._parse_pubmed_xml(response.text)
                    if results:
                        ref = results[0]
                        return {
                            "pmid": pmid,
                            "title": ref.title,
                            "authors": [{"full_name": author.full_name} for author in ref.authors],
                            "year": ref.year,
                            "journal": ref.journal,
                            "doi": ref.doi,
                            "abstract": ref.abstract,
                            "url": ref.url,
                            "publication_type": ref.publication_type,
                            "source_api": "PubMed"
                        }
                
                return {"error": "PubMed article not found"}
                
        except Exception as e:
            logger.error(f"PubMed metadata API error: {str(e)}")
            return {"error": str(e)}


# GROBID Client removed - using LLM for primary parsing
