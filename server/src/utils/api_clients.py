import httpx
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger

from ..config import settings
from ..models.schemas import CrossRefResponse, OpenAlexResponse, SemanticScholarResponse, ReferenceData, Author


class CrossRefClient:
    
    def __init__(self):
        self.base_url = settings.crossref_base_url
        self.headers = {
            "User-Agent": "ResearchPaperAgent/1.0 (mailto:your-email@example.com)",
            "Accept": "application/json"
        }
        if settings.crossref_api_key:
            self.headers["Authorization"] = f"Bearer {settings.crossref_api_key}"
    
    async def search_reference(self, query: str, limit: int = 5) -> List[ReferenceData]:
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
    
    async def get_doi_metadata(self, doi: str) -> Dict[str, Any]:
        """Get metadata for a specific DOI from CrossRef"""
        logger.info(f"🔍 CROSSREF DOI METADATA: {doi}")
        try:
            # Normalize DOI
            normalized_doi = self._normalize_doi(doi)
            if not normalized_doi:
                return {"error": "Invalid DOI format"}
            
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/works/{normalized_doi}"
                
                logger.info(f"📡 CrossRef DOI URL: {url}")
                
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )
                logger.info(f"📡 CrossRef DOI response status: {response.status_code}")
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"📡 CrossRef DOI response keys: {list(data.keys())}")
                
                if "message" not in data:
                    return {"error": "No message in CrossRef response"}
                
                metadata = self._parse_crossref_doi_metadata(data["message"])
                logger.info(f"✅ CrossRef DOI metadata extracted successfully")
                return metadata
                
        except Exception as e:
            logger.error(f"❌ CrossRef DOI API error: {str(e)}")
            return {"error": str(e)}
    
    def _normalize_doi(self, doi: str) -> str:
        """Normalize DOI: strip spaces, ensure lowercase, remove prefixes"""
        if not doi:
            return ""
        
        # Strip whitespace
        doi = doi.strip()
        
        # Remove any existing https://doi.org/ prefix
        if doi.startswith("https://doi.org/"):
            doi = doi[16:]
        elif doi.startswith("http://doi.org/"):
            doi = doi[15:]
        elif doi.startswith("doi.org/"):
            doi = doi[8:]
        
        # Ensure it starts with 10.
        if not doi.startswith("10."):
            logger.warning(f"⚠️ Invalid DOI format: {doi}")
            return ""
        
        # Convert to lowercase
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
            
            # Extract publication year
            year = None
            if "published-print" in item and "date-parts" in item["published-print"]:
                year = item["published-print"]["date-parts"][0][0]
            elif "published-online" in item and "date-parts" in item["published-online"]:
                year = item["published-online"]["date-parts"][0][0]
            elif "published" in item and "date-parts" in item["published"]:
                year = item["published"]["date-parts"][0][0]
            
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
    
    async def get_doi_metadata(self, doi: str) -> Dict[str, Any]:
        """Get metadata for a specific DOI from OpenAlex"""
        logger.info(f"🔍 OPENALEX DOI METADATA: {doi}")
        try:
            # Normalize DOI
            normalized_doi = self._normalize_doi(doi)
            if not normalized_doi:
                return {"error": "Invalid DOI format"}
            
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/works/doi:{normalized_doi}"
                
                logger.info(f"📡 OpenAlex DOI URL: {url}")
                
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )
                logger.info(f"📡 OpenAlex DOI response status: {response.status_code}")
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"📡 OpenAlex DOI response keys: {list(data.keys())}")
                
                metadata = self._parse_openalex_doi_metadata(data)
                logger.info(f"✅ OpenAlex DOI metadata extracted successfully")
                return metadata
                
        except Exception as e:
            logger.error(f"❌ OpenAlex DOI API error: {str(e)}")
            return {"error": str(e)}
    
    def _normalize_doi(self, doi: str) -> str:
        """Normalize DOI: strip spaces, ensure lowercase, remove prefixes"""
        if not doi:
            return ""
        
        # Strip whitespace
        doi = doi.strip()
        
        # Remove any existing https://doi.org/ prefix
        if doi.startswith("https://doi.org/"):
            doi = doi[16:]
        elif doi.startswith("http://doi.org/"):
            doi = doi[15:]
        elif doi.startswith("doi.org/"):
            doi = doi[8:]
        
        # Ensure it starts with 10.
        if not doi.startswith("10."):
            logger.warning(f"⚠️ Invalid DOI format: {doi}")
            return ""
        
        # Convert to lowercase
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