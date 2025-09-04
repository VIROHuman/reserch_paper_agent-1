"""
HTML tagging utilities for references
"""
from typing import List, Dict, Any, Optional
from loguru import logger

from ..models.schemas import ReferenceData, Author


class ReferenceTagger:
    """Generates HTML tags for references in various formats"""
    
    def __init__(self):
        self.styles = {
            "elsevier": self._tag_elsevier_style,
            "sage": self._tag_sage_style,
            "custom": self._tag_custom_style
        }
    
    def tag_references(self, references: List[ReferenceData], style: str = "elsevier") -> List[str]:
        """Tag a list of references with HTML"""
        tagged_references = []
        
        if style not in self.styles:
            logger.warning(f"Unknown style '{style}', using 'elsevier'")
            style = "elsevier"
        
        tagger_func = self.styles[style]
        
        for i, reference in enumerate(references, 1):
            try:
                tagged_ref = tagger_func(reference, i)
                tagged_references.append(tagged_ref)
            except Exception as e:
                logger.error(f"Error tagging reference {i}: {str(e)}")
                tagged_references.append(f"<error>Error processing reference {i}</error>")
        
        return tagged_references
    
    def _tag_elsevier_style(self, reference: ReferenceData, ref_id: int) -> str:
        """Tag reference in Elsevier style"""
        # Generate label (first author surname + year)
        label = self._generate_label(reference)
        
        # Generate authors section
        authors_xml = self._generate_authors_xml(reference.authors)
        
        # Generate title section
        title_xml = ""
        if reference.title:
            title_xml = f'<title><maintitle>{reference.title}</maintitle></title>'
        
        # Generate host section (journal/conference info)
        host_xml = self._generate_host_xml(reference)
        
        # Generate comment section (DOI, etc.)
        comment_xml = self._generate_comment_xml(reference)
        
        # Combine all parts
        reference_xml = f'''<reference id="ref{ref_id}">
<label>{label}</label>
{authors_xml}
{title_xml}
{host_xml}
{comment_xml}
</reference>'''
        
        return reference_xml
    
    def _tag_sage_style(self, reference: ReferenceData, ref_id: int) -> str:
        """Tag reference in Sage Publishing style"""
        # Similar to Elsevier but with slight variations
        return self._tag_elsevier_style(reference, ref_id)
    
    def _tag_custom_style(self, reference: ReferenceData, ref_id: int) -> str:
        """Tag reference in custom style"""
        # Basic custom tagging
        label = self._generate_label(reference)
        
        # Simple format
        authors_str = ", ".join([f"{author.first_name} {author.surname}" for author in reference.authors if author.first_name and author.surname])
        
        result = f"<ref id='ref{ref_id}'>{label}: {authors_str}"
        if reference.title:
            result += f". {reference.title}"
        if reference.journal:
            result += f". {reference.journal}"
        if reference.year:
            result += f" ({reference.year})"
        result += "</ref>"
        
        return result
    
    def _generate_label(self, reference: ReferenceData) -> str:
        """Generate reference label"""
        if not reference.authors:
            return f"Unknown, {reference.year or 'n.d.'}"
        
        first_author = reference.authors[0]
        surname = first_author.surname or "Unknown"
        year = reference.year or "n.d."
        
        if len(reference.authors) == 1:
            return f"{surname}, {year}"
        elif len(reference.authors) == 2:
            second_surname = reference.authors[1].surname or "Unknown"
            return f"{surname} & {second_surname}, {year}"
        else:
            return f"{surname} et al., {year}"
    
    def _generate_authors_xml(self, authors: List[Author]) -> str:
        """Generate authors XML section"""
        if not authors:
            return "<authors></authors>"
        
        author_elements = []
        for author in authors:
            fnm = author.first_name or ""
            surname = author.surname or ""
            
            author_xml = f'''<author>
<fnm>{fnm}</fnm>
<surname>{surname}</surname>
</author>'''
            author_elements.append(author_xml)
        
        return f"<authors>{''.join(author_elements)}</authors>"
    
    def _generate_host_xml(self, reference: ReferenceData) -> str:
        """Generate host XML section (journal/conference info)"""
        if not reference.journal and not reference.year:
            return ""
        
        # Determine if it's a journal or conference
        is_journal = reference.publication_type in ["journal-article", "journal"] or not reference.publication_type
        
        if is_journal:
            # Journal format
            series_xml = f'<series><title><maintitle>{reference.journal or "Unknown Journal"}</maintitle></title>'
            if reference.volume:
                series_xml += f'<volume>{reference.volume}</volume>'
            series_xml += '</series>'
            
            issue_xml = ""
            if reference.issue:
                issue_xml = f'<issue>{reference.issue}</issue>'
            
            date_xml = ""
            if reference.year:
                date_xml = f'<date>{reference.year}</date>'
            
            issue_section = f'<issue>{series_xml}{issue_xml}{date_xml}</issue>'
            
            pages_xml = ""
            if reference.pages:
                pages_xml = self._generate_pages_xml(reference.pages)
            
            return f'<host>{issue_section}{pages_xml}</host>'
        
        else:
            # Conference format
            book_xml = f'<book><title><maintitle>{reference.journal or "Unknown Conference"}</maintitle></title>'
            if reference.year:
                book_xml += f'<date>{reference.year}</date>'
            book_xml += '</book>'
            
            pages_xml = ""
            if reference.pages:
                pages_xml = self._generate_pages_xml(reference.pages)
            
            return f'<host>{book_xml}{pages_xml}</host>'
    
    def _generate_pages_xml(self, pages: str) -> str:
        """Generate pages XML section"""
        # Try to parse page range
        if '-' in pages:
            try:
                fpage, lpage = pages.split('-', 1)
                return f'<pages><fpage>{fpage.strip()}</fpage><lpage>{lpage.strip()}</lpage></pages>'
            except:
                pass
        
        # Single page or unparseable
        return f'<pages><fpage>{pages.strip()}</fpage></pages>'
    
    def _generate_comment_xml(self, reference: ReferenceData) -> str:
        """Generate comment XML section (DOI, URL, etc.)"""
        comments = []
        
        if reference.doi:
            comments.append(f"DOI: {reference.doi}")
        
        if reference.url:
            comments.append(f"URL: {reference.url}")
        
        if reference.publisher:
            comments.append(f"Publisher: {reference.publisher}")
        
        if not comments:
            return ""
        
        comment_text = "; ".join(comments)
        return f'<comment>{comment_text}</comment>'
    
    def validate_tagged_reference(self, tagged_ref: str) -> Dict[str, Any]:
        """Validate a tagged reference for completeness"""
        validation_result = {
            "has_label": "<label>" in tagged_ref,
            "has_authors": "<authors>" in tagged_ref and "<author>" in tagged_ref,
            "has_title": "<title>" in tagged_ref,
            "has_host": "<host>" in tagged_ref,
            "has_comment": "<comment>" in tagged_ref,
            "is_well_formed": self._check_xml_well_formed(tagged_ref)
        }
        
        validation_result["completeness_score"] = sum(validation_result.values()) / len(validation_result)
        
        return validation_result
    
    def _check_xml_well_formed(self, xml_string: str) -> bool:
        """Basic check if XML is well-formed"""
        try:
            # Simple check for matching tags
            import re
            open_tags = re.findall(r'<(\w+)[^>]*>', xml_string)
            close_tags = re.findall(r'</(\w+)>', xml_string)
            
            # Check if all open tags have corresponding close tags
            return len(open_tags) == len(close_tags)
        except:
            return False