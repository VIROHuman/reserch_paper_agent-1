"""
Shared utility module for generating consistent XML tagged output for all references.
This ensures all parsers produce the same standardized bibitem format.
"""
import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


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
    normalized["title"] = str(parsed_ref.get("title") or "").strip()
    normalized["journal"] = str(parsed_ref.get("journal") or "").strip()
    normalized["pages"] = str(parsed_ref.get("pages") or "").strip()
    normalized["doi"] = str(parsed_ref.get("doi") or "").strip()
    normalized["url"] = str(parsed_ref.get("url") or "").strip()
    normalized["publisher"] = str(parsed_ref.get("publisher") or "").strip()
    normalized["abstract"] = str(parsed_ref.get("abstract") or "").strip()
    
    # Handle volume/issue - may be in separate fields or embedded in journal
    volume_info = extract_volume_issue_info(parsed_ref)
    normalized["volume"] = volume_info.get("volume", "")
    normalized["issue"] = volume_info.get("issue", "")
    
    # Handle issue_month
    issue_month = parsed_ref.get("issue_month")
    if issue_month:
        normalized["issue_month"] = str(issue_month).strip()
    else:
        normalized["issue_month"] = ""
    
    return normalized


def generate_tagged_output(parsed_ref: Dict[str, Any], index: int) -> str:
    """
    Generate standardized XML tagged output matching the bibitem format.
    This function works with any parser's output format by normalizing it first.
    
    Args:
        parsed_ref: Dictionary containing parsed reference data (from any parser)
        index: Zero-based index of the reference
        
    Returns:
        XML string in bibitem format
    """
    # Normalize the parsed reference to ensure consistent format
    ref = normalize_parsed_reference(parsed_ref)
    
    # Generate label ID (bibitem format)
    label_id = f"bib{index + 1}"
    family_names = ref.get("family_names", [])
    
    # Generate label text: "FirstAuthor, Year" or "FirstAuthor et al., Year"
    label_text = ""
    year = ref.get("year") or "n.d."  # Handle None explicitly
    if family_names:
        first_author = family_names[0]
        
        if len(family_names) == 1:
            label_text = f"{first_author}, {year}"
        else:
            label_text = f"{first_author} et al., {year}"
    else:
        # Fallback label
        label_text = f"Reference {index + 1}, {year}"
    
    # Start building XML with bibitem root
    xml_parts = [f'<bibitem><label id="{label_id}">{label_text}</label>']
    
    # Generate authors section with proper format: <aus><au><snm>...</snm><x>, </x><fnm>...</fnm></au>...
    authors_parts = ['<x> </x><aus>']
    full_names = ref.get("full_names", [])
    given_names = ref.get("given_names", [])
    family_names = ref.get("family_names", [])
    
    # Priority 1: Use API-provided family_names and given_names if available
    # Use the API's classification exactly as provided - no modifications, no heuristics
    # Whatever the API says is surname → family_names → <snm>
    # Whatever the API says is first_name → given_names → <fnm>
    # Only fall back to parsing full_names if family_names are not available from API
    # Note: We use API names if family_names exist, even if given_names is incomplete (some authors may only have surnames)
    use_api_names = family_names and len(family_names) > 0
    
    if use_api_names:
        # Use API-provided names directly - use exactly what the API provided
        # The API's surname/first_name classification is used as-is for snm/fnm tags
        # Match family_names and given_names by index
        num_authors = max(len(family_names), len(given_names))
        
        # Debug: Log what we have
        logger.debug(f"Tagging - family_names: {family_names}, given_names: {given_names}, num_authors: {num_authors}")
        
        # First, collect all valid authors (non-empty surnames)
        valid_authors = []
        for i in range(num_authors):
            surname_raw = family_names[i] if i < len(family_names) else None
            given_name_raw = given_names[i] if i < len(given_names) else None
            
            surname = str(surname_raw).strip() if surname_raw is not None else ""
            given_name = str(given_name_raw).strip() if given_name_raw is not None else ""
            
            # Debug: Log each author
            logger.debug(f"Author {i}: surname='{surname}' (→ <snm>), given_name='{given_name}' (→ <fnm>)")
            
            if surname:
                valid_authors.append((surname, given_name))
        
        # Generate XML for valid authors with proper separators
        # Use API's classification directly: family_names → <snm>, given_names → <fnm>
        for i, (surname, given_name) in enumerate(valid_authors):
            # Add separator before this author if it's not the first
            if i > 0:
                # Add "and" before last author, comma otherwise
                if i == len(valid_authors) - 1:
                    authors_parts.append('<x>, and </x>')
                else:
                    authors_parts.append('<x>, </x>')
            
            if given_name:
                # Both surname and given name available from API - use directly
                authors_parts.append(f'<au><snm>{surname}</snm><x>, </x><fnm>{given_name}</fnm></au>')
            else:
                # Only surname available from API
                authors_parts.append(f'<au><snm>{surname}</snm></au>')
    else:
        # Fallback: Parse from full_names if API names not available
        # This handles cases where no API was called or API didn't return separate fields
        if full_names and len(full_names) > 0:
            author_list = full_names
        else:
            # Build from family_names + given_names (if only partial data available)
            author_list = []
            for i, family in enumerate(family_names):
                given = given_names[i] if i < len(given_names) else ""
                if given and family:
                    author_list.append(f"{given} {family}")
                elif family:
                    author_list.append(family)
        
        # Generate author XML by parsing full names (fallback method)
        for i, author_name in enumerate(author_list):
            if author_name:
                name_parts = author_name.strip().split()
                if len(name_parts) >= 2:
                    surname = name_parts[-1].strip()
                    given_name = " ".join(name_parts[:-1]).strip()
                    # Preserve periods in initials (e.g., "A." or "E.A.S.")
                    # Format: <au><snm>...</snm><x>, </x><fnm>...</fnm></au>
                    authors_parts.append(f'<au><snm>{surname}</snm><x>, </x><fnm>{given_name}</fnm></au>')
                elif len(name_parts) == 1:
                    # Only surname
                    authors_parts.append(f'<au><snm>{name_parts[0].strip()}</snm></au>')
                
                # Add separator between authors
                if i < len(author_list) - 1:
                    # Check if next-to-last author (add "and" before last)
                    if i == len(author_list) - 2:
                        authors_parts.append('<x>, and </x>')
                    else:
                        authors_parts.append('<x>, </x>')
    
    authors_parts.append('</aus>')
    xml_parts.append(''.join(authors_parts))
    
    # Add date (year)
    year = ref.get("year")
    if year:
        xml_parts.append('<x>, </x><adate>')
        xml_parts.append(str(year))
        xml_parts.append('</adate>')
    
    # Generate title section - use <atl> for article title, <btl> for book title
    title = ref.get("title", "")
    if title:
        # Determine if it's a book or article based on presence of journal
        if ref.get("journal"):
            # Article title
            xml_parts.append('<x>. </x><atl>')
            xml_parts.append(title.strip())
            xml_parts.append('</atl>')
        else:
            # Book title
            xml_parts.append('<x>. </x><btl>')
            xml_parts.append(title.strip())
            xml_parts.append('</btl>')
    
    # Generate journal/source title (<stl>)
    if ref.get("journal"):
        xml_parts.append('<x>. </x><stl>')
        xml_parts.append(ref["journal"].strip())
        xml_parts.append('</stl>')
        
        # Add volume and issue if available
        volume_info = extract_volume_issue_info(ref)
        if volume_info.get("volume"):
            xml_parts.append('<x> </x><vol>')
            xml_parts.append(str(volume_info["volume"]))
            xml_parts.append('</vol>')
        
        if volume_info.get("issue"):
            xml_parts.append('<x>(</x><iss>')
            xml_parts.append(str(volume_info["issue"]))
            xml_parts.append('</iss><x>)</x>')
        
        # Add issue month if available
        issue_month = ref.get("issue_month", "")
        if issue_month:
            xml_parts.append('<x> </x><issue>')
            xml_parts.append(issue_month.strip())
            xml_parts.append('</issue>')
    
    # Generate pages section - handle both page ranges and article numbers
    pages = ref.get("pages", "")
    # Check if it looks like an article number instead of pages
    if pages and not re.match(r'^\d+[-–—]?\d*$', pages.strip()) and len(pages.strip()) > 5:
        # Likely an article number (e.g., "103892", "04022010")
        xml_parts.append('<x> </x><atlno>')
        xml_parts.append(pages.strip())
        xml_parts.append('</atlno>')
    elif pages:
        pages = pages.strip()
        xml_parts.append('<x> </x>')
        
        # Parse page range
        if '-' in pages or '–' in pages or '—' in pages:
            page_parts = re.split(r'[-–—]', pages, 1)
            if len(page_parts) == 2:
                xml_parts.append('<first-page>')
                xml_parts.append(page_parts[0].strip())
                xml_parts.append('</first-page><x>-</x><last-page>')
                xml_parts.append(page_parts[1].strip())
                xml_parts.append('</last-page>')
            else:
                xml_parts.append('<first-page>')
                xml_parts.append(pages)
                xml_parts.append('</first-page>')
        else:
            xml_parts.append('<first-page>')
            xml_parts.append(pages)
            xml_parts.append('</first-page>')
    
    # Add publisher if available
    if ref.get("publisher"):
        xml_parts.append('<x>. </x><pub>')
        xml_parts.append(ref["publisher"].strip())
        xml_parts.append('</pub>')
    
    # Add DOI if available
    if ref.get("doi"):
        xml_parts.append('<x>. </x><doi>')
        xml_parts.append(ref["doi"].strip())
        xml_parts.append('</doi>')
    
    # Close bibitem
    xml_parts.append('<x>.</x></bibitem>')
    
    return ''.join(xml_parts)

