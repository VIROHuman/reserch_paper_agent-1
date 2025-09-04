"""
Reference validation utilities
"""
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
import re
from difflib import SequenceMatcher

from ..models.schemas import ReferenceData, ValidationResult, Author


class ReferenceValidator:
    """Validates reference data and identifies missing fields"""
    
    def __init__(self):
        self.required_fields = ["title", "authors", "year"]
        self.important_fields = ["journal", "volume", "issue", "pages", "doi"]
        self.optional_fields = ["publisher", "url", "abstract"]
    
    def validate_reference(self, reference: ReferenceData, original_text: str = "") -> ValidationResult:
        """Validate a single reference and return validation result"""
        missing_fields = []
        warnings = []
        suggestions = {}
        confidence_score = 0.0
        
        # Check required fields
        if not reference.title or not reference.title.strip():
            missing_fields.append("title")
        else:
            confidence_score += 0.3
        
        if not reference.authors or len(reference.authors) == 0:
            missing_fields.append("authors")
        else:
            # Validate author completeness
            incomplete_authors = []
            for author in reference.authors:
                if not author.surname or not author.surname.strip():
                    incomplete_authors.append("surname")
                if not author.first_name or not author.first_name.strip():
                    incomplete_authors.append("first_name")
            
            if incomplete_authors:
                warnings.append(f"Incomplete author information: {', '.join(set(incomplete_authors))}")
            confidence_score += 0.3
        
        if not reference.year:
            missing_fields.append("year")
        else:
            # Validate year range
            if reference.year < 1900 or reference.year > 2024:
                warnings.append(f"Year {reference.year} seems unusual")
            confidence_score += 0.2
        
        # Check important fields
        important_missing = []
        if not reference.journal or not reference.journal.strip():
            important_missing.append("journal")
        else:
            confidence_score += 0.1
        
        if not reference.volume:
            important_missing.append("volume")
        else:
            confidence_score += 0.05
        
        if not reference.issue:
            important_missing.append("issue")
        else:
            confidence_score += 0.05
        
        if not reference.pages:
            important_missing.append("pages")
        else:
            confidence_score += 0.05
        
        if not reference.doi:
            important_missing.append("doi")
        else:
            confidence_score += 0.1
        
        # Generate suggestions for missing fields
        if missing_fields or important_missing:
            suggestions = self._generate_suggestions(reference, original_text, missing_fields + important_missing)
        
        # Determine if reference is valid
        is_valid = len(missing_fields) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            missing_fields=missing_fields + important_missing,
            confidence_score=min(confidence_score, 1.0),
            suggestions=suggestions,
            warnings=warnings
        )
    
    def _generate_suggestions(self, reference: ReferenceData, original_text: str, missing_fields: List[str]) -> Dict[str, Any]:
        """Generate suggestions for missing fields"""
        suggestions = {}
        
        for field in missing_fields:
            if field == "title" and original_text:
                # Try to extract title from original text
                title_candidates = self._extract_title_candidates(original_text)
                if title_candidates:
                    suggestions["title"] = {
                        "candidates": title_candidates,
                        "confidence": 0.7
                    }
            
            elif field == "authors" and original_text:
                # Try to extract authors from original text
                author_candidates = self._extract_author_candidates(original_text)
                if author_candidates:
                    suggestions["authors"] = {
                        "candidates": author_candidates,
                        "confidence": 0.8
                    }
            
            elif field == "year" and original_text:
                # Try to extract year from original text
                year_candidates = self._extract_year_candidates(original_text)
                if year_candidates:
                    suggestions["year"] = {
                        "candidates": year_candidates,
                        "confidence": 0.9
                    }
            
            elif field == "journal" and original_text:
                # Try to extract journal from original text
                journal_candidates = self._extract_journal_candidates(original_text)
                if journal_candidates:
                    suggestions["journal"] = {
                        "candidates": journal_candidates,
                        "confidence": 0.6
                    }
        
        return suggestions
    
    def _extract_title_candidates(self, text: str) -> List[str]:
        """Extract potential titles from reference text"""
        # Look for text in quotes or after common patterns
        patterns = [
            r'"([^"]+)"',  # Text in quotes
            r'\.\s+([A-Z][^.]{10,})',  # Text after period starting with capital
            r'^\s*([A-Z][^.]{10,})',  # Text at start of line
        ]
        
        candidates = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            candidates.extend(matches)
        
        # Filter and clean candidates
        cleaned = []
        for candidate in candidates:
            candidate = candidate.strip()
            if len(candidate) > 10 and len(candidate) < 200:
                cleaned.append(candidate)
        
        return list(set(cleaned))[:3]  # Return top 3 unique candidates
    
    def _extract_author_candidates(self, text: str) -> List[Dict[str, str]]:
        """Extract potential authors from reference text"""
        # Look for author patterns
        patterns = [
            r'([A-Z][a-z]+,\s*[A-Z]\.)',  # Last, First.
            r'([A-Z][a-z]+\s+[A-Z]\.)',  # First Last.
            r'([A-Z][a-z]+,\s*[A-Z][a-z]+)',  # Last, First
        ]
        
        candidates = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if ',' in match:
                    parts = match.split(',')
                    if len(parts) == 2:
                        candidates.append({
                            "surname": parts[0].strip(),
                            "first_name": parts[1].strip().replace('.', '')
                        })
                else:
                    parts = match.split()
                    if len(parts) >= 2:
                        candidates.append({
                            "surname": parts[-1],
                            "first_name": parts[0]
                        })
        
        return candidates[:5]  # Return top 5 candidates
    
    def _extract_year_candidates(self, text: str) -> List[int]:
        """Extract potential years from reference text"""
        # Look for 4-digit years
        year_pattern = r'\b(19|20)\d{2}\b'
        matches = re.findall(year_pattern, text)
        
        years = []
        for match in matches:
            try:
                year = int(match)
                if 1900 <= year <= 2024:
                    years.append(year)
            except ValueError:
                continue
        
        return list(set(years))  # Return unique years
    
    def _extract_journal_candidates(self, text: str) -> List[str]:
        """Extract potential journal names from reference text"""
        # Look for italicized text or text in quotes that might be journal names
        patterns = [
            r'([A-Z][a-z\s]+(?:Journal|Review|Proceedings|Conference|Symposium))',
            r'([A-Z][a-z\s]{5,}(?:\s+[A-Z][a-z]+)*)',
        ]
        
        candidates = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                match = match.strip()
                if len(match) > 5 and len(match) < 100:
                    candidates.append(match)
        
        return list(set(candidates))[:3]  # Return top 3 unique candidates
    
    def compare_references(self, ref1: ReferenceData, ref2: ReferenceData) -> float:
        """Compare two references and return similarity score"""
        if not ref1.title or not ref2.title:
            return 0.0
        
        # Compare titles
        title_similarity = SequenceMatcher(None, ref1.title.lower(), ref2.title.lower()).ratio()
        
        # Compare years
        year_similarity = 1.0 if ref1.year == ref2.year else 0.0
        
        # Compare authors
        author_similarity = self._compare_authors(ref1.authors, ref2.authors)
        
        # Weighted average
        similarity = (title_similarity * 0.5 + year_similarity * 0.3 + author_similarity * 0.2)
        
        return similarity
    
    def _compare_authors(self, authors1: List[Author], authors2: List[Author]) -> float:
        """Compare two lists of authors"""
        if not authors1 or not authors2:
            return 0.0
        
        # Extract surnames for comparison
        surnames1 = [author.surname.lower() for author in authors1 if author.surname]
        surnames2 = [author.surname.lower() for author in authors2 if author.surname]
        
        if not surnames1 or not surnames2:
            return 0.0
        
        # Calculate Jaccard similarity
        set1 = set(surnames1)
        set2 = set(surnames2)
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0