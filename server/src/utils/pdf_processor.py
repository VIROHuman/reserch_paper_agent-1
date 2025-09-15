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
import spacy


class PDFReferenceExtractor:
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.nlp = None
        self._load_spacy_model()
        
    def _load_spacy_model(self):
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
        use_ml: bool = True
    ) -> Dict[str, Any]:
        """Process PDF and extract references using simplified approach"""
        try:
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
                "paper_type": paper_type
            }
                
        except Exception as e:
            logger.error(f"PDF processing error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "references": [],
                "reference_count": 0
            }
    
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
