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
                logger.info("Loaded spaCy transformer model (en_core_web_trf)")
            except OSError:
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("Loaded spaCy small model (en_core_web_sm)")
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
            # Method 1: Try pdfplumber first
            references = self._extract_with_pdfplumber(pdf_path)
            
            # Method 2: Fallback to PyMuPDF if pdfplumber fails
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
                # Extract text from all pages first
                all_text = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        all_text += text + "\n"
                
                # Now process all text together to find references across pages
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
            # Extract text from all pages first
            all_text = ""
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text()
                if text:
                    all_text += text + "\n"
            doc.close()
            
            # Now process all text together to find references across pages
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
        search_start = max(0, int(total_lines * 0.8))  # Start from 80% of document
        logger.info(f"🔍 Searching for references starting from line {search_start} (last 20% of {total_lines} lines)")
        
        # Try to find reference section in last 20%
        ref_section_start = self._find_reference_section(lines[search_start:])
        if ref_section_start is not None:
            actual_start = search_start + ref_section_start
            logger.info(f"📚 Found reference section at line {actual_start}")
            references = self._extract_references_from_section(lines[actual_start:])
        
        # Strategy 2: If not enough references found, expand to last 30%
        if len(references) < 5:
            logger.info(f"⚠️  Only found {len(references)} references, expanding search to last 30%")
            search_start = max(0, int(total_lines * 0.7))
            ref_section_start = self._find_reference_section(lines[search_start:])
            if ref_section_start is not None:
                actual_start = search_start + ref_section_start
                logger.info(f"📚 Found reference section at line {actual_start}")
                references = self._extract_references_from_section(lines[actual_start:])
        
        # Strategy 3: If still not enough, try last 1-2 pages worth of lines
        if len(references) < 5:
            logger.info(f"⚠️  Only found {len(references)} references, trying last 1-2 pages")
            # Assume ~50 lines per page, so last 100 lines
            last_pages_start = max(0, total_lines - 100)
            ref_section_start = self._find_reference_section(lines[last_pages_start:])
            if ref_section_start is not None:
                actual_start = last_pages_start + ref_section_start
                logger.info(f"📚 Found reference section at line {actual_start}")
                references = self._extract_references_from_section(lines[actual_start:])
        
        logger.info(f"📊 Reference extraction completed: {len(references)} references found")
        return references
    
    def _find_reference_section(self, lines: List[str]) -> Optional[int]:
        """Find the start of reference section in given lines"""
        ref_keywords = ['references', 'bibliography', 'works cited', 'literature cited', 'citations']
        
        for i, line in enumerate(lines):
            line_clean = line.strip().lower()
            
            # Simple keyword matching
            for keyword in ref_keywords:
                if keyword in line_clean and len(line_clean.split()) <= 4:
                    logger.info(f"🎯 Found reference section header: '{line.strip()}'")
                    return i
            
            # Check for numbered sections like "1. References"
            if re.match(r'^\d+\.?\s*(references?|bibliography|citations?)', line_clean):
                logger.info(f"🎯 Found numbered reference section: '{line.strip()}'")
                return i
        
        return None
    
    def _extract_references_from_section(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Extract individual references from reference section - SIMPLE SPLITTING ONLY"""
        # Join all lines into a single text
        full_text = "\n".join(lines)
        
        logger.info(f"🔍 Processing {len(lines)} lines from reference section")
        
        # Use simple, reliable reference splitting
        references = self._extract_references_simple(full_text)
        
        # Return simple format with just raw text
        structured_refs = []
        for i, ref_text in enumerate(references):
            structured_refs.append({
                "raw": ref_text.strip()
            })
        
        logger.info(f"📊 Extracted {len(structured_refs)} references")
        return structured_refs
    
    def _extract_references_simple(self, text: str) -> List[str]:
        """Simple, reliable reference extraction using regex patterns"""
        logger.debug("🔧 Using simple reference extraction")
        
        # More aggressive splitting approach that handles newlines properly
        references = []
        
        # Split on bracket references first (most reliable) - handle newlines properly
        # First, split on newlines to get individual lines
        lines = text.split('\n')
        
        current_ref = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this line starts with a bracket reference
            if re.match(r'^\[\d+\]', line):
                # Save previous reference
                if current_ref:
                    references.append(current_ref.strip())
                current_ref = line
            elif current_ref:
                # This is continuation of current reference
                current_ref += " " + line
            elif len(line) > 20:
                # This might be an orphaned reference
                current_ref = line
        
        # Add last reference
        if current_ref:
            references.append(current_ref.strip())
        
        # If we didn't find bracket references, try numbered references
        if len(references) < 3:
            logger.debug("⚠️  Few bracket references found, trying numbered references")
            references = self._extract_numbered_references(text)
        
        # If still not enough, try author-year format
        if len(references) < 3:
            logger.debug("⚠️  Few numbered references found, trying author-year format")
            references = self._extract_author_year_references(text)
        
        logger.debug(f"📊 Simple extraction found {len(references)} references")
        return references
    
    def _extract_numbered_references(self, text: str) -> List[str]:
        """Extract numbered references (1. Author, 2) Author, etc.) - handles newlines properly"""
        references = []
        
        # First, split on newlines to get individual lines
        lines = text.split('\n')
        
        current_ref = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this line starts a new numbered reference
            if re.match(r'^\d+[\.\)]?\s*[A-Z]', line):
                # Save previous reference
                if current_ref:
                    references.append(current_ref.strip())
                current_ref = line
            elif current_ref:
                # This is continuation of current reference
                current_ref += " " + line
            elif len(line) > 20:
                # This might be an orphaned reference
                current_ref = line
        
        # Add last reference
        if current_ref:
            references.append(current_ref.strip())
        
        return references
    
    def _extract_author_year_references(self, text: str) -> List[str]:
        """Extract author-year references (Smith, J. (2020), etc.) - handles newlines properly"""
        references = []
        
        # First, split on newlines to get individual lines
        lines = text.split('\n')
        
        current_ref = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this line starts an author-year reference
            if re.match(r'^[A-Z][a-z]+,\s*[A-Z]\.\s*\(\d{4}\)', line):
                # Save previous reference
                if current_ref:
                    references.append(current_ref.strip())
                current_ref = line
            elif current_ref:
                # This is continuation of current reference
                current_ref += " " + line
            elif len(line) > 20:
                # This might be an orphaned reference
                current_ref = line
        
        # Add last reference
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
                
                # Extract from first few pages
                for page_num in range(min(3, len(pdf.pages))):
                    page = pdf.pages[page_num]
                    text = page.extract_text()
                    
                    if text and not metadata["title"]:
                        # Try to extract title (usually first large text)
                        lines = [line.strip() for line in text.split('\n') if line.strip()]
                        if lines:
                            metadata["title"] = lines[0]
                    
                    if text and not metadata["abstract"]:
                        # Look for abstract section
                        abstract_start = text.lower().find('abstract')
                        if abstract_start != -1:
                            abstract_text = text[abstract_start:abstract_start + 1000]
                            metadata["abstract"] = abstract_text[:500]  # First 500 chars
                            
        except Exception as e:
            logger.warning(f"Metadata extraction failed: {e}")
        
        return metadata
    
    def detect_paper_type(self, pdf_path: str) -> str:
        """Detect paper type based on content"""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Check first few pages for conference/journal indicators
                text = ""
                for page in pdf.pages[:3]:
                    text += page.extract_text() or ""
                
                text_lower = text.lower()
                
                # Check for conference indicators
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
