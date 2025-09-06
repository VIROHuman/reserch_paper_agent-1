"""
Hybrid reference parser using format-specific + NLP + regex for maximum accuracy
"""
import re
from typing import List, Optional, Dict, Any
from loguru import logger

from ..models.schemas import ReferenceData, Author
from ..utils.nlp_parser import NLPReferenceParser
from ..utils.reference_format_detector import FormatSpecificParser


class ReferenceParser:
    """Hybrid parser for reference text using format-specific + NLP + regex"""
    
    def __init__(self):
        # Initialize format-specific parser
        self.format_parser = FormatSpecificParser()
        
        # Initialize NLP parser as fallback
        self.nlp_parser = NLPReferenceParser()
        
        # Common patterns for different reference formats (fallback)
        self.patterns = {
            'year': r'\b(19|20)\d{2}\b',
            'doi': r'10\.\d+/[^\s]+',
            'url': r'https?://[^\s]+',
            'pages': r'\b\d+(?:-\d+)?\b',
            'volume': r'vol\.?\s*(\d+)',
            'issue': r'no\.?\s*(\d+)|\((\d+)\)',
        }
    
    def parse_reference(self, reference_text: str) -> ReferenceData:
        """Parse a reference text string using format-specific + NLP + regex approach"""
        logger.info(f"🔍 HYBRID PARSING REFERENCE: {reference_text}")
        
        # Strategy 1: Try format-specific parsing first
        try:
            reference = self.format_parser.parse_reference(reference_text)
            
            # Check if we got meaningful results
            if self._is_meaningful_result(reference):
                logger.info("✅ Format-specific parsing completed successfully")
                return reference
            else:
                logger.warning("⚠️ Format-specific parsing produced poor results, trying NLP...")
        except Exception as e:
            logger.error(f"❌ Format-specific parsing failed: {e}")
        
        # Strategy 2: Fallback to NLP parsing
        try:
            reference = self.nlp_parser.parse_reference(reference_text)
            logger.info("✅ NLP parsing completed successfully")
            return reference
        except Exception as e:
            logger.error(f"❌ NLP parsing failed: {e}")
            logger.info("🔄 Falling back to regex-only parsing...")
            
            # Strategy 3: Fallback to regex-only parsing
            return self._parse_with_regex_only(reference_text)
    
    def _is_meaningful_result(self, reference: ReferenceData) -> bool:
        """Check if the parsing result is meaningful (not just empty fields)"""
        meaningful_fields = 0
        
        if reference.title and len(reference.title.strip()) > 5:
            meaningful_fields += 1
        
        if reference.authors and len(reference.authors) > 0:
            meaningful_fields += 1
        
        if reference.journal and len(reference.journal.strip()) > 2:
            meaningful_fields += 1
        
        if reference.year and 1900 <= reference.year <= 2024:
            meaningful_fields += 1
        
        # Consider it meaningful if we have at least 2 important fields
        return meaningful_fields >= 2
    
    def _parse_with_regex_only(self, reference_text: str) -> ReferenceData:
        """Fallback regex-only parsing method"""
        logger.info("🔍 REGEX-ONLY PARSING REFERENCE: {reference_text}")
        
        # Initialize empty reference data
        reference = ReferenceData(raw_text=reference_text)
        
        # Extract year
        logger.info("📅 Extracting year...")
        year_match = re.search(self.patterns['year'], reference_text)
        if year_match:
            try:
                reference.year = int(year_match.group())
                logger.info(f"✅ Year found: {reference.year}")
            except ValueError:
                logger.warning(f"❌ Invalid year: {year_match.group()}")
        else:
            logger.warning("❌ No year found")
        
        # Extract DOI
        logger.info("🔗 Extracting DOI...")
        doi_match = re.search(self.patterns['doi'], reference_text)
        if doi_match:
            reference.doi = doi_match.group()
            logger.info(f"✅ DOI found: {reference.doi}")
        else:
            logger.warning("❌ No DOI found")
        
        # Extract URL
        logger.info("🌐 Extracting URL...")
        url_match = re.search(self.patterns['url'], reference_text)
        if url_match:
            reference.url = url_match.group()
            logger.info(f"✅ URL found: {reference.url}")
        else:
            logger.warning("❌ No URL found")
        
        # Extract volume
        logger.info("📚 Extracting volume...")
        # Try multiple volume patterns
        volume_patterns = [
            r'vol\.?\s*(\d+)',  # vol. 15
            r'Volume\s*(\d+)',  # Volume 15
            r'v\.?\s*(\d+)',    # v. 15
            r'(\d+)\s*\(\d+\)', # 2020 (18) - year as volume
        ]
        
        volume_found = False
        for i, pattern in enumerate(volume_patterns):
            logger.info(f"🔍 Trying volume pattern {i+1}: {pattern}")
            volume_match = re.search(pattern, reference_text, re.IGNORECASE)
            if volume_match:
                reference.volume = volume_match.group(1)
                logger.info(f"✅ Volume found with pattern {i+1}: {reference.volume}")
                volume_found = True
                break
        
        if not volume_found:
            logger.warning("❌ No volume found")
        
        # Extract issue
        logger.info("📖 Extracting issue...")
        # Try multiple issue patterns
        issue_patterns = [
            r'(\d+)\s*\((\d+)\)', # 2020 (18) - second number as issue
            r'no\.?\s*(\d+)',   # no. 18
            r'Issue\s*(\d+)',   # Issue 18
            r'\(\s*(\d+)\s*\)', # (18)
        ]
        
        issue_found = False
        for i, pattern in enumerate(issue_patterns):
            logger.info(f"🔍 Trying issue pattern {i+1}: {pattern}")
            issue_match = re.search(pattern, reference_text, re.IGNORECASE)
            if issue_match:
                if len(issue_match.groups()) == 2:
                    # For pattern like "2020 (18)", take the second group (issue)
                    reference.issue = issue_match.group(2)
                else:
                    # For other patterns, take the first group
                    reference.issue = issue_match.group(1)
                logger.info(f"✅ Issue found with pattern {i+1}: {reference.issue}")
                issue_found = True
                break
        
        if not issue_found:
            logger.warning("❌ No issue found")
        
        # Extract pages
        logger.info("📄 Extracting pages...")
        # Try multiple page patterns
        page_patterns = [
            r'(\d+)\s*[-–]\s*(\d+)',  # 5-7 or 5–7
            r'pp\.?\s*(\d+(?:-\d+)?)', # pp. 5-7
            r'p\.?\s*(\d+(?:-\d+)?)',  # p. 5-7
            r'(\d+(?:-\d+)?)\s*$',     # 5-7 at end
        ]
        
        pages_found = False
        for i, pattern in enumerate(page_patterns):
            logger.info(f"🔍 Trying page pattern {i+1}: {pattern}")
            pages_match = re.search(pattern, reference_text, re.IGNORECASE)
            if pages_match:
                if len(pages_match.groups()) == 2:
                    # Range format: 5-7
                    reference.pages = f"{pages_match.group(1)}-{pages_match.group(2)}"
                else:
                    # Single or already formatted range
                    reference.pages = pages_match.group(1)
                logger.info(f"✅ Pages found with pattern {i+1}: {reference.pages}")
                pages_found = True
                break
        
        if not pages_found:
            logger.warning("❌ No pages found")
        
        # Try to extract title (usually the longest sentence-like text)
        logger.info("📝 Extracting title...")
        title = self._extract_title(reference_text)
        if title:
            reference.title = title
            logger.info(f"✅ Title found: {title}")
        else:
            logger.warning("❌ No title found")
        
        # Try to extract authors
        logger.info("👥 Extracting authors...")
        authors = self._extract_authors(reference_text)
        if authors:
            reference.authors = authors
            logger.info(f"✅ Authors found: {[f'{a.first_name} {a.surname}' for a in authors]}")
        else:
            logger.warning("❌ No authors found")
        
        # Try to extract journal
        logger.info("📰 Extracting journal...")
        journal = self._extract_journal(reference_text)
        if journal:
            reference.journal = journal
            logger.info(f"✅ Journal found: {journal}")
        else:
            logger.warning("❌ No journal found")
        
        logger.info(f"🎯 FINAL PARSED DATA: {reference.dict()}")
        return reference
    
    def _extract_title(self, text: str) -> Optional[str]:
        """Extract title from reference text"""
        logger.info(f"🔍 Extracting title from: {text}")
        
        # Look for text in quotes
        quoted_match = re.search(r'"([^"]+)"', text)
        if quoted_match:
            title = quoted_match.group(1)
            logger.info(f"✅ Found quoted title: {title}")
            return title
        
        # Look for text after common patterns
        patterns = [
            r'\.\s*([^.]{10,100})\.\s*(?:In|Journal|Proceedings)',
            r'\.\s*([^.]{10,100})\.\s*\d{4}',
            r'\.\s*([^.]{10,100})\.\s*[A-Z][a-z]+',
            # New pattern for the specific format: Author (Year). Title. Journal
            r'\)\.\s*([^.]{10,200})\.\s*[A-Z]',
            # Pattern for single quotes
            r"'([^']+)'",
        ]
        
        for i, pattern in enumerate(patterns):
            logger.info(f"🔍 Trying pattern {i+1}: {pattern}")
            match = re.search(pattern, text)
            if match:
                title = match.group(1).strip()
                logger.info(f"✅ Pattern {i+1} matched: {title}")
                if len(title) > 10 and len(title) < 200:  # Reasonable title length
                    logger.info(f"✅ Valid title found: {title}")
                    return title
                else:
                    logger.warning(f"❌ Title too short/long: {len(title)} chars")
            else:
                logger.info(f"❌ Pattern {i+1} no match")
        
        logger.warning("❌ No title found with any pattern")
        return None
    
    def _extract_authors(self, text: str) -> List[Author]:
        """Extract authors from reference text"""
        logger.info(f"🔍 Extracting authors from: {text}")
        authors = []
        
        # Look for author patterns
        # Pattern 1: Last, First. (Year) - e.g., "Hu, J. (2020)"
        author_pattern1 = r'([A-Z][a-z]+),\s*([A-Z][a-z.]+)\s*\((\d{4})\)'
        logger.info(f"🔍 Trying pattern 1: {author_pattern1}")
        matches1 = re.findall(author_pattern1, text)
        logger.info(f"✅ Pattern 1 matches: {matches1}")
        
        for last, first, year in matches1:
            # Clean up first name (remove trailing period)
            first_clean = first.rstrip('.')
            authors.append(Author(
                fnm=first_clean,
                surname=last,
                full_name=f"{first_clean} {last}"
            ))
            logger.info(f"✅ Added author: {first_clean} {last}")
        
        # Pattern 1.5: Last, First. (Year) - e.g., "Hu, J. (2020)" - more specific for single letter
        if not authors:
            author_pattern1_5 = r'([A-Z][a-z]+),\s*([A-Z]\.)\s*\((\d{4})\)'
            logger.info(f"🔍 Trying pattern 1.5: {author_pattern1_5}")
            matches1_5 = re.findall(author_pattern1_5, text)
            logger.info(f"✅ Pattern 1.5 matches: {matches1_5}")
            
            for last, first, year in matches1_5:
                # Clean up first name (remove trailing period)
                first_clean = first.rstrip('.')
                authors.append(Author(
                    fnm=first_clean,
                    surname=last,
                    full_name=f"{first_clean} {last}"
                ))
                logger.info(f"✅ Added author: {first_clean} {last}")
        
        # Pattern 2: First Last, First Last, ... (without year)
        if not authors:
            author_pattern2 = r'([A-Z][a-z.]+)\s+([A-Z][a-z]+)'
            logger.info(f"🔍 Trying pattern 2: {author_pattern2}")
            matches2 = re.findall(author_pattern2, text)
            logger.info(f"✅ Pattern 2 matches: {matches2}")
            
            for first, last in matches2[:3]:  # Limit to first 3 authors
                first_clean = first.rstrip('.')
                authors.append(Author(
                    fnm=first_clean,
                    surname=last,
                    full_name=f"{first_clean} {last}"
                ))
                logger.info(f"✅ Added author: {first_clean} {last}")
        
        # Pattern 3: Single letter first name - e.g., "Hu, J." (with or without year)
        if not authors:
            author_pattern3 = r'([A-Z][a-z]+),\s*([A-Z]\.)'
            logger.info(f"🔍 Trying pattern 3: {author_pattern3}")
            matches3 = re.findall(author_pattern3, text)
            logger.info(f"✅ Pattern 3 matches: {matches3}")
            
            for last, first in matches3:
                first_clean = first.rstrip('.')
                authors.append(Author(
                    fnm=first_clean,
                    surname=last,
                    full_name=f"{first_clean} {last}"
                ))
                logger.info(f"✅ Added author: {first_clean} {last}")
        
        # Pattern 4: Single letter first name with year - e.g., "Hu, J. (2020)"
        if not authors:
            author_pattern4 = r'([A-Z][a-z]+),\s*([A-Z]\.)\s*\((\d{4})\)'
            logger.info(f"🔍 Trying pattern 4: {author_pattern4}")
            matches4 = re.findall(author_pattern4, text)
            logger.info(f"✅ Pattern 4 matches: {matches4}")
            
            for last, first, year in matches4:
                first_clean = first.rstrip('.')
                authors.append(Author(
                    first_name=first_clean,
                    surname=last,
                    full_name=f"{first_clean} {last}"
                ))
                logger.info(f"✅ Added author: {first_clean} {last}")
        
        logger.info(f"🎯 Final authors: {[f'{a.first_name} {a.surname}' for a in authors]}")
        return authors
    
    def _extract_journal(self, text: str) -> Optional[str]:
        """Extract journal name from reference text"""
        logger.info(f"🔍 Extracting journal from: {text}")
        
        # Look for common journal patterns
        patterns = [
            # Pattern for "Educational Teaching Forum" format - most specific first
            r'\.\s*([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)\s*,\s*\d{4}\s*\(\d+\)',
            # Pattern for journal before year in parentheses
            r'([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)\s*,\s*\d{4}\s*\(\d+\)',
            # New pattern for the specific format: Title. Journal, Year
            r'\.\s*([A-Z][^,]+?)\s*,\s*\d{4}',
            r'In\s+([^,]+),',
            r'Journal\s+of\s+([^,]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s*,\s*\d+',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)\s*,\s*\d+',
        ]
        
        for i, pattern in enumerate(patterns):
            logger.info(f"🔍 Trying journal pattern {i+1}: {pattern}")
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                journal = match.group(1).strip()
                logger.info(f"✅ Pattern {i+1} matched: {journal}")
                if len(journal) > 3 and len(journal) < 100:  # Reasonable journal name length
                    logger.info(f"✅ Valid journal found: {journal}")
                    return journal
                else:
                    logger.warning(f"❌ Journal too short/long: {len(journal)} chars")
            else:
                logger.info(f"❌ Journal pattern {i+1} no match")
        
        logger.warning("❌ No journal found with any pattern")
        return None
