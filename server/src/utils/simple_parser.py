"""
Simple reference parser using regex patterns
"""
import re
from typing import List, Dict, Any, Optional
from loguru import logger


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
        
        # Clean the text
        text = ref_text.strip()
        
        # Extract year
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        if year_match:
            result["year"] = year_match.group()
        
        # Extract DOI
        doi_match = re.search(r'10\.\d+/[^\s,)]+', text)
        if doi_match:
            result["doi"] = doi_match.group()
        
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
        """Extract author names from reference text with improved patterns"""
        authors = []
        
        # More specific patterns that require proper author context
        # Pattern 1: Last, F. or Last, F.M. format - must be at start or after proper context
        pattern1 = r'(?:^|\s)([A-Z][a-z]{2,}),\s*([A-Z]\.(?:\s*[A-Z]\.)*)(?=\s|$)'
        matches1 = re.findall(pattern1, text)
        
        for surname, given in matches1:
            # Validate that this looks like a real author name
            if self._is_valid_author_name(surname, given, text):
                authors.append({
                    "surname": surname.strip(),
                    "given": given.strip().replace('.', '').replace(' ', '')
                })
        
        # Pattern 2: F. Last format - more specific context
        if not authors:
            pattern2 = r'(?:^|\s)([A-Z]\.(?:\s*[A-Z]\.)*)\s+([A-Z][a-z]{2,})(?=\s|$)'
            matches2 = re.findall(pattern2, text)
            
            for given, surname in matches2:
                if self._is_valid_author_name(surname, given, text):
                    authors.append({
                        "surname": surname.strip(),
                        "given": given.strip().replace('.', '').replace(' ', '')
                    })
        
        # Pattern 3: Handle multiple authors separated by semicolons or "and"
        if len(authors) > 1:
            # Check for "et al." pattern
            if 'et al' in text.lower():
                # Keep only first few authors
                authors = authors[:3]
        
        # Final validation: remove any authors that appear to be from the title
        authors = self._filter_title_words(authors, text)
        
        return authors
    
    def _is_valid_author_name(self, surname: str, given: str, full_text: str) -> bool:
        """Validate if a name candidate is actually an author name"""
        # Check minimum length requirements
        if len(surname) < 3 or len(given.strip('.')) < 1:
            return False
        
        # Common title words that should not be author names
        title_words = {
            'health', 'care', 'blockchain', 'revolution', 'sweeps', 'offering',
            'possibility', 'much', 'needed', 'data', 'solution', 'reaction',
            'system', 'technology', 'digital', 'innovation', 'development',
            'research', 'study', 'analysis', 'approach', 'method', 'model',
            'framework', 'algorithm', 'network', 'platform', 'application'
        }
        
        # Don't accept common title words as surnames
        if surname.lower() in title_words:
            return False
        
        # Check if the surname appears in a title-like context
        # Look for patterns like "Title, Journal" where the surname might be part of title
        title_patterns = [
            r'[A-Z][^,]*' + re.escape(surname) + r'[^,]*,',  # Title, surname, something
            r'[A-Z][^.]*' + re.escape(surname) + r'[^.]*\.',  # Title. surname. something
        ]
        
        for pattern in title_patterns:
            if re.search(pattern, full_text, re.IGNORECASE):
                return False
        
        return True
    
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
    
    def _appears_in_title_context(self, surname: str, title_section: str) -> bool:
        """Check if a surname appears in title-like context"""
        # Look for patterns where the surname is part of a title phrase
        title_context_patterns = [
            r'[A-Z][a-z]*\s+' + re.escape(surname) + r'\s+[A-Z][a-z]*',  # Word Surname Word
            r'[A-Z][a-z]*\s+' + re.escape(surname) + r'[,:]',  # Word Surname, or Word Surname:
        ]
        
        for pattern in title_context_patterns:
            if re.search(pattern, title_section):
                return True
        
        return False
    
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
        
        # Enhanced journal patterns
        journal_patterns = [
            r'In:\s*([^,.]{5,})',  # "In: Conference Name"
            r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*[,.]\s*\d{4}',  # Journal Name, 2020
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\.\s*\d{4}',  # Journal Name. 2020
            r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*vol',  # Journal Name, vol
            r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*pp',  # Journal Name, pp
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\(\d{4}\)',  # Journal Name (2020)
        ]
        
        for pattern in journal_patterns:
            match = re.search(pattern, text)
            if match:
                journal = match.group(1).strip()
                # Clean up common artifacts
                journal = re.sub(r'^[,.\s]+', '', journal)
                journal = re.sub(r'[,.\s]+$', '', journal)
                if len(journal) > 5 and not journal.lower().startswith(('vol', 'pp', 'p.')):
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
        """Generate XML-like tagged output"""
        ref_id = f"ref{index + 1}"
        
        # Build authors section
        authors_xml = "<authors>"
        for i, (family, given) in enumerate(zip(parsed_ref["family_names"], parsed_ref["given_names"])):
            authors_xml += f'<author><fnm>{given}</fnm><surname>{family}</surname></author>'
        authors_xml += "</authors>"
        
        # Build title section
        title_xml = ""
        if parsed_ref["title"]:
            title_xml = f'<title><maintitle>{parsed_ref["title"]}</maintitle></title>'
        
        # Build year section
        year_xml = ""
        if parsed_ref["year"]:
            year_xml = f'<date>{parsed_ref["year"]}</date>'
        
        # Build journal section
        journal_xml = ""
        if parsed_ref["journal"]:
            journal_xml = f'<host><issue><series><title><maintitle>{parsed_ref["journal"]}</maintitle></title></series>{year_xml}</issue></host>'
        
        # Build pages section
        pages_xml = ""
        if parsed_ref["pages"]:
            if '-' in parsed_ref["pages"] or '–' in parsed_ref["pages"]:
                page_parts = re.split(r'[-–]', parsed_ref["pages"])
                if len(page_parts) == 2:
                    pages_xml = f'<pages><fpage>{page_parts[0]}</fpage><lpage>{page_parts[1]}</lpage></pages>'
                else:
                    pages_xml = f'<pages>{parsed_ref["pages"]}</pages>'
            else:
                pages_xml = f'<pages><fpage>{parsed_ref["pages"]}</fpage></pages>'
        
        # Build DOI section
        doi_xml = ""
        if parsed_ref["doi"]:
            doi_xml = f'<comment>DOI: {parsed_ref["doi"]}</comment>'
        
        # Create label
        label = ""
        if parsed_ref["family_names"]:
            if len(parsed_ref["family_names"]) == 1:
                label = f"{parsed_ref['family_names'][0]}, {parsed_ref['year']}"
            else:
                label = f"{parsed_ref['family_names'][0]} et al., {parsed_ref['year']}"
        
        # Combine everything
        tagged_output = f'<reference id="{ref_id}">'
        if label:
            tagged_output += f'<label>{label}</label>'
        tagged_output += authors_xml
        tagged_output += title_xml
        tagged_output += journal_xml
        tagged_output += pages_xml
        tagged_output += doi_xml
        tagged_output += '</reference>'
        
        return tagged_output
