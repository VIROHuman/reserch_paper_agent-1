import httpx
import requests
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
                results = self._parse_crossref_response(data)
                return results
                
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
                    timeout=30.0
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
                results = self._parse_openalex_response(data)
                return results
                
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
        
        word_positions = []
        for word, positions in abstract_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        
        word_positions.sort(key=lambda x: x[0])
        
        return " ".join([word for _, word in word_positions])
    
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
                    timeout=30.0
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
    """Client for GROBID API - specialized for academic document parsing"""
    
    def __init__(self):
        self.base_url = settings.grobid_base_url
        self.headers = {
            "Accept": "application/xml, text/plain, */*"
        }
    
    async def process_pdf_document(self, pdf_path: str) -> Dict[str, Any]:
        """Process entire PDF document with GROBID using requests for reliable file uploads"""
        try:
            logger.info(f"🔬 GROBID: Processing PDF document: {pdf_path}")
            
            # Use requests in a thread pool to avoid blocking the event loop
            # This ensures immediate file reading and eliminates httpx I/O issues
            response = await asyncio.to_thread(self._process_pdf_with_requests, pdf_path)
            
            # Debug log for raw XML
            logger.info(f"🔬 GROBID raw XML response (first 500 chars): {response.text[:500]}")
            logger.info(f"🔬 GROBID response length: {len(response.text)} characters")

            # Parse XML response
            result = self._parse_grobid_xml_response(response.text)
            logger.info(f"🔬 GROBID parsing result: success={result.get('success')}, references={result.get('reference_count', 0)}")
            return result
                    
        except Exception as e:
            logger.error(f"❌ GROBID API error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _process_pdf_with_requests(self, pdf_path: str):
        """Synchronous method using requests for GROBID PDF processing"""
        try:
            logger.info(f"🔬 GROBID: Opening PDF file: {pdf_path}")
            with open(pdf_path, 'rb') as pdf_file:
                files = {"input": (pdf_path, pdf_file, "application/pdf")}
                data = {
                    "consolidateHeader": 1,
                    "consolidateCitations": 0,
                    "includeRawCitations": 1,
                    "includeRawAffiliations": 1
                }
                
                logger.info(f"🔬 GROBID: Sending request to {self.base_url}/api/processFulltextDocument")
                response = requests.post(
                    f"{self.base_url}/api/processFulltextDocument",
                    files=files,
                    data=data,
                    timeout=120.0
                )
                logger.info(f"🔬 GROBID: Response status: {response.status_code}")
                response.raise_for_status()
                return response
        except Exception as e:
            logger.error(f"❌ GROBID requests error: {str(e)}")
            raise
    
    async def process_reference_text(self, reference_text: str) -> Optional[ReferenceData]:
        """Parse individual reference text using GROBID"""
        try:
            logger.info(f"🔬 GROBID: Processing reference text: {reference_text[:100]}...")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                data = {"input": reference_text}
                
                response = await client.post(
                    f"{self.base_url}/api/processReferences",
                    data=data
                )
                response.raise_for_status()
                
                return self._parse_grobid_xml_response(response.text)
                
        except Exception as e:
            logger.error(f"❌ GROBID API error: {str(e)}")
            return None
    
    def _parse_grobid_xml_response(self, xml_content: str) -> Dict[str, Any]:
        """Parse GROBID XML response and extract references"""
        try:
            import xml.etree.ElementTree as ET
            
            root = ET.fromstring(xml_content)
            
            # Extract document metadata
            doc_metadata = self._extract_document_metadata(root)
            
            # Extract references
            references = self._extract_references_from_xml(root)
            
            return {
                "success": True,
                "document_metadata": doc_metadata,
                "references": references,
                "reference_count": len(references)
            }
            
        except Exception as e:
            logger.error(f"❌ GROBID XML parsing error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _extract_document_metadata(self, root) -> Dict[str, Any]:
        """Extract document metadata from GROBID XML"""
        metadata = {}
        
        # Extract title
        title_elem = root.find('.//titleStmt/title')
        if title_elem is not None:
            metadata["title"] = title_elem.text
        
        # Extract authors
        authors = []
        for author in root.findall('.//titleStmt/author'):
            pers_name = author.find('persName')
            if pers_name is not None:
                surname = pers_name.find('surname')
                forename = pers_name.find('forename')
                if surname is not None and forename is not None:
                    authors.append({
                        "family_name": surname.text,
                        "given_name": forename.text
                    })
        metadata["authors"] = authors
        
        # Extract abstract
        abstract_elem = root.find('.//abstract')
        if abstract_elem is not None:
            metadata["abstract"] = abstract_elem.text
        
        return metadata
    
    def _extract_references_from_xml(self, root) -> List[Dict[str, Any]]:
        """Extract references from GROBID XML"""
        references = []
        
        # Debug: Log the XML structure to understand what GROBID returns
        logger.info(f"🔬 GROBID XML structure analysis:")
        
        # Check for different possible reference structures
        list_bibl = root.findall('.//listBibl')
        logger.info(f"🔬 Found {len(list_bibl)} listBibl elements")
        
        bibl_struct = root.findall('.//biblStruct')
        logger.info(f"🔬 Found {len(bibl_struct)} biblStruct elements")
        
        # Also check for other possible reference structures
        ref_elements = root.findall('.//ref')
        logger.info(f"🔬 Found {len(ref_elements)} ref elements")
        
        # Check for references in different namespaces
        all_refs = root.findall('.//{http://www.tei-c.org/ns/1.0}listBibl/{http://www.tei-c.org/ns/1.0}biblStruct')
        logger.info(f"🔬 Found {len(all_refs)} namespaced biblStruct elements")
        
        # Try both namespaced and non-namespaced references
        for ref_elem in root.findall('.//listBibl/biblStruct'):
            ref_data = self._parse_single_reference(ref_elem)
            if ref_data:
                references.append(ref_data)
        
        # Also try namespaced references
        for ref_elem in root.findall('.//{http://www.tei-c.org/ns/1.0}listBibl/{http://www.tei-c.org/ns/1.0}biblStruct'):
            ref_data = self._parse_single_reference(ref_elem)
            if ref_data:
                references.append(ref_data)
        
        logger.info(f"🔬 GROBID extracted {len(references)} references")
        return references
    
    def _parse_single_reference(self, ref_elem) -> Optional[Dict[str, Any]]:
        """Parse a single reference from GROBID XML"""
        try:
            ref_data = {
                "family_names": [],
                "given_names": [],
                "year": None,
                "title": None,
                "journal": None,
                "doi": None,
                "pages": None,
                "publisher": None,
                "url": None
            }
            
            # Extract authors (try both namespaced and non-namespaced)
            for author in ref_elem.findall('.//author/persName') + ref_elem.findall('.//{http://www.tei-c.org/ns/1.0}author/{http://www.tei-c.org/ns/1.0}persName'):
                surname = author.find('surname') or author.find('{http://www.tei-c.org/ns/1.0}surname')
                forename = author.find('forename') or author.find('{http://www.tei-c.org/ns/1.0}forename')
                if surname is not None:
                    ref_data["family_names"].append(surname.text or "")
                if forename is not None:
                    ref_data["given_names"].append(forename.text or "")
            
            # Extract title (try both namespaced and non-namespaced)
            title_elem = (ref_elem.find('.//title[@level="a"]') or 
                         ref_elem.find('.//{http://www.tei-c.org/ns/1.0}title[@level="a"]'))
            if title_elem is not None:
                ref_data["title"] = title_elem.text
            
            # Extract journal (try both namespaced and non-namespaced)
            journal_elem = (ref_elem.find('.//title[@level="j"]') or 
                           ref_elem.find('.//{http://www.tei-c.org/ns/1.0}title[@level="j"]'))
            if journal_elem is not None:
                ref_data["journal"] = journal_elem.text
            
            # Extract year (try both namespaced and non-namespaced)
            date_elem = (ref_elem.find('.//date') or 
                        ref_elem.find('.//{http://www.tei-c.org/ns/1.0}date'))
            if date_elem is not None:
                ref_data["year"] = date_elem.get('when', date_elem.text)
            
            # Extract pages (try both namespaced and non-namespaced)
            pages_elem = (ref_elem.find('.//biblScope[@unit="page"]') or 
                         ref_elem.find('.//{http://www.tei-c.org/ns/1.0}biblScope[@unit="page"]'))
            if pages_elem is not None:
                ref_data["pages"] = pages_elem.text
            
            # Extract DOI (try both namespaced and non-namespaced)
            doi_elem = (ref_elem.find('.//idno[@type="DOI"]') or 
                       ref_elem.find('.//{http://www.tei-c.org/ns/1.0}idno[@type="DOI"]'))
            if doi_elem is not None:
                ref_data["doi"] = doi_elem.text
            
            # Extract publisher (try both namespaced and non-namespaced)
            publisher_elem = (ref_elem.find('.//publisher') or 
                             ref_elem.find('.//{http://www.tei-c.org/ns/1.0}publisher'))
            if publisher_elem is not None:
                ref_data["publisher"] = publisher_elem.text
            
            return ref_data
            
        except Exception as e:
            logger.error(f"❌ Error parsing single reference: {str(e)}")
        return None
