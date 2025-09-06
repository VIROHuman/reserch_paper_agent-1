"""
NLP-based reference parser using spaCy and specialized models
"""
import re
import spacy
from typing import List, Optional, Dict, Any, Tuple
from loguru import logger
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.chunk import ne_chunk
from nltk.tag import pos_tag

from ..models.schemas import ReferenceData, Author


class NLPReferenceParser:
    """Advanced reference parser using NLP models"""
    
    def __init__(self):
        self.nlp = None
        self._load_models()
        
        # Regex patterns as fallback
        self.regex_patterns = {
            'year': r'\b(19|20)\d{2}\b',
            'doi': r'10\.\d+/[^\s]+',
            'url': r'https?://[^\s]+',
            'pages': r'\b\d+(?:-\d+)?\b',
            'volume': r'vol\.?\s*(\d+)',
            'issue': r'no\.?\s*(\d+)|\((\d+)\)',
        }
    
    def _load_models(self):
        """Load NLP models"""
        try:
            # Load spaCy model
            logger.info("🤖 Loading spaCy model...")
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("✅ spaCy model loaded successfully")
            
            # Download NLTK data
            logger.info("📚 Downloading NLTK data...")
            nltk.download('punkt', quiet=True)
            nltk.download('averaged_perceptron_tagger', quiet=True)
            nltk.download('maxent_ne_chunker', quiet=True)
            nltk.download('words', quiet=True)
            logger.info("✅ NLTK data downloaded")
            
        except OSError as e:
            logger.error(f"❌ Error loading spaCy model: {e}")
            logger.info("💡 Install with: python -m spacy download en_core_web_sm")
            self.nlp = None
        except Exception as e:
            logger.error(f"❌ Error loading NLP models: {e}")
            self.nlp = None
    
    def parse_reference(self, reference_text: str) -> ReferenceData:
        """Parse reference using NLP + regex hybrid approach"""
        logger.info(f"🤖 NLP PARSING REFERENCE: {reference_text}")
        
        # Initialize empty reference data
        reference = ReferenceData(raw_text=reference_text)
        
        # Step 1: Basic regex extraction for structured data
        self._extract_structured_data(reference, reference_text)
        
        # Step 2: NLP-based extraction for complex fields
        if self.nlp:
            self._extract_with_nlp(reference, reference_text)
        else:
            logger.warning("⚠️ NLP model not available, using regex fallback")
            self._extract_with_regex_fallback(reference, reference_text)
        
        # Step 3: Post-processing and validation
        self._post_process_reference(reference)
        
        logger.info(f"🎯 NLP PARSED DATA: {reference.dict()}")
        return reference
    
    def _extract_structured_data(self, reference: ReferenceData, text: str):
        """Extract structured data using regex (DOI, URL, year)"""
        logger.info("🔍 Extracting structured data with regex...")
        
        # Extract year
        year_match = re.search(self.regex_patterns['year'], text)
        if year_match:
            try:
                reference.year = int(year_match.group())
                logger.info(f"✅ Year found: {reference.year}")
            except ValueError:
                logger.warning(f"❌ Invalid year: {year_match.group()}")
        
        # Extract DOI
        doi_match = re.search(self.regex_patterns['doi'], text)
        if doi_match:
            reference.doi = doi_match.group()
            logger.info(f"✅ DOI found: {reference.doi}")
        
        # Extract URL
        url_match = re.search(self.regex_patterns['url'], text)
        if url_match:
            reference.url = url_match.group()
            logger.info(f"✅ URL found: {reference.url}")
    
    def _extract_with_nlp(self, reference: ReferenceData, text: str):
        """Extract complex fields using NLP"""
        logger.info("🧠 Extracting with NLP...")
        
        # Process text with spaCy
        doc = self.nlp(text)
        
        # Extract title using NLP
        self._extract_title_nlp(reference, doc, text)
        
        # Extract authors using NLP
        self._extract_authors_nlp(reference, doc, text)
        
        # Extract journal using NLP
        self._extract_journal_nlp(reference, doc, text)
        
        # Extract volume, issue, pages using NLP
        self._extract_publication_details_nlp(reference, doc, text)
    
    def _extract_title_nlp(self, reference: ReferenceData, doc, text: str):
        """Extract title using NLP analysis with improved academic reference support"""
        logger.info("📝 Extracting title with NLP...")
        
        # Strategy 1: Look for quoted text
        quoted_match = re.search(r'"([^"]+)"', text)
        if quoted_match:
            title = quoted_match.group(1)
            logger.info(f"✅ Found quoted title: {title}")
            reference.title = title
            return
        
        # Strategy 2: Pattern-based extraction for academic references
        # Pattern: [1] Authors. Title. Journal
        pattern1 = r'\[\d+\]\s+[^.]+\.\s+([^.]+)\.'
        match1 = re.search(pattern1, text)
        if match1:
            title = match1.group(1).strip()
            if len(title.split()) >= 3:  # Reasonable title length
                reference.title = title
                logger.info(f"✅ Found title via academic pattern: {reference.title}")
                return
        
        # Pattern: Authors. Title. Journal (without brackets)
        pattern2 = r'^[^.]+\.\s+([^.]+)\.'
        match2 = re.search(pattern2, text)
        if match2:
            title = match2.group(1).strip()
            if len(title.split()) >= 3:  # Reasonable title length
                reference.title = title
                logger.info(f"✅ Found title via academic pattern (no brackets): {reference.title}")
                return
        
        # Strategy 3: Use sentence analysis
        sentences = sent_tokenize(text)
        if len(sentences) >= 2:
            # The title is usually the longest sentence that's not the last one
            potential_titles = sentences[:-1]  # Exclude last sentence (usually journal info)
            if potential_titles:
                # Find the longest sentence that looks like a title
                best_title = max(potential_titles, key=lambda s: len(s.split()))
                if len(best_title.split()) >= 5:  # Reasonable title length
                    reference.title = best_title.strip()
                    logger.info(f"✅ Found title via sentence analysis: {reference.title}")
                    return
        
        # Strategy 4: Use spaCy entities and POS tagging
        # Look for noun phrases that could be titles
        title_candidates = []
        for chunk in doc.noun_chunks:
            if len(chunk.text.split()) >= 3:  # Multi-word phrases
                title_candidates.append(chunk.text)
        
        if title_candidates:
            # Take the longest candidate
            best_candidate = max(title_candidates, key=len)
            if len(best_candidate.split()) >= 5:
                reference.title = best_candidate
                logger.info(f"✅ Found title via noun chunks: {reference.title}")
                return
        
        logger.warning("❌ No title found with NLP")
    
    def _extract_authors_nlp(self, reference: ReferenceData, doc, text: str):
        """Extract authors using NLP NER with improved fallback logic"""
        logger.info("👥 Extracting authors with NLP...")
        
        authors = []
        
        # Strategy 1: Pattern-based extraction first (most reliable for academic references)
        pattern_authors = self._extract_authors_pattern_based(text)
        if pattern_authors:
            authors = pattern_authors
            logger.info(f"✅ Found {len(authors)} authors via pattern matching")
            reference.authors = authors
            return
        
        # Strategy 2: Use spaCy NER to find PERSON entities
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                # Parse the person entity
                author = self._parse_person_entity(ent.text)
                if author:
                    authors.append(author)
                    logger.info(f"✅ Found author via NER: {author.first_name} {author.surname}")
        
        # Strategy 3: Use NLTK NER as backup
        if not authors:
            nltk_tokens = word_tokenize(text)
            nltk_pos = pos_tag(nltk_tokens)
            nltk_entities = ne_chunk(nltk_pos)
            
            for entity in nltk_entities:
                if hasattr(entity, 'label') and entity.label() == 'PERSON':
                    person_text = ' '.join([token for token, pos in entity.leaves()])
                    author = self._parse_person_entity(person_text)
                    if author:
                        authors.append(author)
                        logger.info(f"✅ Found author via NLTK NER: {author.first_name} {author.surname}")
        
        # Strategy 4: Enhanced pattern-based extraction as final fallback
        if not authors:
            authors = self._extract_authors_enhanced_patterns(text)
        
        if authors:
            reference.authors = authors
            logger.info(f"✅ Total authors found: {len(authors)}")
        else:
            logger.warning("❌ No authors found with NLP")
    
    def _parse_person_entity(self, person_text: str) -> Optional[Author]:
        """Parse a person entity into Author object"""
        try:
            # Handle common formats
            if ',' in person_text:
                # "Last, First" format
                parts = person_text.split(',', 1)
                surname = parts[0].strip()
                first_name = parts[1].strip().rstrip('.')
            else:
                # "First Last" format
                parts = person_text.split()
                if len(parts) >= 2:
                    first_name = parts[0]
                    surname = ' '.join(parts[1:])
                else:
                    return None
            
            return Author(
                fnm=first_name,
                surname=surname,
                full_name=f"{first_name} {surname}"
            )
        except Exception as e:
            logger.warning(f"❌ Error parsing person entity '{person_text}': {e}")
            return None
    
    def _extract_authors_pattern_based(self, text: str) -> List[Author]:
        """Enhanced pattern-based author extraction with better academic reference support"""
        authors = []
        
        # Pattern 1: [1] Author1, Author2, Author3. format
        pattern1 = r'\[\d+\]\s+([^.]+)\.'
        match1 = re.search(pattern1, text)
        if match1:
            authors_text = match1.group(1).strip()
            logger.info(f"🔍 Found authors text: {authors_text}")
            
            # Split by comma and parse each author
            author_parts = [part.strip() for part in authors_text.split(',')]
            for part in author_parts:
                if part:
                    author = self._parse_author_part(part)
                    if author:
                        authors.append(author)
                        logger.info(f"✅ Parsed author: {author.first_name} {author.surname}")
        
        # Pattern 2: Author1, Author2, Author3. (without brackets)
        if not authors:
            pattern2 = r'^([^.]+)\.'
            match2 = re.search(pattern2, text)
            if match2:
                authors_text = match2.group(1).strip()
                logger.info(f"🔍 Found authors text (no brackets): {authors_text}")
                
                # Split by comma and parse each author
                author_parts = [part.strip() for part in authors_text.split(',')]
                for part in author_parts:
                    if part:
                        author = self._parse_author_part(part)
                        if author:
                            authors.append(author)
                            logger.info(f"✅ Parsed author: {author.first_name} {author.surname}")
        
        # Pattern 3: Last, First. (Year) format
        if not authors:
            pattern3 = r'([A-Z][a-z]+),\s*([A-Z][a-z.]+)\s*\((\d{4})\)'
            matches3 = re.findall(pattern3, text)
            
            for last, first, year in matches3:
                first_clean = first.rstrip('.')
                authors.append(Author(
                    fnm=first_clean,
                    surname=last,
                    full_name=f"{first_clean} {last}"
                ))
                logger.info(f"✅ Added author: {first_clean} {last}")
        
        # Pattern 4: First Last format (multiple authors)
        if not authors:
            pattern4 = r'([A-Z][a-z.]+)\s+([A-Z][a-z]+)'
            matches4 = re.findall(pattern4, text)
            
            for first, last in matches4[:3]:  # Limit to first 3 authors
                first_clean = first.rstrip('.')
                authors.append(Author(
                    fnm=first_clean,
                    surname=last,
                    full_name=f"{first_clean} {last}"
                ))
                logger.info(f"✅ Added author: {first_clean} {last}")
        
        return authors
    
    def _extract_authors_enhanced_patterns(self, text: str) -> List[Author]:
        """Enhanced pattern-based author extraction as final fallback"""
        authors = []
        
        # Pattern 1: [1] Author1, Author2, Author3. format
        pattern1 = r'\[\d+\]\s+([^.]+)\.'
        match1 = re.search(pattern1, text)
        if match1:
            authors_text = match1.group(1).strip()
            logger.info(f"🔍 Found authors text: {authors_text}")
            
            # Split by comma and parse each author
            author_parts = [part.strip() for part in authors_text.split(',')]
            for part in author_parts:
                if part:
                    author = self._parse_author_part(part)
                    if author:
                        authors.append(author)
                        logger.info(f"✅ Parsed author: {author.first_name} {author.surname}")
        
        # Pattern 2: Author1, Author2, Author3. (without brackets)
        if not authors:
            pattern2 = r'^([^.]+)\.'
            match2 = re.search(pattern2, text)
            if match2:
                authors_text = match2.group(1).strip()
                logger.info(f"🔍 Found authors text (no brackets): {authors_text}")
                
                # Split by comma and parse each author
                author_parts = [part.strip() for part in authors_text.split(',')]
                for part in author_parts:
                    if part:
                        author = self._parse_author_part(part)
                        if author:
                            authors.append(author)
                            logger.info(f"✅ Parsed author: {author.first_name} {author.surname}")
        
        # Pattern 3: Last, First. (Year) format
        if not authors:
            pattern3 = r'([A-Z][a-z]+),\s*([A-Z][a-z.]+)\s*\((\d{4})\)'
            matches3 = re.findall(pattern3, text)
            
            for last, first, year in matches3:
                first_clean = first.rstrip('.')
                authors.append(Author(
                    fnm=first_clean,
                    surname=last,
                    full_name=f"{first_clean} {last}"
                ))
                logger.info(f"✅ Added author: {first_clean} {last}")
        
        # Pattern 4: First Last format (multiple authors)
        if not authors:
            pattern4 = r'([A-Z][a-z.]+)\s+([A-Z][a-z]+)'
            matches4 = re.findall(pattern4, text)
            
            for first, last in matches4[:3]:  # Limit to first 3 authors
                first_clean = first.rstrip('.')
                authors.append(Author(
                    fnm=first_clean,
                    surname=last,
                    full_name=f"{first_clean} {last}"
                ))
                logger.info(f"✅ Added author: {first_clean} {last}")
        
        return authors
    
    def _parse_author_part(self, author_text: str) -> Optional[Author]:
        """Parse a single author part (e.g., 'Church KW' or 'Chen Z')"""
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
            logger.warning(f"❌ Error parsing author part '{author_text}': {e}")
            return None
    
    def _extract_journal_nlp(self, reference: ReferenceData, doc, text: str):
        """Extract journal using NLP analysis with improved academic reference support"""
        logger.info("📰 Extracting journal with NLP...")
        
        # Strategy 1: Pattern-based extraction for academic references
        # Pattern: [1] Authors. Title. Journal Year;Volume(Issue):Pages
        pattern1 = r'\[\d+\]\s+[^.]+\.\s+[^.]+\.\s+([^.]+)\s+\d{4}'
        match1 = re.search(pattern1, text)
        if match1:
            journal = match1.group(1).strip()
            if len(journal.split()) >= 2:  # Reasonable journal name length
                reference.journal = journal
                logger.info(f"✅ Found journal via academic pattern: {reference.journal}")
                return
        
        # Pattern: Authors. Title. Journal Year;Volume(Issue):Pages (without brackets)
        pattern2 = r'^[^.]+\.\s+[^.]+\.\s+([^.]+)\s+\d{4}'
        match2 = re.search(pattern2, text)
        if match2:
            journal = match2.group(1).strip()
            if len(journal.split()) >= 2:  # Reasonable journal name length
                reference.journal = journal
                logger.info(f"✅ Found journal via academic pattern (no brackets): {reference.journal}")
                return
        
        # Strategy 2: Look for ORG entities (journals are often organizations)
        for ent in doc.ents:
            if ent.label_ == "ORG":
                # Check if it looks like a journal name
                if self._is_likely_journal(ent.text):
                    reference.journal = ent.text
                    logger.info(f"✅ Found journal via ORG entity: {reference.journal}")
                    return
        
        # Strategy 3: Use sentence analysis to find journal
        sentences = sent_tokenize(text)
        if len(sentences) >= 2:
            # Journal is usually in the last sentence
            last_sentence = sentences[-1]
            journal_candidates = self._extract_journal_candidates(last_sentence)
            
            if journal_candidates:
                # Take the most likely candidate
                best_journal = max(journal_candidates, key=lambda x: self._journal_confidence_score(x))
                reference.journal = best_journal
                logger.info(f"✅ Found journal via sentence analysis: {reference.journal}")
                return
        
        # Strategy 4: Pattern-based fallback
        journal = self._extract_journal_pattern_based(text)
        if journal:
            reference.journal = journal
            logger.info(f"✅ Found journal via pattern: {reference.journal}")
        else:
            logger.warning("❌ No journal found with NLP")
    
    def _is_likely_journal(self, text: str) -> bool:
        """Check if text looks like a journal name"""
        journal_indicators = [
            'journal', 'review', 'proceedings', 'conference', 'symposium',
            'forum', 'bulletin', 'magazine', 'quarterly', 'annual'
        ]
        
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in journal_indicators) or \
               (len(text.split()) >= 2 and len(text.split()) <= 6)
    
    def _extract_journal_candidates(self, text: str) -> List[str]:
        """Extract potential journal names from text"""
        candidates = []
        
        # Look for capitalized phrases
        patterns = [
            r'([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)',  # Three words
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Two words
            r'([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)',  # Four words
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            candidates.extend(matches)
        
        return candidates
    
    def _journal_confidence_score(self, journal: str) -> float:
        """Calculate confidence score for journal name"""
        score = 0.0
        
        # Length penalty for very short/long names
        word_count = len(journal.split())
        if 2 <= word_count <= 4:
            score += 0.5
        elif word_count == 1 or word_count > 6:
            score -= 0.3
        
        # Bonus for journal indicators
        journal_indicators = ['journal', 'review', 'proceedings', 'conference', 'forum']
        if any(indicator in journal.lower() for indicator in journal_indicators):
            score += 0.3
        
        # Penalty for numbers (journals usually don't have numbers in name)
        if re.search(r'\d', journal):
            score -= 0.2
        
        return max(0.0, min(1.0, score))
    
    def _extract_journal_pattern_based(self, text: str) -> Optional[str]:
        """Pattern-based journal extraction as fallback"""
        patterns = [
            r'\.\s*([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)\s*,\s*\d{4}\s*\(\d+\)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)\s*,\s*\d{4}\s*\(\d+\)',
            r'\.\s*([A-Z][^,]+?)\s*,\s*\d{4}',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                journal = match.group(1).strip()
                if 3 <= len(journal) <= 100:
                    return journal
        
        return None
    
    def _extract_publication_details_nlp(self, reference: ReferenceData, doc, text: str):
        """Extract volume, issue, pages using NLP"""
        logger.info("📚 Extracting publication details with NLP...")
        
        # Extract volume and issue using regex patterns
        volume_patterns = [
            r'vol\.?\s*(\d+)',
            r'Volume\s*(\d+)',
            r'v\.?\s*(\d+)',
            r'(\d+)\s*\(\d+\)',  # 2020 (18) - year as volume
        ]
        
        for pattern in volume_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                reference.volume = match.group(1)
                logger.info(f"✅ Volume found: {reference.volume}")
                break
        
        # Extract issue
        issue_patterns = [
            r'no\.?\s*(\d+)',
            r'Issue\s*(\d+)',
            r'\(\s*(\d+)\s*\)',  # (18)
        ]
        
        for pattern in issue_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                reference.issue = match.group(1)
                logger.info(f"✅ Issue found: {reference.issue}")
                break
        
        # Extract pages
        page_patterns = [
            r'(\d+)\s*[-–]\s*(\d+)',  # 5-7 or 5–7
            r'pp\.?\s*(\d+(?:-\d+)?)',  # pp. 5-7
            r'p\.?\s*(\d+(?:-\d+)?)',   # p. 5-7
            r'(\d+(?:-\d+)?)\s*$',      # 5-7 at end
        ]
        
        for pattern in page_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    reference.pages = f"{match.group(1)}-{match.group(2)}"
                else:
                    reference.pages = match.group(1)
                logger.info(f"✅ Pages found: {reference.pages}")
                break
    
    def _extract_with_regex_fallback(self, reference: ReferenceData, text: str):
        """Fallback to regex-only extraction if NLP is not available"""
        logger.info("⚠️ Using regex fallback...")
        
        # Use the original regex-based extraction
        from .reference_parser import ReferenceParser
        regex_parser = ReferenceParser()
        regex_result = regex_parser.parse_reference(text)
        
        # Copy over any missing fields
        if not reference.title and regex_result.title:
            reference.title = regex_result.title
        if not reference.authors and regex_result.authors:
            reference.authors = regex_result.authors
        if not reference.journal and regex_result.journal:
            reference.journal = regex_result.journal
        if not reference.volume and regex_result.volume:
            reference.volume = regex_result.volume
        if not reference.issue and regex_result.issue:
            reference.issue = regex_result.issue
        if not reference.pages and regex_result.pages:
            reference.pages = regex_result.pages
    
    def _post_process_reference(self, reference: ReferenceData):
        """Post-process and validate the extracted reference"""
        logger.info("🔧 Post-processing reference...")
        
        # Clean up title
        if reference.title:
            reference.title = reference.title.strip()
            # Remove extra quotes if present
            if reference.title.startswith("'") and reference.title.endswith("'"):
                reference.title = reference.title[1:-1]
        
        # Clean up journal
        if reference.journal:
            reference.journal = reference.journal.strip()
        
        # Validate year range
        if reference.year and (reference.year < 1900 or reference.year > 2024):
            logger.warning(f"⚠️ Unusual year: {reference.year}")
        
        # Clean up authors
        if reference.authors:
            for author in reference.authors:
                if author.first_name:
                    author.first_name = author.first_name.strip()
                if author.surname:
                    author.surname = author.surname.strip()
                if author.full_name:
                    author.full_name = author.full_name.strip()
        
        logger.info("✅ Post-processing complete")
