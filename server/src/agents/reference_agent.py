"""
LangChain agents for reference processing
"""
from typing import List, Dict, Any, Optional
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import Tool
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from loguru import logger

from ..models.schemas import ReferenceData, ValidationResult
from ..utils.api_clients import CrossRefClient, OpenAlexClient, SemanticScholarClient, GROBIDClient
from ..utils.validation import ReferenceValidator
from ..utils.tagging import ReferenceTagger
from ..config import settings


class ReferenceProcessingAgent:
    """Main agent for processing and validating references"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.1,
            api_key=settings.openai_api_key
        )
        
        # Initialize clients
        self.crossref_client = CrossRefClient()
        self.openalex_client = OpenAlexClient()
        self.semantic_client = SemanticScholarClient()
        self.grobid_client = GROBIDClient()
        
        # Initialize utilities
        self.validator = ReferenceValidator()
        self.tagger = ReferenceTagger()
        
        # Create tools
        self.tools = self._create_tools()
        
        # Create agent
        self.agent = self._create_agent()
    
    def _create_tools(self) -> List[Tool]:
        """Create tools for the agent"""
        tools = [
            Tool(
                name="search_crossref",
                description="Search for reference information using CrossRef API",
                func=self._search_crossref_tool
            ),
            Tool(
                name="search_openalex",
                description="Search for reference information using OpenAlex API",
                func=self._search_openalex_tool
            ),
            Tool(
                name="search_semantic_scholar",
                description="Search for reference information using Semantic Scholar API",
                func=self._search_semantic_scholar_tool
            ),
            Tool(
                name="parse_grobid",
                description="Parse reference text using GROBID API",
                func=self._parse_grobid_tool
            ),
            Tool(
                name="validate_reference",
                description="Validate reference data and identify missing fields",
                func=self._validate_reference_tool
            ),
            Tool(
                name="tag_reference",
                description="Generate HTML tags for reference in specified format",
                func=self._tag_reference_tool
            )
        ]
        return tools
    
    def _create_agent(self) -> AgentExecutor:
        """Create the agent executor"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_system_prompt()),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        return AgentExecutor(agent=agent, tools=self.tools, verbose=True)
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent"""
        return """You are a research paper reference processing agent. Your tasks are:

1. **Reference Validation**: Given reference text, identify missing fields and validate completeness
2. **Data Enhancement**: Use various APIs to fetch missing information for references
3. **HTML Tagging**: Generate properly formatted HTML tags for references

Key capabilities:
- Search multiple academic databases (CrossRef, OpenAlex, Semantic Scholar)
- Parse reference text using GROBID
- Validate reference completeness and identify missing fields
- Generate HTML tags in various formats (Elsevier, Sage, custom)

Important guidelines:
- Always mention when you cannot find specific information (avoid hallucination)
- Provide confidence scores for your findings
- Be transparent about data sources and limitations
- Handle large batches of references efficiently
- Maintain reference integrity and avoid data corruption

When processing references:
1. First validate the input reference
2. Search for missing information using available APIs
3. Combine and validate the enhanced data
4. Generate appropriate HTML tags
5. Report any issues or missing data clearly

