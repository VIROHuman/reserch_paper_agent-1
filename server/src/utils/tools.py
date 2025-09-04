"""
Custom tools for LangChain agents
"""
from typing import List, Dict, Any, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from loguru import logger

from ..models.schemas import ReferenceData, ValidationResult
from ..utils.api_clients import CrossRefClient, OpenAlexClient, SemanticScholarClient, GROBIDClient
from ..utils.validation import ReferenceValidator
from ..utils.tagging import ReferenceTagger
from ..utils.db_utils import DatabaseManager


class ReferenceSearchInput(BaseModel):
    """Input for reference search tool"""
    query: str = Field(description="Search query for finding references")
    api: str = Field(default="crossref", description="API to use: crossref, openalex, semantic_scholar")
    limit: int = Field(default=5, description="Maximum number of results to return")


class ReferenceSearchTool(BaseTool):
    """Tool for searching references using various APIs"""
    name = "search_references"
    description = "Search for reference information using CrossRef, OpenAlex, or Semantic Scholar APIs"
    args_schema = ReferenceSearchInput
    
    def __init__(self):
        super().__init__()
        self.crossref_client = CrossRefClient()
        self.openalex_client = OpenAlexClient()
        self.semantic_client = SemanticScholarClient()
    
    def _run(self, query: str, api: str = "crossref", limit: int = 5) -> str:
        """Run the tool synchronously"""
        import asyncio
        return asyncio.run(self._arun(query, api, limit))
    
    async def _arun(self, query: str, api: str = "crossref", limit: int = 5) -> str:
        """Run the tool asynchronously"""
        try:
            if api == "crossref":
                results = await self.crossref_client.search_reference(query, limit)
            elif api == "openalex":
                results = await self.openalex_client.search_reference(query, limit)
            elif api == "semantic_scholar":
                results = await self.semantic_client.search_reference(query, limit)
            else:
                return f"Unknown API: {api}. Available APIs: crossref, openalex, semantic_scholar"
            
            if not results:
                return f"No results found using {api} API"
            
            # Format results
            formatted_results = []
            for i, result in enumerate(results, 1):
                authors = ", ".join([f"{a.first_name} {a.surname}" for a in result.authors if a.first_name and a.surname])
                formatted_results.append(f"{i}. {result.title} - {authors} ({result.year})")
            
            return f"Found {len(results)} results from {api}:\n" + "\n".join(formatted_results)
            
        except Exception as e:
            logger.error(f"Reference search error: {str(e)}")
            return f"Error searching references: {str(e)}"


class ReferenceValidationInput(BaseModel):
    """Input for reference validation tool"""
    reference_data: Dict[str, Any] = Field(description="Reference data to validate")
    original_text: str = Field(default="", description="Original reference text")


class ReferenceValidationTool(BaseTool):
    """Tool for validating reference data"""
    name = "validate_reference"
    description = "Validate reference data and identify missing fields"
    args_schema = ReferenceValidationInput
    
    def __init__(self):
        super().__init__()
        self.validator = ReferenceValidator()
    
    def _run(self, reference_data: Dict[str, Any], original_text: str = "") -> str:
        """Run the tool synchronously"""
        try:
            # Convert dict to ReferenceData object
            reference = ReferenceData(**reference_data)
            
            # Validate reference
            validation_result = self.validator.validate_reference(reference, original_text)
            
            # Format result
            result = {
                "is_valid": validation_result.is_valid,
                "missing_fields": validation_result.missing_fields,
                "confidence_score": validation_result.confidence_score,
                "warnings": validation_result.warnings
            }
            
            if validation_result.suggestions:
                result["suggestions"] = validation_result.suggestions
            
            return f"Validation result: {result}"
            
        except Exception as e:
            logger.error(f"Reference validation error: {str(e)}")
            return f"Error validating reference: {str(e)}"


class ReferenceTaggingInput(BaseModel):
    """Input for reference tagging tool"""
    reference_data: Dict[str, Any] = Field(description="Reference data to tag")
    style: str = Field(default="elsevier", description="Tagging style: elsevier, sage, custom")


class ReferenceTaggingTool(BaseTool):
    """Tool for generating HTML tags for references"""
    name = "tag_reference"
    description = "Generate HTML tags for reference in specified format"
    args_schema = ReferenceTaggingInput
    
    def __init__(self):
        super().__init__()
        self.tagger = ReferenceTagger()
    
    def _run(self, reference_data: Dict[str, Any], style: str = "elsevier") -> str:
        """Run the tool synchronously"""
        try:
            # Convert dict to ReferenceData object
            reference = ReferenceData(**reference_data)
            
            # Generate tags
            tagged_references = self.tagger.tag_references([reference], style)
            
            if tagged_references:
                return tagged_references[0]
            else:
                return "Error: No tagged reference generated"
            
        except Exception as e:
            logger.error(f"Reference tagging error: {str(e)}")
            return f"Error tagging reference: {str(e)}"


class ReferenceEnhancementInput(BaseModel):
    """Input for reference enhancement tool"""
    reference_data: Dict[str, Any] = Field(description="Reference data to enhance")
    original_text: str = Field(default="", description="Original reference text")
    apis: List[str] = Field(default=["crossref", "openalex"], description="APIs to use for enhancement")


