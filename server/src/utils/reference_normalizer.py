"""
Reference Normalization Layer (Step 2)

Normalizes raw reference strings by:
- Normalizing whitespace and punctuation
- Removing layout artifacts
- Preserving original for comparison
"""
import re
import unicodedata
from typing import Tuple
from loguru import logger


class ReferenceNormalizer:
    """
    Normalizes reference text to prepare for classification and parsing.
    
    This is a critical preprocessing step that ensures consistent input
    for downstream processing.
    """
    
    def __init__(self):
        # Patterns for common layout artifacts
        self.hyphenation_pattern = re.compile(r'(\w+)-\s*\n\s*(\w+)', re.MULTILINE)
        self.multiple_spaces = re.compile(r'\s+')
        self.multiple_newlines = re.compile(r'\n+')
        
    def normalize(self, raw_text: str) -> Tuple[str, str]:
        """
        Normalize a raw reference string.
        
        Args:
            raw_text: Raw reference text from document
            
        Returns:
            Tuple of (normalized_text, original_text)
            - normalized_text: Cleaned text ready for processing
            - original_text: Preserved original for comparison
        """
        if not raw_text:
            return "", raw_text
        
        original_text = raw_text.strip()
        
        # Step 1: Unicode normalization (NFKC - compatibility decomposition + composition)
        normalized = unicodedata.normalize('NFKC', original_text)
        
        # Step 2: Remove hyphenation artifacts
        # "word-\nword" → "wordword" (rejoin hyphenated words across lines)
        normalized = self.hyphenation_pattern.sub(r'\1\2', normalized)
        
        # Step 3: Normalize line breaks and whitespace
        # Replace all line breaks with spaces
        normalized = normalized.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
        # Collapse multiple spaces to single space
        normalized = self.multiple_spaces.sub(' ', normalized)
        
        # Step 4: Normalize punctuation
        # Standardize quotes
        normalized = normalized.replace('"', '"').replace('"', '"')
        normalized = normalized.replace(''', "'").replace(''', "'")
        # Standardize dashes
        normalized = normalized.replace('—', '-').replace('–', '-')
        # Remove zero-width spaces and other invisible characters
        normalized = re.sub(r'[\u200b-\u200f\u202a-\u202e]', '', normalized)
        
        # Step 5: Trim and final cleanup
        normalized = normalized.strip()
        
        # Step 6: Remove trailing punctuation artifacts
        # Remove trailing periods that are likely artifacts
        normalized = re.sub(r'\.+$', '.', normalized)
        
        logger.debug(f"Normalized reference: '{original_text[:50]}...' → '{normalized[:50]}...'")
        
        return normalized, original_text