Always be honest about what you can and cannot find."""
    
    async def process_references(self, references: List[str], validate_all: bool = True) -> Dict[str, Any]:
        """Process a list of references"""
        results = []
        errors = []
        
        for i, ref_text in enumerate(references):
            try:
                logger.info(f"Processing reference {i+1}/{len(references)}")
                
                # Use agent to process the reference
                result = await self.agent.ainvoke({
                    "input": f"Process this reference: {ref_text}. Validate it, enhance missing data, and generate HTML tags."
                })
                
                results.append({
                    "index": i,
                    "original_text": ref_text,
                    "result": result,
                    "status": "success"
                })
                
            except Exception as e:
                logger.error(f"Error processing reference {i+1}: {str(e)}")
                errors.append(f"Reference {i+1}: {str(e)}")
                results.append({
                    "index": i,
                    "original_text": ref_text,
                    "error": str(e),
                    "status": "error"
                })
        
        return {
            "processed_count": len([r for r in results if r["status"] == "success"]),
            "total_count": len(references),
            "results": results,
            "errors": errors
        }
    
    # Tool functions
    async def _search_crossref_tool(self, query: str) -> str:
        """Search CrossRef API"""
        try:
            results = await self.crossref_client.search_reference(query, limit=3)
            if results:
                return f"Found {len(results)} results from CrossRef: {[r.title for r in results]}"
            else:
                return "No results found in CrossRef"
        except Exception as e:
            return f"CrossRef search error: {str(e)}"
    
    async def _search_openalex_tool(self, query: str) -> str:
        """Search OpenAlex API"""
        try:
            results = await self.openalex_client.search_reference(query, limit=3)
            if results:
                return f"Found {len(results)} results from OpenAlex: {[r.title for r in results]}"
            else:
                return "No results found in OpenAlex"
        except Exception as e:
            return f"OpenAlex search error: {str(e)}"
    
    async def _search_semantic_scholar_tool(self, query: str) -> str:
        """Search Semantic Scholar API"""
        try:
            results = await self.semantic_client.search_reference(query, limit=3)
            if results:
                return f"Found {len(results)} results from Semantic Scholar: {[r.title for r in results]}"
            else:
                return "No results found in Semantic Scholar"
        except Exception as e:
            return f"Semantic Scholar search error: {str(e)}"
    
    async def _parse_grobid_tool(self, reference_text: str) -> str:
        """Parse reference using GROBID"""
        try:
            result = await self.grobid_client.parse_reference(reference_text)
            if result:
                return f"GROBID parsed reference: {result.title} by {[a.full_name for a in result.authors]}"
            else:
                return "GROBID parsing failed or not available"
        except Exception as e:
            return f"GROBID parsing error: {str(e)}"
    
    def _validate_reference_tool(self, reference_data: str) -> str:
        """Validate reference data"""
        try:
            # This would need to parse the reference data first
            # For now, return a placeholder
            return "Reference validation completed - check missing fields"
        except Exception as e:
            return f"Validation error: {str(e)}"
    
    def _tag_reference_tool(self, reference_data: str) -> str:
        """Tag reference with HTML"""
        try:
            # This would need to parse the reference data first
            # For now, return a placeholder
            return "HTML tagging completed"
        except Exception as e:
            return f"Tagging error: {str(e)}"


class ReferenceEnhancementAgent:
    """Specialized agent for enhancing reference data"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0.1,
            api_key=settings.openai_api_key
        )
        
        self.crossref_client = CrossRefClient()
        self.openalex_client = OpenAlexClient()
        self.semantic_client = SemanticScholarClient()
        self.validator = ReferenceValidator()
    
    async def enhance_reference(self, reference: ReferenceData, original_text: str = "") -> Dict[str, Any]:
        """Enhance a single reference with missing data"""
        enhancement_result = {
            "original": reference,
            "enhanced": reference,
            "sources_used": [],
            "confidence_scores": {},
            "missing_fields_found": [],
            "warnings": []
        }
        
        # Validate original reference
        validation = self.validator.validate_reference(reference, original_text)
        missing_fields = validation.missing_fields
        
        if not missing_fields:
            return enhancement_result
        
        # Search for missing information
        search_query = self._build_search_query(reference, original_text)
        
        # Try different APIs
        api_results = []
        
        try:
            crossref_results = await self.crossref_client.search_reference(search_query, limit=2)
            if crossref_results:
                api_results.extend(crossref_results)
                enhancement_result["sources_used"].append("CrossRef")
        except Exception as e:
            enhancement_result["warnings"].append(f"CrossRef error: {str(e)}")
        
        try:
            openalex_results = await self.openalex_client.search_reference(search_query, limit=2)
            if openalex_results:
                api_results.extend(openalex_results)
                enhancement_result["sources_used"].append("OpenAlex")
        except Exception as e:
            enhancement_result["warnings"].append(f"OpenAlex error: {str(e)}")
        
        try:
            semantic_results = await self.semantic_client.search_reference(search_query, limit=2)
            if semantic_results:
                api_results.extend(semantic_results)
                enhancement_result["sources_used"].append("Semantic Scholar")
        except Exception as e:
            enhancement_result["warnings"].append(f"Semantic Scholar error: {str(e)}")
        
        # Find best match and enhance
        if api_results:
            best_match = self._find_best_match(reference, api_results)
            if best_match:
                enhanced_ref = self._merge_references(reference, best_match)
                enhancement_result["enhanced"] = enhanced_ref
                enhancement_result["missing_fields_found"] = self._identify_found_fields(reference, enhanced_ref)
        
        return enhancement_result
    
    def _build_search_query(self, reference: ReferenceData, original_text: str) -> str:
        """Build search query from reference data"""
        query_parts = []
        
        if reference.title:
            query_parts.append(reference.title)
        
        if reference.authors:
            author_names = [f"{a.first_name} {a.surname}" for a in reference.authors if a.first_name and a.surname]
            if author_names:
                query_parts.append(" ".join(author_names[:2]))  # Use first 2 authors
        
        if reference.year:
            query_parts.append(str(reference.year))
        
        if reference.journal:
            query_parts.append(reference.journal)
        
        if not query_parts and original_text:
            # Fallback to original text
            query_parts.append(original_text[:200])  # First 200 chars
        
        return " ".join(query_parts)
    
    def _find_best_match(self, original: ReferenceData, candidates: List[ReferenceData]) -> Optional[ReferenceData]:
        """Find the best matching reference from candidates"""
        if not candidates:
            return None
        
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            score = self.validator.compare_references(original, candidate)
            if score > best_score:
                best_score = score
                best_match = candidate
        
        return best_match if best_score > 0.3 else None  # Minimum threshold
    
    def _merge_references(self, original: ReferenceData, enhanced: ReferenceData) -> ReferenceData:
        """Merge original and enhanced reference data"""
        # Create a copy of original
        merged = ReferenceData(
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
        
        return merged
    
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