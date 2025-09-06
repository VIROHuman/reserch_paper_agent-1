"""
Simplified PDF processing for academic paper reference extraction
"""
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


class PDFReferenceExtractor:
    """Simplified PDF reference extractor using pdfplumber and PyMuPDF"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.reference_patterns = [
            r'^\d+\.\s+(.+?)(?=\n\d+\.|\n\n|$)',  # Numbered references
            r'^\[[\d,\-\s]+\]\s+(.+?)(?=\n\[|\n\n|$)',  # [1,2,3] format
            r'^\([^)]+\)\s+(.+?)(?=\n\(|\n\n|$)',  # (Author, Year) format
        ]
    
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
    
    def _extract_references_from_pdf(self, pdf_path: str) -> List[str]:
        """Extract references from PDF using multiple methods"""
        references = []
        
        try:
            # Method 1: Try pdfplumber first
            references = self._extract_with_pdfplumber(pdf_path)
            
            # Method 2: Fallback to PyMuPDF if pdfplumber fails
            if not references:
                references = self._extract_with_pymupdf(pdf_path)
            
            # Clean and filter references
            references = self._clean_references(references)
            
        except Exception as e:
            logger.error(f"Error extracting references: {e}")
        
        return references
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> List[str]:
        """Extract references using pdfplumber"""
        references = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        page_refs = self._extract_references_from_text(text)
                        references.extend(page_refs)
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")
        
        return references
    
    def _extract_with_pymupdf(self, pdf_path: str) -> List[str]:
        """Extract references using PyMuPDF"""
        references = []
        
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text()
                if text:
                    page_refs = self._extract_references_from_text(text)
                    references.extend(page_refs)
            doc.close()
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {e}")
        
        return references
    
    def _extract_references_from_text(self, text: str) -> List[str]:
        """Extract references from text using regex patterns"""
        references = []
        
        # Split text into lines
        lines = text.split('\n')
        
        # Look for reference sections with better detection
        ref_section = False
        current_ref = ""
        ref_section_keywords = ['references', 'bibliography', 'works cited', 'literature cited']
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Better reference section detection
            if self._is_reference_section_header(line, ref_section_keywords):
                ref_section = True
                logger.info(f"Found reference section at line {i}: {line}")
                continue
            
            # Check if we've moved to a new section (end of references)
            if ref_section and self._is_new_section_header(line):
                ref_section = False
                logger.info(f"End of reference section at line {i}: {line}")
                continue
            
            if ref_section and line:
                # Check if line starts a new reference
                if self._is_reference_start(line):
                    if current_ref:
                        references.append(current_ref.strip())
                    current_ref = line
                elif current_ref and line:
                    # Continue building current reference
                    current_ref += " " + line
                elif not current_ref and line and len(line) > 10:
                    # Potential orphaned reference line (fallback)
                    current_ref = line
        
        # Add last reference
        if current_ref:
            references.append(current_ref.strip())
        
        return references
    
    def _is_reference_section_header(self, line: str, keywords: List[str]) -> bool:
        """Check if line is a reference section header"""
        line_lower = line.lower().strip()
        
        # Must be a standalone header (not part of a sentence)
        if len(line.split()) > 5:  # Too long to be a header
            return False
            
        # Check for exact keyword matches
        for keyword in keywords:
            if line_lower == keyword or line_lower == keyword.title():
                return True
            # Check for numbered headers like "1. References"
            if re.match(rf'^\d+\.?\s*{re.escape(keyword)}$', line_lower):
                return True
        
        return False
    
    def _is_new_section_header(self, line: str) -> bool:
        """Check if line starts a new section (end of references)"""
        line_lower = line.lower().strip()
        
        # Common section headers that come after references
        new_section_keywords = [
            'appendix', 'appendices', 'acknowledgments', 'acknowledgements',
            'author contributions', 'conflicts of interest', 'funding',
            'data availability', 'supplementary', 'supplementary material'
        ]
        
        # Check for numbered sections
        if re.match(r'^\d+\.?\s+[A-Z]', line):
            return True
            
        # Check for keyword matches
        for keyword in new_section_keywords:
            if keyword in line_lower and len(line.split()) <= 4:
                return True
        
        return False
    
    def _is_reference_start(self, line: str) -> bool:
        """Check if line starts a new reference"""
        # Check for numbered references (1. Author Name...)
        if re.match(r'^\d+\.\s+[A-Z]', line):
            return True
        
        # Check for bracketed references ([1] Author Name...)
        if re.match(r'^\[\d+\]\s+[A-Z]', line):
            return True
        
        # Check for author-year format (Author, A. (2020)...)
        if re.match(r'^[A-Z][a-z]+,\s*[A-Z]\.\s*\(\d{4}\)', line):
            return True
        
        # Check for simple numbered format (1 Author Name...)
        if re.match(r'^\d+\s+[A-Z]', line):
            return True
        
        return False
    
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
    
    def _clean_references(self, references: List[str]) -> List[str]:
        """Clean and filter extracted references"""
        cleaned = []
        
        for ref in references:
            ref = ref.strip()
            
            # Skip very short references
            if len(ref) < 20:
                continue
                
            # Skip references that look like headers
            if ref.lower() in ['references', 'bibliography', 'works cited']:
                continue
                
            # Skip references that are just numbers
            if ref.isdigit():
                continue
                
            cleaned.append(ref)
        
        return cleaned
    
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
