"""
Validation service for enriching references with external API data
Optimized with parallel processing, caching, and smart validation
"""
import asyncio
import json
import re
import requests
from typing import List, Dict, Any, AsyncGenerator
from loguru import logger
# Caching removed as requested


class ValidationService:
    """
    Service for validating and enriching parsed references
    """
    
    def __init__(self, enhanced_parser):
        self.enhanced_parser = enhanced_parser
        self.max_concurrent = 5  # Max parallel API calls
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
    
    def needs_validation(self, reference: Dict[str, Any]) -> bool:
        """
        Determine if a reference needs validation/enrichment
        """
        # Check if critical fields are missing
        critical_fields = ["doi", "abstract", "url"]
        missing_critical = sum(1 for field in critical_fields if not reference.get(field))
        
        # If missing 2+ critical fields, definitely needs validation
        if missing_critical >= 2:
            return True
        
        # If missing DOI or abstract, likely needs validation
        if not reference.get("doi") or not reference.get("abstract"):
            return True
        
        return False
    
    def calculate_priority(self, reference: Dict[str, Any]) -> int:
        """
        Calculate priority score for validation (higher = more important)
        """
        score = 0
        
        # Field importance weights
        weights = {
            "doi": 10,
            "abstract": 8,
            "url": 6,
            "publisher": 5,
            "journal": 4,
            "volume": 2,
            "pages": 2
        }
        
        # Add score for each missing field
        for field, weight in weights.items():
            if not reference.get(field):
                score += weight
        
        return score
    
    async def validate_single_reference(
        self, 
        reference: Dict[str, Any], 
        index: int
    ) -> Dict[str, Any]:
        """
        Validate and enrich a single reference with rate limiting
        """
        async with self.semaphore:
            try:
                # Parse with enrichment (no caching)
                ref_text = reference.get("original_text", "")
                if not ref_text:
                    return reference
                
                logger.info(f"🔍 Validating reference {index}: {ref_text[:60]}...")
                
                # Parse with enrichment (no timeout - user controls API selection)
                parsed_ref = await self.enhanced_parser.parse_reference_enhanced(
                    ref_text,
                    enable_api_enrichment=True,
                    selected_apis=getattr(self, '_selected_apis', None)
                )
                
                # Generate tagged output
                tagged_output = self.enhanced_parser.generate_tagged_output(parsed_ref, index)
                
                # Track changes from validation
                changes_made = self._track_changes(reference, parsed_ref)
                
                # Build full names
                full_names = self._build_full_names(parsed_ref)
                
                result = {
                    "index": index,
                    "original_text": ref_text,
                    "parser_used": parsed_ref.get("parser_used", "unknown"),
                    "api_enrichment_used": parsed_ref.get("api_enrichment_used", False),
                    "enrichment_sources": parsed_ref.get("enrichment_sources", []),
                    "extracted_fields": {
                        "family_names": parsed_ref.get("family_names", []),
                        "given_names": parsed_ref.get("given_names", []),
                        "full_names": full_names,
                        "year": parsed_ref.get("year"),
                        "title": parsed_ref.get("title"),
                        "journal": parsed_ref.get("journal"),
                        "doi": parsed_ref.get("doi"),
                        "pages": parsed_ref.get("pages"),
                        "publisher": parsed_ref.get("publisher"),
                        "url": parsed_ref.get("url"),
                        "abstract": parsed_ref.get("abstract")
                    },
                    "quality_metrics": {
                        "quality_improvement": parsed_ref.get("quality_improvement", 0),
                        "final_quality_score": parsed_ref.get("final_quality_score", 0)
                    },
                    "missing_fields": parsed_ref.get("missing_fields", []),
                    "tagged_output": tagged_output,
                    "flagging_analysis": parsed_ref.get("flagging_analysis", {}),
                    "comparison_analysis": parsed_ref.get("conflict_analysis", {}),
                    "doi_metadata": parsed_ref.get("doi_metadata", {}),
                    "validation_changes": changes_made,  # New: track what changed
                    "from_cache": False  # Always false since caching is disabled
                }
                
                return result
                
            except Exception as e:
                logger.error(f"❌ Error validating reference {index}: {str(e)}")
                return {
                    **reference,
                    "validation_error": str(e),
                    "api_enrichment_used": False
                }
    
    async def validate_batch_with_progress(
        self,
        references: List[Dict[str, Any]],
        mode: str = "standard",  # quick, standard, thorough, custom
        selected_indices: List[int] = None,
        selected_apis: List[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Validate a batch of references with progress updates (streaming)
        
        Args:
            references: List of parsed references
            mode: Validation mode (quick/standard/thorough/custom)
            selected_indices: Optional list of specific indices to validate
        
        Yields:
            Progress updates and results
        """
        # Filter references based on mode and selection
        refs_to_validate = []
        
        if selected_indices is not None:
            # Validate only selected references
            refs_to_validate = [
                (i, ref) for i, ref in enumerate(references)
                if i in selected_indices
            ]
            logger.info(f"📋 Validating {len(refs_to_validate)} selected references")
        else:
            # Filter based on mode
            if mode == "quick":
                # Only validate refs missing DOI
                refs_to_validate = [
                    (i, ref) for i, ref in enumerate(references)
                    if not ref.get("extracted_fields", {}).get("doi")
                ]
                logger.info(f"⚡ Quick mode: Validating {len(refs_to_validate)} references missing DOI")
            
            elif mode == "standard":
                # Validate refs that need enrichment
                refs_to_validate = [
                    (i, ref) for i, ref in enumerate(references)
                    if self.needs_validation(ref.get("extracted_fields", {}))
                ]
                logger.info(f"📊 Standard mode: Validating {len(refs_to_validate)} references")
            
            elif mode == "thorough":
                # Validate all references
                refs_to_validate = list(enumerate(references))
                logger.info(f"🔬 Thorough mode: Validating all {len(refs_to_validate)} references")
            
            else:
                # Default to standard
                refs_to_validate = [
                    (i, ref) for i, ref in enumerate(references)
                    if self.needs_validation(ref.get("extracted_fields", {}))
                ]
        
        # Store selected APIs for use during validation
        if selected_apis:
            self._selected_apis = selected_apis
        
        total_to_validate = len(refs_to_validate)
        
        if total_to_validate == 0:
            yield {
                "type": "complete",
                "message": "No references need validation",
                "results": references
            }
            return
        
        # Sort by priority for better UX
        refs_to_validate.sort(
            key=lambda x: self.calculate_priority(x[1].get("extracted_fields", {})),
            reverse=True
        )
        
        # Initial progress
        yield {
            "type": "progress",
            "progress": 0,
            "current": 0,
            "total": total_to_validate,
            "message": f"Starting validation of {total_to_validate} references..."
        }
        
        # Process in batches for better progress updates
        batch_size = 5
        validated_results = references.copy()
        validated_count = 0
        enriched_count = 0
        cached_count = 0  # Always 0 since caching is disabled
        
        for batch_start in range(0, total_to_validate, batch_size):
            try:
                batch_end = min(batch_start + batch_size, total_to_validate)
                batch = refs_to_validate[batch_start:batch_end]
                
                batch_num = batch_start//batch_size + 1
                total_batches = (total_to_validate + batch_size - 1) // batch_size
                logger.info(f"📦 Processing batch {batch_num}/{total_batches}: references {batch_start}-{batch_end-1}")
                
                # Process batch in parallel (no timeout - user controls API selection)
                tasks = [
                    self.validate_single_reference(ref, idx)
                    for idx, ref in batch
                ]
                
                logger.debug(f"🔍 Starting asyncio.gather for batch {batch_num} with {len(tasks)} tasks...")
                # Add timeout to prevent hangs (30s per ref * batch_size, max 180s total)
                batch_timeout = min(180.0, 30.0 * len(tasks))
                try:
                    batch_results = await asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True),
                        timeout=batch_timeout
                    )
                    logger.info(f"✅ Batch {batch_num} completed with {len(batch_results)} results")
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ Batch {batch_num} timed out after {batch_timeout}s - some references may be incomplete")
                    # Create timeout error results for remaining tasks
                    batch_results = []
                    for idx, ref in batch:
                        timeout_result = {
                            **ref,
                            "validation_error": f"Batch processing timed out after {batch_timeout}s",
                            "api_enrichment_used": False
                        }
                        batch_results.append(timeout_result)
                
                # Update results and count successes
                for (idx, original_ref), result in zip(batch, batch_results):
                    try:
                        if isinstance(result, Exception):
                            logger.error(f"❌ Error validating reference {idx}: {result}")
                            # Create error result to keep validation progressing
                            error_result = {
                                **original_ref,
                                "validation_error": str(result),
                                "api_enrichment_used": False
                            }
                            validated_results[idx] = error_result
                            validated_count += 1  # Count even errors as processed
                            
                            # Yield error result
                            progress = int((validated_count / total_to_validate) * 100)
                            yield {
                                "type": "result",
                                "progress": progress,
                                "current": validated_count,
                                "total": total_to_validate,
                                "index": idx,
                                "data": error_result,
                                "message": f"Validated reference {validated_count}/{total_to_validate} (with error)"
                            }
                            continue
                        
                        # Ensure result is a dict (safety check)
                        if not isinstance(result, dict):
                            logger.warning(f"⚠️ Reference {idx} returned non-dict result, converting...")
                            result = {
                                **original_ref,
                                "validation_error": "Invalid result format",
                                "api_enrichment_used": False
                            }
                        
                        validated_results[idx] = result
                        validated_count += 1
                        
                        # Check if enrichment was used
                        if result.get("api_enrichment_used"):
                            enriched_count += 1
                        
                        # Yield individual result
                        progress = int((validated_count / total_to_validate) * 100)
                        logger.info(f"📊 Progress: {validated_count}/{total_to_validate} references validated ({progress}%)")
                        yield {
                            "type": "result",
                            "progress": progress,
                            "current": validated_count,
                            "total": total_to_validate,
                            "index": idx,
                            "data": result,
                            "message": f"Validated reference {validated_count}/{total_to_validate}"
                        }
                    except Exception as result_error:
                        # Even if processing a single result fails, continue
                        logger.error(f"❌ Error processing result for reference {idx}: {result_error}")
                        error_result = {
                            **original_ref,
                            "validation_error": f"Result processing error: {str(result_error)}",
                            "api_enrichment_used": False
                        }
                        validated_results[idx] = error_result
                        validated_count += 1
                        progress = int((validated_count / total_to_validate) * 100)
                        yield {
                            "type": "result",
                            "progress": progress,
                            "current": validated_count,
                            "total": total_to_validate,
                            "index": idx,
                            "data": error_result,
                            "message": f"Validated reference {validated_count}/{total_to_validate} (with error)"
                        }
            except Exception as batch_error:
                # If entire batch fails, mark all references in batch as errors and continue
                logger.error(f"❌ Batch {batch_start//batch_size + 1} failed: {batch_error}")
                # Get batch references that should have been processed
                batch_end = min(batch_start + batch_size, total_to_validate)
                failed_batch = refs_to_validate[batch_start:batch_end]
                for idx, ref in failed_batch:
                    error_result = {
                        **ref,
                        "validation_error": f"Batch processing error: {str(batch_error)}",
                        "api_enrichment_used": False
                    }
                    validated_results[idx] = error_result
                    validated_count += 1
                    progress = int((validated_count / total_to_validate) * 100)
                    yield {
                        "type": "result",
                        "progress": progress,
                        "current": validated_count,
                        "total": total_to_validate,
                        "index": idx,
                        "data": error_result,
                        "message": f"Validated reference {validated_count}/{total_to_validate} (batch error)"
                    }
        
        logger.info(f"✅ Completed all batches: {validated_count}/{total_to_validate} references validated")
        
        # Cache stats disabled
        cache_stats = {"hits": 0, "misses": 0, "size": 0}
        
        # Final complete message - convert dict to array for frontend
        logger.info(f"📋 Converting {len(validated_results)} results to array format...")
        results_array = [validated_results[i] for i in range(len(references))]
        
        # Sanitize results to ensure JSON serializability
        sanitized_results = []
        for result in results_array:
            try:
                # Deep sanitize the result
                sanitized = self._sanitize_for_json(result)
                # Test if it's JSON serializable
                json.dumps(sanitized, default=str)
                sanitized_results.append(sanitized)
            except (TypeError, ValueError) as serialization_error:
                logger.error(f"Error serializing validation result: {serialization_error}")
                # Create a safe fallback
                safe_result = {
                    "index": result.get("index", 0),
                    "original_text": str(result.get("original_text", ""))[:500],
                    "parser_used": result.get("parser_used", "error"),
                    "error": f"Serialization error: {str(serialization_error)}"
                }
                sanitized_results.append(safe_result)
        
        # Build complete event
        complete_event = {
            "type": "complete",
            "progress": 100,
            "message": f"Validation complete! Enriched {enriched_count}/{total_to_validate} references",
            "results": sanitized_results,
            "summary": {
                "total_references": len(references),
                "validated": validated_count,
                "enriched": enriched_count,
                "from_cache": cached_count,
                "cache_stats": cache_stats
            }
        }
        
        # Test if complete event is serializable
        try:
            json.dumps(complete_event, default=str)
            logger.info(f"✅ Sending complete event with {len(sanitized_results)} sanitized results")
            yield complete_event
        except Exception as final_error:
            logger.error(f"❌ Failed to serialize complete event: {final_error}")
            # Send minimal completion event
            yield {
                "type": "complete",
                "progress": 100,
                "message": f"Validation complete! Processed {validated_count} references",
                "results": [],
                "summary": {
                    "total_references": len(references),
                    "validated": validated_count,
                    "enriched": enriched_count
                },
                "error": "Full results unavailable due to serialization error"
            }
    
    async def _improve_authors_with_llm(self, parsed_ref: dict, ref_text: str):
        """
        Use LLM to improve author extraction during validation
        This provides high accuracy while keeping parsing fast
        """
        try:
            # Check if Ollama is available
            response = requests.get("http://localhost:11434/api/tags", timeout=1)
            if response.status_code != 200:
                return  # LLM not available, skip
        except Exception:
            return  # LLM not available, skip
        
        # Only use LLM if authors are missing or look incomplete
        family_names = parsed_ref.get("family_names", [])
        if len(family_names) >= 2:  # Already has authors, skip LLM
            return
        
        logger.info(f"🤖 Using LLM to improve author extraction during validation")
        
        prompt = f"""Extract ONLY the authors from this academic reference. Return a JSON array of author objects with "given" and "family" names.

Reference: {ref_text}

Return JSON format:
{{"authors": [{{"given": "First", "family": "Last"}}, ...]}}

IMPORTANT:
- Extract ALL authors, separated by commas, "and", "&", or semicolons
- Do NOT include years, dates, or publication info
- Return ONLY the JSON, no explanation"""

        try:
            llm_response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3:latest",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=15  # Reasonable timeout for validation step
            )
            
            if llm_response.status_code == 200:
                result = llm_response.json()
                response_text = result.get("response", "")
                
                # Parse JSON response
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    authors_data = json.loads(json_match.group())
                    authors = authors_data.get("authors", [])
                    
                    if authors and len(authors) > len(family_names):
                        # LLM found more authors, use them
                        parsed_ref["family_names"] = [a.get("family", "") for a in authors]
                        parsed_ref["given_names"] = [a.get("given", "") for a in authors]
                        logger.info(f"✅ LLM improved authors: {len(authors)} authors found")
                        
        except Exception as e:
            logger.debug(f"LLM author extraction failed: {e}")
            # Silently fail, keep original NER results
    
    def _sanitize_for_json(self, obj: Any) -> Any:
        """Recursively sanitize objects to ensure JSON serializability"""
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, dict):
            return {k: self._sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._sanitize_for_json(item) for item in obj]
        elif isinstance(obj, set):
            return [self._sanitize_for_json(item) for item in obj]
        else:
            # Convert unknown types to string
            try:
                return str(obj)
            except Exception:
                return None
    
    def _build_full_names(self, parsed_ref: dict) -> list:
        """Build full names from family_names and given_names"""
        family_names = parsed_ref.get("family_names", [])
        given_names = parsed_ref.get("given_names", [])
        
        full_names = []
        for i, family in enumerate(family_names):
            if i < len(given_names) and given_names[i]:
                full_names.append(f"{given_names[i]} {family}")
            else:
                full_names.append(family)
        
        return full_names
    
    def _track_changes(self, before: Dict[str, Any], after: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Track what changed during validation"""
        changes = []
        
        # Fields to check for changes
        fields_to_check = [
            "title", "year", "journal", "doi", "pages", 
            "publisher", "url", "abstract", "volume", "issue"
        ]
        
        for field in fields_to_check:
            before_val = before.get(field) or before.get("extracted_fields", {}).get(field)
            after_val = after.get(field)
            
            # Check if value was added or changed
            if not before_val and after_val:
                changes.append({
                    "field": field,
                    "type": "added",
                    "before": None,
                    "after": str(after_val)[:100]  # Limit length
                })
            elif before_val != after_val and after_val:
                changes.append({
                    "field": field,
                    "type": "updated",
                    "before": str(before_val)[:100],  # Limit length
                    "after": str(after_val)[:100]
                })
        
        # Check authors separately
        before_family = before.get("family_names") or before.get("extracted_fields", {}).get("family_names", [])
        after_family = after.get("family_names", [])
        
        if not before_family and after_family:
            changes.append({
                "field": "authors",
                "type": "added",
                "before": None,
                "after": after_family
            })
        elif before_family != after_family:
            changes.append({
                "field": "authors",
                "type": "updated",
                "before": before_family,
                "after": after_family
            })
        
        return changes
