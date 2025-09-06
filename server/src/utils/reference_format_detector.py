"""
Reference Format Detector - Identifies different academic reference formats
"""
import re
from typing import Dict, List, Tuple, Optional
from loguru import logger

from ..models.schemas import ReferenceData, Author


class ReferenceFormatDetector:
    """Detects and categorizes different academic reference formats"""
    
    def __init__(self):
        self.format_patterns = {
            "format_1": {
                "pattern": r'\[\d+\]\s+[^.]+\.\s+[^.]+\.\s+[^.]+.*\d{4};\d+\(\d+\):',
                "description": "[1] Authors. Title. Journal Year;Volume(Issue):Pages",
                "confidence": 0.9
            },
            "format_2": {
                "pattern": r'\[\d+\]\s+[^,]+,\s+[^,]+,\s+[^,]+.*\d+\(\d{4}\)',
                "description": "[3] Authors, Title, Journal Volume (Year) Pages",
                "confidence": 0.9
            },
            "format_3": {
                "pattern": r'^[^[].*\.\s+[^.]+\.\s+[^.]+,\s*\d{4}',
                "description": "Authors. Title. Journal, Year",
                "confidence": 0.8
            },
            "format_4": {
                "pattern": r'[^[]+\(\d{4}\)\.\s+[^.]+\.\s+[^,]+',
                "description": "Authors (Year). Title. Journal",
                "confidence": 0.8
            },
            "format_5": {
                "pattern": r'[^[]+\.\s+"[^"]+"\.\s+[^,]+',
                "description": "Authors. \"Title.\" Journal",
                "confidence": 0.8
            },
            "format_6": {
                "pattern": r'\[\d+\]\s+[^,]+,\s+[^,]+\.\s+[^.]+\.\s+[^.]+.*\d{4}',
                "description": "[1] Authors, Title. Journal. Year",
                "confidence": 0.7
            }
        }
    
    def detect_format(self, text: str) -> Tuple[str, float]:
        """Detect the most likely format for a reference text"""
        logger.info(f"🔍 Detecting format for: {text[:100]}...")
        
        best_format = "unknown"
        best_confidence = 0.0
        
        for format_name, format_info in self.format_patterns.items():
            pattern = format_info["pattern"]
            confidence = format_info["confidence"]
            
            if re.search(pattern, text):
                logger.info(f"✅ Matched {format_name}: {format_info['description']}")
                if confidence > best_confidence:
                    best_format = format_name
                    best_confidence = confidence
        
        if best_format == "unknown":
            logger.warning("❌ No format pattern matched")
            best_confidence = 0.0
        else:
            logger.info(f"🎯 Best format: {best_format} (confidence: {best_confidence})")
        
        return best_format, best_confidence
    
    def get_format_info(self, format_name: str) -> Optional[Dict]:
        """Get information about a specific format"""
        return self.format_patterns.get(format_name)


