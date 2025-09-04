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
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                return self._parse_crossref_response(data)
                
        except Exception as e:
            logger.error(f"CrossRef API error: {str(e)}")
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
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "search": query,
                    "per_page": limit,
                    "sort": "relevance_score:desc"
                }
                
                response = await client.get(
                    f"{self.base_url}/works",
                    headers=self.headers,
                    params=params,
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                return self._parse_openalex_response(data)
                
        except Exception as e:
            logger.error(f"OpenAlex API error: {str(e)}")
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
                    reference = ReferenceData(
                        title=item.get("title"),
                        authors=authors,
                        year=item.get("publication_year"),
                        journal=item.get("primary_location", {}).get("source", {}).get("display_name"),
                        doi=item.get("doi"),
                        url=item.get("id"),
                        abstract=item.get("abstract_inverted_index"),
                        publication_type=item.get("type", "journal-article")
                    )
                    references.append(reference)
                    
                except Exception as e:
                    logger.warning(f"Error parsing OpenAlex item: {str(e)}")
                    continue
        
        return references


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