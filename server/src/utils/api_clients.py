"""
API clients for various academic databases
"""
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger

from ..config import settings
from ..models.schemas import CrossRefResponse, OpenAlexResponse, SemanticScholarResponse, ReferenceData, Author


class CrossRefClient:
    """Client for CrossRef API"""
    
    def __init__(self):
        self.base_url = settings.crossref_base_url
        self.headers = {
            "User-Agent": "ResearchPaperAgent/1.0 (mailto:your-email@example.com)",
            "Accept": "application/json"
        }
        if settings.crossref_api_key:
            self.headers["Authorization"] = f"Bearer {settings.crossref_api_key}"
    
    async def search_reference(self, query: str, limit: int = 5) -> List[ReferenceData]:
        """Search for reference using CrossRef API"""
        logger.info(f"🔍 CROSSREF SEARCH: '{query}' (limit: {limit})")
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "query": query,
                    "rows": limit,
                    "sort": "relevance"
                }
                
                logger.info(f"📡 CrossRef URL: {self.base_url}/works")
                logger.info(f"📡 CrossRef params: {params}")
                
                response = await client.get(
                    f"{self.base_url}/works",
                    headers=self.headers,
                    params=params,
                    timeout=30.0
                )
                logger.info(f"📡 CrossRef response status: {response.status_code}")
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"📡 CrossRef response keys: {list(data.keys())}")
                if "message" in data and "items" in data["message"]:
                    logger.info(f"📡 CrossRef found {len(data['message']['items'])} items")
                else:
                    logger.warning("📡 CrossRef response has no items")
                
                results = self._parse_crossref_response(data)
                logger.info(f"✅ CrossRef parsed {len(results)} references")
                for i, ref in enumerate(results):
                    logger.info(f"  {i+1}. {ref.title} - {ref.year}")
                
                return results
                
        except Exception as e:
            logger.error(f"❌ CrossRef API error: {str(e)}")
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
                            authors.append(Author(
                                first_name=author.get("given"),
                                surname=author.get("family"),
                                full_name=f"{author.get('given', '')} {author.get('family', '')}".strip()
                            ))
                    
                    # Extract publication details
                    reference = ReferenceData(
                        title=item.get("title", [""])[0] if item.get("title") else None,
                        authors=authors,
                        year=item.get("published-print", {}).get("date-parts", [[None]])[0][0] or 
                             item.get("published-online", {}).get("date-parts", [[None]])[0][0],
                        journal=item.get("container-title", [""])[0] if item.get("container-title") else None,
                        volume=item.get("volume"),
                        issue=item.get("issue"),
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


class OpenAlexClient:
    """Client for OpenAlex API"""
    
    def __init__(self):
        self.base_url = settings.openalex_base_url
        self.headers = {
            "User-Agent": "ResearchPaperAgent/1.0 (mailto:your-email@example.com)",
            "Accept": "application/json"
        }
    
    async def search_reference(self, query: str, limit: int = 5) -> List[ReferenceData]:
        """Search for reference using OpenAlex API"""
        logger.info(f"🔍 OPENALEX SEARCH: '{query}' (limit: {limit})")
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "search": query,
                    "per_page": limit,
                    "sort": "relevance_score:desc"
                }
                
                logger.info(f"📡 OpenAlex URL: {self.base_url}/works")
                logger.info(f"📡 OpenAlex params: {params}")
                
                response = await client.get(
                    f"{self.base_url}/works",
                    headers=self.headers,
                    params=params,
                    timeout=30.0
                )
                logger.info(f"📡 OpenAlex response status: {response.status_code}")
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"📡 OpenAlex response keys: {list(data.keys())}")
                if "results" in data:
                    logger.info(f"📡 OpenAlex found {len(data['results'])} items")
                else:
                    logger.warning("📡 OpenAlex response has no results")
                
                results = self._parse_openalex_response(data)
                logger.info(f"✅ OpenAlex parsed {len(results)} references")
                for i, ref in enumerate(results):
                    logger.info(f"  {i+1}. {ref.title} - {ref.year}")
                
                return results
                
        except Exception as e:
            logger.error(f"❌ OpenAlex API error: {str(e)}")
            return []
    
    def _parse_openalex_response(self, data: Dict[str, Any]) -> List[ReferenceData]:
        """Parse OpenAlex API response"""
        references = []
        
        if "results" in data:
            for item in data["results"]:
                try:
                    # Extract authors
                    authors = []
                    if "authorships" in item:
                        for authorship in item["authorships"]:
                            author = authorship.get("author", {})
                            authors.append(Author(
                                first_name=author.get("display_name", "").split()[0] if author.get("display_name") else None,
                                surname=" ".join(author.get("display_name", "").split()[1:]) if author.get("display_name") else None,
                                full_name=author.get("display_name")
                            ))
                    
                    # Extract publication details
                    # Convert abstract_inverted_index to string
                    abstract_text = None
                    if item.get("abstract_inverted_index"):
                        abstract_text = self._convert_abstract_index_to_text(item["abstract_inverted_index"])
                    
                    reference = ReferenceData(
                        title=item.get("title"),
                        authors=authors,
                        year=item.get("publication_year"),
                        journal=item.get("primary_location", {}).get("source", {}).get("display_name"),
                        doi=item.get("doi"),
                        url=item.get("id"),
                        abstract=abstract_text,
                        publication_type=item.get("type", "journal-article")
                    )
                    references.append(reference)
                    
                except Exception as e:
                    logger.warning(f"Error parsing OpenAlex item: {str(e)}")
                    continue
        
        return references
    
    def _convert_abstract_index_to_text(self, abstract_index: Dict[str, List[int]]) -> str:
        """Convert OpenAlex abstract_inverted_index to readable text"""
        if not abstract_index:
            return ""
        
        # Create a list of (word, position) tuples
        word_positions = []
        for word, positions in abstract_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        
        # Sort by position
        word_positions.sort(key=lambda x: x[0])
        
        # Join words in order
        return " ".join([word for _, word in word_positions])