class FormatSpecificParser:
    """Format-specific parsers for different academic reference formats"""
    
    def __init__(self):
        self.detector = ReferenceFormatDetector()
    
    def parse_reference(self, text: str) -> ReferenceData:
        """Parse reference using format-specific approach"""
        logger.info(f"🔍 FORMAT-SPECIFIC PARSING: {text}")
        
        # Detect format
        format_name, confidence = self.detector.detect_format(text)
        
        # Parse using appropriate format-specific parser
        if format_name == "format_1":
            return self._parse_format_1(text)
        elif format_name == "format_2":
            return self._parse_format_2(text)
        elif format_name == "format_3":
            return self._parse_format_3(text)
        elif format_name == "format_4":
            return self._parse_format_4(text)
        elif format_name == "format_5":
            return self._parse_format_5(text)
        elif format_name == "format_6":
            return self._parse_format_6(text)
        else:
            logger.warning("⚠️ Unknown format, using generic parsing")
            return self._parse_generic(text)
    
    def _parse_format_1(self, text: str) -> ReferenceData:
        """Parse format: [1] Authors. Title. Journal Year;Volume(Issue):Pages"""
        logger.info("📝 Parsing Format 1: [1] Authors. Title. Journal Year;Volume(Issue):Pages")
        
        reference = ReferenceData(raw_text=text)
        
        # Extract authors: [1] Author1, Author2, Author3.
        author_match = re.search(r'\[\d+\]\s+([^.]+)\.', text)
        if author_match:
            authors_text = author_match.group(1).strip()
            reference.authors = self._parse_authors_list(authors_text)
            logger.info(f"✅ Authors: {[f'{a.first_name} {a.surname}' for a in reference.authors]}")
        
        # Extract title: Authors. Title.
        title_match = re.search(r'\[\d+\]\s+[^.]+\.\s+([^.]+)\.', text)
        if title_match:
            reference.title = title_match.group(1).strip()
            logger.info(f"✅ Title: {reference.title}")
        
        # Extract journal: Title. Journal Year
        journal_match = re.search(r'\[\d+\]\s+[^.]+\.\s+[^.]+\.\s+([^.]+)\s+\d{4}', text)
        if journal_match:
            reference.journal = journal_match.group(1).strip()
            logger.info(f"✅ Journal: {reference.journal}")
        
        # Extract year
        year_match = re.search(r'(\d{4});', text)
        if year_match:
            reference.year = int(year_match.group(1))
            logger.info(f"✅ Year: {reference.year}")
        
        # Extract volume
        volume_match = re.search(r';\s*(\d+)\(', text)
        if volume_match:
            reference.volume = volume_match.group(1)
            logger.info(f"✅ Volume: {reference.volume}")
        
        # Extract issue
        issue_match = re.search(r'\(\s*(\d+)\s*\):', text)
        if issue_match:
            reference.issue = issue_match.group(1)
            logger.info(f"✅ Issue: {reference.issue}")
        
        # Extract pages
        pages_match = re.search(r':\s*(\d+(?:-\d+)?)', text)
        if pages_match:
            reference.pages = pages_match.group(1)
            logger.info(f"✅ Pages: {reference.pages}")
        
        return reference
    
    def _parse_format_2(self, text: str) -> ReferenceData:
        """Parse format: [3] Authors, Title, Journal Volume (Year) Pages"""
        logger.info("📝 Parsing Format 2: [3] Authors, Title, Journal Volume (Year) Pages")
        
        reference = ReferenceData(raw_text=text)
        
        # Extract authors: [3] Author1, Author2,
        author_match = re.search(r'\[\d+\]\s+([^,]+,\s+[^,]+),', text)
        if author_match:
            authors_text = author_match.group(1).strip()
            reference.authors = self._parse_authors_list(authors_text)
            logger.info(f"✅ Authors: {[f'{a.first_name} {a.surname}' for a in reference.authors]}")
        
        # Extract title: Authors, Title,
        title_match = re.search(r'\[\d+\]\s+[^,]+,\s+[^,]+,\s+([^,]+),', text)
        if title_match:
            reference.title = title_match.group(1).strip()
            logger.info(f"✅ Title: {reference.title}")
        
        # Extract journal: Title, Journal Volume
        journal_match = re.search(r'\[\d+\]\s+[^,]+,\s+[^,]+,\s+[^,]+,\s+([^,]+)\s+\d+', text)
        if journal_match:
            reference.journal = journal_match.group(1).strip()
            logger.info(f"✅ Journal: {reference.journal}")
        
        # Extract volume
        volume_match = re.search(r'([^,]+)\s+(\d+)\s+\(\d{4}\)', text)
        if volume_match:
            reference.volume = volume_match.group(2)
            logger.info(f"✅ Volume: {reference.volume}")
        
        # Extract year
        year_match = re.search(r'\(\s*(\d{4})\s*\)', text)
        if year_match:
            reference.year = int(year_match.group(1))
            logger.info(f"✅ Year: {reference.year}")
        
        # Extract pages
        pages_match = re.search(r'\(\d{4}\)\s+(\d+(?:-\d+)?)', text)
        if pages_match:
            reference.pages = pages_match.group(1)
            logger.info(f"✅ Pages: {reference.pages}")
        
        return reference
    
    def _parse_format_3(self, text: str) -> ReferenceData:
        """Parse format: Authors. Title. Journal, Year"""
        logger.info("📝 Parsing Format 3: Authors. Title. Journal, Year")
        
        reference = ReferenceData(raw_text=text)
        
        # Extract authors: Authors.
        author_match = re.search(r'^([^.]+)\.', text)
        if author_match:
            authors_text = author_match.group(1).strip()
            reference.authors = self._parse_authors_list(authors_text)
            logger.info(f"✅ Authors: {[f'{a.first_name} {a.surname}' for a in reference.authors]}")
        
        # Extract title: Authors. Title.
        title_match = re.search(r'^[^.]+\.\s+([^.]+)\.', text)
        if title_match:
            reference.title = title_match.group(1).strip()
            logger.info(f"✅ Title: {reference.title}")
        
        # Extract journal: Title. Journal,
        journal_match = re.search(r'^[^.]+\.\s+[^.]+\.\s+([^,]+),', text)
        if journal_match:
            reference.journal = journal_match.group(1).strip()
            logger.info(f"✅ Journal: {reference.journal}")
        
        # Extract year
        year_match = re.search(r',\s*(\d{4})', text)
        if year_match:
            reference.year = int(year_match.group(1))
            logger.info(f"✅ Year: {reference.year}")
        
        return reference
    
    def _parse_format_4(self, text: str) -> ReferenceData:
        """Parse format: Authors (Year). Title. Journal"""
        logger.info("📝 Parsing Format 4: Authors (Year). Title. Journal")
        
        reference = ReferenceData(raw_text=text)
        
        # Extract authors and year: Authors (Year)
        author_year_match = re.search(r'^([^(]+)\s+\((\d{4})\)', text)
        if author_year_match:
            authors_text = author_year_match.group(1).strip()
            reference.authors = self._parse_authors_list(authors_text)
            reference.year = int(author_year_match.group(2))
            logger.info(f"✅ Authors: {[f'{a.first_name} {a.surname}' for a in reference.authors]}")
            logger.info(f"✅ Year: {reference.year}")
        
        # Extract title: (Year). Title.
        title_match = re.search(r'\(\d{4}\)\.\s+([^.]+)\.', text)
        if title_match:
            reference.title = title_match.group(1).strip()
            logger.info(f"✅ Title: {reference.title}")
        
        # Extract journal: Title. Journal
        journal_match = re.search(r'\(\d{4}\)\.\s+[^.]+\.\s+(.+)$', text)
        if journal_match:
            reference.journal = journal_match.group(1).strip()
            logger.info(f"✅ Journal: {reference.journal}")
        
        return reference
    
    def _parse_format_5(self, text: str) -> ReferenceData:
        """Parse format: Authors. "Title." Journal"""
        logger.info("📝 Parsing Format 5: Authors. \"Title.\" Journal")
        
        reference = ReferenceData(raw_text=text)
        
        # Extract authors: Authors.
        author_match = re.search(r'^([^.]+)\.', text)
        if author_match:
            authors_text = author_match.group(1).strip()
            reference.authors = self._parse_authors_list(authors_text)
            logger.info(f"✅ Authors: {[f'{a.first_name} {a.surname}' for a in reference.authors]}")
        
        # Extract title: "Title."
        title_match = re.search(r'"([^"]+)"', text)
        if title_match:
            reference.title = title_match.group(1).strip()
            logger.info(f"✅ Title: {reference.title}")
        
        # Extract journal: "Title." Journal
        journal_match = re.search(r'"[^"]+"\.\s+(.+)$', text)
        if journal_match:
            reference.journal = journal_match.group(1).strip()
            logger.info(f"✅ Journal: {reference.journal}")
        
        return reference
    
    def _parse_format_6(self, text: str) -> ReferenceData:
        """Parse format: [1] Authors, Title. Journal. Year"""
        logger.info("📝 Parsing Format 6: [1] Authors, Title. Journal. Year")
        
        reference = ReferenceData(raw_text=text)
        
        # Extract authors: [1] Authors,
        author_match = re.search(r'\[\d+\]\s+([^,]+),', text)
        if author_match:
            authors_text = author_match.group(1).strip()
            reference.authors = self._parse_authors_list(authors_text)
            logger.info(f"✅ Authors: {[f'{a.first_name} {a.surname}' for a in reference.authors]}")
        
        # Extract title: Authors, Title.
        title_match = re.search(r'\[\d+\]\s+[^,]+,\s+([^.]+)\.', text)
        if title_match:
            reference.title = title_match.group(1).strip()
            logger.info(f"✅ Title: {reference.title}")
        
        # Extract journal: Title. Journal.
        journal_match = re.search(r'\[\d+\]\s+[^,]+,\s+[^.]+\.\s+([^.]+)\.', text)
        if journal_match:
            reference.journal = journal_match.group(1).strip()
            logger.info(f"✅ Journal: {reference.journal}")
        
        # Extract year
        year_match = re.search(r'\.\s+(\d{4})', text)
        if year_match:
            reference.year = int(year_match.group(1))
            logger.info(f"✅ Year: {reference.year}")
        
        return reference
    
    def _parse_generic(self, text: str) -> ReferenceData:
        """Generic parsing fallback"""
        logger.info("📝 Using generic parsing fallback")
        
        reference = ReferenceData(raw_text=text)
        
        # Basic year extraction
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        if year_match:
            reference.year = int(year_match.group())
        
        # Basic DOI extraction
        doi_match = re.search(r'10\.\d+/[^\s]+', text)
        if doi_match:
            reference.doi = doi_match.group()
        
        return reference
    
    def _parse_authors_list(self, authors_text: str) -> List[Author]:
        """Parse a comma-separated list of authors"""
        authors = []
        
        # Split by comma and parse each author
        author_parts = [part.strip() for part in authors_text.split(',')]
        
        for part in author_parts:
            if part:
                author = self._parse_single_author(part)
                if author:
                    authors.append(author)
        
        return authors
    
    def _parse_single_author(self, author_text: str) -> Optional[Author]:
        """Parse a single author name"""
        try:
            author_text = author_text.strip()
            if not author_text:
                return None
            
            # Handle different formats
            if ',' in author_text:
                # "Last, First" format
                parts = author_text.split(',', 1)
                surname = parts[0].strip()
                first_name = parts[1].strip().rstrip('.')
            else:
                # "First Last" format (most common for academic references)
                parts = author_text.split()
                if len(parts) >= 2:
                    first_name = parts[0]
                    surname = ' '.join(parts[1:])
                elif len(parts) == 1:
                    # Single name - treat as surname
                    surname = parts[0]
                    first_name = ""
                else:
                    return None
            
            return Author(
                fnm=first_name,
                surname=surname,
                full_name=f"{first_name} {surname}".strip()
            )
        except Exception as e:
            logger.warning(f"❌ Error parsing author '{author_text}': {e}")
            return None
