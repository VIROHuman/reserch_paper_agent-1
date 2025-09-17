import pdfplumber
import fitz  # PyMuPDF
import re
import tempfile
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger
import asyncio
from concurrent.futures import ThreadPoolExecutor
from .api_clients import GROBIDClient

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False


class PDFReferenceExtractor:
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.nlp = None
        self._load_spacy_model()
        self.grobid_client = GROBIDClient()
        
    def _load_spacy_model(self):
        if not SPACY_AVAILABLE:
            logger.warning("spaCy not available. GROBID will be used for all processing.")
            self.nlp = None
            return
            
        try:
            try:
                self.nlp = spacy.load("en_core_web_trf")
                logger.info("Loaded spaCy transformer model")
            except OSError:
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("Loaded spaCy small model")
        except OSError:
            logger.warning("spaCy model not found. Install with: python -m spacy download en_core_web_sm")
            self.nlp = None
    
    async def process_pdf_with_extraction(
        self,
        pdf_path: str,
        paper_type: str = "ACL",
        use_ml: bool = True,
        use_grobid: bool = True
    ) -> Dict[str, Any]:
        """Process PDF and extract references with GROBID as primary method"""
        try:
            # Try GROBID first for better accuracy
            if use_grobid:
                try:
                    logger.info("🔬 Attempting GROBID processing first...")
                    grobid_result = await self.grobid_client.process_pdf_document(pdf_path)
                    
                    if grobid_result.get("success") and grobid_result.get("references"):
                        logger.info(f"✅ GROBID processing successful: {grobid_result['reference_count']} references found")
                        
                        # Convert GROBID references to expected format with smart enrichment
                        formatted_references = []
                        for ref in grobid_result["references"]:
                            # Use GROBID data as base, only enrich missing fields
                            enriched_ref = await self._enrich_grobid_reference(ref)
                            formatted_references.append({
                                "raw": self._format_reference_from_grobid(ref),
                                "parsed": enriched_ref
                            })
                        
                        # Extract paper metadata from GROBID or fallback to local extraction
                        paper_data = grobid_result.get("document_metadata", {})
                        if not paper_data:
                            paper_data = await asyncio.get_event_loop().run_in_executor(
                                self.executor,
                                self._extract_paper_metadata,
                                pdf_path
                            )
                        
                        return {
                            "success": True,
                            "paper_data": paper_data,
                            "references": formatted_references,
                            "reference_count": len(formatted_references),
                            "paper_type": paper_type,
                            "processing_method": "grobid"
                        }
                    else:
                        logger.warning("⚠️ GROBID processing failed, falling back to local extraction")
                        
                except Exception as e:
                    logger.warning(f"⚠️ GROBID processing error: {str(e)}, falling back to local extraction")
            
            # Fallback to local extraction
            logger.info("📄 Using local PDF extraction...")
            references = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._extract_references_from_pdf,
                pdf_path
            )
            
            paper_data = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._extract_paper_metadata,
                pdf_path
            )
            
            return {
                "success": True,
                "paper_data": paper_data,
                "references": references,
                "reference_count": len(references),
                "paper_type": paper_type,
                "processing_method": "local"
            }
                
        except Exception as e:
            logger.error(f"PDF processing error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "references": [],
                "reference_count": 0
            }
    
    def _format_reference_from_grobid(self, ref_data: Dict[str, Any]) -> str:
        """Format GROBID parsed reference data back to text format"""
        try:
            parts = []
            
            # Add authors
            if ref_data.get("family_names") and ref_data.get("given_names"):
                authors = []
                for i, (family, given) in enumerate(zip(ref_data["family_names"], ref_data["given_names"])):
                    if family and given:
                        authors.append(f"{family}, {given}")
                    elif family:
                        authors.append(family)
                if authors:
                    if len(authors) == 1:
                        parts.append(authors[0])
                    else:
                        parts.append(f"{authors[0]} et al." if len(authors) > 1 else ", ".join(authors))
            
            # Add year
            if ref_data.get("year"):
                parts.append(f"({ref_data['year']})")
            
            # Add title
            if ref_data.get("title"):
                parts.append(f'"{ref_data["title"]}"')
            
            # Add journal
            if ref_data.get("journal"):
                parts.append(ref_data["journal"])
            
            # Add pages
            if ref_data.get("pages"):
                parts.append(f"pp. {ref_data['pages']}")
            
            # Add DOI
            if ref_data.get("doi"):
                parts.append(f"DOI: {ref_data['doi']}")
            
            return ". ".join(parts) + "."
            
        except Exception as e:
            logger.error(f"Error formatting GROBID reference: {str(e)}")
            return str(ref_data)
    
    def _extract_references_from_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Extract references from PDF using multiple methods"""
        references = []
        
        try:
            references = self._extract_with_pdfplumber(pdf_path)
            
            if not references:
                references = self._extract_with_pymupdf(pdf_path)
            
        except Exception as e:
            logger.error(f"Error extracting references: {e}")
        
        return references
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Extract references using pdfplumber - process all pages together"""
        references = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                all_text = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        all_text += text + "\n"
                
                if all_text:
                    references = self._extract_references_from_text(all_text)
                    
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")
        
        return references
    
    def _extract_with_pymupdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Extract references using PyMuPDF - process all pages together"""
        references = []
        
        try:
            doc = fitz.open(pdf_path)
            all_text = ""
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text()
                if text:
                    all_text += text + "\n"
            doc.close()
            
            if all_text:
                references = self._extract_references_from_text(all_text)
                
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {e}")
        
        return references
    
    def _extract_references_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract references from text using simplified approach focusing on document end"""
        references = []
        
        # Split text into lines
        lines = text.split('\n')
        total_lines = len(lines)
        
        # Strategy 1: Look for reference section in last 20% of text (or last 1-2 pages)
        search_start = max(0, int(total_lines * 0.8))
        logger.info(f" Searching for references starting from line {search_start} (last 20% of {total_lines} lines)")
        
        ref_section_start = self._find_reference_section(lines[search_start:])
        if ref_section_start is not None:
            actual_start = search_start + ref_section_start
            logger.info(f"📚 Found reference section at line {actual_start}")
            references = self._extract_references_from_section(lines[actual_start:])
        
        if len(references) < 5:
            logger.info(f"  Only found {len(references)} references, expanding search to last 30%")
            search_start = max(0, int(total_lines * 0.7))
            ref_section_start = self._find_reference_section(lines[search_start:])
            if ref_section_start is not None:
                actual_start = search_start + ref_section_start
                logger.info(f"📚 Found reference section at line {actual_start}")
                references = self._extract_references_from_section(lines[actual_start:])
        
        if len(references) < 5:
            logger.info(f"  Only found {len(references)} references, trying last 1-2 pages")
            last_pages_start = max(0, total_lines - 100)
            ref_section_start = self._find_reference_section(lines[last_pages_start:])
            if ref_section_start is not None:
                actual_start = last_pages_start + ref_section_start
                logger.info(f"📚 Found reference section at line {actual_start}")
                references = self._extract_references_from_section(lines[actual_start:])
        
        logger.info(f" Reference extraction completed: {len(references)} references found")
        return references
    
    def _find_reference_section(self, lines: List[str]) -> Optional[int]:
        """Find the start of reference section in given lines"""
        ref_keywords = ['references', 'bibliography', 'works cited', 'literature cited', 'citations']
        
        for i, line in enumerate(lines):
            line_clean = line.strip().lower()
            
            for keyword in ref_keywords:
                if keyword in line_clean and len(line_clean.split()) <= 4:
                    logger.info(f" Found reference section header: '{line.strip()}'")
                    return i
            
            if re.match(r'^\d+\.?\s*(references?|bibliography|citations?)', line_clean):
                logger.info(f" Found numbered reference section: '{line.strip()}'")
                return i
        
        return None
    
    def _extract_references_from_section(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Extract individual references from reference section - SIMPLE SPLITTING ONLY"""
        full_text = "\n".join(lines)
        
        logger.info(f" Processing {len(lines)} lines from reference section")
        
        references = self._extract_references_simple(full_text)
        
        structured_refs = []
        for i, ref_text in enumerate(references):
            structured_refs.append({
                "raw": ref_text.strip()
            })
        
        logger.info(f" Extracted {len(structured_refs)} references")
        return structured_refs
    
    def _extract_references_simple(self, text: str) -> List[str]:
        """Simple, reliable reference extraction using regex patterns"""
        logger.debug(" Using simple reference extraction")

        references = []
        
        lines = text.split('\n')
        
        current_ref = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if re.match(r'^\[\d+\]', line):
                if current_ref:
                    references.append(current_ref.strip())
                current_ref = line
            elif current_ref:
                current_ref += " " + line
            elif len(line) > 20:
                current_ref = line
        
        if current_ref:
            references.append(current_ref.strip())
        
        if len(references) < 3:
            logger.debug("  Few bracket references found, trying numbered references")
            references = self._extract_numbered_references(text)
        
        if len(references) < 3:
            logger.debug("  Few numbered references found, trying author-year format")
            references = self._extract_author_year_references(text)
        
        logger.debug(f" Simple extraction found {len(references)} references")
        return references
    
    def _extract_numbered_references(self, text: str) -> List[str]:
        """Extract numbered references (1. Author, 2) Author, etc.)"""
        references = []
        
        lines = text.split('\n')
        
        current_ref = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if re.match(r'^\d+[\.\)]?\s*[A-Z]', line):
                if current_ref:
                    references.append(current_ref.strip())
                current_ref = line
            elif current_ref:
                current_ref += " " + line
            elif len(line) > 20:
                current_ref = line
        
        if current_ref:
            references.append(current_ref.strip())
        
        return references
    
    def _extract_author_year_references(self, text: str) -> List[str]:
        """Extract author-year references (Smith, J. (2020), etc.)"""
        references = []
        
        lines = text.split('\n')
        
        current_ref = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if re.match(r'^[A-Z][a-z]+,\s*[A-Z]\.\s*\(\d{4}\)', line):
                if current_ref:
                    references.append(current_ref.strip())
                current_ref = line
            elif current_ref:
                current_ref += " " + line
            elif len(line) > 20:
                current_ref = line
        
        if current_ref:
            references.append(current_ref.strip())
        
        return references
    
    def _extract_paper_metadata(self, pdf_path: str) -> Dict[str, Any]:
        """Extract basic paper metadata"""
        metadata = {
            "title": "",
            "authors": [],
            "abstract": "",
            "keywords": [],
            "pages": 0
        }
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                metadata["pages"] = len(pdf.pages)
                
                for page_num in range(min(3, len(pdf.pages))):
                    page = pdf.pages[page_num]
                    text = page.extract_text()
                    
                    if text and not metadata["title"]:
                        lines = [line.strip() for line in text.split('\n') if line.strip()]
                        if lines:
                            metadata["title"] = lines[0]
                    
                    if text and not metadata["abstract"]:
                        abstract_start = text.lower().find('abstract')
                        if abstract_start != -1:
                            abstract_text = text[abstract_start:abstract_start + 1000]
                            metadata["abstract"] = abstract_text[:500]
                            
        except Exception as e:
            logger.warning(f"Metadata extraction failed: {e}")
        
        return metadata
    
    def detect_paper_type(self, pdf_path: str) -> str:
        """Detect paper type based on content"""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages[:3]:
                    text += page.extract_text() or ""
                
                text_lower = text.lower()
                
                if any(conf in text_lower for conf in ['acl', 'emnlp', 'naacl', 'conll']):
                    return "ACL"
                elif any(conf in text_lower for conf in ['aaai', 'ijcai', 'icml', 'iclr', 'neurips']):
                    return "AAAI"
                elif any(conf in text_lower for conf in ['ieee', 'acm', 'springer']):
                    return "IEEE"
                else:
                    return "Generic"
                    
        except Exception as e:
            logger.warning(f"Paper type detection failed: {e}")
            return "Generic"
    
    def get_supported_paper_types(self) -> List[str]:
        """Get list of supported paper types"""
        return ["AAAI", "ACL", "ICML", "ICLR", "NeurIPS", "IEEE", "ACM", "Springer", "Generic"]
    
    async def _enrich_grobid_reference(self, grobid_ref: Dict[str, Any]) -> Dict[str, Any]:
        """Smart enrichment of GROBID reference - only fill missing fields"""
        try:
            logger.info(f"🔍 Smart enrichment for GROBID reference: {grobid_ref.get('title', 'Unknown')[:50]}...")
            
            # Start with GROBID data as base
            enriched_ref = grobid_ref.copy()
            
            # Identify missing fields
            missing_fields = []
            if not enriched_ref.get('family_names') or not enriched_ref.get('given_names'):
                missing_fields.append('authors')
            if not enriched_ref.get('title'):
                missing_fields.append('title')
            if not enriched_ref.get('year'):
                missing_fields.append('year')
            if not enriched_ref.get('journal'):
                missing_fields.append('journal')
            if not enriched_ref.get('doi'):
                missing_fields.append('doi')
            if not enriched_ref.get('publisher'):
                missing_fields.append('publisher')
            if not enriched_ref.get('url'):
                missing_fields.append('url')
            
            logger.info(f"🔍 Missing fields: {missing_fields}")
            
            # Only enrich if we have missing fields
            if missing_fields:
                # Create search query from available data
                search_query = self._create_search_query_from_grobid(grobid_ref)
                
                # Try API enrichment only for missing fields
                api_result = await self._enrich_missing_fields_only(
                    enriched_ref, missing_fields, search_query
                )
                
                if api_result:
                    # Merge only the missing fields
                    for field in missing_fields:
                        if field in api_result and api_result[field]:
                            enriched_ref[field] = api_result[field]
                            logger.info(f"✅ Enriched {field}: {api_result[field]}")
            
            # Calculate confidence score
            confidence = self._calculate_confidence_score(enriched_ref)
            enriched_ref['confidence'] = confidence
            
            logger.info(f"🎯 Final confidence: {confidence:.2f}")
            return enriched_ref
            
        except Exception as e:
            logger.error(f"❌ Smart enrichment failed: {str(e)}")
            return grobid_ref
    
    def _create_search_query_from_grobid(self, grobid_ref: Dict[str, Any]) -> str:
        """Create search query from GROBID reference data"""
        parts = []
        
        if grobid_ref.get('title'):
            parts.append(grobid_ref['title'])
        
        if grobid_ref.get('family_names'):
            parts.extend(grobid_ref['family_names'][:2])  # First 2 authors
        
        if grobid_ref.get('year'):
            parts.append(str(grobid_ref['year']))
        
        return ' '.join(parts)
    
    async def _enrich_missing_fields_only(self, ref: Dict[str, Any], missing_fields: List[str], search_query: str) -> Optional[Dict[str, Any]]:
        """Enrich only the missing fields using APIs"""
        try:
            # Try CrossRef first
            crossref_result = await self.enhanced_parser.smart_api_strategy.crossref_client.search_reference(search_query, limit=1)
            if crossref_result:
                return self._extract_missing_fields_from_api_result(crossref_result[0], missing_fields)
            
            # Try OpenAlex
            openalex_result = await self.enhanced_parser.smart_api_strategy.openalex_client.search_reference(search_query, limit=1)
            if openalex_result:
                return self._extract_missing_fields_from_api_result(openalex_result[0], missing_fields)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ API enrichment failed: {str(e)}")
            return None
    
    def _extract_missing_fields_from_api_result(self, api_result: Dict[str, Any], missing_fields: List[str]) -> Dict[str, Any]:
        """Extract only the missing fields from API result"""
        result = {}
        
        for field in missing_fields:
            if field == 'authors' and 'authors' in api_result:
                result['family_names'] = api_result['authors'].get('family_names', [])
                result['given_names'] = api_result['authors'].get('given_names', [])
            elif field in api_result:
                result[field] = api_result[field]
        
        return result
    
    def _calculate_confidence_score(self, ref: Dict[str, Any]) -> float:
        """Calculate confidence score based on data completeness"""
        fields = ['family_names', 'given_names', 'title', 'year', 'journal']
        filled_fields = sum(1 for field in fields if ref.get(field))
        
        # Base score from GROBID
        base_score = filled_fields / len(fields)
        
        # Bonus for DOI (indicates high quality)
        if ref.get('doi'):
            base_score += 0.1
        
        # Bonus for publisher
        if ref.get('publisher'):
            base_score += 0.05
        
        return min(base_score, 1.0)
