"""
Reference Text Preprocessor
Cleans and normalizes reference strings before NER parsing
"""
import re
import unicodedata
from typing import Optional
from loguru import logger


class ReferencePreprocessor:
    """
    Preprocesses reference text to improve NER model accuracy
    Can be toggled on/off for easy testing
    """
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        
        # Unicode normalization mappings
        self.unicode_fixes = {
            'â€™': "'",
            'â€œ': '"',
            'â€': '"',
            'â€"': '—',
            'â€"': '–',
            'Ã©': 'é',
            'Ã¨': 'è',
            'Ã¡': 'á',
            'Ã ': 'à',
            'Ã³': 'ó',
            'Ã²': 'ò',
            'Ã­': 'í',
            'Ã±': 'ñ',
        }
        
        # Common OCR errors in DOIs and references
        self.ocr_fixes = {
            # Preserve these - they're likely correct in academic text
        }
        
        logger.info(f"ReferencePreprocessor initialized (enabled={enabled})")
    
    def preprocess(self, text: str) -> str:
        """
        Main preprocessing pipeline
        Returns cleaned text if enabled, otherwise returns original
        """
        if not self.enabled:
            return text
        
        if not text or not isinstance(text, str):
            return text
        
        original_text = text
        
        try:
            # Step 1: Fix Unicode encoding issues
            text = self._fix_unicode(text)
            
            # Step 2: Normalize whitespace
            text = self._normalize_whitespace(text)
            
            # Step 3: Normalize punctuation
            text = self._normalize_punctuation(text)
            
            # Step 4: Normalize author separators
            text = self._normalize_author_separators(text)
            
            # Step 5: Fix common OCR errors (conservative)
            text = self._fix_ocr_errors(text)
            
            # Step 6: Remove control characters
            text = self._remove_control_characters(text)
            
            # Log if significant changes were made
            if len(text) != len(original_text) or text != original_text:
                logger.debug(f"Preprocessed: '{original_text[:50]}...' → '{text[:50]}...'")
            
            return text.strip()
            
        except Exception as e:
            logger.warning(f"Preprocessing failed: {e}, returning original text")
            return original_text
    
    def _fix_unicode(self, text: str) -> str:
        """Fix common Unicode encoding issues from PDF extraction"""
        for bad, good in self.unicode_fixes.items():
            text = text.replace(bad, good)
        
        # Normalize Unicode to NFC form (canonical composition)
        text = unicodedata.normalize('NFC', text)
        
        return text
    
    def _normalize_whitespace(self, text: str) -> str:
        """Normalize all whitespace to single spaces"""
        # Replace tabs, newlines, multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Fix spacing around punctuation
        text = re.sub(r'\s+([.,;:!?])', r'\1', text)  # Remove space before punctuation
        text = re.sub(r'([.,;:!?])(\S)', r'\1 \2', text)  # Add space after punctuation if missing
        
        return text
    
    def _normalize_punctuation(self, text: str) -> str:
        """Normalize punctuation marks"""
        # Normalize different types of quotes
        text = text.replace('"', '"').replace('"', '"')  # Smart quotes to straight
        text = text.replace(''', "'").replace(''', "'")  # Smart apostrophes to straight
        
        # Normalize different types of dashes
        text = text.replace('–', '-').replace('—', '-')  # En/em dash to hyphen
        
        # Remove duplicate punctuation (but preserve ellipsis)
        text = re.sub(r'\.\.(?!\.)', '.', text)  # .. → .
        text = re.sub(r',,+', ',', text)  # ,, → ,
        text = re.sub(r';;+', ';', text)  # ;; → ;
        
        return text
    
    def _normalize_author_separators(self, text: str) -> str:
        """Normalize author separators to consistent format"""
        # Semicolon with space → comma with space (in author lists)
        # Pattern: Name, Initial; Name, Initial → Name, Initial, Name, Initial
        text = re.sub(r'([A-Z][a-z]+,\s*[A-Z]\.?)\s*;\s*', r'\1, ', text)
        
        # Ampersand → 'and' (Smith & Jones → Smith and Jones)
        text = re.sub(r'\s+&\s+', ' and ', text)
        
        return text
    
    def _fix_ocr_errors(self, text: str) -> str:
        """Fix common OCR errors (very conservative to avoid breaking text)"""
        # Only fix obvious DOI errors
        # DOI format: 10.xxxx/yyyy
        
        # Fix spaces in DOIs
        text = re.sub(r'(DOI:?\s*)(\d+)\s*\.\s*(\d+)\s*/\s*', r'\1\2.\3/', text, flags=re.IGNORECASE)
        
        return text
    
    def _remove_control_characters(self, text: str) -> str:
        """Remove control characters that might confuse NER"""
        # Remove control characters except newline and tab (already handled)
        text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or char in '\n\t')
        
        return text
    
    def toggle(self, enabled: bool):
        """Enable or disable preprocessing"""
        self.enabled = enabled
        logger.info(f"Preprocessing {'enabled' if enabled else 'disabled'}")


# Global instance
preprocessor = ReferencePreprocessor(enabled=True)


def preprocess_reference(text: str) -> str:
    """
    Convenience function for preprocessing
    """
    return preprocessor.preprocess(text)


