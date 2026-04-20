"""
Mandatory API Selection System

Automatically selects mandatory APIs based on reference type and available identifiers.
Users can only control optional augmentation APIs.
"""
from typing import List, Dict, Any, Set, Optional
from loguru import logger

from .api_clients import APIProvider
from ..models.reference_models import ReferenceType


class MandatoryAPISelector:
    """
    Automatically selects mandatory APIs based on reference type and identifiers.
    
    Mandatory APIs are ALWAYS called to ensure core metadata completeness.
    Optional APIs can be enabled/disabled by users for augmentation.
    """
    
    # Mandatory APIs by reference type and identifier availability
    MANDATORY_API_RULES = {
        ReferenceType.JOURNAL_ARTICLE: {
            # If DOI available: CrossRef (best for DOI resolution)
            "has_doi": [APIProvider.CROSSREF],
            # If no DOI but has title: CrossRef + OpenAlex (best for title search)
            "has_title": [APIProvider.CROSSREF, APIProvider.OPENALEX],
            # If no DOI/title but has authors: CrossRef + OpenAlex + Semantic Scholar
            "has_authors": [APIProvider.CROSSREF, APIProvider.OPENALEX, APIProvider.SEMANTIC_SCHOLAR],
            # Fallback: at least CrossRef
            "fallback": [APIProvider.CROSSREF]
        },
        ReferenceType.CONFERENCE_PAPER: {
            "has_doi": [APIProvider.CROSSREF],
            "has_title": [APIProvider.CROSSREF, APIProvider.OPENALEX],
            "has_authors": [APIProvider.CROSSREF, APIProvider.OPENALEX, APIProvider.SEMANTIC_SCHOLAR],
            "fallback": [APIProvider.CROSSREF]
        },
        ReferenceType.BOOK: {
            "has_doi": [APIProvider.CROSSREF],
            "has_title": [APIProvider.CROSSREF, APIProvider.OPENALEX],
            "has_authors": [APIProvider.CROSSREF, APIProvider.OPENALEX],
            "fallback": [APIProvider.CROSSREF]
        },
        ReferenceType.BOOK_CHAPTER: {
            "has_doi": [APIProvider.CROSSREF],
            "has_title": [APIProvider.CROSSREF, APIProvider.OPENALEX],
            "has_authors": [APIProvider.CROSSREF, APIProvider.OPENALEX],
            "fallback": [APIProvider.CROSSREF]
        },
        ReferenceType.REPORT: {
            "has_doi": [APIProvider.CROSSREF],
            "has_title": [APIProvider.CROSSREF, APIProvider.OPENALEX],
            "fallback": [APIProvider.CROSSREF]
        },
        ReferenceType.THESIS: {
            "has_doi": [APIProvider.CROSSREF],
            "has_title": [APIProvider.CROSSREF, APIProvider.OPENALEX],
            "has_authors": [APIProvider.CROSSREF, APIProvider.OPENALEX],
            "fallback": [APIProvider.CROSSREF]
        },
        ReferenceType.UNKNOWN: {
            "has_doi": [APIProvider.CROSSREF],
            "has_title": [APIProvider.CROSSREF, APIProvider.OPENALEX],
            "fallback": [APIProvider.CROSSREF]
        }
    }
    
    # Optional APIs (can be enabled/disabled by users)
    OPTIONAL_APIS = {
        APIProvider.PUBMED,      # Biomedical literature
        APIProvider.ARXIV,        # Preprints
        APIProvider.SEMANTIC_SCHOLAR,  # AI-powered search
        APIProvider.DOAJ          # Open access journals
    }
    
    def select_mandatory_apis(
        self,
        reference_type: ReferenceType,
        parsed_ref: Dict[str, Any]
    ) -> List[APIProvider]:
        """
        Automatically select mandatory APIs based on reference type and identifiers.
        
        Args:
            reference_type: Classified reference type
            parsed_ref: Parsed reference data
            
        Returns:
            List of mandatory API providers (always called, cannot be disabled)
        """
        # Get rules for this reference type
        rules = self.MANDATORY_API_RULES.get(reference_type, self.MANDATORY_API_RULES[ReferenceType.UNKNOWN])
        
        # Check available identifiers (in priority order)
        has_doi = bool(parsed_ref.get("doi") and parsed_ref.get("doi").strip())
        has_title = bool(parsed_ref.get("title") and len(parsed_ref.get("title", "").strip()) > 10)
        has_authors = bool(
            parsed_ref.get("family_names") and 
            len(parsed_ref.get("family_names", [])) > 0
        )
        
        # Select mandatory APIs based on available identifiers
        if has_doi and "has_doi" in rules:
            mandatory_apis = rules["has_doi"]
            logger.info(f"📌 Reference type {reference_type.value} with DOI → mandatory APIs: {[api.value for api in mandatory_apis]}")
        elif has_title and "has_title" in rules:
            mandatory_apis = rules["has_title"]
            logger.info(f"📌 Reference type {reference_type.value} with title → mandatory APIs: {[api.value for api in mandatory_apis]}")
        elif has_authors and "has_authors" in rules:
            mandatory_apis = rules["has_authors"]
            logger.info(f"📌 Reference type {reference_type.value} with authors → mandatory APIs: {[api.value for api in mandatory_apis]}")
        else:
            mandatory_apis = rules["fallback"]
            logger.info(f"📌 Reference type {reference_type.value} (minimal data) → mandatory APIs: {[api.value for api in mandatory_apis]}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_apis = []
        for api in mandatory_apis:
            if api not in seen:
                seen.add(api)
                unique_apis.append(api)
        
        return unique_apis
    
    def filter_optional_apis(
        self,
        enabled_optional_apis: Optional[List[str]] = None
    ) -> List[APIProvider]:
        """
        Filter optional APIs based on user selection.
        
        Args:
            enabled_optional_apis: List of optional API names enabled by user (None = all disabled)
            
        Returns:
            List of optional API providers to use
        """
        if enabled_optional_apis is None:
            return []  # No optional APIs enabled
        
        # Convert string names to APIProvider enum
        enabled_set = set(enabled_optional_apis)
        optional_apis = [
            APIProvider(api_name) 
            for api_name in enabled_set 
            if APIProvider(api_name) in self.OPTIONAL_APIS
        ]
        
        logger.info(f"🔧 User enabled {len(optional_apis)} optional APIs: {[api.value for api in optional_apis]}")
        return optional_apis
    
    def get_all_apis(
        self,
        reference_type: ReferenceType,
        parsed_ref: Dict[str, Any],
        enabled_optional_apis: Optional[List[str]] = None
    ) -> List[APIProvider]:
        """
        Get all APIs to call (mandatory + optional).
        
        Args:
            reference_type: Classified reference type
            parsed_ref: Parsed reference data
            enabled_optional_apis: Optional list of optional API names enabled by user
            
        Returns:
            Combined list of mandatory and optional API providers
        """
        # Get mandatory APIs (always included)
        mandatory_apis = self.select_mandatory_apis(reference_type, parsed_ref)
        
        # Get optional APIs (user-controlled)
        optional_apis = self.filter_optional_apis(enabled_optional_apis)
        
        # Combine (mandatory first, then optional)
        all_apis = mandatory_apis + optional_apis
        
        # Remove duplicates while preserving order (mandatory takes precedence)
        seen = set()
        unique_apis = []
        for api in all_apis:
            if api not in seen:
                seen.add(api)
                unique_apis.append(api)
        
        logger.info(f"🎯 Total APIs to call: {len(unique_apis)} ({len(mandatory_apis)} mandatory + {len(optional_apis)} optional)")
        
        return unique_apis
    
    def get_mandatory_api_names(self) -> List[str]:
        """Get list of all mandatory API names (for UI display)"""
        all_mandatory = set()
        for rules in self.MANDATORY_API_RULES.values():
            for api_list in rules.values():
                all_mandatory.update(api_list)
        return [api.value for api in all_mandatory]
    
    def get_optional_api_names(self) -> List[str]:
        """Get list of all optional API names (for UI display)"""
        return [api.value for api in self.OPTIONAL_APIS]

