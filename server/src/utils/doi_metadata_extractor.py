"""
DOI Metadata Extractor - Comprehensive DOI-based metadata retrieval
"""
import re
import httpx
import asyncio
from typing import Dict, Any, Optional, List
from loguru import logger
from urllib.parse import urlparse

from ..config import settings


class DOIMetadataExtractor:
    """Comprehensive DOI metadata extraction from multiple APIs"""
    
    def __init__(self):
        self.crossref_client = None
        self.openalex_client = None
        self.unpaywall_client = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize API clients"""
        try:
            from .api_clients import CrossRefClient, OpenAlexClient
            self.crossref_client = CrossRefClient()
            self.openalex_client = OpenAlexClient()
            logger.info("✅ DOI Metadata Extractor initialized with CrossRef and OpenAlex")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize some clients: {e}")
    
    def normalize_doi(self, doi: str) -> str:
        """Normalize DOI: strip spaces, ensure lowercase, prepend https://doi.org/ if missing"""
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
        
        # Return normalized DOI
        return doi
    
    def get_doi_url(self, doi: str) -> str:
        """Get full DOI URL"""
        normalized_doi = self.normalize_doi(doi)
        if not normalized_doi:
            return ""
        return f"https://doi.org/{normalized_doi}"
    
    async def extract_metadata(self, doi: str) -> Dict[str, Any]:
        """Extract metadata for a DOI using multiple APIs in order"""
        normalized_doi = self.normalize_doi(doi)
        if not normalized_doi:
            return {"error": "Invalid DOI format"}
        
        logger.info(f"🔍 DOI METADATA EXTRACTION: {normalized_doi}")
        
        # Try APIs in order of preference
        apis_to_try = [
            ("CrossRef", self._extract_from_crossref),
            ("OpenAlex", self._extract_from_openalex),
            ("Unpaywall", self._extract_from_unpaywall),
        ]
        
        for api_name, extract_func in apis_to_try:
            try:
                logger.info(f"🌐 Trying {api_name} API...")
                metadata = await extract_func(normalized_doi)
                if metadata and not metadata.get("error"):
                    logger.info(f"✅ Successfully extracted metadata from {api_name}")
                    metadata["source_api"] = api_name
                    metadata["doi_url"] = self.get_doi_url(normalized_doi)
                    return metadata
                else:
                    logger.warning(f"⚠️ {api_name} returned no data")
            except Exception as e:
                logger.warning(f"⚠️ {api_name} API failed: {str(e)}")
                continue
        
        logger.error(f"❌ All APIs failed for DOI: {normalized_doi}")
        return {"error": "Metadata not found for DOI"}
    
    async def _extract_from_crossref(self, doi: str) -> Dict[str, Any]:
        """Extract metadata from CrossRef API"""
        try:
            async with httpx.AsyncClient() as client:
                url = f"https://api.crossref.org/works/{doi}"
                headers = {
                    "User-Agent": "ResearchPaperAgent/1.0 (mailto:your-email@example.com)",
                    "Accept": "application/json"
                }
                
                response = await client.get(url, headers=headers, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                
                if "message" not in data:
                    return {"error": "No message in CrossRef response"}
                
                item = data["message"]
                return self._parse_crossref_metadata(item)
                
        except Exception as e:
            logger.error(f"CrossRef API error: {str(e)}")
            return {"error": str(e)}
    
    async def _extract_from_openalex(self, doi: str) -> Dict[str, Any]:
        """Extract metadata from OpenAlex API"""
        try:
            async with httpx.AsyncClient() as client:
                url = f"https://api.openalex.org/works/doi:{doi}"
                headers = {
                    "User-Agent": "ResearchPaperAgent/1.0 (mailto:your-email@example.com)",
                    "Accept": "application/json"
                }
                
                response = await client.get(url, headers=headers, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                
                return self._parse_openalex_metadata(data)
                
        except Exception as e:
            logger.error(f"OpenAlex API error: {str(e)}")
            return {"error": str(e)}
    
    async def _extract_from_unpaywall(self, doi: str) -> Dict[str, Any]:
        """Extract metadata from Unpaywall API (optional)"""
        try:
            # Unpaywall requires email registration
            email = getattr(settings, 'unpaywall_email', None)
            if not email:
                logger.info("Unpaywall email not configured, skipping")
                return {"error": "Unpaywall email not configured"}
            
            async with httpx.AsyncClient() as client:
                url = f"https://api.unpaywall.org/v2/{doi}"
                params = {"email": email}
                headers = {
                    "User-Agent": "ResearchPaperAgent/1.0 (mailto:your-email@example.com)",
                    "Accept": "application/json"
                }
                
                response = await client.get(url, headers=headers, params=params, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                
                return self._parse_unpaywall_metadata(data)
                
        except Exception as e:
            logger.error(f"Unpaywall API error: {str(e)}")
            return {"error": str(e)}
    
    def _parse_crossref_metadata(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Parse CrossRef metadata into standardized format"""
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
                "citation_count": citation_count
            }
            
        except Exception as e:
            logger.error(f"Error parsing CrossRef metadata: {str(e)}")
            return {"error": str(e)}
    
    def _parse_openalex_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse OpenAlex metadata into standardized format"""
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
                "citation_count": citation_count
            }
            
        except Exception as e:
            logger.error(f"Error parsing OpenAlex metadata: {str(e)}")
            return {"error": str(e)}
    
    def _parse_unpaywall_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Unpaywall metadata into standardized format"""
        try:
            # Extract authors
            authors = []
            if "z_authors" in data:
                for author in data["z_authors"]:
                    given = author.get("given", "")
                    family = author.get("family", "")
                    full_name = f"{given} {family}".strip()
                    if full_name:
                        authors.append(full_name)
            
            return {
                "doi": data.get("doi", "").lower(),
                "title": data.get("title"),
                "authors": authors,
                "journal": data.get("journal_name"),
                "publisher": data.get("publisher"),
                "year": data.get("year"),
                "abstract": data.get("abstract"),
                "url": data.get("best_oa_location", {}).get("url") if data.get("best_oa_location") else None,
                "is_open_access": data.get("is_oa", False),
                "open_access_url": data.get("best_oa_location", {}).get("url") if data.get("best_oa_location") else None
            }
            
        except Exception as e:
            logger.error(f"Error parsing Unpaywall metadata: {str(e)}")
            return {"error": str(e)}
    
    def _convert_abstract_index_to_text(self, abstract_index: Dict[str, List[int]]) -> str:
        """Convert OpenAlex abstract inverted index to text"""
        try:
            # Create a list of (position, word) tuples
            words_with_positions = []
            for word, positions in abstract_index.items():
                for pos in positions:
                    words_with_positions.append((pos, word))
            
            # Sort by position
            words_with_positions.sort(key=lambda x: x[0])
            
            # Join words
            return " ".join([word for _, word in words_with_positions])
        except Exception as e:
            logger.error(f"Error converting abstract index: {str(e)}")
            return ""


class DOIMetadataConflictDetector:
    """Detect conflicts between online metadata and Ollama-extracted data"""
    
    @staticmethod
    def detect_conflicts(online_metadata: Dict[str, Any], ollama_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect conflicts between online and Ollama data"""
        conflicts = {
            "has_conflicts": False,
            "conflicts": [],
            "preferred_data": {},
            "confidence_scores": {}
        }
        
        # Check title conflicts
        online_title = online_metadata.get("title", "").lower().strip() if online_metadata.get("title") else ""
        ollama_title = ollama_data.get("title", "").lower().strip() if ollama_data.get("title") else ""
        
        if online_title and ollama_title and online_title != ollama_title:
            conflicts["has_conflicts"] = True
            conflicts["conflicts"].append({
                "field": "title",
                "online_value": online_metadata.get("title"),
                "ollama_value": ollama_data.get("title"),
                "preferred": "online"
            })
            conflicts["preferred_data"]["title"] = online_metadata.get("title")
        elif online_title:
            conflicts["preferred_data"]["title"] = online_metadata.get("title")
        elif ollama_title:
            conflicts["preferred_data"]["title"] = ollama_data.get("title")
        
        # Check year conflicts
        online_year = online_metadata.get("year")
        ollama_year = ollama_data.get("year")
        
        if online_year and ollama_year and str(online_year) != str(ollama_year):
            conflicts["has_conflicts"] = True
            conflicts["conflicts"].append({
                "field": "year",
                "online_value": online_year,
                "ollama_value": ollama_year,
                "preferred": "online"
            })
            conflicts["preferred_data"]["year"] = online_year
        elif online_year:
            conflicts["preferred_data"]["year"] = online_year
        elif ollama_year:
            conflicts["preferred_data"]["year"] = ollama_year
        
        # Check journal conflicts
        online_journal = online_metadata.get("journal", "").lower().strip() if online_metadata.get("journal") else ""
        ollama_journal = ollama_data.get("journal", "").lower().strip() if ollama_data.get("journal") else ""
        
        if online_journal and ollama_journal and online_journal != ollama_journal:
            conflicts["has_conflicts"] = True
            conflicts["conflicts"].append({
                "field": "journal",
                "online_value": online_metadata.get("journal"),
                "ollama_value": ollama_data.get("journal"),
                "preferred": "online"
            })
            conflicts["preferred_data"]["journal"] = online_metadata.get("journal")
        elif online_journal:
            conflicts["preferred_data"]["journal"] = online_metadata.get("journal")
        elif ollama_journal:
            conflicts["preferred_data"]["journal"] = ollama_data.get("journal")
        
        # Check author conflicts (more complex)
        online_authors = [author.lower().strip() for author in online_metadata.get("authors", [])]
        ollama_authors = []
        if ollama_data.get("family_names") and ollama_data.get("given_names"):
            for i in range(len(ollama_data["family_names"])):
                given = ollama_data["given_names"][i] if i < len(ollama_data["given_names"]) else ""
                family = ollama_data["family_names"][i] if i < len(ollama_data["family_names"]) else ""
                full_name = f"{given} {family}".strip()
                if full_name:
                    ollama_authors.append(full_name.lower().strip())
        
        if online_authors and ollama_authors:
            # Check if author lists are significantly different
            online_set = set(online_authors)
            ollama_set = set(ollama_authors)
            
            if len(online_set.symmetric_difference(ollama_set)) > 0:
                conflicts["has_conflicts"] = True
                conflicts["conflicts"].append({
                    "field": "authors",
                    "online_value": online_metadata.get("authors"),
                    "ollama_value": ollama_authors,
                    "preferred": "online"
                })
                conflicts["preferred_data"]["authors"] = online_metadata.get("authors")
        elif online_authors:
            conflicts["preferred_data"]["authors"] = online_metadata.get("authors")
        elif ollama_authors:
            conflicts["preferred_data"]["authors"] = ollama_authors
        
        # Calculate confidence scores
        conflicts["confidence_scores"] = {
            "online_confidence": 0.9 if online_metadata.get("source_api") else 0.0,
            "ollama_confidence": 0.7 if ollama_data.get("title") else 0.0
        }
        
        return conflicts
