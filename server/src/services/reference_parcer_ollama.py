from transformers import pipeline
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
from collections import defaultdict
import json
import requests
import re
import sys
from loguru import logger

# Import preprocessor
try:
    from ..utils.reference_preprocessor import preprocess_reference
    PREPROCESSOR_AVAILABLE = True
except ImportError:
    PREPROCESSOR_AVAILABLE = False
    def preprocess_reference(text):
        return text  # No-op if not available

# Fix encoding issues on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')


class Author(BaseModel):
    first_name: Optional[str] = Field(None, alias="fnm")
    surname: Optional[str] = Field(None, alias="surname")
    full_name: Optional[str] = None


class ReferenceData(BaseModel):
    title: Optional[str] = None
    authors: List[Author] = []
    year: Optional[int] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    publisher: Optional[str] = None
    publication_type: Optional[str] = None
    raw_text: Optional[str] = None
    # Advanced metadata
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    entity_count: Dict[str, int] = Field(default_factory=dict)
    ambiguity_flags: List[str] = Field(default_factory=list)


class AdvancedNERParser:
    """
    NER implementation with LLM fallback for improved accuracy.
    Uses NER as primary (fast), falls back to LLM when results are suspicious.
    """
    
    # Common date abbreviations that get misclassified as authors
    DATE_ABBREVIATIONS = {
        'jan', 'feb', 'mar', 'apr', 'may', 'jun',
        'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
        'january', 'february', 'march', 'april', 'june',
        'july', 'august', 'september', 'october', 'november', 'december'
    }
    
    def __init__(self, 
                 confidence_threshold: float = 0.1,  # Lowered to 0.1 to catch more entities
                 enable_entity_disambiguation: bool = True,
                 enable_confidence_weighting: bool = True,
                 use_llm_primary: bool = False,  # Disabled for fast parsing; LLM used during validation
                 ollama_base_url: str = "http://localhost:11434"):
        
        # Try to load the NER model with fallback
        try:
            # Load with aggregation_strategy for automatic B-/I- merging
            self.parser = pipeline(
                "ner",
                model="SIRIS-Lab/citation-parser-ENTITY",
                aggregation_strategy="simple",  # Merges tokens automatically
                device=-1  # CPU
            )
            self.model_available = True
            print("✅ NER model loaded successfully")
        except Exception as e:
            print(f"⚠️ Failed to load NER model: {e}")
            print("🔄 Using regex-based parsing as fallback")
            self.parser = None
            self.model_available = False
        
        self.confidence_threshold = confidence_threshold
        self.enable_disambiguation = enable_entity_disambiguation
        self.enable_confidence_weighting = enable_confidence_weighting
        self.use_llm_primary = use_llm_primary  # Use LLM as primary, not fallback
        self.ollama_base_url = ollama_base_url
        
        # Entity type mappings
        self.entity_mappings = {
            'PUBLICATION_YEAR': 'YEAR',
            'PAGE_FIRST': 'PAGES',
            'PAGE_LAST': 'PAGES',
            'LINK_ONLINE_AVAILABILITY': 'URL',
        }
        
        # Test Ollama availability
        self.llm_available = self._test_ollama_connection()
    
    def _normalize_entity_type(self, entity_type: str) -> str:
        """Normalize entity types to canonical forms"""
        return self.entity_mappings.get(entity_type, entity_type)
    
    def _test_ollama_connection(self) -> bool:
        """Test if Ollama is available"""
        if not self.use_llm_primary:
            return False
        
        try:
            response = requests.get(
                f"{self.ollama_base_url}/api/tags",
                timeout=2
            )
            if response.status_code == 200:
                print("✅ Ollama LLM ready for primary parsing")
                return True
        except Exception:
            pass
        
        print("⚠️ Ollama not available - falling back to NER only")
        return False
    
    def _filter_false_positive_authors(self, authors: List[Author]) -> List[Author]:
        """Remove common false positives from author list"""
        filtered = []
        
        for author in authors:
            # Get text to check (full_name, surname, or first_name)
            check_text = (author.full_name or author.surname or author.first_name or "").lower().strip()
            
            # Skip if empty
            if not check_text:
                continue
            
            # Skip if it's a date abbreviation
            if check_text in self.DATE_ABBREVIATIONS:
                print(f"🔍 Filtered false positive author: '{check_text}'")
                continue
            
            # Skip if it's just numbers or too short
            if len(check_text) < 2 or check_text.isdigit():
                continue
            
            filtered.append(author)
        
        return filtered
    
    def _should_use_llm_fallback(self, authors: List[Author], raw_text: str, confidence: float) -> bool:
        """Detect if NER results are suspicious and need LLM fallback"""
        if not self.llm_available:
            return False
        
        # Trigger 1: No authors extracted but "and" appears
        and_count = raw_text.lower().count(' and ')
        if len(authors) == 0 and and_count >= 1:
            print(f"🔍 LLM fallback: No authors but '{and_count}' 'and' detected")
            return True
        
        # Trigger 2: Merged authors detected (full_name contains multiple commas)
        # This happens when NER extracts "Smith, J., Jones, P., Brown, M." as ONE author
        for author in authors:
            full_name = author.full_name or ""
            comma_count = full_name.count(',')
            if comma_count >= 2:  # "Smith, J., Jones, P." has 2+ commas = merged authors
                print(f"🔍 LLM fallback: Merged authors detected ('{full_name[:50]}...')")
                return True
        
        # Trigger 3: Very few authors but lots of commas (likely missed splits)
        # Count expected authors from commas and "and"
        comma_count = raw_text.count(',')
        # Heuristic: if commas > authors * 3, likely still merged
        # Raised threshold to 3x to avoid false positives
        if len(authors) > 0 and comma_count > len(authors) * 3:
            print(f"🔍 LLM fallback: {len(authors)} authors but {comma_count} commas detected")
            return True
        
        # Trigger 4: Low confidence
        if confidence < 0.4 and len(authors) < 3:
            print(f"🔍 LLM fallback: Low confidence ({confidence:.2f}) with few authors")
            return True
        
        # Trigger 5: Contains suspicious patterns (date abbreviations in author text)
        for author in authors:
            author_text = (author.full_name or author.surname or "").lower()
            if any(date_abbr in author_text.split() for date_abbr in self.DATE_ABBREVIATIONS):
                print(f"🔍 LLM fallback: Date abbreviation in authors")
                return True
        
        return False
    
    def _extract_authors_with_llm(self, raw_citation: str) -> List[Author]:
        """Use LLM to extract authors from citation"""
        try:
            prompt = f"""Extract ONLY the author names from this academic citation. Return them as a JSON array of objects with "full_name", "surname", and "first_name" fields.

Citation: {raw_citation}

Rules:
- Extract ALL author names
- Do NOT include month abbreviations (Jan, Feb, etc.) as authors
- Do NOT include years, journal names, or other metadata
- If a name has format "Surname, FirstName" use that structure
- If a name has format "FirstName Surname" use that structure

Return ONLY valid JSON array, nothing else. Example format:
[{{"full_name": "John Smith", "surname": "Smith", "first_name": "John"}}]"""

            response = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json={
                    "model": "llama3:latest",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9
                    }
                },
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"❌ LLM request failed: {response.status_code}")
                return []
            
            result = response.json()
            llm_output = result.get('response', '').strip()
            
            # Extract JSON from response (sometimes LLM adds extra text)
            json_match = re.search(r'\[.*\]', llm_output, re.DOTALL)
            if not json_match:
                print(f"⚠️ No JSON found in LLM output")
                return []
            
            authors_data = json.loads(json_match.group(0))
            
            # Convert to Author objects
            authors = []
            for author_dict in authors_data:
                authors.append(Author(
                    full_name=author_dict.get('full_name'),
                    surname=author_dict.get('surname'),
                    first_name=author_dict.get('first_name')
                ))
            
            print(f"✅ LLM extracted {len(authors)} authors")
            return authors
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error from LLM: {e}")
            return []
        except Exception as e:
            print(f"❌ LLM extraction failed: {e}")
            return []
    
    def _extract_raw_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities with position information"""
        entities = self.parser(text)
        
        # Add normalized types and metadata
        for ent in entities:
            ent['normalized_type'] = self._normalize_entity_type(ent['entity_group'])
            ent['text'] = ent['word'].strip()
            ent['confidence'] = ent.get('score', 1.0)
        
        # DEBUG: Log what NER actually detected
        if entities:
            logger.info(f"🔍 NER detected {len(entities)} entities:")
            for ent in entities[:10]:  # Show first 10
                logger.info(f"   {ent['entity_group']:<15} | {ent['text']:<30} | confidence: {ent['confidence']:.3f}")
            if len(entities) > 10:
                logger.info(f"   ... and {len(entities) - 10} more")
        
        return entities
    
    def _group_entities_by_type(self, entities: List[Dict]) -> Dict[str, List[Dict]]:
        """Group entities by normalized type with confidence filtering"""
        grouped = defaultdict(list)
        filtered_out = []
        
        for ent in entities:
            if ent['confidence'] >= self.confidence_threshold:
                grouped[ent['normalized_type']].append(ent)
            else:
                filtered_out.append(ent)
        
        # DEBUG: Show what was filtered out
        if filtered_out:
            logger.info(f"⚠️  Filtered out {len(filtered_out)} entities below threshold {self.confidence_threshold}:")
            for ent in filtered_out[:5]:  # Show first 5
                logger.info(f"   {ent['normalized_type']:<15} | {ent['text']:<30} | confidence: {ent['confidence']:.3f}")
        
        # DEBUG: Show what passed
        if grouped:
            logger.info(f"✅ Kept {sum(len(v) for v in grouped.values())} entities:")
            for entity_type, ents in grouped.items():
                logger.info(f"   {entity_type}: {len(ents)} entities")
        
        return dict(grouped)
    
    def _resolve_conflicts(self, entities: List[Dict]) -> Optional[Dict]:
        """
        Advanced: When multiple entities of same type exist,
        choose best one using confidence weighting and position heuristics
        """
        if not entities:
            return None
        
        if len(entities) == 1:
            return entities[0]
        
        if self.enable_confidence_weighting:
            # Weight by confidence
            best = max(entities, key=lambda e: e['confidence'])
            return best
        else:
            # Take first occurrence
            return entities[0]
    
    def _merge_page_entities(self, page_entities: List[Dict]) -> Optional[str]:
        """
        Advanced: Intelligently merge PAGE_FIRST and PAGE_LAST
        using position and confidence
        """
        if not page_entities:
            return None
        
        # Sort by start position
        sorted_pages = sorted(page_entities, key=lambda e: e['start'])
        
        # If we have exactly 2 page entities, likely first-last pair
        if len(sorted_pages) == 2:
            first = sorted_pages[0]['text']
            last = sorted_pages[1]['text']
            return f"{first}-{last}"
        
        # Single page or multiple - take highest confidence span
        best = max(sorted_pages, key=lambda e: e['confidence'])
        return best['text']
    
    def _parse_author_string(self, author_text: str, confidence: float) -> List[Author]:
        """
        Parse author strings, handling merged authors like "Gu Y, Tinn R, Cheng H"
        Handles: single initials, multiple initials, 3+ word names, 5+ authors
        """
        logger.info(f"📝 Parsing author string: '{author_text}'")
        
        if not author_text:
            return []
        
        # CLEAN: Remove reference numbers like [26] or 27] at the start
        author_text = re.sub(r'^\s*\[?\d+\]\s*', '', author_text)
        
        # CLEAN: Remove title fragments (anything after a period followed by a capital letter)
        # E.g., "Lan Z, Chen M. Albert:" -> "Lan Z, Chen M"
        author_text = re.sub(r'\.\s*[A-Z][a-z]+.*$', '', author_text)
        
        logger.info(f"📝 After cleaning: '{author_text}'")
        
        # Final check
        if not author_text or len(author_text) < 2:
            return []
        
        authors = []
        
        # Remove " et al" and similar
        author_text = re.sub(r',?\s*(et\s+al\.?|and\s+others).*$', '', author_text, flags=re.IGNORECASE)
        
        # First, split on " and " or " & " to handle those delimiters
        and_parts = re.split(r'\s+(?:and|&)\s+', author_text)
        
        for and_part in and_parts:
            and_part = and_part.strip()
            if not and_part:
                continue
            
            # Check if this looks like merged authors by counting commas
            comma_count = and_part.count(',')
            
            if comma_count >= 2:
                # Likely merged authors: "Gu Y, Tinn R, Cheng H" or "Smith, J., Jones, P."
                # 
                # IMPROVED PATTERN:
                # Split on comma when followed by:
                # 1. Capital letter + lowercase (surname start): ", Smith"
                # 2. Capital letter + space + capital (initial + surname): ", Y Tinn"
                # 3. Capital letter alone or with period (surname alone): ", Y," or ", Y"
                #
                # Pattern explanation:
                # (?=[A-Z](?:[a-z]|\s+[A-Z]|[,\s]|$))
                # - [A-Z] = starts with capital
                # - (?:[a-z]|\s+[A-Z]|[,\s]|$) = followed by lowercase OR space+capital OR comma/space/end
                
                parts = re.split(r',\s+(?=[A-Z](?:[a-z]|\s+[A-Z]|[,\s]|$))', and_part)
                
                for part in parts:
                    part = part.strip().rstrip(',')
                    if part and len(part) > 1:  # Skip empty or single char
                        author = self._parse_single_author(part)
                        if author.surname or author.first_name:  # Valid author
                            authors.append(author)
            else:
                # Single author or simple format
                author = self._parse_single_author(and_part)
                if author.surname or author.first_name:
                    authors.append(author)
        
        # Limit to reasonable number (no hard limit, but log if excessive)
        if len(authors) > 20:
            logger.warning(f"⚠️ Extracted {len(authors)} authors, which seems excessive")
        
        logger.info(f"✅ Parsed {len(authors)} authors:")
        for i, author in enumerate(authors):
            logger.info(f"   Author {i+1}: first_name='{author.first_name}', surname='{author.surname}', full_name='{author.full_name}'")
        
        return authors
    
    def _parse_single_author(self, author_text: str) -> Author:
        """
        Parse a single author name
        Handles: "Surname, F.", "Surname F", "FirstName MiddleName Surname", "F. M. Surname"
        """
        author_text = author_text.strip().rstrip(',').rstrip('.').strip()
        
        # Handle empty
        if not author_text or len(author_text) < 2:
            return Author(first_name="", surname="", full_name="")
        
        if ',' in author_text:
            # "Surname, FirstName" format
            segments = author_text.split(',', 1)
            surname = segments[0].strip()
            first_name = segments[1].strip() if len(segments) > 1 else None
            
            return Author(
                first_name=first_name,
                surname=surname,
                full_name=author_text
            )
        else:
            # "FirstName Surname" format
            tokens = author_text.split()
            if len(tokens) >= 2:
                surname = tokens[-1]
                first_name = ' '.join(tokens[:-1])
                
                return Author(
                    first_name=first_name,
                    surname=surname,
                    full_name=author_text
                )
            else:
                # Single name
                return Author(full_name=author_text)
    
    def _infer_publication_type(self, 
                                journal: Optional[str],
                                publisher: Optional[str],
                                title: Optional[str]) -> Optional[str]:
        """
        Advanced: Infer publication type from entity patterns.
        No regex - uses string analysis.
        """
        if journal:
            # Check for conference indicators in journal name
            journal_lower = journal.lower()
            conf_keywords = ['proceedings', 'conference', 'workshop', 'symposium', 'conf.']
            
            for keyword in conf_keywords:
                if keyword in journal_lower:
                    return 'conference paper'
            
            return 'journal article'
        
        if publisher and not journal:
            return 'book'
        
        if title:
            title_lower = title.lower()
            if 'thesis' in title_lower or 'dissertation' in title_lower:
                return 'thesis'
        
        return None
    
    def _calculate_extraction_quality(self, 
                                     grouped: Dict[str, List[Dict]],
                                     result: ReferenceData) -> Tuple[float, List[str]]:
        """
        Advanced: Calculate overall quality score and identify ambiguities
        """
        # Count non-null fields
        filled_fields = sum(1 for field in [
            result.title, result.journal, result.year, result.volume,
            result.issue, result.pages, result.doi, result.url, result.publisher
        ] if field is not None)
        filled_fields += len(result.authors)
        
        # Average confidence of extracted entities
        all_confidences = []
        for ent_list in grouped.values():
            all_confidences.extend([e['confidence'] for e in ent_list])
        
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        
        # Identify ambiguities
        ambiguities = []
        for etype, ents in grouped.items():
            if len(ents) > 1:
                ambiguities.append(f"multiple_{etype.lower()}_detected")
        
        # Quality score: blend of field completeness and confidence
        quality_score = float((filled_fields / 10) * 0.5 + avg_confidence * 0.5)
        
        return quality_score, ambiguities
    
    def parse_reference_to_dict(self, raw_citation: str) -> dict:
        """
        Main parsing method - uses NER if available, otherwise regex fallback
        """
        # Step 1: Preprocess the text for better NER accuracy
        if PREPROCESSOR_AVAILABLE:
            preprocessed_citation = preprocess_reference(raw_citation)
        else:
            preprocessed_citation = raw_citation
        
        if not self.model_available or not self.parser:
            # Use regex-based fallback parsing
            return self._regex_fallback_parsing(preprocessed_citation)
        
        # Stage 1: Extract raw entities from PREPROCESSED text
        raw_entities = self._extract_raw_entities(preprocessed_citation)
        
        # Stage 2: Group and filter by type
        grouped = self._group_entities_by_type(raw_entities)
        
        # Stage 3: Resolve conflicts and build result
        result_data = {
            'title': None,
            'authors': [],
            'year': None,
            'journal': None,
            'volume': None,
            'issue': None,
            'pages': None,
            'doi': None,
            'url': None,
            'publisher': None,
            'publication_type': None,
            'raw_text': raw_citation,
            'confidence_scores': {},
            'entity_count': {k: len(v) for k, v in grouped.items()},
            'ambiguity_flags': []
        }
        
        # Title
        if 'TITLE' in grouped:
            title_entity = self._resolve_conflicts(grouped['TITLE'])
            if title_entity:
                result_data['title'] = title_entity['text']
                result_data['confidence_scores']['title'] = float(title_entity['confidence'])
        
        # Authors - LLM PRIMARY for 100% accuracy
        author_confidence = 0.0
        
        # STRATEGY: Use LLM first for maximum accuracy
        if self.llm_available:
            # Try LLM first (primary method)
            llm_authors = self._extract_authors_with_llm(raw_citation)
            if llm_authors:
                # Filter false positives
                llm_authors = self._filter_false_positive_authors(llm_authors)
                result_data['authors'] = llm_authors
                result_data['confidence_scores']['authors'] = 0.95  # High confidence with LLM
                result_data['ambiguity_flags'].append('llm_primary_extraction')
            else:
                # LLM failed, fallback to NER
                print("⚠️ LLM extraction failed, using NER fallback...")
                if 'AUTHORS' in grouped:
                    author_entity = self._resolve_conflicts(grouped['AUTHORS'])
                    if author_entity:
                        ner_authors = self._parse_author_string(
                            author_entity['text'],
                            author_entity['confidence']
                        )
                        filtered_authors = self._filter_false_positive_authors(ner_authors)
                        result_data['authors'] = filtered_authors
                        result_data['confidence_scores']['authors'] = float(author_entity['confidence'])
                        result_data['ambiguity_flags'].append('ner_fallback_used')
        else:
            # LLM not available, use NER only
            if 'AUTHORS' in grouped:
                author_entity = self._resolve_conflicts(grouped['AUTHORS'])
                if author_entity:
                    ner_authors = self._parse_author_string(
                        author_entity['text'],
                        author_entity['confidence']
                    )
                    filtered_authors = self._filter_false_positive_authors(ner_authors)
                    result_data['authors'] = filtered_authors
                    result_data['confidence_scores']['authors'] = float(author_entity['confidence'])
                    result_data['ambiguity_flags'].append('ner_only')
        
        # Year
        if 'YEAR' in grouped:
            year_entity = self._resolve_conflicts(grouped['YEAR'])
            if year_entity:
                # Extract numeric year from text
                year_text = year_entity['text']
                # Simple numeric extraction without regex
                numeric_chars = ''.join(c for c in year_text if c.isdigit())
                if len(numeric_chars) == 4:
                    try:
                        result_data['year'] = int(numeric_chars)
                        result_data['confidence_scores']['year'] = float(year_entity['confidence'])
                    except ValueError:
                        pass
        
        # Journal
        if 'JOURNAL' in grouped:
            journal_entity = self._resolve_conflicts(grouped['JOURNAL'])
            if journal_entity:
                result_data['journal'] = journal_entity['text']
                result_data['confidence_scores']['journal'] = float(journal_entity['confidence'])
        
        # Volume
        if 'VOLUME' in grouped:
            volume_entity = self._resolve_conflicts(grouped['VOLUME'])
            if volume_entity:
                result_data['volume'] = volume_entity['text']
                result_data['confidence_scores']['volume'] = float(volume_entity['confidence'])
        
        # Issue
        if 'ISSUE' in grouped:
            issue_entity = self._resolve_conflicts(grouped['ISSUE'])
            if issue_entity:
                result_data['issue'] = issue_entity['text']
                result_data['confidence_scores']['issue'] = float(issue_entity['confidence'])
        
        # Pages
        if 'PAGES' in grouped:
            pages_text = self._merge_page_entities(grouped['PAGES'])
            if pages_text:
                result_data['pages'] = pages_text
                avg_conf = sum(e['confidence'] for e in grouped['PAGES']) / len(grouped['PAGES'])
                result_data['confidence_scores']['pages'] = float(avg_conf)
        
        # DOI
        if 'DOI' in grouped:
            doi_entity = self._resolve_conflicts(grouped['DOI'])
            if doi_entity:
                result_data['doi'] = doi_entity['text']
                result_data['confidence_scores']['doi'] = float(doi_entity['confidence'])
        
        # URL
        if 'URL' in grouped:
            url_entity = self._resolve_conflicts(grouped['URL'])
            if url_entity:
                result_data['url'] = url_entity['text']
                result_data['confidence_scores']['url'] = float(url_entity['confidence'])
        
        # Publisher
        if 'PUBLISHER' in grouped:
            pub_entity = self._resolve_conflicts(grouped['PUBLISHER'])
            if pub_entity:
                result_data['publisher'] = pub_entity['text']
                result_data['confidence_scores']['publisher'] = float(pub_entity['confidence'])
        
        # Infer publication type
        result_data['publication_type'] = self._infer_publication_type(
            result_data['journal'],
            result_data['publisher'],
            result_data['title']
        )
        
        # Build Pydantic model
        result = ReferenceData(**result_data)
        
        # Calculate quality metrics
        quality_score, ambiguities = self._calculate_extraction_quality(grouped, result)
        result.confidence_scores['overall'] = float(quality_score)
        result.ambiguity_flags = ambiguities
        
        return result.model_dump(by_alias=True)
    
    def parse_batch(self, citations: List[str]) -> List[dict]:
        """Batch processing"""
        return [self.parse_reference_to_dict(c) for c in citations]


# ==================== TEST WITH DIVERSE INPUTS ====================

if __name__ == "__main__":
    # Test pure NER on diverse, challenging citations
    parser = AdvancedNERParser(
        confidence_threshold=0.5,
        enable_entity_disambiguation=True,
        enable_confidence_weighting=True
    )
    
    test_cases = [
        # Standard journal article
        """Smith, John A., and Jane Doe. "Machine Learning in Healthcare: A Review."
        Journal of Medical AI 15, no. 3 (2023): 234-256. https://doi.org/10.1234/jmai.2023.15.3.234""",
        
        # Abbreviated format
        "Doe, J. (2020). Deep Learning. Nature, 10(2), 45-67.",
        
        # Multiple authors, abbreviated journal
        "Wang, L., Zhang, M. (2021). Neural Networks in Medicine. IEEE Trans. 15:120-135. DOI:10.1109/example",
        
        # Book format
        "Goodfellow, Ian; Bengio, Yoshua; Courville, Aaron. Deep Learning. MIT Press, 2016.",
        
        # Conference paper
        "Lin, X.; Rao, P. (2019). Vision Transformers in Practice. Proceedings of the IEEE CVPR, 22(6): 100-110.",
        
        # Complex with ISSN
        "Brown, T. (2018). Data Methods. Journal of Data Sci., 12(4), 200-212. ISSN 1234-5678. https://example.org/paper.pdf",
        
        # Edge case: minimal info
        "Anonymous (2022). A Study. Unknown Journal.",
        
        # Edge case: many authors
        "Lee, A., Kim, B., Park, C., and Choi, D. (2021). Title Here. Nature Communications, 12:456.",
    ]
    
    for i, citation in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"Citation {i}:")
        print(f"{'='*80}")
        print(f"Input: {citation[:100]}...")
        print()
        
        result = parser.parse_reference_to_dict(citation)
        
        # Pretty print with highlights
        print(f"EXTRACTED FIELDS:")
        print(f"  Title: {result['title']}")
        print(f"  Authors: {len(result['authors'])} detected")
        for author in result['authors']:
            print(f"    - {author.get('full_name', 'N/A')} (surname: {author.get('surname', 'N/A')})")
        print(f"  Year: {result['year']}")
        print(f"  Journal: {result['journal']}")
        print(f"  Volume: {result['volume']}, Issue: {result['issue']}, Pages: {result['pages']}")
        print(f"  DOI: {result['doi']}")
        print(f"  URL: {result['url']}")
        print(f"  Type: {result['publication_type']}")
        print()
        print(f"QUALITY METRICS:")
        print(f"  Overall Score: {result['confidence_scores'].get('overall', 0):.2f}")
        print(f"  Entity Counts: {result['entity_count']}")
        print(f"  Ambiguities: {result['ambiguity_flags'] if result['ambiguity_flags'] else 'None'}")
        print(f"  Field Confidences: {json.dumps({k: f'{v:.2f}' for k, v in result['confidence_scores'].items() if k != 'overall'}, indent=4)}")
    
    def _regex_fallback_parsing(self, raw_citation: str) -> dict:
        """
        Regex-based fallback parsing when NER model is not available
        """
        import re
        
        result = {
            'title': None,
            'authors': [],
            'year': None,
            'journal': None,
            'volume': None,
            'issue': None,
            'pages': None,
            'doi': None,
            'url': None,
            'publisher': None,
            'publication_type': None,
            'raw_text': raw_citation,
            'confidence_scores': {'overall': 0.5},
            'entity_count': {},
            'ambiguity_flags': [],
            'missing_fields': []
        }
        
        # Extract year
        year_match = re.search(r'\b(19|20)\d{2}\b', raw_citation)
        if year_match:
            result['year'] = int(year_match.group())
            result['confidence_scores']['year'] = 0.8
        
        # Extract DOI
        doi_match = re.search(r'10\.\d+/[^\s]+', raw_citation)
        if doi_match:
            result['doi'] = doi_match.group()
            result['confidence_scores']['doi'] = 0.9
        
        # Extract URL
        url_match = re.search(r'https?://[^\s]+', raw_citation)
        if url_match:
            result['url'] = url_match.group()
            result['confidence_scores']['url'] = 0.9
        
        # Extract pages
        pages_match = re.search(r'(\d+)(?:[-–—]\s*(\d+))?(?:\s*[,\s]|$)', raw_citation)
        if pages_match:
            if pages_match.group(2):
                result['pages'] = f"{pages_match.group(1)}-{pages_match.group(2)}"
            else:
                result['pages'] = pages_match.group(1)
            result['confidence_scores']['pages'] = 0.7
        
        # Extract authors (simple pattern)
        author_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        authors = re.findall(author_pattern, raw_citation)
        if authors:
            for author in authors[:5]:  # Limit to 5 authors
                if len(author.split()) >= 2:  # At least first and last name
                    name_parts = author.split()
                    result['authors'].append(Author(
                        first_name=name_parts[0],
                        surname=name_parts[-1],
                        full_name=author
                    ))
            result['confidence_scores']['authors'] = 0.6
        
        # Extract title (text between authors and year/journal)
        title_pattern = r'(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*[,\s]*)*([^,]+?)(?:\s*,\s*(?:19|20)\d{2}|\s*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        title_match = re.search(title_pattern, raw_citation)
        if title_match:
            title = title_match.group(1).strip()
            if len(title) > 10:  # Reasonable title length
                result['title'] = title
                result['confidence_scores']['title'] = 0.7
        
        # Extract journal (text after title, before year)
        journal_pattern = r'(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*[,\s]*)*[^,]+?,\s*([^,]+?)(?:\s*,\s*(?:19|20)\d{2})'
        journal_match = re.search(journal_pattern, raw_citation)
        if journal_match:
            journal = journal_match.group(1).strip()
            if len(journal) > 3:  # Reasonable journal name length
                result['journal'] = journal
                result['confidence_scores']['journal'] = 0.6
        
        # Calculate overall confidence
        confidences = [v for k, v in result['confidence_scores'].items() if k != 'overall']
        if confidences:
            result['confidence_scores']['overall'] = float(sum(confidences) / len(confidences))
        
        # Identify missing fields
        missing_fields = []
        if not result['title']:
            missing_fields.append('title')
        if not result['authors']:
            missing_fields.append('authors')
        if not result['year']:
            missing_fields.append('year')
        if not result['journal']:
            missing_fields.append('journal')
        
        result['missing_fields'] = missing_fields
        
        return result