class ReferenceEnhancementTool(BaseTool):
    """Tool for enhancing reference data with missing information"""
    name = "enhance_reference"
    description = "Enhance reference data by searching for missing information using multiple APIs"
    args_schema = ReferenceEnhancementInput
    
    def __init__(self):
        super().__init__()
        self.crossref_client = CrossRefClient()
        self.openalex_client = OpenAlexClient()
        self.semantic_client = SemanticScholarClient()
        self.validator = ReferenceValidator()
    
    def _run(self, reference_data: Dict[str, Any], original_text: str = "", apis: List[str] = None) -> str:
        """Run the tool synchronously"""
        import asyncio
        return asyncio.run(self._arun(reference_data, original_text, apis))
    
    async def _arun(self, reference_data: Dict[str, Any], original_text: str = "", apis: List[str] = None) -> str:
        """Run the tool asynchronously"""
        try:
            if apis is None:
                apis = ["crossref", "openalex"]
            
            # Convert dict to ReferenceData object
            reference = ReferenceData(**reference_data)
            
            # Build search query
            query_parts = []
            if reference.title:
                query_parts.append(reference.title)
            if reference.authors:
                author_names = [f"{a.first_name} {a.surname}" for a in reference.authors if a.first_name and a.surname]
                if author_names:
                    query_parts.append(" ".join(author_names[:2]))
            if reference.year:
                query_parts.append(str(reference.year))
            
            search_query = " ".join(query_parts) if query_parts else original_text
            
            # Search using specified APIs
            all_results = []
            sources_used = []
            
            for api in apis:
                try:
                    if api == "crossref":
                        results = await self.crossref_client.search_reference(search_query, limit=2)
                        sources_used.append("CrossRef")
                    elif api == "openalex":
                        results = await self.openalex_client.search_reference(search_query, limit=2)
                        sources_used.append("OpenAlex")
                    elif api == "semantic_scholar":
                        results = await self.semantic_client.search_reference(search_query, limit=2)
                        sources_used.append("Semantic Scholar")
                    else:
                        continue
                    
                    all_results.extend(results)
                    
                except Exception as e:
                    logger.warning(f"Error searching {api}: {str(e)}")
                    continue
            
            if not all_results:
                return "No enhancement data found from any API"
            
            # Find best match
            best_match = None
            best_score = 0.0
            
            for candidate in all_results:
                score = self.validator.compare_references(reference, candidate)
                if score > best_score:
                    best_score = score
                    best_match = candidate
            
            if not best_match or best_score < 0.3:
                return f"No suitable match found (best score: {best_score:.2f})"
            
            # Merge data
            enhanced_data = self._merge_references(reference, best_match)
            
            # Identify found fields
            found_fields = self._identify_found_fields(reference, enhanced_data)
            
            result = {
                "enhanced_data": enhanced_data.dict(),
                "sources_used": sources_used,
                "found_fields": found_fields,
                "confidence_score": best_score
            }
            
            return f"Enhancement result: {result}"
            
        except Exception as e:
            logger.error(f"Reference enhancement error: {str(e)}")
            return f"Error enhancing reference: {str(e)}"
    
    def _merge_references(self, original: ReferenceData, enhanced: ReferenceData) -> ReferenceData:
        """Merge original and enhanced reference data"""
        return ReferenceData(
            title=original.title or enhanced.title,
            authors=original.authors or enhanced.authors,
            year=original.year or enhanced.year,
            journal=original.journal or enhanced.journal,
            volume=original.volume or enhanced.volume,
            issue=original.issue or enhanced.issue,
            pages=original.pages or enhanced.pages,
            doi=original.doi or enhanced.doi,
            url=original.url or enhanced.url,
            abstract=original.abstract or enhanced.abstract,
            publisher=original.publisher or enhanced.publisher,
            publication_type=original.publication_type or enhanced.publication_type,
            raw_text=original.raw_text
        )
    
    def _identify_found_fields(self, original: ReferenceData, enhanced: ReferenceData) -> List[str]:
        """Identify which fields were found during enhancement"""
        found_fields = []
        
        if not original.title and enhanced.title:
            found_fields.append("title")
        if not original.authors and enhanced.authors:
            found_fields.append("authors")
        if not original.year and enhanced.year:
            found_fields.append("year")
        if not original.journal and enhanced.journal:
            found_fields.append("journal")
        if not original.volume and enhanced.volume:
            found_fields.append("volume")
        if not original.issue and enhanced.issue:
            found_fields.append("issue")
        if not original.pages and enhanced.pages:
            found_fields.append("pages")
        if not original.doi and enhanced.doi:
            found_fields.append("doi")
        
        return found_fields


class DatabaseLoggingInput(BaseModel):
    """Input for database logging tool"""
    operation: str = Field(description="Operation being performed")
    reference_data: Dict[str, Any] = Field(description="Reference data")
    status: str = Field(description="Operation status: success, error, warning")
    details: str = Field(default="", description="Additional details")


class DatabaseLoggingTool(BaseTool):
    """Tool for logging operations to database"""
    name = "log_operation"
    description = "Log operation details to database for tracking and debugging"
    args_schema = DatabaseLoggingInput
    
    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager()
    
    def _run(self, operation: str, reference_data: Dict[str, Any], status: str, details: str = "") -> str:
        """Run the tool synchronously"""
        try:
            # Save reference to database
            reference = ReferenceData(**reference_data)
            reference_id = self.db_manager.save_reference(
                original_text=reference.raw_text or "",
                processed_data=reference
            )
            
            # Log the operation
            self.db_manager.log_processing(reference_id, operation, status, details)
            
            return f"Logged operation '{operation}' with status '{status}' for reference ID {reference_id}"
            
        except Exception as e:
            logger.error(f"Database logging error: {str(e)}")
            return f"Error logging operation: {str(e)}"


# Export all tools
def get_all_tools() -> List[BaseTool]:
    """Get all available tools"""
    return [
        ReferenceSearchTool(),
        ReferenceValidationTool(),
        ReferenceTaggingTool(),
        ReferenceEnhancementTool(),
        DatabaseLoggingTool()
    ]
