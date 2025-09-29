"""
Advanced text normalization for reference parsing and matching
"""
import re
import unicodedata
from typing import Dict, List, Set, Tuple
from loguru import logger


class TextNormalizer:
    """Advanced text normalization for robust matching"""
    
    def __init__(self):
        # Common stop words to remove
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'among', 'against',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'must', 'can', 'shall', 'this', 'that', 'these', 'those', 'i', 'you', 'he',
            'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
        }
        
        # Academic stop words specific to references
        self.academic_stop_words = {
            'journal', 'proceedings', 'conference', 'workshop', 'symposium',
            'volume', 'vol', 'issue', 'no', 'number', 'pages', 'pp', 'page',
            'doi', 'isbn', 'issn', 'url', 'http', 'https', 'www',
            'published', 'publication', 'publisher', 'press', 'academic',
            'international', 'annual', 'biennial', 'edition', 'ed', 'eds',
            'editor', 'editors', 'author', 'authors', 'editorial', 'committee'
        }
        
        # Punctuation patterns for normalization
        self.punctuation_patterns = [
            r'[^\w\s]',  # Remove all punctuation except word chars and spaces
            r'\s+',      # Normalize whitespace
        ]
        
        logger.info("Text normalizer initialized")
    
    def normalize_text(self, text: str, preserve_case: bool = False) -> str:
        """Comprehensive text normalization"""
        if not text:
            return ""
        
        try:
            # Step 1: Unicode normalization (NFKC - compatibility decomposition + canonical composition)
            normalized = unicodedata.normalize('NFKC', text)
            
            # Step 2: Handle common encoding issues
            normalized = self._fix_encoding_issues(normalized)
            
            # Step 3: Remove or replace problematic characters
            normalized = self._clean_special_characters(normalized)
            
            # Step 4: Normalize whitespace
            normalized = re.sub(r'\s+', ' ', normalized).strip()
            
            # Step 5: Case normalization (unless preserving case)
            if not preserve_case:
                normalized = normalized.lower()
            
            return normalized
            
        except Exception as e:
            logger.warning(f"Text normalization failed for '{text}': {e}")
            return text.lower().strip() if not preserve_case else text.strip()
    
    def normalize_title(self, title: str) -> Dict[str, str]:
        """Normalize title and create multiple matching keys"""
        if not title:
            return {}
        
        # Basic normalization
        basic = self.normalize_text(title, preserve_case=False)
        
        # Remove stop words for better matching
        no_stopwords = self._remove_stop_words(basic)
        
        # Create token-sorted signature (order-independent matching)
        tokens = no_stopwords.split()
        token_sorted = ' '.join(sorted(tokens))
        
        # Create n-gram signatures for fuzzy matching
        bigrams = self._create_ngrams(no_stopwords, n=2)
        trigrams = self._create_ngrams(no_stopwords, n=3)
        
        # Create acronym version (for titles with lots of acronyms)
        acronyms = self._extract_acronyms(title)
        
        return {
            'basic': basic,
            'no_stopwords': no_stopwords,
            'token_sorted': token_sorted,
            'bigrams': bigrams,
            'trigrams': trigrams,
            'acronyms': acronyms,
            'original': title
        }
    
    def normalize_author_name(self, name: str) -> Dict[str, str]:
        """Normalize author name and create variants"""
        if not name:
            return {}
        
        # Basic normalization
        basic = self.normalize_text(name, preserve_case=False)
        
        # Handle common author name patterns
        variants = self._create_author_variants(basic)
        
        # Extract initials and full names
        initials, full_names = self._extract_name_components(basic)
        
        return {
            'basic': basic,
            'variants': variants,
            'initials': initials,
            'full_names': full_names,
            'original': name
        }
    
    def normalize_journal_venue(self, venue: str) -> Dict[str, str]:
        """Normalize journal/venue name"""
        if not venue:
            return {}
        
        # Basic normalization
        basic = self.normalize_text(venue, preserve_case=False)
        
        # Remove academic stop words
        cleaned = self._remove_academic_stop_words(basic)
        
        # Extract key terms (remove common words)
        key_terms = self._extract_key_terms(cleaned)
        
        # Create acronym version
        acronym = self._create_venue_acronym(basic)
        
        return {
            'basic': basic,
            'cleaned': cleaned,
            'key_terms': key_terms,
            'acronym': acronym,
            'original': venue
        }
    
    def create_blocking_key(self, authors: List[str], year: str, venue: str = None) -> str:
        """Create blocking key for efficient candidate filtering"""
        try:
            # Use first author's last name
            first_author = ""
            if authors:
                first_author = self.normalize_text(authors[0], preserve_case=False)
                # Extract last name (assume it's the last word)
                first_author = first_author.split()[-1] if first_author.split() else ""
            
            # Normalize year
            normalized_year = str(year).strip() if year else ""
            
            # Normalize venue (first few words)
            venue_key = ""
            if venue:
                venue_normalized = self.normalize_text(venue, preserve_case=False)
                venue_words = venue_normalized.split()[:3]  # First 3 words
                venue_key = '_'.join(venue_words)
            
            # Create composite key
            key_parts = [first_author, normalized_year]
            if venue_key:
                key_parts.append(venue_key)
            
            blocking_key = '_'.join(key_parts)
            return blocking_key if blocking_key else "unknown"
            
        except Exception as e:
            logger.warning(f"Failed to create blocking key: {e}")
            return "unknown"
    
    def _fix_encoding_issues(self, text: str) -> str:
        """Fix common encoding issues"""
        # Replace common problematic characters
        replacements = {
            '"': '"',  # Smart quotes
            '"': '"',
            ''': "'",
            ''': "'",
            '–': '-',  # En dash
            '—': '-',  # Em dash
            '…': '...',  # Ellipsis
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text
    
    def _clean_special_characters(self, text: str) -> str:
        """Clean special characters while preserving important ones"""
        # Keep alphanumeric, spaces, hyphens, and parentheses for titles
        text = re.sub(r'[^\w\s\-\(\)]', ' ', text)
        return text
    
    def _remove_stop_words(self, text: str) -> str:
        """Remove common stop words"""
        words = text.split()
        filtered_words = [word for word in words if word not in self.stop_words]
        return ' '.join(filtered_words)
    
    def _remove_academic_stop_words(self, text: str) -> str:
        """Remove academic-specific stop words"""
        words = text.split()
        filtered_words = [word for word in words if word not in self.academic_stop_words]
        return ' '.join(filtered_words)
    
    def _create_ngrams(self, text: str, n: int) -> Set[str]:
        """Create n-grams for fuzzy matching"""
        words = text.split()
        ngrams = set()
        
        for i in range(len(words) - n + 1):
            ngram = ' '.join(words[i:i+n])
            ngrams.add(ngram)
        
        return ngrams
    
    def _extract_acronyms(self, text: str) -> Set[str]:
        """Extract potential acronyms from title"""
        # Find words that are all caps or have capital letters
        words = text.split()
        acronyms = set()
        
        for word in words:
            # Remove punctuation
            clean_word = re.sub(r'[^\w]', '', word)
            
            # If it's short and has capitals, might be an acronym
            if len(clean_word) <= 6 and clean_word.isupper():
                acronyms.add(clean_word.lower())
            
            # If it has mixed case and is short, might be an acronym
            elif len(clean_word) <= 4 and any(c.isupper() for c in clean_word):
                acronyms.add(clean_word.lower())
        
        return acronyms
    
    def _create_author_variants(self, name: str) -> List[str]:
        """Create common variants of author name"""
        variants = [name]
        
        # Split into parts
        parts = name.split()
        if len(parts) >= 2:
            # Last name, First name format
            variants.append(f"{parts[-1]}, {parts[0]}")
            
            # First name Last name format
            variants.append(f"{parts[0]} {parts[-1]}")
            
            # With middle initials
            if len(parts) > 2:
                first = parts[0]
                middle_initials = '.'.join([part[0] for part in parts[1:-1]])
                last = parts[-1]
                variants.append(f"{first} {middle_initials}. {last}")
                variants.append(f"{last}, {first} {middle_initials}.")
        
        return list(set(variants))  # Remove duplicates
    
    def _extract_name_components(self, name: str) -> Tuple[List[str], List[str]]:
        """Extract initials and full names"""
        parts = name.split()
        initials = []
        full_names = []
        
        for part in parts:
            if len(part) == 1:
                initials.append(part)
            else:
                full_names.append(part)
        
        return initials, full_names
    
    def _extract_key_terms(self, text: str) -> str:
        """Extract key terms from venue name"""
        words = text.split()
        # Remove very short words and common words
        key_words = [word for word in words if len(word) > 2 and word not in self.stop_words]
        return ' '.join(key_words)
    
    def _create_venue_acronym(self, venue: str) -> str:
        """Create acronym from venue name"""
        words = venue.split()
        if len(words) <= 2:
            return venue  # Too short for acronym
        
        # Take first letter of each significant word
        acronym_parts = []
        for word in words:
            if len(word) > 2 and word not in self.academic_stop_words:
                acronym_parts.append(word[0].upper())
        
        return ''.join(acronym_parts) if acronym_parts else venue
    
    def calculate_similarity(self, text1: str, text2: str, method: str = 'jaccard') -> float:
        """Calculate similarity between normalized texts"""
        if not text1 or not text2:
            return 0.0
        
        if method == 'jaccard':
            return self._jaccard_similarity(text1, text2)
        elif method == 'token_overlap':
            return self._token_overlap_similarity(text1, text2)
        else:
            return self._jaccard_similarity(text1, text2)
    
    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _token_overlap_similarity(self, text1: str, text2: str) -> float:
        """Calculate token overlap similarity"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        min_length = min(len(words1), len(words2))
        
        return intersection / min_length if min_length > 0 else 0.0


# Global instance for easy access
text_normalizer = TextNormalizer()