class SemanticScholarClient:
    """Client for Semantic Scholar API"""
    
    def __init__(self):
        self.base_url = settings.semantic_scholar_base_url
        self.headers = {
            "User-Agent": "ResearchPaperAgent/1.0 (mailto:your-email@example.com)",
            "Accept": "application/json"
        }
        if settings.semantic_scholar_api_key:
            self.headers["x-api-key"] = settings.semantic_scholar_api_key
    
    async def search_reference(self, query: str, limit: int = 5) -> List[ReferenceData]:
        """Search for reference using Semantic Scholar API"""
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
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                return self._parse_semantic_scholar_response(data)
                
        except Exception as e:
            logger.error(f"Semantic Scholar API error: {str(e)}")
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
                            authors.append(Author(
                                first_name=author.get("name", "").split()[0] if author.get("name") else None,
                                surname=" ".join(author.get("name", "").split()[1:]) if author.get("name") else None,
                                full_name=author.get("name")
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
            "User-Agent": "ResearchPaperAgent/1.0 (mailto:your-email@example.com)",
            "Accept": "application/json"
        }
    
    async def search_reference(self, query: str, limit: int = 5) -> List[ReferenceData]:
        """Search for reference using DOAJ API"""
        try:
            async with httpx.AsyncClient() as client:
                # DOAJ uses path parameter for search query
                encoded_query = query.replace(" ", "%20")
                
                response = await client.get(
                    f"{self.base_url}/search/articles/{encoded_query}",
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                return self._parse_doaj_response(data)
                
        except Exception as e:
            logger.error(f"DOAJ API error: {str(e)}")
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
                            name_parts = author.get("name", "").split()
                            first_name = name_parts[0] if name_parts else None
                            surname = " ".join(name_parts[1:]) if len(name_parts) > 1 else None
                            authors.append(Author(
                                first_name=first_name,
                                surname=surname,
                                full_name=author.get("name")
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


class GROBIDClient:
    """Client for GROBID API"""
    
    def __init__(self):
        self.base_url = settings.grobid_base_url
        self.headers = {
            "Accept": "application/xml"
        }
    
    async def parse_reference(self, reference_text: str) -> Optional[ReferenceData]:
        """Parse reference text using GROBID API"""
        try:
            async with httpx.AsyncClient() as client:
                data = {
                    "input": reference_text
                }
                
                response = await client.post(
                    f"{self.base_url}/processReferences",
                    headers=self.headers,
                    data=data,
                    timeout=30.0
                )
                response.raise_for_status()
                
                # Parse XML response (simplified)
                return self._parse_grobid_response(response.text)
                
        except Exception as e:
            logger.error(f"GROBID API error: {str(e)}")
            return None
    
    def _parse_grobid_response(self, xml_content: str) -> Optional[ReferenceData]:
        """Parse GROBID XML response"""
        # This is a simplified parser - in production, use proper XML parsing
        # For now, return None as GROBID parsing requires more complex XML handling
        logger.info("GROBID parsing not fully implemented - requires XML parsing")
        return None