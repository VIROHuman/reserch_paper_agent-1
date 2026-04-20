"""
Simple reference parser using regex patterns
"""
import re
from typing import List, Dict, Any, Optional
from loguru import logger
from .text_normalizer import text_normalizer
from .reference_tagging import generate_tagged_output as shared_generate_tagged_output
from .safe_string_utils import is_valid_doi, looks_like_article_number


class SimpleReferenceParser:
    """Simple but powerful reference parser using regex patterns"""
    
    def __init__(self):
        logger.info("Simple reference parser initialized")
    
    def parse_reference(self, ref_text: str) -> Dict[str, Any]:
        """Parse reference text and extract key fields"""
        result = {
            "family_names": [],
            "given_names": [],
            "year": None,
            "title": None,
            "journal": None,
            "doi": None,
            "pages": None,
            "missing_fields": []
        }
        
        # Clean and normalize the text
        text = text_normalizer.normalize_text(ref_text, preserve_case=True).strip()
        
        # Extract year
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        if year_match:
            result["year"] = year_match.group()
        
        # Extract DOI with STRICT VALIDATION
        doi_match = re.search(r'10\.\d+/[^\s,)]+', text)
        if doi_match:
            candidate_doi = doi_match.group()
            # STRICT VALIDATION: Check if it's a valid DOI
            if is_valid_doi(candidate_doi):
                result["doi"] = candidate_doi
            elif looks_like_article_number(candidate_doi):
                # Mislabeled as DOI but is actually article number
                logger.info(f"Simple parser detected '{candidate_doi}' as DOI but it's an article number, storing as article_number")
                result["article_number"] = candidate_doi
                result["doi"] = None
            else:
                logger.warning(f"Simple parser detected invalid DOI format: '{candidate_doi}', rejecting")
                result["doi"] = None
        
        # Extract pages (various formats)
        pages_patterns = [
            r'pp\.?\s*(\d+(?:[-–]\d+)?)',  # pp. 123-456
            r'p\.?\s*(\d+(?:[-–]\d+)?)',   # p. 123-456
            r'(\d+(?:[-–]\d+)?)\s*$',      # 123-456 at end
            r'(\d+(?:[-–]\d+)?)(?=\s*[,\.])',  # 123-456 before comma/period
        ]
        
        for pattern in pages_patterns:
            pages_match = re.search(pattern, text)
            if pages_match:
                result["pages"] = pages_match.group(1)
                break
        
        # Extract authors (multiple patterns)
        authors = self._extract_authors(text)
        result["family_names"] = [author["surname"] for author in authors]
        result["given_names"] = [author["given"] for author in authors]
        
        # Extract title (between quotes or after authors)
        title = self._extract_title(text, authors)
        result["title"] = title
        
        # Extract journal/conference
        journal = self._extract_journal(text)
        result["journal"] = journal
        
        # Determine missing fields
        result["missing_fields"] = self._get_missing_fields(result)
        
        return result
    
    def _extract_authors(self, text: str) -> List[Dict[str, str]]:
        """Very conservative author extraction - only detect clear author patterns"""
        authors = []
        
        # Strategy 1: Very strict academic format at the beginning of reference
        pattern1 = r'^(?:^|\s)([A-Z][a-z]{3,}),\s*([A-Z]\.(?:\s*[A-Z]\.)*)(?=\s)'
        matches1 = re.findall(pattern1, text)
        
        for surname, given in matches1:
            # Very strict validation
            if self._is_definitely_author(surname, given, text):
                authors.append({
                    "surname": surname.strip(),
                    "given": given.strip().replace('.', '').replace(' ', '')
                })
        
        # Strategy 2: Look for author patterns with year context (very conservative)
        if not authors:
            # Pattern: "Author, F. (Year)" or "Author, F. Year" - very specific
            pattern2 = r'([A-Z][a-z]{3,}),\s*([A-Z]\.)\s*[\(]?(19|20)\d{2}'
            matches2 = re.findall(pattern2, text)
            
            for surname, given, year in matches2:
                if self._is_definitely_author(surname, given, text):
                    authors.append({
                        "surname": surname.strip(),
                        "given": given.strip().replace('.', '')
                    })
        
        # Strategy 3: Look for multiple authors pattern (very conservative)
        if not authors:
            # Pattern: "Author1, F., Author2, F." - must have multiple authors
            pattern3 = r'([A-Z][a-z]{3,}),\s*([A-Z]\.)(?:\s*[,.]?\s*([A-Z][a-z]{3,}),\s*([A-Z]\.))'
            match3 = re.search(pattern3, text)
            if match3:
                surname1, given1, surname2, given2 = match3.groups()
                if self._is_definitely_author(surname1, given1, text):
                    authors.append({
                        "surname": surname1.strip(),
                        "given": given1.strip().replace('.', '')
                    })
                if surname2 and given2 and self._is_definitely_author(surname2, given2, text):
                    authors.append({
                        "surname": surname2.strip(),
                        "given": given2.strip().replace('.', '')
                    })
        
        # Final strict validation: remove any questionable authors
        authors = self._filter_title_words(authors, text)
        
        # Only return authors if we're confident they are real authors
        return authors[:3] if len(authors) > 0 and self._has_good_author_confidence(authors, text) else []
    
    def _is_definitely_author(self, surname: str, given: str, full_text: str) -> bool:
        """Very strict validation - only accept if we're confident it's an author"""
        import re
        
        # Basic length requirements
        if len(surname) < 4 or len(given.strip('.')) < 1:
            return False
        
        # Must not be common English words or technical terms
        common_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 
            'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 
            'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'way', 'who',
            'mobile', 'cloud', 'computing', 'model', 'big', 'analysis', 'healthcare',
            'applications', 'internet', 'things', 'comprehensive', 'survey',
            'design', 'implementation', 'various', 'datapath', 'architectures',
            'lightweight', 'cipher', 'fpga', 'frontiers', 'information', 'technology',
            'electronic', 'engineering', 'student', 'centered', 'teaching',
            'studying', 'community', 'exploration', 'index', 'reconstructing',
            'evaluation', 'standard', 'universities', 'educational', 'forum',
            'blockchain', 'machine', 'learning', 'artificial', 'intelligence',
            'deep', 'neural', 'network', 'algorithm', 'framework', 'platform',
            'system', 'software', 'hardware', 'database', 'server', 'client',
            'interface', 'protocol', 'architecture', 'component', 'module',
            'service', 'application', 'program', 'code', 'function', 'method'
        }
        
        if surname.lower() in common_words:
            return False
        
        # Must not appear in title-like context
        if self._appears_in_title_context(surname, full_text):
            return False
        
        # Must be a real surname (not a made-up technical term)
        if not self._looks_like_real_surname(surname):
            return False
        
        return True
    
    def _appears_in_title_context(self, surname: str, title_section: str) -> bool:
        """Check if a surname appears in title-like context"""
        import re
        
        # Look for patterns where the surname is part of a title phrase
        title_context_patterns = [
            r'[A-Z][a-z]*\s+' + re.escape(surname) + r'\s+[A-Z][a-z]*',  # Word Surname Word
            r'[A-Z][a-z]*\s+' + re.escape(surname) + r'[,:]',  # Word Surname, or Word Surname:
            r':\s*[A-Z][a-z]*\s+' + re.escape(surname),  # : Word Surname
            r'[A-Z][a-z]*\s+' + re.escape(surname) + r'\s+[A-Z][a-z]*\s+[A-Z]',  # Word Surname Word Word
        ]
        
        for pattern in title_context_patterns:
            if re.search(pattern, title_section, re.IGNORECASE):
                return True
        
        return False
    
    def _looks_like_real_surname(self, surname: str) -> bool:
        """Check if a word looks like a real surname"""
        # Real surnames typically:
        # 1. Are not all uppercase (unless very short)
        # 2. Don't contain numbers
        # 3. Don't contain special characters (except hyphens in some cases)
        # 4. Are not common technical acronyms
        
        if surname.isupper() and len(surname) > 3:
            return False
        
        if any(char.isdigit() for char in surname):
            return False
        
        if any(char in surname for char in '.,!@#$%^&*()+=[]{}|\\:";\'<>?/~`'):
            return False
        
        # Check for common surname patterns
        surname_endings = ['son', 'sen', 'sson', 'ez', 'ovich', 'evich', 'ski', 'ska', 'ova', 'eva', 'ko', 'chuk', 'uk', 'ak', 'ik', 'yk']
        
        # If it ends in a common surname suffix, it's more likely to be real
        if any(surname.lower().endswith(ending) for ending in surname_endings):
            return True
        
        # If it's a reasonable length and doesn't look technical, it might be real
        return len(surname) >= 4 and len(surname) <= 15
    
    def _has_good_author_confidence(self, authors: List[Dict[str, str]], text: str) -> bool:
        """Check if we have good confidence that these are real authors"""
        if not authors:
            return False
        
        # If we have multiple authors, that's a good sign
        if len(authors) > 1:
            return True
        
        # For single author, need additional evidence
        if len(authors) == 1:
            author = authors[0]
            surname = author['surname']
            
            # Check if surname appears in author-like context
            author_context_patterns = [
                rf'{re.escape(surname)},\s*[A-Z]\.\s+et\s+al\.',
                rf'{re.escape(surname)},\s*[A-Z]\.\s+and',
                rf'{re.escape(surname)},\s*[A-Z]\.\s*[,.]?\s*[A-Z][a-z]{{3,}},',
            ]
            
            import re
            for pattern in author_context_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
            
            # If surname is at the very beginning of the reference, that's a good sign
            if text.strip().lower().startswith(surname.lower()):
                return True
        
        return False
    
    def _filter_title_words(self, authors: List[Dict[str, str]], full_text: str) -> List[Dict[str, str]]:
        """Filter out author candidates that are likely title words"""
        filtered_authors = []
        
        # Extract potential title section (before year or journal indicators)
        year_match = re.search(r'\b(19|20)\d{2}\b', full_text)
        title_section = full_text[:year_match.start()] if year_match else full_text
        
        for author in authors:
            surname = author['surname']
            
            # Skip if surname appears in title section with title-like context
            if self._appears_in_title_context(surname, title_section):
                continue
                
            filtered_authors.append(author)
        
        return filtered_authors
    
    def _extract_title(self, text: str, authors: List[Dict[str, str]]) -> Optional[str]:
        """Extract title from reference text"""
        # Remove author patterns first
        clean_text = text
        
        # Remove author patterns
        for author in authors:
            # Remove "Surname, Given" pattern
            author_pattern = f"{author['surname']},?\\s*{author['given']}"
            clean_text = re.sub(author_pattern, '', clean_text, flags=re.IGNORECASE)
        
        # Look for title in quotes
        title_in_quotes = re.search(r'"([^"]+)"', clean_text)
        if title_in_quotes:
            return title_in_quotes.group(1).strip()
        
        # Look for title after authors (before year)
        # Split by year and take the part that looks like title
        year_pos = text.find(authors[0]["surname"]) if authors else 0
        if year_pos > 0:
            # Find text between authors and year
            year_match = re.search(r'\b(19|20)\d{2}\b', text)
            if year_match:
                start_pos = year_pos + len(authors[0]["surname"])
                end_pos = year_match.start()
                potential_title = text[start_pos:end_pos].strip()
                
                # Clean up the potential title
                potential_title = re.sub(r'^[.,\s]+', '', potential_title)
                potential_title = re.sub(r'[.,\s]+$', '', potential_title)
                
                # Check if it looks like a title (has reasonable length and words)
                if len(potential_title) > 10 and len(potential_title.split()) > 2:
                    return potential_title
        
        return None
    
    def _extract_journal(self, text: str) -> Optional[str]:
        """Extract journal/conference name"""
        # Look for italicized text (often journal names)
        # This is a simplified approach - in real PDFs, formatting info is lost
        
        # Common journal patterns
        journal_patterns = [
            r'In:\s*([^,]+)',  # "In: Conference Name"
            r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+\d{4}',  # Journal Name 2020
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\.\s*\d{4}',  # Journal Name. 2020
        ]
        
        for pattern in journal_patterns:
            match = re.search(pattern, text)
            if match:
                journal = match.group(1).strip()
                # Clean up
                journal = re.sub(r'[.,;]$', '', journal)
                if len(journal) > 3:  # Reasonable journal name length
                    return journal
        
        return None
    
    def _get_missing_fields(self, result: Dict[str, Any]) -> List[str]:
        """Determine which required fields are missing"""
        missing = []
        required_fields = ["family_names", "year", "title"]
        
        for field in required_fields:
            if not result.get(field) or (isinstance(result[field], list) and len(result[field]) == 0):
                missing.append(field)
        
        return missing
    
    def generate_tagged_output(self, parsed_ref: Dict[str, Any], index: int) -> str:
        """
        Generate XML tagged output matching the bibitem format.
        Uses shared tagging utility to ensure consistency across all parsers.
        """
        return shared_generate_tagged_output(parsed_ref, index)
    
    def _extract_volume_issue_info(self, parsed_ref: Dict[str, Any]) -> Dict[str, str]:
        """Extract volume and issue information from parsed reference"""
        volume_info = {"volume": "", "issue": ""}
        
        # Try to extract from journal field
        journal_text = parsed_ref.get("journal", "")
        if journal_text:
            import re
            
            # Look for volume patterns: vol. 4, vol 4, volume 4, v. 4
            volume_patterns = [
                r'vol\.?\s*(\d+)',
                r'volume\s*(\d+)',
                r'v\.?\s*(\d+)',
                r'vol\s*(\d+)'
            ]
            
            for pattern in volume_patterns:
                match = re.search(pattern, journal_text, re.IGNORECASE)
                if match:
                    volume_info["volume"] = match.group(1)
                    break
            
            # Look for issue patterns: no. 18, issue 18, n. 18
            issue_patterns = [
                r'no\.?\s*(\d+)',
                r'issue\s*(\d+)',
                r'n\.?\s*(\d+)',
                r'number\s*(\d+)'
            ]
            
            for pattern in issue_patterns:
                match = re.search(pattern, journal_text, re.IGNORECASE)
                if match:
                    volume_info["issue"] = match.group(1)
                    break
        
        # Also check if there are separate volume/issue fields
        if parsed_ref.get("volume"):
            volume_info["volume"] = str(parsed_ref["volume"])
        if parsed_ref.get("issue"):
            volume_info["issue"] = str(parsed_ref["issue"])
            
        return volume_info
