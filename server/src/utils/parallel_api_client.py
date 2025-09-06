"""
Parallel API client for concurrent reference validation
"""
import asyncio
import httpx
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from dataclasses import dataclass
from enum import Enum

from .api_clients import CrossRefClient, OpenAlexClient, SemanticScholarClient, DOAJClient
from ..models.schemas import ReferenceData


class APIPriority(Enum):
    """API priority levels"""
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    SKIP = 4


@dataclass
class APIConfig:
    """Configuration for API calls"""
    name: str
    client: Any
    priority: APIPriority
    timeout: float = 5.0
    enabled: bool = True


class ParallelAPIClient:
    """Client for parallel API processing"""
    
    def __init__(self):
        self.crossref = CrossRefClient()
        self.openalex = OpenAlexClient()
        self.semantic_scholar = SemanticScholarClient()
        self.doj = DOAJClient()
        
        # Configure APIs with priorities and timeouts
        self.api_configs = [
            APIConfig("CrossRef", self.crossref, APIPriority.HIGH, 5.0, True),
            APIConfig("OpenAlex", self.openalex, APIPriority.MEDIUM, 5.0, True),
            APIConfig("SemanticScholar", self.semantic_scholar, APIPriority.LOW, 5.0, True),
            APIConfig("DOAJ", self.doj, APIPriority.LOW, 5.0, True),
        ]
    
    async def search_reference_parallel(
        self, 
        query: str, 
        limit: int = 3,
        max_apis: int = 4,
        timeout: float = 10.0
    ) -> Dict[str, List[ReferenceData]]:
        """
        Search reference using multiple APIs in parallel
        
        Args:
            query: Search query
            limit: Max results per API
            max_apis: Maximum number of APIs to call
            timeout: Overall timeout for all APIs
            
        Returns:
            Dictionary with API names as keys and results as values
        """
        logger.info(f"🚀 PARALLEL API SEARCH: '{query}' (max_apis: {max_apis}, timeout: {timeout}s)")
        
        # Select APIs to call based on priority
        apis_to_call = self._select_apis(max_apis)
        
        # Create tasks for parallel execution
        tasks = []
        for api_config in apis_to_call:
            if api_config.enabled:
                task = self._call_api_with_timeout(
                    api_config, query, limit, api_config.timeout
                )
                tasks.append((api_config.name, task))
        
        # Execute all APIs in parallel
        results = {}
        try:
            # Use asyncio.wait_for for overall timeout
            parallel_results = await asyncio.wait_for(
                asyncio.gather(*[task for _, task in tasks], return_exceptions=True),
                timeout=timeout
            )
            
            # Process results
            for i, (api_name, _) in enumerate(tasks):
                result = parallel_results[i]
                if isinstance(result, Exception):
                    logger.warning(f"❌ {api_name} failed: {result}")
                    results[api_name] = []
                else:
                    results[api_name] = result
                    logger.info(f"✅ {api_name} returned {len(result)} results")
            
        except asyncio.TimeoutError:
            logger.warning(f"⏰ Parallel API search timed out after {timeout}s")
            # Return partial results
            for api_name, _ in tasks:
                if api_name not in results:
                    results[api_name] = []
        
        return results
    
    def _select_apis(self, max_apis: int) -> List[APIConfig]:
        """Select APIs to call based on priority"""
        # Sort by priority and take the top N
        sorted_apis = sorted(
            [api for api in self.api_configs if api.enabled],
            key=lambda x: x.priority.value
        )
        return sorted_apis[:max_apis]
    
    async def _call_api_with_timeout(
        self, 
        api_config: APIConfig, 
        query: str, 
        limit: int, 
        timeout: float
    ) -> List[ReferenceData]:
        """Call a single API with timeout"""
        try:
            logger.info(f"🔍 Calling {api_config.name} (timeout: {timeout}s)")
            
            # Use asyncio.wait_for for individual API timeout
            result = await asyncio.wait_for(
                api_config.client.search_reference(query, limit),
                timeout=timeout
            )
            
            logger.info(f"✅ {api_config.name} completed: {len(result)} results")
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"⏰ {api_config.name} timed out after {timeout}s")
            return []
        except Exception as e:
            logger.error(f"❌ {api_config.name} error: {str(e)}")
            return []
    
    async def search_reference_smart(
        self, 
        query: str, 
        limit: int = 3,
        min_results: int = 1
    ) -> List[ReferenceData]:
        """
        Smart API search that stops when enough results are found
        
        Args:
            query: Search query
            limit: Max results per API
            min_results: Minimum results needed before stopping
            
        Returns:
            Combined results from all APIs
        """
        logger.info(f"🧠 SMART API SEARCH: '{query}' (min_results: {min_results})")
        
        # Start with high priority APIs
        high_priority_apis = [api for api in self.api_configs 
                             if api.priority == APIPriority.HIGH and api.enabled]
        
        all_results = []
        api_results = {}
        
        # Call high priority APIs first
        for api_config in high_priority_apis:
            try:
                result = await self._call_api_with_timeout(
                    api_config, query, limit, api_config.timeout
                )
                api_results[api_config.name] = result
                all_results.extend(result)
                
                # Check if we have enough results
                if len(all_results) >= min_results:
                    logger.info(f"🎯 Found {len(all_results)} results, stopping early")
                    break
                    
            except Exception as e:
                logger.warning(f"❌ {api_config.name} failed: {e}")
                continue
        
        # If we still need more results, call medium priority APIs
        if len(all_results) < min_results:
            medium_priority_apis = [api for api in self.api_configs 
                                   if api.priority == APIPriority.MEDIUM and api.enabled]
            
            for api_config in medium_priority_apis:
                try:
                    result = await self._call_api_with_timeout(
                        api_config, query, limit, api_config.timeout
                    )
                    api_results[api_config.name] = result
                    all_results.extend(result)
                    
                    if len(all_results) >= min_results:
                        break
                        
                except Exception as e:
                    logger.warning(f"❌ {api_config.name} failed: {e}")
                    continue
        
        # Remove duplicates based on title and year
        unique_results = self._remove_duplicates(all_results)
        
        logger.info(f"🎯 SMART SEARCH COMPLETE: {len(unique_results)} unique results from {len(api_results)} APIs")
        return unique_results
    
    def _remove_duplicates(self, results: List[ReferenceData]) -> List[ReferenceData]:
        """Remove duplicate results based on title and year"""
        seen = set()
        unique_results = []
        
        for result in results:
            # Create a key based on title and year
            key = (result.title or "", result.year or 0)
            if key not in seen and key[0]:  # Only add if title exists
                seen.add(key)
                unique_results.append(result)
        
        return unique_results
    
    def get_api_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all APIs"""
        status = {}
        for api_config in self.api_configs:
            status[api_config.name] = {
                "enabled": api_config.enabled,
                "priority": api_config.priority.name,
                "timeout": api_config.timeout
            }
        return status
