"""
Shared utility module for generating consistent XML tagged output for all references.
This ensures all parsers produce the same standardized bibitem format.

REDESIGNED: Now uses reference type classification and strict tag schemas
to prevent semantic errors in XML generation.
"""
import re
import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from loguru import logger

from .reference_classifier import (
    ReferenceType,
    ReferenceTypeClassifier,
    ReferenceTagSchema,
    normalize_doi
)
from .strict_normalization_validator import StrictNormalizationValidator
from .safe_string_utils import safe_strip, is_valid_doi


def extract_volume_issue_info(parsed_ref: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract volume and issue information from parsed reference.
    Can be called from any parser to ensure consistent extraction.
    """
    volume_info = {"volume": "", "issue": ""}
    
    # Try to extract from journal field
    journal_text = parsed_ref.get("journal", "")
    if journal_text:
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


def normalize_parsed_reference(parsed_ref: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize parsed reference data to ensure consistent format across all parsers.
    This handles different data structures from NER, simple parser, and API enrichments.
    """
    normalized = {
        "family_names": [],
        "given_names": [],
        "full_names": [],
        "year": None,
        "title": "",
        "journal": "",
        "volume": "",
        "issue": "",
        "pages": "",
        "doi": "",
        "url": "",
        "publisher": "",
        "abstract": ""
    }
    
    # Handle family_names - can be list or single value
    # CRITICAL: Preserve all entries to maintain alignment with given_names
    # Filter empty values but maintain index alignment
    family_names = parsed_ref.get("family_names", [])
    if isinstance(family_names, str):
        family_names = [family_names] if family_names else []
    elif not isinstance(family_names, list):
        family_names = []
    # Keep all entries, even empty ones, to maintain alignment with given_names
    # Empty strings will be filtered out in tagging code when creating valid_authors
    normalized["family_names"] = [str(f).strip() if f else "" for f in family_names]
    
    # Handle given_names - can be list or single value
    # IMPORTANT: Keep empty strings to maintain alignment with family_names
    # Empty strings will be handled in tagging code (skipped if empty)
    given_names = parsed_ref.get("given_names", [])
    if isinstance(given_names, str):
        given_names = [given_names] if given_names else []
    elif not isinstance(given_names, list):
        given_names = []
    # Don't filter out empty strings - keep them to maintain list alignment
    normalized["given_names"] = [str(g).strip() if g else "" for g in given_names]
    
    # Ensure both lists have the same length for proper alignment
    max_len = max(len(normalized["family_names"]), len(normalized["given_names"]))
    while len(normalized["family_names"]) < max_len:
        normalized["family_names"].append("")
    while len(normalized["given_names"]) < max_len:
        normalized["given_names"].append("")
    
    # Handle full_names - prioritize from API, or build from family + given
    full_names = parsed_ref.get("full_names", [])
    if isinstance(full_names, str):
        full_names = [full_names] if full_names else []
    elif not isinstance(full_names, list):
        full_names = []
    
    if full_names:
        normalized["full_names"] = [str(f).strip() for f in full_names if f]
    else:
        # Build from family_names + given_names
        for i, family in enumerate(normalized["family_names"]):
            given = normalized["given_names"][i] if i < len(normalized["given_names"]) else ""
            if given and family:
                normalized["full_names"].append(f"{given} {family}")
            elif family:
                normalized["full_names"].append(family)
    
    # Handle authors field (from NER parser) - convert to family/given/full_names
    authors = parsed_ref.get("authors", [])
    if authors and not normalized["family_names"]:
        for author in authors:
            if isinstance(author, dict):
                surname = author.get("surname") or author.get("family_name") or author.get("last_name", "")
                given_name = author.get("first_name") or author.get("given_name", "")
                full_name = author.get("full_name", "")
                
                if surname:
                    normalized["family_names"].append(surname)
                if given_name:
                    normalized["given_names"].append(given_name)
                if full_name:
                    normalized["full_names"].append(full_name)
                elif surname and given_name:
                    normalized["full_names"].append(f"{given_name} {surname}")
            elif isinstance(author, str):
                # Try to parse author string
                name_parts = author.strip().split()
                if len(name_parts) >= 2:
                    normalized["family_names"].append(name_parts[-1])
                    normalized["given_names"].append(" ".join(name_parts[:-1]))
                    normalized["full_names"].append(author.strip())
                elif len(name_parts) == 1:
                    normalized["family_names"].append(name_parts[0])
                    normalized["full_names"].append(name_parts[0])
    
    # Handle scalar fields
    normalized["year"] = parsed_ref.get("year")
    if normalized["year"]:
        try:
            normalized["year"] = int(normalized["year"])
        except (ValueError, TypeError):
            normalized["year"] = None
    
    # Handle scalar string fields - ensure None becomes empty string, not "None"
    # Use safe_strip to prevent NoneType errors (FIX #1)
    normalized["title"] = safe_strip(parsed_ref.get("title")) or ""
    normalized["journal"] = safe_strip(parsed_ref.get("journal")) or ""
    normalized["pages"] = safe_strip(parsed_ref.get("pages")) or ""
    normalized["doi"] = safe_strip(parsed_ref.get("doi")) or ""
    normalized["url"] = safe_strip(parsed_ref.get("url")) or ""
    normalized["publisher"] = safe_strip(parsed_ref.get("publisher")) or ""
    normalized["abstract"] = safe_strip(parsed_ref.get("abstract")) or ""
    normalized["article_number"] = safe_strip(parsed_ref.get("article_number")) or ""
    
    # Handle volume/issue - may be in separate fields or embedded in journal
    volume_info = extract_volume_issue_info(parsed_ref)
    normalized["volume"] = volume_info.get("volume", "")
    normalized["issue"] = volume_info.get("issue", "")
    
    # Issue field may contain month names after conflict resolution
    # No separate issue_month field needed
    
    return normalized


def generate_tagged_output(parsed_ref: Dict[str, Any], index: int) -> str:
    """
    Generate standardized XML tagged output matching the bibitem format.
    
    REDESIGNED: Now uses reference type classification and strict tag schemas
    to ensure semantically correct XML output.
    
    Pipeline:
    1. Normalize parsed reference
    2. Classify reference type
    3. STRICT NORMALIZATION & VALIDATION (NEW)
       - Normalize page ranges
       - Enforce canonical DOI format
       - Resolve issue conflicts
       - Validate core constraints
    4. Generate XML using type-specific schema
    5. Validate schema compliance
    6. Return XML or flag errors
    
    Args:
        parsed_ref: Dictionary containing parsed reference data (from any parser)
        index: Zero-based index of the reference
        
    Returns:
        XML string in bibitem format (semantically correct)
    """
    # Step 1: Normalize the parsed reference
    ref = normalize_parsed_reference(parsed_ref)
    
    # Step 1a: Normalize author names with particles (before classification)
    from .name_particle_normalizer import normalize_author_list
    if ref.get("family_names") and ref.get("given_names"):
        normalized_family, normalized_given = normalize_author_list(
            ref.get("family_names", []),
            ref.get("given_names", [])
        )
        ref["family_names"] = normalized_family
        ref["given_names"] = normalized_given
    
    # Step 2: Classify reference type
    classifier = ReferenceTypeClassifier()
    ref_type = classifier.classify(ref)
    
    # Step 3: STRICT NORMALIZATION & VALIDATION (BEFORE XML GENERATION)
    validator = StrictNormalizationValidator()
    
    # Apply strict normalization directly on dict (avoids Reference model dependency)
    norm_errors, can_generate_xml = _apply_strict_normalization(ref, ref_type, validator)
    
    # Log normalization errors
    if norm_errors:
        logger.warning(f"Reference {index + 1} normalization: {norm_errors}")
    
    # If core constraints violated, return error XML instead
    if not can_generate_xml:
        logger.error(f"Reference {index + 1} core constraints violated - blocking XML generation")
        return _generate_error_xml(index, norm_errors)
    
    # Step 4: Generate XML using type-specific schema
    xml_parts = _generate_xml_by_type(ref, ref_type, index)
    
    # Step 5: Extract used tags for validation
    used_tags = _extract_used_tags(''.join(xml_parts))
    
    # Step 6: Validate schema compliance
    is_valid, errors = ReferenceTagSchema.validate_schema(ref_type, used_tags)
    
    if not is_valid:
        logger.warning(f"Reference {index + 1} schema validation errors: {errors}")
        # Still return XML but log errors for quality tracking
    
    return ''.join(xml_parts)


def _apply_strict_normalization(
    ref: Dict[str, Any], 
    ref_type: ReferenceType, 
    validator: StrictNormalizationValidator
) -> Tuple[List[str], bool]:
    """
    Apply strict normalization and validation to reference dict.
    
    Returns:
        (errors, can_generate_xml)
    """
    errors = []
    can_generate_xml = True
    
    # 1. Normalize DOI (STRICT VALIDATION)
    doi = ref.get("doi", "").strip()
    if doi:
        from .safe_string_utils import is_valid_doi
        
        # Remove DOI prefixes and normalize
        normalized_doi = normalize_doi(doi)
        
        # STRICT VALIDATION: Use is_valid_doi for comprehensive validation
        if not is_valid_doi(normalized_doi):
            errors.append(f"DOI format invalid: '{doi}' → '{normalized_doi}'")
            # Try to fix
            fixed_doi = _attempt_doi_fix(normalized_doi)
            if fixed_doi and is_valid_doi(fixed_doi):
                normalized_doi = fixed_doi
                errors.append(f"DOI auto-corrected to: '{normalized_doi}'")
            else:
                # Invalid DOI - remove it (reject article numbers, volume strings, etc.)
                logger.warning(f"Rejecting invalid DOI: '{doi}' (normalized: '{normalized_doi}')")
                ref["doi"] = None
        else:
            ref["doi"] = normalized_doi
    
    # 2. Normalize page ranges and separate article numbers (with publisher-specific rules)
    pages = ref.get("pages", "").strip()
    if pages:
        from .page_article_separator import separate_pages_and_article_number
        
        # Get DOI for publisher-specific detection
        doi = ref.get("doi", "").strip()
        
        # Separate pages and article numbers (handles cases where both exist)
        # Pass DOI to enable publisher-specific rules (Elsevier, Frontiers)
        normalized_pages, article_number = separate_pages_and_article_number(pages, doi=doi)
        
        # Set article number if found
        if article_number:
            ref["article_number"] = article_number
            errors.append(f"Extracted article number from pages string: '{article_number}'")
        
        # Normalize page range
        if normalized_pages:
            first_page, last_page = validator.extract_page_range(normalized_pages)
            if first_page:
                if last_page:
                    ref["pages"] = f"{first_page}-{last_page}"
                else:
                    ref["pages"] = first_page
            else:
                errors.append(f"Invalid page format: '{normalized_pages}'")
                ref["pages"] = None
        else:
            # No pages found - might be article number only
            if article_number:
                ref["pages"] = None
            else:
                errors.append(f"Could not parse pages/article number from: '{pages}'")
                ref["pages"] = None
    
    # 3. Resolve issue conflicts (month vs numeric)
    issue = ref.get("issue", "").strip()
    if issue:
        # Check for month patterns
        month_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', issue, re.IGNORECASE)
        number_match = re.search(r'\b\d+\b', issue)
        
        if month_match and number_match:
            # Conflict: both present - prefer numeric
            ref["issue"] = number_match.group(0)
            errors.append(f"Issue conflict resolved: '{issue}' → '{number_match.group(0)}' (preferred numeric)")
        elif month_match and not number_match:
            # Only month - keep in issue field (may be converted to number by validator)
            # If conversion failed, keep month name as-is
            errors.append(f"Issue contains month name: '{issue}' (keeping as-is)")
    
    # 4. Validate core constraints (type-specific)
    if ref_type == ReferenceType.JOURNAL_ARTICLE:
        # Must have venue (journal name)
        if not ref.get("journal") or not ref.get("journal", "").strip():
            errors.append("JOURNAL_ARTICLE must have venue (journal name) - XML generation blocked")
            can_generate_xml = False
        
        # Must have title
        if not ref.get("title") or not ref.get("title", "").strip():
            errors.append("JOURNAL_ARTICLE must have title - XML generation blocked")
            can_generate_xml = False
        
        # Must have at least one author
        if not ref.get("family_names") and not ref.get("full_names"):
            errors.append("JOURNAL_ARTICLE must have at least one author - XML generation blocked")
            can_generate_xml = False
        
        # Should have volume OR issue OR pages OR article_number
        # CRITICAL: Do not require pages for Elsevier/Frontiers (they use article numbers)
        has_identifying_info = bool(
            ref.get("volume") or
            ref.get("issue") or
            ref.get("pages") or
            ref.get("article_number")
        )
        if not has_identifying_info:
            errors.append("JOURNAL_ARTICLE should have volume, issue, pages, or article_number - XML generation blocked")
            can_generate_xml = False
        
        # Cannot have publisher
        if ref.get("publisher"):
            errors.append(f"JOURNAL_ARTICLE cannot have publisher: '{ref['publisher']}' - removing")
            ref["publisher"] = None
        
        # Cannot have conference_name
        if ref.get("conference_name"):
            errors.append(f"JOURNAL_ARTICLE cannot have conference_name: '{ref['conference_name']}' - removing")
            ref["conference_name"] = None
    
    elif ref_type == ReferenceType.REPORT:
        # Must have title
        if not ref.get("title") or not ref.get("title", "").strip():
            errors.append("REPORT must have title - XML generation blocked")
            can_generate_xml = False
        
        # Must have publisher (organization)
        if not ref.get("publisher") or not ref.get("publisher", "").strip():
            errors.append("REPORT must have publisher (organization) - XML generation blocked")
            can_generate_xml = False
        
        # Must have at least one author
        if not ref.get("family_names") and not ref.get("full_names"):
            errors.append("REPORT must have at least one author - XML generation blocked")
            can_generate_xml = False
        
        # CRITICAL: Reports do NOT require pages, volume, issue
        # Remove journal fields if present
        if ref.get("journal"):
            errors.append(f"REPORT cannot have journal: '{ref['journal']}' - removing")
            ref["journal"] = None
        
        if ref.get("volume"):
            errors.append(f"REPORT cannot have volume: '{ref['volume']}' - removing")
            ref["volume"] = None
        
        if ref.get("issue"):
            errors.append(f"REPORT cannot have issue: '{ref['issue']}' - removing")
            ref["issue"] = None
    
    return errors, can_generate_xml


def _attempt_doi_fix(doi: str) -> Optional[str]:
    """Attempt to fix common DOI format issues"""
    # Remove leading/trailing punctuation
    doi = doi.strip('.,;:()[]{}')
    
    # Ensure starts with "10."
    if not doi.startswith('10.'):
        match = re.search(r'10\.\d+', doi)
        if match:
            doi = doi[match.start():]
    
    # Ensure has a slash
    if '/' not in doi:
        match = re.match(r'(10\.\d{4,})(.+)', doi)
        if match:
            doi = f"{match.group(1)}/{match.group(2)}"
    
    return doi if re.match(r'^10\.\d{4,}/[^\s]+$', doi) else None


def _generate_error_xml(index: int, errors: List[str]) -> str:
    """Generate error XML when core constraints are violated"""
    label_id = f"bib{index + 1}"
    error_message = "; ".join(errors[:3])  # Limit to first 3 errors
    return f'<bibitem><label id="{label_id}">INVALID REFERENCE</label><x> </x><error>Core constraints violated: {error_message}</error></bibitem>'


def _generate_xml_by_type(ref: Dict[str, Any], ref_type: ReferenceType, index: int) -> List[str]:
    """
    Generate XML parts based on reference type and schema.
    
    Args:
        ref: Normalized reference dictionary
        ref_type: Classified reference type
        index: Reference index
        
    Returns:
        List of XML string parts
    """
    xml_parts = []
    
    # Generate label (common to all types)
    label_id = f"bib{index + 1}"
    family_names = ref.get("family_names", [])
    year = ref.get("year") or "n.d."
    
    if family_names:
        first_author = family_names[0]
        if len(family_names) == 1:
            label_text = f"{first_author}, {year}"
        else:
            label_text = f"{first_author} et al., {year}"
    else:
        label_text = f"Reference {index + 1}, {year}"
    
    xml_parts.append(f'<bibitem><label id="{label_id}">{label_text}</label>')
    
    # Generate authors (common to all types)
    authors_xml = _generate_authors_xml(ref)
    xml_parts.append(authors_xml)
    
    # Add year
    year = ref.get("year")
    if year:
        xml_parts.append('<x>, </x><adate>')
        xml_parts.append(str(year))
        xml_parts.append('</adate>')
    
    # Generate type-specific content
    schema = ReferenceTagSchema.get_allowed_tags(ref_type)
    
    if ref_type == ReferenceType.JOURNAL_ARTICLE:
        xml_parts.extend(_generate_journal_article_xml(ref, schema))
    elif ref_type == ReferenceType.BOOK:
        xml_parts.extend(_generate_book_xml(ref, schema))
    elif ref_type == ReferenceType.CONFERENCE_PAPER:
        xml_parts.extend(_generate_conference_paper_xml(ref, schema))
    elif ref_type == ReferenceType.BOOK_CHAPTER:
        xml_parts.extend(_generate_book_chapter_xml(ref, schema))
    elif ref_type == ReferenceType.REPORT:
        xml_parts.extend(_generate_report_xml(ref, schema))
    elif ref_type == ReferenceType.THESIS:
        xml_parts.extend(_generate_thesis_xml(ref, schema))
    else:  # UNKNOWN
        # Generate minimal XML and flag as invalid
        title = safe_strip(ref.get("title")) or ""
        if title and "atl" in schema:
            xml_parts.append('<x>. </x><atl>')
            xml_parts.append(title)
            xml_parts.append('</atl>')
        elif title and "btl" in schema:
            xml_parts.append('<x>. </x><btl>')
            xml_parts.append(title)
            xml_parts.append('</btl>')
        logger.error(f"Reference {index + 1} classified as UNKNOWN - XML may be invalid")
    
    # Add DOI (allowed for all types) - already normalized by strict validator
    doi = safe_strip(ref.get("doi")) or ""
    if doi and "doi" in schema:
        from .safe_string_utils import is_valid_doi
        
        # STRICT VALIDATION: Double-check format using is_valid_doi (already imported)
        if is_valid_doi(doi):
            xml_parts.append('<x>. </x><doi>')
            xml_parts.append(doi)
            xml_parts.append('</doi>')
        else:
            logger.warning(f"Reference {index + 1}: DOI format still invalid after normalization: {doi}")
    
    url = safe_strip(ref.get("url")) or ""
    if url and "url" in schema:
        xml_parts.append('<x>. </x><url url="')
        xml_parts.append(url)
        xml_parts.append('" title="')
        xml_parts.append(url)
        xml_parts.append('">')
        xml_parts.append(url)
        xml_parts.append('</url>')
    
    # Close bibitem
    xml_parts.append('<x>.</x></bibitem>')
    
    return xml_parts


def _generate_journal_article_xml(ref: Dict[str, Any], schema: Set[str]) -> List[str]:
    """Generate XML for journal articles with normalized page ranges"""
    parts = []
    title = safe_strip(ref.get("title")) or ""
    
    # Prefer API journal title for better casing (e.g., "Cell Metabolism" vs "cell metabolism")
    journal = safe_strip(ref.get("journal")) or ""
    api_journal = safe_strip(ref.get("api_journal")) or safe_strip(ref.get("enrichment_journal")) or ""
    if api_journal:
        journal = api_journal
    
    if title and "atl" in schema:
        parts.append('<x>. </x><atl>')
        parts.append(title)
        parts.append('</atl>')
    
    if journal and "stl" in schema:
        parts.append('<x>. </x><stl>')
        parts.append(journal)
        parts.append('</stl>')
        
        volume_info = extract_volume_issue_info(ref)
        if volume_info.get("volume") and "vol" in schema:
            parts.append('<x> </x><vol>')
            parts.append(str(volume_info["volume"]))
            parts.append('</vol>')
        
        # Issue handling - use normalized issue (may contain month name if conflict resolution kept it)
        issue = safe_strip(ref.get("issue")) or ""
        
        if issue and "iss" in schema:
            parts.append('<x>(</x><iss>')
            parts.append(str(issue))
            parts.append('</iss><x>)</x>')
    
    # Pages AND article number (both can exist together)
    article_number = safe_strip(ref.get("article_number")) or ""
    pages = safe_strip(ref.get("pages")) or ""
    
    # CRITICAL: Both pages and article_number can be emitted together
    # Pages come first, then article number
    has_pages = False
    
    if pages and "first-page" in schema:
        # Extract page range
        from .page_article_separator import extract_first_last_page
        first_page, last_page = extract_first_last_page(pages)
        
        if first_page:
            parts.append('<x> </x>')
            has_pages = True
            if last_page:
                # Page range
                parts.append('<first-page>')
                parts.append(first_page)
                parts.append('</first-page><x>-</x><last-page>')
                parts.append(last_page)
                parts.append('</last-page>')
            else:
                # Single page
                parts.append('<first-page>')
                parts.append(first_page)
                parts.append('</first-page>')
    
    # Article number (can be emitted even if pages exist)
    if article_number and "atlno" in schema:
        # Clean article number: remove punctuation, ensure it's just the number
        article_number = article_number.strip().rstrip('.,;:')
        # Remove any leading/trailing spaces or punctuation
        article_number = re.sub(r'^[^\w]*', '', article_number)
        article_number = re.sub(r'[^\w]*$', '', article_number)
        
        if article_number:
            # Add separator if pages were emitted
            if has_pages:
                parts.append('<x>, </x>')
            else:
                parts.append('<x> </x>')
            
            parts.append('<atlno>')
            parts.append(article_number)
            parts.append('</atlno>')
    
    return parts


def _generate_book_xml(ref: Dict[str, Any], schema: Set[str]) -> List[str]:
    """Generate XML for books"""
    parts = []
    title = safe_strip(ref.get("title")) or ""
    
    if title and "btl" in schema:
        parts.append('<x>. </x><btl>')
        parts.append(title)
        parts.append('</btl>')
    
    publisher = safe_strip(ref.get("publisher")) or ""
    if publisher and "pub" in schema:
        parts.append('<x>. </x><pub>')
        parts.append(publisher)
        parts.append('</pub>')
    
    # Note: city field not currently extracted, but would go here if available
    # if city and "city" in schema:
    #     parts.append('<x>. </x><city>')
    #     parts.append(city)
    #     parts.append('</city>')
    
    return parts


def _generate_conference_paper_xml(ref: Dict[str, Any], schema: Set[str]) -> List[str]:
    """Generate XML for conference papers"""
    parts = []
    title = safe_strip(ref.get("title")) or ""
    journal = safe_strip(ref.get("journal")) or ""  # May contain conference name
    
    if title and "atl" in schema:
        parts.append('<x>. </x><atl>')
        parts.append(title)
        parts.append('</atl>')
    
    # Conference title goes in <ebtl>
    if journal and "ebtl" in schema:
        parts.append('<x>. </x><ebtl>')
        parts.append(journal)
        parts.append('</ebtl>')
    
    publisher = safe_strip(ref.get("publisher")) or ""
    if publisher and "pub" in schema:
        parts.append('<x>. </x><pub>')
        parts.append(publisher)
        parts.append('</pub>')
    
    # Pages
    pages = safe_strip(ref.get("pages")) or ""
    if pages and "first-page" in schema:
        parts.append('<x>: </x>')
        if '-' in pages or '–' in pages or '—' in pages:
            page_parts = re.split(r'[-–—]', pages, 1)
            if len(page_parts) == 2:
                parts.append('<first-page>')
                parts.append(page_parts[0].strip())
                parts.append('</first-page><x>-</x><last-page>')
                parts.append(page_parts[1].strip())
                parts.append('</last-page>')
            else:
                parts.append('<first-page>')
                parts.append(pages)
                parts.append('</first-page>')
        else:
            parts.append('<first-page>')
            parts.append(pages)
            parts.append('</first-page>')
    
    return parts


def _generate_book_chapter_xml(ref: Dict[str, Any], schema: Set[str]) -> List[str]:
    """Generate XML for book chapters"""
    parts = []
    title = safe_strip(ref.get("title")) or ""
    
    if title and "atl" in schema:
        parts.append('<x>. </x><atl>')
        parts.append(title)
        parts.append('</atl>')
    
    # Book title (may be in journal field or need extraction)
    journal = safe_strip(ref.get("journal")) or ""
    if journal and "ebtl" in schema:
        parts.append('<x>. In </x><ebtl>')
        parts.append(journal)
        parts.append('</ebtl>')
    
    publisher = safe_strip(ref.get("publisher")) or ""
    if publisher and "pub" in schema:
        parts.append('<x>: </x><pub>')
        parts.append(publisher)
        parts.append('</pub>')
    
    # Pages
    pages = safe_strip(ref.get("pages")) or ""
    if pages and "first-page" in schema:
        parts.append('<x>, </x>')
        if '-' in pages or '–' in pages or '—' in pages:
            page_parts = re.split(r'[-–—]', pages, 1)
            if len(page_parts) == 2:
                parts.append('<first-page>')
                parts.append(page_parts[0].strip())
                parts.append('</first-page><x>–</x><last-page>')
                parts.append(page_parts[1].strip())
                parts.append('</last-page>')
            else:
                parts.append('<first-page>')
                parts.append(pages)
                parts.append('</first-page>')
        else:
            parts.append('<first-page>')
            parts.append(pages)
            parts.append('</first-page>')
    
    return parts


def _generate_report_xml(ref: Dict[str, Any], schema: Set[str]) -> List[str]:
    """Generate XML for reports"""
    parts = []
    title = safe_strip(ref.get("title")) or ""
    
    # Reports use <atl> (article title), not <btl>
    if title and "atl" in schema:
        parts.append('<x>. </x><atl>')
        parts.append(title)
        parts.append('</atl>')
    
    # Publisher (organization) is REQUIRED for reports
    publisher = safe_strip(ref.get("publisher")) or ""
    if publisher and "pub" in schema:
        parts.append('<x>. </x><pub>')
        parts.append(publisher)
        parts.append('</pub>')
    
    # Report number (if available) can go in msc3
    report_number = safe_strip(ref.get("report_number")) or safe_strip(ref.get("msc3")) or ""
    if report_number and "msc3" in schema:
        parts.append('<x> </x><msc3>')
        parts.append(report_number)
        parts.append('</msc3>')
    
    # Pages are OPTIONAL for reports (not required)
    pages = safe_strip(ref.get("pages")) or ""
    if pages and "first-page" in schema:
        from .page_article_separator import extract_first_last_page
        first_page, last_page = extract_first_last_page(pages)
        
        parts.append('<x>, </x>')
        if first_page and last_page:
            parts.append('<first-page>')
            parts.append(first_page)
            parts.append('</first-page><x>-</x><last-page>')
            parts.append(last_page)
            parts.append('</last-page>')
        elif first_page:
            parts.append('<first-page>')
            parts.append(first_page)
            parts.append('</first-page>')
    
    return parts


def _generate_thesis_xml(ref: Dict[str, Any], schema: Set[str]) -> List[str]:
    """Generate XML for thesis/dissertation"""
    parts = []
    title = safe_strip(ref.get("title")) or ""
    
    if title and "atl" in schema:
        parts.append('<x>. </x><atl>')
        parts.append(title)
        parts.append('</atl>')
    
    # Publisher contains university/institution (REQUIRED for thesis)
    publisher = safe_strip(ref.get("publisher")) or ""
    if publisher and "pub" in schema:
        parts.append('<x>. </x><pub>')
        parts.append(publisher)
        parts.append('</pub>')
    
    return parts


def _generate_authors_xml(ref: Dict[str, Any]) -> str:
    """Generate authors XML section (common to all types) with particle-aware normalization"""
    from .name_particle_normalizer import normalize_author_list
    
    authors_parts = ['<x> </x><aus>']
    full_names = ref.get("full_names", [])
    given_names = ref.get("given_names", [])
    family_names = ref.get("family_names", [])
    
    use_api_names = family_names and len(family_names) > 0
    
    if use_api_names:
        # Normalize author names to handle particles correctly
        normalized_family, normalized_given = normalize_author_list(family_names, given_names)
        
        num_authors = max(len(normalized_family), len(normalized_given))
        valid_authors = []
        for i in range(num_authors):
            surname_raw = normalized_family[i] if i < len(normalized_family) else None
            given_name_raw = normalized_given[i] if i < len(normalized_given) else None
            surname = str(surname_raw).strip() if surname_raw is not None else ""
            given_name = str(given_name_raw).strip() if given_name_raw is not None else ""
            if surname:
                valid_authors.append((surname, given_name))
        
        for i, (surname, given_name) in enumerate(valid_authors):
            if i > 0:
                if i == len(valid_authors) - 1:
                    authors_parts.append('<x>, and </x>')
                else:
                    authors_parts.append('<x>, </x>')
            
            if given_name:
                authors_parts.append(f'<au><snm>{surname}</snm><x>, </x><fnm>{given_name}</fnm></au>')
            else:
                authors_parts.append(f'<au><snm>{surname}</snm></au>')
    else:
        if full_names and len(full_names) > 0:
            author_list = full_names
        else:
            author_list = []
            for i, family in enumerate(family_names):
                given = given_names[i] if i < len(given_names) else ""
                if given and family:
                    author_list.append(f"{given} {family}")
                elif family:
                    author_list.append(family)
        
        for i, author_name in enumerate(author_list):
            if author_name:
                name_parts = author_name.strip().split()
                if len(name_parts) >= 2:
                    surname = name_parts[-1].strip()
                    given_name = " ".join(name_parts[:-1]).strip()
                    authors_parts.append(f'<au><snm>{surname}</snm><x>, </x><fnm>{given_name}</fnm></au>')
                elif len(name_parts) == 1:
                    authors_parts.append(f'<au><snm>{name_parts[0].strip()}</snm></au>')
                
                if i < len(author_list) - 1:
                    if i == len(author_list) - 2:
                        authors_parts.append('<x>, and </x>')
                    else:
                        authors_parts.append('<x>, </x>')
    
    authors_parts.append('</aus>')
    return ''.join(authors_parts)


def _extract_used_tags(xml_string: str) -> Set[str]:
    """Extract all XML tags used in the generated XML (excluding structural tags)"""
    # Find all XML tags, excluding <x> (punctuation) and structural tags
    tag_pattern = r'<([a-z-]+)(?:\s[^>]*)?>'
    tags = set(re.findall(tag_pattern, xml_string, re.IGNORECASE))
    
    # Remove structural tags that don't need validation
    structural_tags = {'bibitem', 'label', 'aus', 'au', 'snm', 'fnm', 'adate', 'x', 'url'}
    return tags - structural_tags

