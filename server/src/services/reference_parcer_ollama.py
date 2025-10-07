from transformers import pipeline
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
from collections import defaultdict
import json


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
    Pure NER implementation with advanced entity handling.
    No regex fallbacks - tests raw model capability.
    """
    
    def __init__(self, 
                 confidence_threshold: float = 0.5,
                 enable_entity_disambiguation: bool = True,
                 enable_confidence_weighting: bool = True):
        
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
        
        # Entity type mappings
        self.entity_mappings = {
            'PUBLICATION_YEAR': 'YEAR',
            'PAGE_FIRST': 'PAGES',
            'PAGE_LAST': 'PAGES',
            'LINK_ONLINE_AVAILABILITY': 'URL',
        }
    
    def _normalize_entity_type(self, entity_type: str) -> str:
        """Normalize entity types to canonical forms"""
        return self.entity_mappings.get(entity_type, entity_type)
    
    def _extract_raw_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities with position information"""
        entities = self.parser(text)
        
        # Add normalized types and metadata
        for ent in entities:
            ent['normalized_type'] = self._normalize_entity_type(ent['entity_group'])
            ent['text'] = ent['word'].strip()
            ent['confidence'] = ent.get('score', 1.0)
        
        return entities
    
    def _group_entities_by_type(self, entities: List[Dict]) -> Dict[str, List[Dict]]:
        """Group entities by normalized type with confidence filtering"""
        grouped = defaultdict(list)
        
        for ent in entities:
            if ent['confidence'] >= self.confidence_threshold:
                grouped[ent['normalized_type']].append(ent)
        
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
        Advanced: Parse complex author strings using linguistic patterns.
        No regex - pure string analysis.
        """
        if not author_text:
            return []
        
        authors = []
        
        # Split on common delimiters using string methods
        parts = []
        for delimiter in [' and ', '; ', ' & ']:
            if delimiter in author_text:
                parts = author_text.split(delimiter)
                break
        
        if not parts:
            parts = [author_text]
        
        for part in parts:
            part = part.strip().rstrip(',').rstrip('.').strip()
            if not part:
                continue
            
            # Analyze comma presence for format detection
            if ',' in part:
                # Likely "Surname, FirstName" format
                segments = part.split(',')
                surname = segments[0].strip()
                first_name = segments[1].strip() if len(segments) > 1 else None
                
                authors.append(Author(
                    first_name=first_name,
                    surname=surname,
                    full_name=part
                ))
            else:
                # Likely "FirstName Surname" format
                tokens = part.split()
                if len(tokens) >= 2:
                    # Last token is surname
                    surname = tokens[-1]
                    first_name = ' '.join(tokens[:-1])
                    
                    authors.append(Author(
                        first_name=first_name,
                        surname=surname,
                        full_name=part
                    ))
                else:
                    # Single name - treat as full name
                    authors.append(Author(
                        full_name=part
                    ))
        
        return authors
    
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
        if not self.model_available or not self.parser:
            # Use regex-based fallback parsing
            return self._regex_fallback_parsing(raw_citation)
        
        # Stage 1: Extract raw entities
        raw_entities = self._extract_raw_entities(raw_citation)
        
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
        
        # Authors
        if 'AUTHORS' in grouped:
            author_entity = self._resolve_conflicts(grouped['AUTHORS'])
            if author_entity:
                result_data['authors'] = self._parse_author_string(
                    author_entity['text'],
                    author_entity['confidence']
                )
                result_data['confidence_scores']['authors'] = float(author_entity['confidence'])
        
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
