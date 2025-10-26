"""
Fixed enhanced reference parser that correctly handles the reference format
"""
import asyncio
import re
from typing import List, Dict, Any, Optional
from loguru import logger

from .simple_parser import SimpleReferenceParser
from .ner_reference_parser import NERReferenceParser
from .api_clients import CrossRefClient, OpenAlexClient, SemanticScholarClient, DOAJClient
from .smart_api_strategy import SmartAPIStrategy
from .doi_metadata_extractor import DOIMetadataExtractor, DOIMetadataConflictDetector
from .flagging_system import ReferenceFlaggingSystem


class EnhancedReferenceParser:
    """Enhanced parser that combines local parsing with API client enrichment"""
    
    def __init__(self):
        # Initialize NER parser as the primary parsing method
        self.ner_parser = NERReferenceParser(
            confidence_threshold=0.1,  # Lowered to catch more entities
            enable_entity_disambiguation=True,
            enable_confidence_weighting=True,
            use_llm_primary=False  # Disable LLM for stability - use NER only
        )
        
        # Keep simple parser as fallback
        self.simple_parser = SimpleReferenceParser()
        
        # Initialize smart API strategy
        self.smart_api = SmartAPIStrategy()
        
        # Keep individual clients for backward compatibility
        self.crossref_client = self.smart_api.crossref_client
        self.openalex_client = self.smart_api.openalex_client
        self.semantic_client = self.smart_api.semantic_client
        self.doaj_client = self.smart_api.doaj_client
        
        # Initialize DOI metadata extractor and conflict detector
        self.doi_extractor = DOIMetadataExtractor()
        self.conflict_detector = DOIMetadataConflictDetector()
        
        # Initialize flagging system
        self.flagging_system = ReferenceFlaggingSystem()
        
        logger.info("Enhanced reference parser initialized with NER as primary parser, Smart API Strategy, DOI extraction, and Flagging System")
    
    def _convert_ner_result_to_enhanced_format(self, ner_result: dict) -> Dict[str, Any]:
        """
        Convert NER parser result to the format expected by enhanced parser
        """
        try:
            # Extract authors with robust error handling
            authors = ner_result.get('authors', [])
            logger.info(f"[DEBUG] Converting NER result - authors type: {type(authors)}, count: {len(authors)}")
            if len(authors) > 0:
                logger.info(f"[DEBUG] First author (if exists): {authors[0]}")
                logger.info(f"[DEBUG] Authors full list: {authors}")
            family_names = []
            given_names = []
            
            for author in authors:
                logger.info(f"[DEBUG] Processing author - type: {type(author)}, author keys: {author.keys() if isinstance(author, dict) else 'N/A'}")
                try:
                    if isinstance(author, dict):
                        # Dictionary format - check both 'fnm' (alias) and 'first_name'
                        # Also check for both 'surname' and 'family_name'
                        surname = author.get('surname') or author.get('family_name') or ""
                        first_name = author.get('first_name') or author.get('fnm') or ""
                        
                        # Only add if surname exists and is not 'None' string
                        if surname and str(surname).lower() != 'none' and surname.strip():
                            family_names.append(surname)
                        if first_name and str(first_name).lower() != 'none' and first_name.strip():
                            given_names.append(first_name)
                    elif isinstance(author, str):
                        # String format
                        family_names.append(author)
                    elif hasattr(author, 'surname'):
                        # Pydantic Author object
                        if author.surname and author.surname != 'None':
                            family_names.append(author.surname)
                        if author.first_name and author.first_name != 'None':
                            given_names.append(author.first_name)
                except Exception as author_error:
                    logger.warning(f"Error processing author: {author_error}, skipping author")
                    continue
            
            return {
                "family_names": family_names,
                "given_names": given_names,
                "year": ner_result.get('year'),
                "title": ner_result.get('title'),
                "journal": ner_result.get('journal'),
                "volume": ner_result.get('volume'),
                "issue": ner_result.get('issue'),
                "pages": ner_result.get('pages'),
                "doi": ner_result.get('doi'),
                "url": ner_result.get('url'),
                "publisher": ner_result.get('publisher'),
                "abstract": ner_result.get('abstract'),
                "publication_type": ner_result.get('publication_type'),
                "raw_text": ner_result.get('raw_text', ''),
                "missing_fields": ner_result.get('missing_fields', []),
                "quality_score": ner_result.get('quality_score', 0.0),
                "confidence_scores": ner_result.get('confidence_scores', {}),
                "parser_used": "NER_MODEL"
            }
        except Exception as e:
            logger.error(f"Error converting NER result: {e}")
            # Return a basic structure
            return {
                "family_names": [],
                "given_names": [],
                "year": None,
                "title": None,
                "journal": None,
                "volume": None,
                "issue": None,
                "pages": None,
                "doi": None,
                "url": None,
                "publisher": None,
                "abstract": None,
                "publication_type": None,
                "raw_text": '',
                "missing_fields": ['title', 'authors', 'year'],
                "quality_score": 0.0,
                "confidence_scores": {},
                "parser_used": "NER_MODEL_ERROR"
            }
    
    async def _enhanced_initial_parsing(self, ref_text: str) -> Dict[str, Any]:
        """Enhanced initial parsing using NER as primary method"""
        try:
            # Use NER parser as the primary parsing method
            logger.info(f"🤖 Using NER parser for initial parsing: {ref_text[:100]}...")
            parsed_ref = self.ner_parser.parse_reference_to_dict(ref_text)
            
            # DEBUG: Check what we got from NER parser
            logger.info(f"[DEBUG] NER parser returned: authors count={len(parsed_ref.get('authors', [])) if parsed_ref else 0}")
            if parsed_ref and len(parsed_ref.get('authors', [])) > 0:
                logger.info(f"[DEBUG] First author from NER: {parsed_ref['authors'][0]}")
            
            # DEBUG: Check all keys in parsed_ref
            if parsed_ref:
                logger.info(f"[DEBUG] Keys in parsed_ref: {parsed_ref.keys()}")
                logger.info(f"[DEBUG] Full parsed_ref structure: {parsed_ref}")
            
            # Check if NER parser returned None
            if parsed_ref is None:
                logger.warning("NER parser returned None, using simple parser fallback")
                return self.simple_parser.parse_reference(ref_text)
            
            # Convert NER result to the expected format for further processing
            parsed_ref = self._convert_ner_result_to_enhanced_format(parsed_ref)
            logger.info(f"✅ NER parsing completed - Title: {parsed_ref.get('title', 'None')[:50]}..., Authors: {len(parsed_ref.get('family_names', []))}, Year: {parsed_ref.get('year', 'None')}")
            
            # Only apply fallback enhancements if NER results are insufficient
            if not parsed_ref.get("title") or len(parsed_ref.get("title", "")) < 10:
                logger.info("⚠️ NER didn't extract title, trying fallback methods")
                enhanced_title = self._extract_title_enhanced(ref_text)
                if enhanced_title and len(enhanced_title) > 10:
                    parsed_ref["title"] = enhanced_title
            
            if not parsed_ref.get("journal") or len(parsed_ref.get("journal", "")) < 5:
                logger.info("⚠️ NER didn't extract journal, trying fallback methods")
                parsed_ref["journal"] = self._extract_journal_enhanced(ref_text)
            
            if not parsed_ref.get("family_names"):
                logger.info("⚠️ NER didn't extract authors, trying fallback methods")
                authors = self._extract_authors_enhanced(ref_text)
                parsed_ref["family_names"] = [author["surname"] for author in authors]
                parsed_ref["given_names"] = [author["given"] for author in authors]
            
            if not parsed_ref.get("year"):
                logger.info("⚠️ NER didn't extract year, trying fallback methods")
                parsed_ref["year"] = self._extract_year_enhanced(ref_text)
            
            if not parsed_ref.get("publisher"):
                logger.info("⚠️ NER didn't extract publisher, trying fallback methods")
                parsed_ref["publisher"] = self._extract_publisher(ref_text)
            
            # Try to extract URL if missing
            if not parsed_ref.get("url"):
                parsed_ref["url"] = self._extract_url(ref_text)
            
            # Try to extract DOI if missing
            if not parsed_ref.get("doi"):
                parsed_ref["doi"] = self._extract_doi_enhanced(ref_text)
            
            # Try to extract pages if missing
            if not parsed_ref.get("pages"):
                parsed_ref["pages"] = self._extract_pages_enhanced(ref_text)
            
            # Try to extract abstract if missing
            if not parsed_ref.get("abstract"):
                parsed_ref["abstract"] = self._extract_abstract_enhanced(ref_text)
            
            return parsed_ref
            
        except Exception as e:
            logger.error(f"Enhanced initial parsing error: {str(e)}")
            # Fallback to simple parser
            try:
                fallback_result = self.simple_parser.parse_reference(ref_text)
                if fallback_result is None:
                    logger.error("Simple parser also returned None, creating empty result")
                    return {
                        "family_names": [],
                        "given_names": [],
                        "year": None,
                        "title": None,
                        "journal": None,
                        "parser_used": "FALLBACK_EMPTY"
                    }
                return fallback_result
            except Exception as fallback_error:
                logger.error(f"Fallback parser also failed: {str(fallback_error)}")
                return {
                    "family_names": [],
                    "given_names": [],
                    "year": None,
                    "title": None,
                    "journal": None,
                    "parser_used": "FALLBACK_ERROR"
                }
    
    def _extract_title_enhanced(self, text: str) -> Optional[str]:
        """Enhanced title extraction with multiple robust strategies"""
        import re
        
        # Strategy 1: Title in quotes (most reliable)
        title_in_quotes = re.search(r'"([^"]{15,})"', text)
        if title_in_quotes:
            return title_in_quotes.group(1).strip()
        
        # Strategy 2: Handle title-first format
        # Pattern: "Title, Author1, Author2, Journal (Year)"
        title_first_pattern = r'^([A-Z][^,]{20,}),\s*([^,]+(?:,\s*[^,]+)*),\s*([A-Z]+(?:\s+[A-Z]+)*)\s*\((\d{4})\)'
        title_first_match = re.match(title_first_pattern, text)
        
        if title_first_match:
            title = title_first_match.group(1).strip()
            # Clean up the title - remove any trailing punctuation
            title = re.sub(r'[.,\s]+$', '', title)
            if len(title) > 15:
                return title
        
        # Strategy 2b: Handle title-first format without parentheses
        # Pattern: "Title, Author1, Author2, Journal, Year"
        title_first_no_parens = r'^([A-Z][^,]{20,}),\s*([^,]+(?:,\s*[^,]+)*),\s*([A-Z][^,]+),\s*(\d{4})'
        title_first_no_parens_match = re.match(title_first_no_parens, text)
        
        if title_first_no_parens_match:
            title = title_first_no_parens_match.group(1).strip()
            # Clean up the title - remove any trailing punctuation
            title = re.sub(r'[.,\s]+$', '', title)
            if len(title) > 15:
                return title
        
        # Strategy 2c: Handle title-first format with additional fields
        # Pattern: "Title, Author1, Author2, Journal, Year, vol. X, no. Y, pp. Z"
        title_first_complex = r'^([A-Z][^,]{20,}),\s*([^,]+(?:,\s*[^,]+)*),\s*([A-Z][^,]+),\s*(\d{4})'
        title_first_complex_match = re.match(title_first_complex, text)
        
        if title_first_complex_match:
            title = title_first_complex_match.group(1).strip()
            # Clean up the title - remove any trailing punctuation
            title = re.sub(r'[.,\s]+$', '', title)
            if len(title) > 15:
                return title
        
        # Strategy 2d: Handle title-first format by looking for the first long capitalized phrase
        # This is a more flexible approach for complex references
        words = text.split(',')
        if len(words) >= 3:
            first_part = words[0].strip()
            # Check if the first part looks like a title (long, capitalized, not author names)
            if (len(first_part) > 20 and 
                first_part[0].isupper() and 
                not self._looks_like_author_names(first_part) and
                not first_part.lower().startswith(('vol', 'pp', 'p.', 'no', 'issue', 'volume', 'doi'))):
                return first_part
        
        # Strategy 3: Find the period after authors and extract title
        # Look for pattern: "Authors. Title text. Journal"
        first_period = text.find('.')
        if first_period != -1:
            after_first_period = text[first_period+1:].strip()
            second_period = after_first_period.find('.')
            if second_period != -1:
                title_text = after_first_period[:second_period].strip()
                # Check if it looks like a title
                if (len(title_text) > 15 and 
                    not title_text.lower().startswith(('int j', 'ieee', 'proc', 'vol', 'pp', 'p.', 'no', 'issue', 'volume')) and
                    not self._looks_like_author_names(title_text)):
                    return title_text
            else:
                # If no second period, look for title before year or journal indicators
                year_match = re.search(r'\b(19|20)\d{2}\b', after_first_period)
                journal_match = re.search(r'\b(IEEE|Journal|Proceedings|Conference)', after_first_period, re.IGNORECASE)
                
                if year_match:
                    title_text = after_first_period[:year_match.start()].strip()
                elif journal_match:
                    title_text = after_first_period[:journal_match.start()].strip()
                else:
                    title_text = after_first_period
                
                # Clean up and validate title
                title_text = re.sub(r'[.,\s]+$', '', title_text)  # Remove trailing punctuation
                if (len(title_text) > 15 and 
                    not title_text.lower().startswith(('int j', 'ieee', 'proc', 'vol', 'pp', 'p.', 'no', 'issue', 'volume')) and
                    not self._looks_like_author_names(title_text)):
                    return title_text
        
        # Strategy 4: Look for titles after "In:" or "Proceedings of"
        venue_patterns = [
            r'In:\s*([^,.]{15,})',
            r'Proceedings of\s+([^,.]{15,})',
            r'Proc\.\s+([^,.]{15,})',
        ]
        
        for pattern in venue_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                if len(title) > 15:
                    return title
        
        # Strategy 5: More flexible title extraction - look for text between authors and year/journal
        # Find year pattern first
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        if year_match:
            before_year = text[:year_match.start()].strip()
            
            # Remove author patterns from the beginning
            author_patterns = [
                r'^[A-Z][a-z]{2,},\s*[A-Z]\.(?:\s*[,.]?\s*[A-Z][a-z]{2,},\s*[A-Z]\.)*',  # "Smith, J., Doe, A."
                r'^[A-Z][a-z]{2,}\s+[A-Z]\.(?:\s*[,.]?\s*[A-Z][a-z]{2,}\s+[A-Z]\.)*',   # "Smith J., Doe A."
                r'^[A-Z][a-z]{2,},\s*[A-Z][a-z]+(?:\s*[,.]?\s*[A-Z][a-z]{2,},\s*[A-Z][a-z]+)*',  # "Smith, John, Doe, Jane"
            ]
            
            for pattern in author_patterns:
                before_year = re.sub(pattern, '', before_year).strip()
            
            # Look for title patterns
            title_patterns = [
                r'([A-Z][^.]{20,}\.)',  # Capital letter followed by long text ending with period
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){3,})',  # Multiple capitalized words (3+ words)
                r'([A-Z][^,]{15,}(?=,|\s+[A-Z][a-z]+\s+[A-Z]\.))',  # Title before author patterns
                r'([A-Z][a-z]+(?:\s+[a-z]+){2,}(?:\s+[A-Z][a-z]+)*)',  # Mixed case title pattern
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, before_year)
                if match:
                    title = match.group(1).strip()
                    # Enhanced validation - make sure it's not just author names or common non-title phrases
                    if (len(title) > 15 and 
                        not title.lower().startswith(('vol', 'pp', 'p.', 'no', 'issue', 'volume', 'int j', 'ieee', 'proc')) and
                        not title.endswith(',') and
                        not self._looks_like_author_names(title)):
                        return title
        
        # Strategy 6: Look for title after first period but before common journal indicators
        if first_period != -1:
            after_first_period = text[first_period+1:].strip()
            
            # Look for journal indicators to find where title ends
            journal_indicators = [
                r'\b(Int\s+J|IEEE|Proc|Journal|Proceedings|Conference|Symposium)',
                r'\b(vol\.|volume|pp\.|p\.|no\.|issue)',
                r'\b(19|20)\d{2}\b',  # Year
            ]
            
            title_end = len(after_first_period)
            for indicator in journal_indicators:
                match = re.search(indicator, after_first_period, re.IGNORECASE)
                if match and match.start() < title_end:
                    title_end = match.start()
            
            if title_end > 15:  # Make sure we have a reasonable length
                potential_title = after_first_period[:title_end].strip()
                # Clean up the title
                potential_title = re.sub(r'^[.,\s]+|[.,\s]+$', '', potential_title)  # Remove leading/trailing punctuation
                
                if (len(potential_title) > 15 and 
                    not potential_title.lower().startswith(('vol', 'pp', 'p.', 'no', 'issue', 'volume', 'int j', 'ieee', 'proc')) and
                    not self._looks_like_author_names(potential_title)):
                    return potential_title
        
        return None
    
    def _looks_like_author_names(self, text: str) -> bool:
        """Check if text looks like author names rather than a title"""
        import re
        
        # If it contains patterns like "Name, F." or "Name F." it's likely authors
        author_patterns = [
            r'[A-Z][a-z]{2,},\s*[A-Z]\.',  # "Smith, J."
            r'[A-Z][a-z]{2,}\s+[A-Z]\.',   # "Smith J."
            r'[A-Z][a-z]{2,},\s*[A-Z][a-z]+',  # "Smith, John"
        ]
        
        for pattern in author_patterns:
            if re.search(pattern, text):
                return True
        
        # If it's very short and contains only capitalized words, it might be authors
        words = text.split()
        if len(words) <= 4 and all(word[0].isupper() for word in words if word):
            return True
        
        return False
    
    def _extract_journal_enhanced(self, text: str) -> Optional[str]:
        """Enhanced journal extraction"""
        import re
        
        # Strategy 1: Italicized text
        italic_match = re.search(r'<i>([^<]+)</i>', text)
        if italic_match:
            return italic_match.group(1).strip()
        
        # Strategy 2: Handle title-first format
        # Pattern: "Title, Author1, Author2, Journal (Year)"
        title_first_pattern = r'^([A-Z][^,]{20,}),\s*([^,]+(?:,\s*[^,]+)*),\s*([A-Z]+(?:\s+[A-Z]+)*)\s*\((\d{4})\)'
        title_first_match = re.match(title_first_pattern, text)
        
        if title_first_match:
            journal = title_first_match.group(3).strip()
            # Clean up the journal name
            journal = re.sub(r'[.,\s]+$', '', journal)
            if len(journal) > 2:
                return journal
        
        # Strategy 2b: Handle title-first format without parentheses
        # Pattern: "Title, Author1, Author2, Journal, Year"
        title_first_no_parens = r'^([A-Z][^,]{20,}),\s*([^,]+(?:,\s*[^,]+)*),\s*([A-Z][^,]+),\s*(\d{4})'
        title_first_no_parens_match = re.match(title_first_no_parens, text)
        
        if title_first_no_parens_match:
            journal = title_first_no_parens_match.group(3).strip()
            # Clean up the journal name
            journal = re.sub(r'[.,\s]+$', '', journal)
            if len(journal) > 2:
                return journal
        
        # Strategy 2c: Handle title-first format with additional fields
        # Pattern: "Title, Author1, Author2, Journal, Year, vol. X, no. Y, pp. Z"
        title_first_complex = r'^([A-Z][^,]{20,}),\s*([^,]+(?:,\s*[^,]+)*),\s*([A-Z][^,]+),\s*(\d{4})'
        title_first_complex_match = re.match(title_first_complex, text)
        
        if title_first_complex_match:
            journal = title_first_complex_match.group(3).strip()
            # Clean up the journal name
            journal = re.sub(r'[.,\s]+$', '', journal)
            if len(journal) > 2:
                return journal
        
        # Strategy 2d: Handle title-first format by looking for the first long capitalized phrase
        # This is a more flexible approach for complex references
        words = text.split(',')
        if len(words) >= 3:
            first_part = words[0].strip()
            # Check if the first part looks like a title (long, capitalized, not author names)
            if (len(first_part) > 20 and 
                first_part[0].isupper() and 
                not self._looks_like_author_names(first_part)):
                
                # The third part should contain the journal
                journal = words[2].strip()
                # Clean up the journal name
                journal = re.sub(r'[.,\s]+$', '', journal)
                if len(journal) > 2:
                    return journal
        
        # Strategy 3: Look for journal after second period
        first_period = text.find('.')
        if first_period != -1:
            after_first_period = text[first_period+1:].strip()
            second_period = after_first_period.find('.')
            if second_period != -1:
                after_second_period = after_first_period[second_period+1:].strip()
                
                # Look for journal patterns
                journal_patterns = [
                    r'Int\s+J\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',
                    r'IEEE\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',
                    r'Proc\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',
                    r'[A-Z]{2,}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',
                ]
                
                for pattern in journal_patterns:
                    match = re.search(pattern, after_second_period, re.IGNORECASE)
                    if match:
                        journal = match.group().strip()
                        if len(journal) > 8:
                            return journal
        
        # Strategy 4: Look for journal patterns anywhere in the text
        journal_patterns = [
            r'\b(IEEE\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'\b(Int\s+J\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'\b(Proc\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'\b(Journal\s+of\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'\b([A-Z]{2,}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]
        
        for pattern in journal_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                journal = match.group(1).strip()
                if len(journal) > 3:
                    return journal
        
        return None
    
    def _extract_authors_enhanced(self, text: str) -> List[Dict[str, str]]:
        """Enhanced author extraction with correct logic for different formats"""
        import re
        authors = []
        
        # Strategy 1: Handle format where title comes first, then authors
        # Pattern: "Title, Author1, Author2, Author3, Journal (Year)"
        # Look for pattern where we have a long title followed by comma-separated authors
        
        # First, try to identify if this is a "title-first" format
        # Look for a long capitalized phrase at the beginning (likely title)
        title_first_pattern = r'^([A-Z][^,]{20,}),\s*([^,]+(?:,\s*[^,]+)*),\s*([A-Z]+(?:\s+[A-Z]+)*)\s*\((\d{4})\)'
        title_first_match = re.match(title_first_pattern, text)
        
        if title_first_match:
            # This is title-first format: "Title, Author1, Author2, Journal (Year)"
            authors_text = title_first_match.group(2).strip()
            
            # Split authors by comma
            author_parts = [part.strip() for part in authors_text.split(',') if part.strip()]
            
            # Filter out common non-author words that might appear in the author list
            non_author_words = {'blockchain', 'ieee', 'journal', 'proceedings', 'conference', 'symposium', 'vol', 'volume', 'pp', 'pages'}
            
            for author_part in author_parts:
                # Skip if it's a common non-author word
                if author_part.lower() in non_author_words:
                    continue
                    
                # For single names like "Qi", "Omono", "Emmanuel", "Jianbin"
                if len(author_part.split()) == 1:
                    authors.append({
                        "surname": author_part,
                        "given": ""
                    })
                else:
                    # For multi-word names, treat the last word as surname
                    words = author_part.split()
                    surname = words[-1]
                    given = ' '.join(words[:-1])
                    authors.append({
                        "surname": surname,
                        "given": given
                    })
            
            return authors
        
        # Handle title-first format without parentheses
        # Pattern: "Title, Author1, Author2, Journal, Year"
        title_first_no_parens = r'^([A-Z][^,]{20,}),\s*([^,]+(?:,\s*[^,]+)*),\s*([A-Z][^,]+),\s*(\d{4})'
        title_first_no_parens_match = re.match(title_first_no_parens, text)
        
        if title_first_no_parens_match:
            # This is title-first format: "Title, Author1, Author2, Journal, Year"
            authors_text = title_first_no_parens_match.group(2).strip()
            
            # Split authors by comma
            author_parts = [part.strip() for part in authors_text.split(',') if part.strip()]
            
            # Filter out common non-author words that might appear in the author list
            non_author_words = {'blockchain', 'ieee', 'journal', 'proceedings', 'conference', 'symposium', 'vol', 'volume', 'pp', 'pages', 'security', 'hackers'}
            
            for author_part in author_parts:
                # Skip if it's a common non-author word
                if author_part.lower() in non_author_words:
                    continue
                    
                # For single names like "Johnson"
                if len(author_part.split()) == 1:
                    authors.append({
                        "surname": author_part,
                        "given": ""
                    })
                else:
                    # For multi-word names, treat the last word as surname
                    words = author_part.split()
                    surname = words[-1]
                    given = ' '.join(words[:-1])
                    authors.append({
                        "surname": surname,
                        "given": given
                    })
            
            return authors
        
        # Handle title-first format with additional fields
        # Pattern: "Title, Author1, Author2, Journal, Year, vol. X, no. Y, pp. Z"
        title_first_complex = r'^([A-Z][^,]{20,}),\s*([^,]+(?:,\s*[^,]+)*),\s*([A-Z][^,]+),\s*(\d{4})'
        title_first_complex_match = re.match(title_first_complex, text)
        
        if title_first_complex_match:
            # This is title-first format: "Title, Author1, Author2, Journal, Year, ..."
            authors_text = title_first_complex_match.group(2).strip()
            
            # Split authors by comma
            author_parts = [part.strip() for part in authors_text.split(',') if part.strip()]
            
            # Filter out common non-author words that might appear in the author list
            non_author_words = {'blockchain', 'ieee', 'journal', 'proceedings', 'conference', 'symposium', 'vol', 'volume', 'pp', 'pages', 'security', 'hackers'}
            
            for author_part in author_parts:
                # Skip if it's a common non-author word
                if author_part.lower() in non_author_words:
                    continue
                    
                # For single names like "Johnson"
                if len(author_part.split()) == 1:
                    authors.append({
                        "surname": author_part,
                        "given": ""
                    })
                else:
                    # For multi-word names, treat the last word as surname
                    words = author_part.split()
                    surname = words[-1]
                    given = ' '.join(words[:-1])
                    authors.append({
                        "surname": surname,
                        "given": given
                    })
            
            return authors
        
        # Handle title-first format by looking for the first long capitalized phrase
        # This is a more flexible approach for complex references
        words = text.split(',')
        if len(words) >= 3:
            first_part = words[0].strip()
            # Check if the first part looks like a title (long, capitalized, not author names)
            if (len(first_part) > 20 and 
                first_part[0].isupper() and 
                not self._looks_like_author_names(first_part)):
                
                # The second part should contain authors
                authors_text = words[1].strip()
                author_parts = [part.strip() for part in authors_text.split(',') if part.strip()]
                
                # Filter out common non-author words
                non_author_words = {'blockchain', 'ieee', 'journal', 'proceedings', 'conference', 'symposium', 'vol', 'volume', 'pp', 'pages', 'security', 'hackers'}
                
                for author_part in author_parts:
                    # Skip if it's a common non-author word
                    if author_part.lower() in non_author_words:
                        continue
                        
                    # For single names like "Johnson"
                    if len(author_part.split()) == 1:
                        authors.append({
                            "surname": author_part,
                            "given": ""
                        })
                    else:
                        # For multi-word names, treat the last word as surname
                        words = author_part.split()
                        surname = words[-1]
                        given = ' '.join(words[:-1])
                        authors.append({
                            "surname": surname,
                            "given": given
                        })
                
                return authors
        
        # Strategy 2: Handle traditional format where authors come first
        # Pattern: "Authors. Title. Journal"
        first_period = text.find('.')
        if first_period != -1:
            authors_text = text[:first_period].strip()
            
            # Split by comma and process each author
            author_parts = authors_text.split(',')
            
            for part in author_parts:
                part = part.strip()
                if part:
                    # Skip if it looks like a title (long text with mixed case)
                    if len(part) > 30 and not re.match(r'^[A-Z][a-z]+,\s*[A-Z]', part):
                        continue
                    
                    # Split into words
                    words = part.split()
                    if len(words) >= 1:
                        if len(words) == 1:  # Single name like "Smith"
                            surname = words[0]
                            given = ""
                        elif len(words) == 2:  # "Smith J" or "John Smith"
                            # Check if second word looks like initials
                            if len(words[1]) <= 2 and words[1].isupper():
                                surname = words[0]
                                given = words[1]
                            else:
                                surname = words[1]
                                given = words[0]
                        elif len(words) == 3:  # "Kamel Boulos MN"
                            surname = words[1]  # "Boulos"
                            given = words[0]    # "Kamel"
                        else:
                            # Fallback: last word as surname
                            surname = words[-1]
                            given = ' '.join(words[:-1])
                        
                        # Additional validation - skip if it looks like a title
                        if not self._looks_like_author_names(f"{given} {surname}"):
                            continue
                        
                        authors.append({
                            "surname": surname,
                            "given": given
                        })
        
        return authors
    
    def _extract_year_enhanced(self, text: str) -> Optional[str]:
        """Enhanced year extraction"""
        import re
        
        # Strategy 1: Handle title-first format
        # Pattern: "Title, Author1, Author2, Journal (Year)"
        title_first_pattern = r'^([A-Z][^,]{20,}),\s*([^,]+(?:,\s*[^,]+)*),\s*([A-Z]+(?:\s+[A-Z]+)*)\s*\((\d{4})\)'
        title_first_match = re.match(title_first_pattern, text)
        
        if title_first_match:
            year = title_first_match.group(4).strip()
            if year and year.isdigit() and 1900 <= int(year) <= 2030:
                return year
        
        # Strategy 1b: Handle title-first format without parentheses
        # Pattern: "Title, Author1, Author2, Journal, Year"
        title_first_no_parens = r'^([A-Z][^,]{20,}),\s*([^,]+(?:,\s*[^,]+)*),\s*([A-Z][^,]+),\s*(\d{4})'
        title_first_no_parens_match = re.match(title_first_no_parens, text)
        
        if title_first_no_parens_match:
            year = title_first_no_parens_match.group(4).strip()
            if year and year.isdigit() and 1900 <= int(year) <= 2030:
                return year
        
        # Strategy 1c: Handle title-first format with additional fields
        # Pattern: "Title, Author1, Author2, Journal, Year, vol. X, no. Y, pp. Z"
        title_first_complex = r'^([A-Z][^,]{20,}),\s*([^,]+(?:,\s*[^,]+)*),\s*([A-Z][^,]+),\s*(\d{4})'
        title_first_complex_match = re.match(title_first_complex, text)
        
        if title_first_complex_match:
            year = title_first_complex_match.group(4).strip()
            if year and year.isdigit() and 1900 <= int(year) <= 2030:
                return year
        
        # Strategy 2: Look for year patterns anywhere in the text
        year_patterns = [
            r'\b(19|20)\d{2}\b',  # 4-digit year
            r'\((\d{4})\)',       # Year in parentheses
            r'(\d{4})',           # Any 4-digit number
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, text)
            if match:
                year = match.group(1) if match.groups() else match.group(0)
                if year.isdigit() and 1900 <= int(year) <= 2030:
                    return year
        
        return None
    
    def _extract_doi_enhanced(self, text: str) -> Optional[str]:
        """Enhanced DOI extraction with multiple patterns"""
        import re
        
        # Strategy 1: Standard DOI patterns
        doi_patterns = [
            r'doi:\s*([^\s,)]+)',  # "doi: 10.1234/example"
            r'DOI:\s*([^\s,)]+)',  # "DOI: 10.1234/example"
            r'https?://doi\.org/([^\s,)]+)',  # "https://doi.org/10.1234/example"
            r'https?://dx\.doi\.org/([^\s,)]+)',  # "https://dx.doi.org/10.1234/example"
            r'\b(10\.\d{4,}/[^\s,)]+)',  # Direct DOI pattern "10.1234/example"
        ]
        
        for pattern in doi_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                doi = match.group(1).strip()
                # Clean up the DOI
                doi = re.sub(r'[.,\s]+$', '', doi)  # Remove trailing punctuation
                if len(doi) > 10:  # DOI should be reasonably long
                    return doi
        
        # Strategy 2: Look for DOI in parentheses
        parenthetical_doi = re.search(r'\(doi:\s*([^)]+)\)', text, re.IGNORECASE)
        if parenthetical_doi:
            doi = parenthetical_doi.group(1).strip()
            if len(doi) > 10:
                return doi
        
        # Strategy 3: Look for DOI at the end of the reference
        end_doi = re.search(r'doi:\s*([^\s,)]+)\s*$', text, re.IGNORECASE)
        if end_doi:
            doi = end_doi.group(1).strip()
            if len(doi) > 10:
                return doi
        
        return None
    
    def _extract_pages_enhanced(self, text: str) -> Optional[str]:
        """Enhanced pages extraction"""
        import re
        
        # Strategy 1: Standard page patterns
        page_patterns = [
            r'pp\.\s*(\d+(?:[-–]\d+)?)',  # "pp. 123-456"
            r'p\.\s*(\d+(?:[-–]\d+)?)',   # "p. 123"
            r'pages?\s*(\d+(?:[-–]\d+)?)', # "pages 123-456"
            r'(\d+(?:[-–]\d+)?)\s*pp',    # "123-456 pp"
            r'(\d+(?:[-–]\d+)?)\s*pages', # "123-456 pages"
        ]
        
        for pattern in page_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                pages = match.group(1).strip()
                if pages and re.match(r'\d+', pages):  # Make sure it contains numbers
                    return pages
        
        # Strategy 2: Look for page ranges in various formats
        page_range_patterns = [
            r'(\d+)\s*[-–]\s*(\d+)',  # "123-456" or "123–456"
            r'(\d+)\s*to\s*(\d+)',    # "123 to 456"
        ]
        
        for pattern in page_range_patterns:
            match = re.search(pattern, text)
            if match:
                start_page = match.group(1)
                end_page = match.group(2)
                if start_page and end_page:
                    return f"{start_page}-{end_page}"
        
        return None
    
    def _extract_abstract_enhanced(self, text: str) -> Optional[str]:
        """Enhanced abstract extraction"""
        import re
        
        # Strategy 1: Look for abstract indicators
        abstract_patterns = [
            r'Abstract[:\s]+([^.]+(?:\.[^.]*){2,})',  # "Abstract: This is the abstract..."
            r'Summary[:\s]+([^.]+(?:\.[^.]*){2,})',   # "Summary: This is the summary..."
            r'Description[:\s]+([^.]+(?:\.[^.]*){2,})', # "Description: This is the description..."
        ]
        
        for pattern in abstract_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                abstract = match.group(1).strip()
                if len(abstract) > 50:  # Abstract should be reasonably long
                    return abstract
        
        # Strategy 2: Look for long descriptive text that might be an abstract
        # This is more heuristic and should be used carefully
        sentences = re.split(r'[.!?]', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if (len(sentence) > 100 and 
                not sentence.lower().startswith(('doi:', 'url:', 'http', 'www', 'vol', 'pp', 'p.', 'no', 'issue')) and
                not re.match(r'^[A-Z][a-z]+,\s*[A-Z]', sentence)):  # Not author names
                return sentence
        
        return None
    
    def _extract_publisher(self, text: str) -> Optional[str]:
        """Extract publisher information"""
        import re
        
        # Common publisher patterns
        publisher_patterns = [
            r'Published by\s+([^,.]{5,})',
            r'Publisher:\s*([^,.]{5,})',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Press',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Publishing',
        ]
        
        for pattern in publisher_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_url(self, text: str) -> Optional[str]:
        """Extract URL from reference"""
        import re
        
        # Look for URLs
        url_pattern = r'https?://[^\s,)]+'
        match = re.search(url_pattern, text)
        if match:
            return match.group().strip()
        
        return None
    
    async def parse_reference_enhanced(
        self, 
        ref_text: str, 
        enable_api_enrichment: bool = True
    ) -> Dict[str, Any]:
        try:
            logger.info(f"🔧 parse_reference_enhanced called with enable_api_enrichment={enable_api_enrichment}")
            
            # Use NER as primary parsing strategy with fallbacks
            parsed_ref = await self._enhanced_initial_parsing(ref_text)
            parser_used = parsed_ref.get("parser_used", "NER_MODEL")
            
            # Ensure we have basic fields before proceeding
            if not parsed_ref.get("title") and not parsed_ref.get("family_names"):
                logger.warning("Enhanced parsing failed to extract basic fields, trying simple parser")
                parsed_ref = self.simple_parser.parse_reference(ref_text)
                parser_used = "simple"
            
            doi_metadata = None
            conflict_analysis = None
            
            if enable_api_enrichment:
                # Only extract DOI metadata during validation, not parsing
                if parsed_ref.get('doi'):
                    try:
                        doi_metadata = await self.doi_extractor.extract_metadata(parsed_ref.get('doi'))
                        if doi_metadata and not doi_metadata.get('error'):
                            conflict_analysis = self.conflict_detector.detect_conflicts(doi_metadata, parsed_ref)
                    except Exception as e:
                        logger.error(f"DOI metadata extraction error: {str(e)}")
                try:
                    # Enhanced API enrichment with aggressive missing data search
                    enriched_ref = await self.smart_api.enrich_reference_smart(
                        parsed_ref, 
                        ref_text,
                        force_enrichment=True,
                        aggressive_search=True,  # New parameter for aggressive search
                        fill_missing_fields=True  # New parameter to fill missing fields
                    )
                    enriched_ref["parser_used"] = parser_used
                    enriched_ref["api_enrichment_used"] = True
                    
                    enriched_ref["doi_metadata"] = doi_metadata
                    enriched_ref["conflict_analysis"] = conflict_analysis
                    
                    if conflict_analysis and conflict_analysis.get('has_conflicts'):
                        for field, value in conflict_analysis.get('preferred_data', {}).items():
                            if value:
                                enriched_ref[field] = value
                    
                    flags = self.flagging_system.analyze_reference_extraction(
                        original_parsed=parsed_ref,
                        final_result=enriched_ref,
                        api_enrichment_data=enriched_ref if enriched_ref.get("api_enrichment_used") else None,
                        doi_metadata=doi_metadata,
                        conflict_analysis=conflict_analysis
                    )
                    
                    enriched_ref["flagging_analysis"] = self.flagging_system.format_flags_for_api(flags)
                    
                    # Calculate missing fields properly
                    missing_fields = self._calculate_missing_fields(enriched_ref)
                    enriched_ref["missing_fields"] = missing_fields
                    
                    # Calculate status and confidence
                    status_info = self._calculate_status_and_confidence(enriched_ref, enriched_ref.get("flagging_analysis", {}))
                    enriched_ref.update(status_info)
                    
                    return enriched_ref
                except Exception as e:
                    logger.error(f"API enrichment failed: {str(e)}, falling back to basic parsing")
                    # Fallback to basic parsing if API enrichment fails
                    parsed_ref["parser_used"] = parser_used
                    parsed_ref["api_enrichment_used"] = False
                    parsed_ref["enrichment_error"] = str(e)
            else:
                parsed_ref["parser_used"] = parser_used
                parsed_ref["api_enrichment_used"] = False
            
            parsed_ref["doi_metadata"] = doi_metadata
            parsed_ref["conflict_analysis"] = conflict_analysis
            
            if conflict_analysis and conflict_analysis.get('has_conflicts'):
                for field, value in conflict_analysis.get('preferred_data', {}).items():
                    if value:
                        parsed_ref[field] = value
            
            flags = self.flagging_system.analyze_reference_extraction(
                original_parsed=parsed_ref.copy(),
                final_result=parsed_ref,
                api_enrichment_data=None,
                doi_metadata=doi_metadata,
                conflict_analysis=conflict_analysis
            )
            
            parsed_ref["flagging_analysis"] = self.flagging_system.format_flags_for_api(flags)
            
            # Calculate missing fields properly
            missing_fields = self._calculate_missing_fields(parsed_ref)
            parsed_ref["missing_fields"] = missing_fields
            
            # Calculate status and confidence
            status_info = self._calculate_status_and_confidence(parsed_ref, parsed_ref.get("flagging_analysis", {}))
            parsed_ref.update(status_info)
            
            return parsed_ref
                
        except Exception as e:
            logger.error(f"Error in enhanced parsing: {e}")
            # Final fallback to simple parser
            try:
                parsed_ref = self.simple_parser.parse_reference(ref_text)
                parsed_ref["parser_used"] = "simple"
                parsed_ref["api_enrichment_used"] = False
                parsed_ref["error"] = str(e)
                return parsed_ref
            except Exception as fallback_error:
                logger.error(f"Even simple parsing failed: {fallback_error}")
                return {
                    "parser_used": "failed",
                    "api_enrichment_used": False,
                    "error": f"Parsing failed: {str(e)}",
                    "original_text": ref_text,
                    "title": "",
                    "family_names": [],
                    "given_names": [],
                    "year": None,
                    "journal": "",
                    "doi": "",
                    "pages": "",
                    "publisher": "",
                    "url": "",
                    "abstract": "",
                    "quality_metrics": {"quality_improvement": 0, "final_quality_score": 0},
                    "missing_fields": ["title", "family_names", "year"],
                    "flagging_analysis": {"flags": ["parsing_failed"]}
                }
    
    def generate_tagged_output(self, parsed_ref: Dict[str, Any], index: int) -> str:
        """Generate XML-like tagged output matching the target format exactly"""
        ref_id = f"ref{index + 1}"
        
        # Generate authors section with proper formatting
        authors_xml = "<authors>"
        family_names = parsed_ref.get("family_names", [])
        given_names = parsed_ref.get("given_names", [])
        
        for i, (family, given) in enumerate(zip(family_names, given_names)):
            if family and given:
                # Clean and format names properly
                clean_family = family.strip()
                clean_given = given.strip().replace('.', '')  # Remove periods from initials
                authors_xml += f'<author><fnm>{clean_given}</fnm><surname>{clean_family}</surname></author>'
        authors_xml += "</authors>"
        
        # Generate title section
        title_xml = ""
        if parsed_ref.get("title"):
            clean_title = parsed_ref["title"].strip()
            title_xml = f'<title><maintitle>{clean_title}</maintitle></title>'
        
        # Generate host/issue/series structure for journal information
        host_xml = ""
        if parsed_ref.get("journal"):
            journal_name = parsed_ref["journal"].strip()
            
            # Check if we have volume and issue information
            volume_xml = ""
            issue_xml = ""
            date_xml = ""
            
            if parsed_ref.get("year"):
                date_xml = f'<date>{parsed_ref["year"]}</date>'
            
            # Try to extract volume and issue from journal field or separate fields
            volume_info = self._extract_volume_issue_info(parsed_ref)
            if volume_info.get("volume"):
                volume_xml = f'<volume>{volume_info["volume"]}</volume>'
            if volume_info.get("issue"):
                issue_xml = f'<issue>{volume_info["issue"]}</issue>'
            
            # Build the nested structure: host > issue > series
            series_content = f'<title><maintitle>{journal_name}</maintitle></title>'
            if volume_xml:
                series_content += volume_xml
            if issue_xml:
                series_content += issue_xml
            
            issue_content = f'<series>{series_content}</series>'
            if date_xml:
                issue_content += date_xml
                
            host_xml = f'<host><issue>{issue_content}</issue></host>'
        
        # Generate pages section with proper formatting
        pages_xml = ""
        if parsed_ref.get("pages"):
            pages = parsed_ref["pages"].strip()
            if '-' in pages or '–' in pages:
                import re
                page_parts = re.split(r'[-–]', pages)
                if len(page_parts) == 2:
                    pages_xml = f'<pages><fpage>{page_parts[0].strip()}</fpage><lpage>{page_parts[1].strip()}</lpage></pages>'
                else:
                    pages_xml = f'<pages>{pages}</pages>'
            else:
                pages_xml = f'<pages><fpage>{pages}</fpage></pages>'
        
        # Generate comment section for additional information
        comments = []
        if parsed_ref.get("doi"):
            comments.append(f'DOI: {parsed_ref["doi"]}')
        if parsed_ref.get("publisher"):
            comments.append(f'Publisher: {parsed_ref["publisher"]}')
        if parsed_ref.get("url"):
            comments.append(f'URL: {parsed_ref["url"]}')
        if parsed_ref.get("abstract"):
            abstract_text = parsed_ref["abstract"][:200] + "..." if len(parsed_ref["abstract"]) > 200 else parsed_ref["abstract"]
            comments.append(f'Abstract: {abstract_text}')
        
        comment_xml = ""
        for comment in comments:
            comment_xml += f'<comment>{comment}</comment>'
        
        # Generate label in the exact format: "FirstAuthor, Year" or "FirstAuthor et al., Year"
        label = ""
        if family_names:
            first_author = family_names[0]
            year = parsed_ref.get("year", "n.d.")
            
            if len(family_names) == 1:
                label = f"{first_author}, {year}"
            else:
                label = f"{first_author} et al., {year}"
        
        # Assemble the final XML structure
        tagged_output = f'<reference id="{ref_id}">'
        if label:
            tagged_output += f'<label>{label}</label>'
        tagged_output += authors_xml
        tagged_output += title_xml
        tagged_output += host_xml
        tagged_output += pages_xml
        tagged_output += comment_xml
        tagged_output += '</reference>'
        
        return tagged_output
    
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
    
    def _calculate_missing_fields(self, parsed_ref: Dict[str, Any]) -> List[str]:
        """Calculate which important fields are missing from the parsed reference"""
        missing_fields = []
        
        # Critical fields that should always be present
        critical_fields = ["title", "family_names", "year"]
        for field in critical_fields:
            if not parsed_ref.get(field) or (isinstance(parsed_ref.get(field), list) and len(parsed_ref.get(field)) == 0):
                missing_fields.append(field)
        
        # Important fields that are commonly expected
        important_fields = ["journal", "doi", "pages", "publisher"]
        for field in important_fields:
            if not parsed_ref.get(field) or (isinstance(parsed_ref.get(field), str) and parsed_ref.get(field).strip() == ""):
                missing_fields.append(field)
        
        # Optional fields that would be nice to have
        optional_fields = ["abstract", "url"]
        for field in optional_fields:
            if not parsed_ref.get(field) or (isinstance(parsed_ref.get(field), str) and parsed_ref.get(field).strip() == ""):
                missing_fields.append(field)
        
        return missing_fields
    
    def _calculate_status_and_confidence(self, parsed_ref: Dict[str, Any], flagging_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate realistic status and confidence based on actual parsing quality"""
        try:
            # Get missing fields to understand what's actually missing
            missing_fields = parsed_ref.get("missing_fields", [])
            
            # Extract key metrics
            has_timeout = any("timeout" in str(flag).lower() for flag in flagging_analysis.get("flags", []))
            has_conflicts = flagging_analysis.get("has_conflicts", False)
            has_domain_issues = any("domain" in str(flag).lower() for flag in flagging_analysis.get("flags", []))
            
            # Calculate realistic confidence based on field quality and completeness
            confidence = 0.0
            field_count = 0
            quality_penalties = 0
            
            # Critical fields (high weight, high penalty if missing)
            critical_fields = {
                "title": 0.25,
                "family_names": 0.25, 
                "year": 0.20
            }
            
            # Important fields (medium weight)
            important_fields = {
                "journal": 0.15,
                "doi": 0.10,
                "pages": 0.05
            }
            
            # Optional fields (low weight)
            optional_fields = {
                "publisher": 0.03,
                "abstract": 0.02,
                "url": 0.01
            }
            
            # Check critical fields
            for field, weight in critical_fields.items():
                if field not in missing_fields and parsed_ref.get(field):
                    confidence += weight
                    field_count += 1
                else:
                    quality_penalties += weight * 0.5  # Heavy penalty for missing critical fields
            
            # Check important fields
            for field, weight in important_fields.items():
                if field not in missing_fields and parsed_ref.get(field):
                    confidence += weight
                    field_count += 1
                else:
                    quality_penalties += weight * 0.3  # Medium penalty for missing important fields
            
            # Check optional fields
            for field, weight in optional_fields.items():
                if field not in missing_fields and parsed_ref.get(field):
                    confidence += weight
                    field_count += 1
                # No penalty for missing optional fields
            
            # Apply quality penalties
            confidence = max(0, confidence - quality_penalties)
            
            # Determine realistic status based on actual quality
            missing_critical = [field for field in critical_fields.keys() if field in missing_fields]
            missing_important = [field for field in important_fields.keys() if field in missing_fields]
            
            if has_timeout or has_conflicts or has_domain_issues:
                status = "Unverified"
                confidence = min(confidence, 0.3)
            elif len(missing_critical) >= 2:  # Missing 2+ critical fields
                status = "Unverified"
                confidence = min(confidence, 0.4)
            elif len(missing_critical) == 1:  # Missing 1 critical field
                status = "Suspect"
                confidence = min(confidence, 0.7)
            elif len(missing_important) >= 3:  # Missing 3+ important fields
                status = "Suspect"
                confidence = min(confidence, 0.6)
            elif confidence >= 0.8 and field_count >= 6:  # High quality with many fields
                status = "Verified"
            elif confidence >= 0.6 and field_count >= 4:  # Good quality
                status = "Suspect"
            else:
                status = "Unverified"
            
            # Generate realistic reasons
            reasons = []
            if len(missing_critical) > 0:
                reasons.append(f"missing critical fields: {', '.join(missing_critical)}")
            if len(missing_important) >= 2:
                reasons.append(f"missing important fields: {', '.join(missing_important[:2])}")
            if confidence < 0.6:
                reasons.append("low parsing quality")
            if has_timeout:
                reasons.append("API timeout")
            if has_conflicts:
                reasons.append("data conflicts")
            if has_domain_issues:
                reasons.append("domain mismatch")
            if field_count < 4:
                reasons.append("insufficient data")
            
            # Determine matched fields (fields that were enriched from external sources)
            matched_fields = []
            if parsed_ref.get("doi") and "doi" not in missing_fields:
                matched_fields.append("doi")
            if parsed_ref.get("journal") and "journal" not in missing_fields:
                matched_fields.append("journal")
            if parsed_ref.get("abstract") and "abstract" not in missing_fields:
                matched_fields.append("abstract")
            if parsed_ref.get("url") and "url" not in missing_fields:
                matched_fields.append("url")
            
            # Determine sources used
            sources_used = []
            if parsed_ref.get("api_enrichment_used"):
                sources_used.extend(parsed_ref.get("enrichment_sources", []))
            if parsed_ref.get("doi_metadata"):
                sources_used.append("DOI")
            
            # Calculate success rate based on actual quality
            success_rate = min(100, int(confidence * 100))
            
            return {
                "status": status,
                "confidence": round(confidence, 2),
                "success_rate": success_rate,
                "sources_used": sources_used,
                "matched_fields": matched_fields,
                "reasons": reasons,
                "domain_check": "pass" if not has_domain_issues else "fail",
                "timeout": has_timeout,
                "missing_fields_count": len(missing_fields),
                "total_fields_extracted": field_count
            }
            
        except Exception as e:
            logger.error(f"Error calculating status: {e}")
            return {
                "status": "Unverified",
                "confidence": 0.0,
                "success_rate": 0,
                "sources_used": [],
                "matched_fields": [],
                "reasons": ["calculation error"],
                "domain_check": "unknown",
                "timeout": False,
                "missing_fields_count": 0,
                "total_fields_extracted": 0
            }