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
            logger.info("DOI Metadata Extractor initialized with CrossRef and OpenAlex")
        except Exception as e:
            logger.warning(f"Failed to initialize some clients: {e}")
    
    def normalize_doi(self, doi: str) -> str:
        """Normalize DOI: strip spaces, ensure lowercase, prepend https://doi.org/ if missing"""
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
            logger.warning(f" Invalid DOI format: {doi}")
            return ""
        
        doi = doi.lower()
        
        return doi
    
    def get_doi_url(self, doi: str) -> str:
        """Get full DOI URL"""
        normalized_doi = self.normalize_doi(doi)
        if not normalized_doi:
            return ""
        return f"https://doi.org/{normalized_doi}"
    
    async def extract_metadata(self, doi: str) -> Dict[str, Any]:
        normalized_doi = self.normalize_doi(doi)
        if not normalized_doi:
            return {"error": "Invalid DOI format"}
        
        apis_to_try = [
            ("CrossRef", self._extract_from_crossref),
            ("OpenAlex", self._extract_from_openalex),
            ("Unpaywall", self._extract_from_unpaywall),
        ]
        
        for api_name, extract_func in apis_to_try:
            try:
                metadata = await extract_func(normalized_doi)
                if metadata and not metadata.get("error"):
                    metadata["source_api"] = api_name
                    metadata["doi_url"] = self.get_doi_url(normalized_doi)
                    return metadata
            except Exception as e:
                logger.warning(f"{api_name} API failed: {str(e)}")
                continue
        
        return {"error": "Metadata not found for DOI"}
    
    async def _extract_from_crossref(self, doi: str) -> Dict[str, Any]:
        """Extract metadata from CrossRef API"""
        try:
            async with httpx.AsyncClient() as client:
                url = f"https://api.crossref.org/works/{doi}"
                headers = {
                    "User-Agent": "ResearchPaperAgent/1.0 (mailto:user@example.com)",
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
                    "User-Agent": "ResearchPaperAgent/1.0 (mailto:user@example.com)",
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
                    "User-Agent": "ResearchPaperAgent/1.0 (mailto:user@example.com)",
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
            words_with_positions = []
            for word, positions in abstract_index.items():
                for pos in positions:
                    words_with_positions.append((pos, word))
            
            words_with_positions.sort(key=lambda x: x[0])
            
            return " ".join([word for _, word in words_with_positions])
        except Exception as e:
            logger.error(f"Error converting abstract index: {str(e)}")
            return ""


class DOIMetadataConflictDetector:
    """Enhanced conflict detection between online metadata and LLM-extracted data"""
    
    def __init__(self):
        self.field_weights = {
            "title": 0.30,
            "authors": 0.25,
            "year": 0.20,
            "journal": 0.15,
            "doi": 0.10
        }
        
        self.similarity_thresholds = {
            "title": 0.7,
            "journal": 0.6,
            "authors": 0.5
        }
        
        logger.info("Enhanced DOI Metadata Conflict Detector initialized")
    
    def detect_conflicts(self, online_metadata: Dict[str, Any], ollama_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced conflict detection with detailed comparison analysis"""
        conflicts = {
            "has_conflicts": False,
            "conflicts": [],
            "preferred_data": {},
            "confidence_scores": {},
            "field_comparisons": {},
            "similarity_scores": {},
            "resolution_strategy": "online_preferred"
        }
        
        fields_to_compare = ["title", "year", "journal", "authors", "doi"]
        
        for field in fields_to_compare:
            field_comparison = self._compare_field(
                field, 
                online_metadata.get(field), 
                ollama_data.get(field)
            )
            
            conflicts["field_comparisons"][field] = field_comparison
            conflicts["similarity_scores"][field] = field_comparison["similarity"]
            
            if field_comparison["has_conflict"]:
                conflicts["has_conflicts"] = True
                conflicts["conflicts"].append({
                    "field": field,
                    "online_value": field_comparison["online_value"],
                    "ollama_value": field_comparison["ollama_value"],
                    "preferred": field_comparison["preferred"],
                    "confidence": field_comparison["confidence"],
                    "similarity": field_comparison["similarity"],
                    "conflict_reason": field_comparison["conflict_reason"]
                })
                conflicts["preferred_data"][field] = field_comparison["preferred_value"]
            else:
                conflicts["preferred_data"][field] = field_comparison["preferred_value"]
        
        conflicts["confidence_scores"] = self._calculate_confidence_scores(
            online_metadata, ollama_data, conflicts["field_comparisons"]
        )
        
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
        
        conflicts["confidence_scores"] = {
            "online_confidence": 0.9 if online_metadata.get("source_api") else 0.0,
            "ollama_confidence": 0.7 if ollama_data.get("title") else 0.0
        }
        
        return conflicts
    
    def _compare_field(self, field: str, online_value: Any, ollama_value: Any) -> Dict[str, Any]:
        """Compare a specific field between online and LLM data"""
        comparison = {
            "field": field,
            "online_value": online_value,
            "ollama_value": ollama_value,
            "has_conflict": False,
            "preferred": "none",
            "preferred_value": None,
            "confidence": 0.0,
            "similarity": 0.0,
            "conflict_reason": None
        }
        
        if field == "title":
            return self._compare_title_field(online_value, ollama_value, comparison)
        elif field == "year":
            return self._compare_year_field(online_value, ollama_value, comparison)
        elif field == "journal":
            return self._compare_journal_field(online_value, ollama_value, comparison)
        elif field == "authors":
            return self._compare_authors_field(online_value, ollama_value, comparison)
        elif field == "doi":
            return self._compare_doi_field(online_value, ollama_value, comparison)
        
        return comparison
    
    def _compare_title_field(self, online_title: str, ollama_title: str, comparison: Dict[str, Any]) -> Dict[str, Any]:
        """Compare title fields with enhanced similarity analysis"""
        if not online_title and not ollama_title:
            comparison["preferred_value"] = None
            return comparison
        
        if not online_title:
            comparison["preferred_value"] = ollama_title
            comparison["preferred"] = "LLM"
            comparison["confidence"] = 0.7
            return comparison
        
        if not ollama_title:
            comparison["preferred_value"] = online_title
            comparison["preferred"] = "online"
            comparison["confidence"] = 0.9
            return comparison
        
        # Calculate similarity
        similarity = self._calculate_text_similarity(online_title, ollama_title)
        comparison["similarity"] = similarity
        
        if similarity < self.similarity_thresholds["title"]:
            comparison["has_conflict"] = True
            comparison["conflict_reason"] = f"Title similarity too low ({similarity:.2f})"
            
            # Prefer online data for titles (more authoritative)
            comparison["preferred"] = "online"
            comparison["preferred_value"] = online_title
            comparison["confidence"] = 0.9
        else:
            # High similarity - prefer LLM data
            comparison["preferred"] = "online"
            comparison["preferred_value"] = online_title
            comparison["confidence"] = 0.95
        
        return comparison
    
    def _compare_year_field(self, online_year: Any, ollama_year: Any, comparison: Dict[str, Any]) -> Dict[str, Any]:
        """Compare year fields"""
        if not online_year and not ollama_year:
            comparison["preferred_value"] = None
            return comparison
        
        if not online_year:
            comparison["preferred_value"] = ollama_year
            comparison["preferred"] = "ollama"
            comparison["confidence"] = 0.7
            return comparison
        
        if not ollama_year:
            comparison["preferred_value"] = online_year
            comparison["preferred"] = "online"
            comparison["confidence"] = 0.95
            return comparison
        
        # Convert to strings for comparison
        online_year_str = str(online_year)
        ollama_year_str = str(ollama_year)
        
        if online_year_str != ollama_year_str:
            comparison["has_conflict"] = True
            comparison["conflict_reason"] = f"Year mismatch: {online_year} vs {ollama_year}"
            
            # Prefer online data for years (more reliable)
            comparison["preferred"] = "online"
            comparison["preferred_value"] = online_year
            comparison["confidence"] = 0.95
        else:
            comparison["preferred"] = "online"
            comparison["preferred_value"] = online_year
            comparison["confidence"] = 0.98
        
        return comparison
    
    def _compare_journal_field(self, online_journal: str, ollama_journal: str, comparison: Dict[str, Any]) -> Dict[str, Any]:
        """Compare journal fields with similarity analysis"""
        if not online_journal and not ollama_journal:
            comparison["preferred_value"] = None
            return comparison
        
        if not online_journal:
            comparison["preferred_value"] = ollama_journal
            comparison["preferred"] = "ollama"
            comparison["confidence"] = 0.7
            return comparison
        
        if not ollama_journal:
            comparison["preferred_value"] = online_journal
            comparison["preferred"] = "online"
            comparison["confidence"] = 0.9
            return comparison
        
        # Calculate similarity
        similarity = self._calculate_text_similarity(online_journal, ollama_journal)
        comparison["similarity"] = similarity
        
        if similarity < self.similarity_thresholds["journal"]:
            comparison["has_conflict"] = True
            comparison["conflict_reason"] = f"Journal similarity too low ({similarity:.2f})"
            
            # Prefer online data for journals
            comparison["preferred"] = "online"
            comparison["preferred_value"] = online_journal
            comparison["confidence"] = 0.9
        else:
            comparison["preferred"] = "online"
            comparison["preferred_value"] = online_journal
            comparison["confidence"] = 0.95
        
        return comparison
    
    def _compare_authors_field(self, online_authors: List[str], ollama_authors: List[str], comparison: Dict[str, Any]) -> Dict[str, Any]:
        """Compare author lists with enhanced analysis"""
        if not online_authors and not ollama_authors:
            comparison["preferred_value"] = []
            return comparison
        
        if not online_authors:
            comparison["preferred_value"] = ollama_authors
            comparison["preferred"] = "ollama"
            comparison["confidence"] = 0.7
            return comparison
        
        if not ollama_authors:
            comparison["preferred_value"] = online_authors
            comparison["preferred"] = "online"
            comparison["confidence"] = 0.9
            return comparison
        
        # Calculate author similarity
        similarity = self._calculate_author_similarity(online_authors, ollama_authors)
        comparison["similarity"] = similarity
        
        if similarity < self.similarity_thresholds["authors"]:
            comparison["has_conflict"] = True
            comparison["conflict_reason"] = f"Author similarity too low ({similarity:.2f})"
            
            # Prefer online data for authors (more complete)
            comparison["preferred"] = "online"
            comparison["preferred_value"] = online_authors
            comparison["confidence"] = 0.9
        else:
            # Prefer online data if it's more complete
            if len(online_authors) >= len(ollama_authors):
                comparison["preferred"] = "online"
                comparison["preferred_value"] = online_authors
                comparison["confidence"] = 0.95
            else:
                comparison["preferred"] = "ollama"
                comparison["preferred_value"] = ollama_authors
                comparison["confidence"] = 0.85
        
        return comparison
    
    def _compare_doi_field(self, online_doi: str, ollama_doi: str, comparison: Dict[str, Any]) -> Dict[str, Any]:
        """Compare DOI fields"""
        if not online_doi and not ollama_doi:
            comparison["preferred_value"] = None
            return comparison
        
        if not online_doi:
            comparison["preferred_value"] = ollama_doi
            comparison["preferred"] = "ollama"
            comparison["confidence"] = 0.7
            return comparison
        
        if not ollama_doi:
            comparison["preferred_value"] = online_doi
            comparison["preferred"] = "online"
            comparison["confidence"] = 0.98
            return comparison
        
        # Normalize DOIs for comparison
        online_doi_norm = online_doi.lower().strip()
        ollama_doi_norm = ollama_doi.lower().strip()
        
        if online_doi_norm != ollama_doi_norm:
            comparison["has_conflict"] = True
            comparison["conflict_reason"] = f"DOI mismatch: {online_doi} vs {ollama_doi}"
            
            # Prefer online DOI (more reliable)
            comparison["preferred"] = "online"
            comparison["preferred_value"] = online_doi
            comparison["confidence"] = 0.98
        else:
            comparison["preferred"] = "online"
            comparison["preferred_value"] = online_doi
            comparison["confidence"] = 0.99
        
        return comparison
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using Jaccard similarity"""
        if not text1 or not text2:
            return 0.0
        
        # Normalize text
        text1_norm = text1.lower().strip()
        text2_norm = text2.lower().strip()
        
        if text1_norm == text2_norm:
            return 1.0
        
        # Word-based similarity
        words1 = set(text1_norm.split())
        words2 = set(text2_norm.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_author_similarity(self, authors1: List[str], authors2: List[str]) -> float:
        """Calculate similarity between author lists"""
        if not authors1 or not authors2:
            return 0.0
        
        # Normalize author names
        authors1_norm = [author.lower().strip() for author in authors1]
        authors2_norm = [author.lower().strip() for author in authors2]
        
        # Calculate overlap
        set1 = set(authors1_norm)
        set2 = set(authors2_norm)
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_confidence_scores(
        self, 
        online_metadata: Dict[str, Any], 
        ollama_data: Dict[str, Any],
        field_comparisons: Dict[str, Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate confidence scores for each data source"""
        return {
            "online_confidence": 0.9 if online_metadata.get("source_api") else 0.0,
            "ollama_confidence": 0.75 if ollama_data.get("title") else 0.0,
            "overall_confidence": sum(comp.get("confidence", 0) for comp in field_comparisons.values()) / len(field_comparisons) if field_comparisons else 0.0
        }
