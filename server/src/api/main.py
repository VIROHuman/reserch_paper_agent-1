"""
FastAPI application entry point
"""
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys
from contextlib import asynccontextmanager

from ..config import settings
from ..models.schemas import (
    ReferenceValidationRequest, 
    TaggingRequest,
    APIResponse,
    ReferenceData,
    PDFUploadRequest,
    PDFProcessingResponse
)
from ..utils.validation import ReferenceValidator
from ..utils.enhanced_validation import EnhancedReferenceValidator
from ..utils.reference_parser import ReferenceParser
from ..utils.tagging import ReferenceTagger
from ..utils.api_clients import CrossRefClient, OpenAlexClient, SemanticScholarClient, DOAJClient
from ..utils.parallel_api_client import ParallelAPIClient
from ..utils.appjsonify_integration import PDFReferenceExtractor
from ..utils.file_handler import FileHandler


# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    level=settings.log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global validator, enhanced_validator, parser, tagger, pdf_extractor, file_handler, parallel_client
    
    logger.info("Starting Research Paper Reference Agent API")
    
    # Initialize utilities
    try:
        logger.info("Initializing utilities...")
        validator = ReferenceValidator()
        enhanced_validator = EnhancedReferenceValidator()
        parser = ReferenceParser()
        tagger = ReferenceTagger()
        pdf_extractor = PDFReferenceExtractor()
        file_handler = FileHandler()
        parallel_client = ParallelAPIClient()
        logger.info("Utilities initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize utilities: {str(e)}")
        raise
    
    yield
    
    logger.info("Shutting down Research Paper Reference Agent API")


# Create FastAPI app
app = FastAPI(
    title="Research Paper Reference Agent",
    description="API for validating, enhancing, and tagging research paper references",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize utilities
validator = None
enhanced_validator = None
parser = None
tagger = None
pdf_extractor = None
file_handler = None
parallel_client = None




@app.get("/")
async def root():
    """Root endpoint"""
    return APIResponse(
        success=True,
        message="Research Paper Reference Agent API is running",
        data={
            "version": "1.0.0",
            "endpoints": [
                "/validate-enhanced",
                "/enhance",
                "/tag",
                "/process",
                "/upload-pdf",
                "/extract-references-only",
                "/health",
                "/apis/status",
                "/parallel-api-status"
            ]
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return APIResponse(
        success=True,
        message="API is healthy",
        data={
            "status": "healthy",
            "utilities_initialized": validator is not None and enhanced_validator is not None and parser is not None and tagger is not None,
            "available_validators": {
                "basic": validator is not None,
                "enhanced": enhanced_validator is not None,
                "parser": parser is not None,
                "tagger": tagger is not None
            }
        }
    )

@app.post("/validate-enhanced", response_model=APIResponse)
async def validate_references_enhanced(request: ReferenceValidationRequest):
    """Enhanced validation with cross-checking and hallucination detection"""
    try:
        logger.info(f"Enhanced validation of {len(request.references)} references")
        
        if not enhanced_validator:
            raise HTTPException(status_code=500, detail="Enhanced validator not initialized")
        
        results = []
        errors = []
        
        for i, ref_text in enumerate(request.references):
            try:
                # Parse reference text using the reference parser
                if not parser:
                    raise HTTPException(status_code=500, detail="Parser not initialized")
                
                reference_data = parser.parse_reference(ref_text)
                
                # Enhanced validation with cross-checking
                validation_result = await enhanced_validator.validate_reference_enhanced(
                    reference_data, ref_text, enable_cross_checking=True
                )
                
                # Format cross-check results
                cross_check_summary = {}
                for field, result in validation_result.cross_check_results.items():
                    cross_check_summary[field] = {
                        "consensus_value": result.consensus_value,
                        "consensus_confidence": result.consensus_confidence,
                        "is_hallucinated": result.is_hallucinated,
                        "hallucination_reason": result.hallucination_reason,
                        "found_in_apis": list(result.found_values.keys()),
                        "missing_from_apis": result.missing_from_apis
                    }
                
                results.append({
                    "index": i,
                    "original_text": ref_text,
                    "is_valid": validation_result.is_valid,
                    "missing_fields": validation_result.missing_fields,
                    "confidence_score": validation_result.confidence_score,
                    "suggestions": validation_result.suggestions,
                    "warnings": validation_result.warnings,
                    "cross_check_results": cross_check_summary,
                    "hallucination_detected": validation_result.hallucination_detected,
                    "hallucination_details": validation_result.hallucination_details,
                    "api_coverage": validation_result.api_coverage
                })
                
            except Exception as e:
                logger.error(f"Error in enhanced validation of reference {i}: {str(e)}")
                errors.append(f"Reference {i}: {str(e)}")
                results.append({
                    "index": i,
                    "original_text": ref_text,
                    "error": str(e),
                    "is_valid": False
                })
        
        return APIResponse(
            success=True,
            message=f"Enhanced validation completed for {len(request.references)} references",
            data={
                "processed_count": len([r for r in results if "error" not in r]),
                "total_count": len(request.references),
                "results": results,
                "errors": errors
            }
        )
        
    except Exception as e:
        logger.error(f"Enhanced validation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/enhance", response_model=APIResponse)
async def enhance_references(request: ReferenceValidationRequest):
    """Enhance references with missing data using various APIs"""
    try:
        logger.info(f"Enhancing {len(request.references)} references")
        
        if not validator:
            raise HTTPException(status_code=500, detail="Validator not initialized")
        
        results = []
        errors = []
        
        for i, ref_text in enumerate(request.references):
            try:
                # Parse reference text (simplified)
                reference_data = ReferenceData(raw_text=ref_text)
                
                # Simple enhancement - just validate and return suggestions
                validation_result = validator.validate_reference(reference_data, ref_text)
                enhancement_result = {
                    "enhanced": reference_data,
                    "sources_used": [],
                    "missing_fields_found": [],
                    "warnings": validation_result.warnings
                }
                
                results.append({
                    "index": i,
                    "original_text": ref_text,
                    "enhanced_data": enhancement_result["enhanced"].dict(),
                    "sources_used": enhancement_result["sources_used"],
                    "missing_fields_found": enhancement_result["missing_fields_found"],
                    "warnings": enhancement_result["warnings"]
                })
                
            except Exception as e:
                logger.error(f"Error enhancing reference {i}: {str(e)}")
                errors.append(f"Reference {i}: {str(e)}")
                results.append({
                    "index": i,
                    "original_text": ref_text,
                    "error": str(e)
                })
        
        return APIResponse(
            success=True,
            message=f"Enhanced {len(request.references)} references",
            data={
                "processed_count": len([r for r in results if "error" not in r]),
                "total_count": len(request.references),
                "results": results,
                "errors": errors
            }
        )
        
    except Exception as e:
        logger.error(f"Enhancement error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tag", response_model=APIResponse)
async def tag_references(request: TaggingRequest):
    """Generate HTML tags for references"""
    try:
        logger.info(f"Tagging {len(request.references)} references in {request.style} style")
        
        if not tagger:
            raise HTTPException(status_code=500, detail="Tagger not initialized")
        
        # Convert ReferenceData objects to list
        references = request.references
        
        # Generate tags
        tagged_references = tagger.tag_references(references, request.style)
        
        # Validate tags
        validation_results = []
        for i, tagged_ref in enumerate(tagged_references):
            validation = tagger.validate_tagged_reference(tagged_ref)
            validation_results.append({
                "index": i,
                "validation": validation
            })
        
        return APIResponse(
            success=True,
            message=f"Tagged {len(references)} references",
            data={
                "tagged_references": tagged_references,
                "style": request.style,
                "validation_results": validation_results
            }
        )
        
    except Exception as e:
        logger.error(f"Tagging error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process", response_model=APIResponse)
async def process_references(request: ReferenceValidationRequest):
    """Complete processing pipeline: validate, enhance, and tag references"""
    try:
        logger.info(f"Processing {len(request.references)} references through complete pipeline")
        
        if not enhanced_validator or not parser or not tagger:
            raise HTTPException(status_code=500, detail="Utilities not initialized")
        
        # Enhanced processing pipeline
        results = []
        errors = []
        
        for i, ref_text in enumerate(request.references):
            try:
                # Parse reference text using the reference parser
                reference_data = parser.parse_reference(ref_text)
                
                # Enhanced validation with cross-checking
                validation_result = await enhanced_validator.validate_reference_enhanced(
                    reference_data, ref_text, enable_cross_checking=True
                )
                
                # Generate tags
                tagged_ref = tagger.tag_references([reference_data], "elsevier")[0]
                
                # Format cross-check results
                cross_check_summary = {}
                for field, result in validation_result.cross_check_results.items():
                    cross_check_summary[field] = {
                        "consensus_value": result.consensus_value,
                        "consensus_confidence": result.consensus_confidence,
                        "is_hallucinated": result.is_hallucinated,
                        "hallucination_reason": result.hallucination_reason,
                        "found_in_apis": list(result.found_values.keys()),
                        "missing_from_apis": result.missing_from_apis
                    }
                
                results.append({
                    "index": i,
                    "original_text": ref_text,
                    "validation": {
                        "is_valid": validation_result.is_valid,
                        "missing_fields": validation_result.missing_fields,
                        "confidence_score": validation_result.confidence_score,
                        "suggestions": validation_result.suggestions,
                        "warnings": validation_result.warnings,
                        "cross_check_results": cross_check_summary,
                        "hallucination_detected": validation_result.hallucination_detected,
                        "hallucination_details": validation_result.hallucination_details,
                        "api_coverage": validation_result.api_coverage
                    },
                    "tagged_reference": tagged_ref,
                    "status": "success"
                })
                
            except Exception as e:
                logger.error(f"Error processing reference {i}: {str(e)}")
                errors.append(f"Reference {i}: {str(e)}")
                results.append({
                    "index": i,
                    "original_text": ref_text,
                    "error": str(e),
                    "status": "error"
                })
        
        result = {
            "processed_count": len([r for r in results if r["status"] == "success"]),
            "total_count": len(request.references),
            "results": results,
            "errors": errors
        }
        
        return APIResponse(
            success=True,
            message=f"Processed {result['processed_count']}/{result['total_count']} references",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/apis/status")
async def check_api_status():
    """Check status of external APIs"""
    try:
        status = {}
        
        # Test CrossRef
        try:
            crossref_client = CrossRefClient()
            # Simple test query
            test_results = await crossref_client.search_reference("test", limit=1)
            status["crossref"] = {"status": "healthy", "results": len(test_results)}
        except Exception as e:
            status["crossref"] = {"status": "error", "error": str(e)}
        
        # Test OpenAlex
        try:
            openalex_client = OpenAlexClient()
            test_results = await openalex_client.search_reference("test", limit=1)
            status["openalex"] = {"status": "healthy", "results": len(test_results)}
        except Exception as e:
            status["openalex"] = {"status": "error", "error": str(e)}
        
        # Test Semantic Scholar
        try:
            semantic_client = SemanticScholarClient()
            test_results = await semantic_client.search_reference("test", limit=1)
            status["semantic_scholar"] = {"status": "healthy", "results": len(test_results)}
        except Exception as e:
            status["semantic_scholar"] = {"status": "error", "error": str(e)}
        
        # Test DOAJ
        try:
            doaj_client = DOAJClient()
            test_results = await doaj_client.search_reference("test", limit=1)
            status["doaj"] = {"status": "healthy", "results": len(test_results)}
        except Exception as e:
            status["doaj"] = {"status": "error", "error": str(e)}
        
        return APIResponse(
            success=True,
            message="API status checked",
            data=status
        )
        
    except Exception as e:
        logger.error(f"API status check error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/parallel-api-status")
async def check_parallel_api_status():
    """Check status of parallel API client"""
    try:
        if not parallel_client:
            raise HTTPException(status_code=500, detail="Parallel API client not initialized")
        
        status = parallel_client.get_api_status()
        
        return APIResponse(
            success=True,
            message="Parallel API status retrieved successfully",
            data={
                "parallel_client_status": "active",
                "api_configurations": status,
                "total_apis": len(status),
                "enabled_apis": len([api for api in status.values() if api["enabled"]])
            }
        )
    except Exception as e:
        logger.error(f"Parallel API status check error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload-pdf", response_model=APIResponse)
async def upload_and_process_pdf(
    file: UploadFile = File(...),
    paper_type: str = Form("auto"),
    use_ml: bool = Form(True),
    process_references: bool = Form(True),
    validate_all: bool = Form(True)
):
    """Upload PDF and extract/process references using appjsonify"""
    try:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        if not pdf_extractor or not file_handler:
            raise HTTPException(status_code=500, detail="PDF processing utilities not initialized")
        
        # Save uploaded file
        file_path = await file_handler.save_uploaded_file(file)
        
        try:
            # Detect paper type if auto
            if paper_type == "auto":
                paper_type = pdf_extractor.detect_paper_type(file_path)
            
            # Process PDF with simplified extractor
            pdf_result = await pdf_extractor.process_pdf_with_extraction(
                file_path, paper_type, use_ml
            )
            
            if not pdf_result["success"]:
                return APIResponse(
                    success=False,
                    message=f"PDF processing failed: {pdf_result['error']}",
                    data={"file_info": {"filename": file.filename, "size": file.size}}
                )
            
            references = pdf_result["references"]
            
            if not references:
                return APIResponse(
                    success=False,
                    message="No references found in PDF",
                    data={
                        "file_info": {"filename": file.filename, "size": file.size},
                        "paper_type": paper_type,
                        "paper_data": pdf_result["paper_data"]
                    }
                )
            
            # Process references if requested
            processing_results = []
            if process_references and enhanced_validator and parser:
                for i, ref_text in enumerate(references):
                    try:
                        # Parse reference
                        reference_data = parser.parse_reference(ref_text)
                        
                        # Enhanced validation
                        validation_result = await enhanced_validator.validate_reference_enhanced(
                            reference_data, ref_text, enable_cross_checking=True
                        )
                        
                        processing_results.append({
                            "index": i,
                            "original_text": ref_text,
                            "parsed_data": reference_data.dict(),
                            "validation": {
                                "is_valid": validation_result.is_valid,
                                "missing_fields": validation_result.missing_fields,
                                "confidence_score": validation_result.confidence_score,
                                "warnings": validation_result.warnings,
                                "cross_check_results": {
                                    field: {
                                        "consensus_value": result.consensus_value,
                                        "consensus_confidence": result.consensus_confidence,
                                        "is_hallucinated": result.is_hallucinated,
                                        "hallucination_reason": result.hallucination_reason,
                                        "found_in_apis": list(result.found_values.keys()),
                                        "missing_from_apis": result.missing_from_apis
                                    } for field, result in validation_result.cross_check_results.items()
                                },
                                "hallucination_detected": validation_result.hallucination_detected,
                                "api_coverage": validation_result.api_coverage
                            }
                        })
                    except Exception as e:
                        processing_results.append({
                            "index": i,
                            "original_text": ref_text,
                            "error": str(e)
                        })
            
            return APIResponse(
                success=True,
                message=f"PDF processed successfully using appjsonify. Found {len(references)} references.",
                data={
                    "file_info": {
                        "filename": file.filename,
                        "size": file.size,
                        "references_found": len(references)
                    },
                    "paper_type": paper_type,
                    "paper_data": pdf_result["paper_data"],
                    "references": references,
                    "processing_results": processing_results
                }
            )
        
        finally:
            # Clean up uploaded file
            file_handler.cleanup_file(file_path)
    
    except Exception as e:
        logger.error(f"PDF processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract-references-only", response_model=APIResponse)
async def extract_references_only(file: UploadFile = File(...)):
    """Upload PDF and extract references without processing"""
    try:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        if not pdf_extractor or not file_handler:
            raise HTTPException(status_code=500, detail="PDF processing utilities not initialized")
        
        file_path = await file_handler.save_uploaded_file(file)
        
        try:
            # Detect paper type
            paper_type = pdf_extractor.detect_paper_type(file_path)
            
            # Process PDF with simplified extractor
            pdf_result = await pdf_extractor.process_pdf_with_extraction(
                file_path, paper_type, use_ml=True
            )
            
            if not pdf_result["success"]:
                return APIResponse(
                    success=False,
                    message=f"PDF processing failed: {pdf_result['error']}",
                    data={"file_info": {"filename": file.filename, "size": file.size}}
                )
            
            references = pdf_result["references"]
            
            return APIResponse(
                success=True,
                message=f"Extracted {len(references)} references from PDF",
                data={
                    "file_info": {"filename": file.filename, "size": file.size},
                    "paper_type": paper_type,
                    "references": references,
                    "paper_data": pdf_result["paper_data"]
                }
            )
        
        finally:
            file_handler.cleanup_file(file_path)
    
    except Exception as e:
        logger.error(f"Reference extraction error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/supported-paper-types")
async def get_supported_paper_types():
    """Get list of supported paper types for PDF processing"""
    if not pdf_extractor:
        raise HTTPException(status_code=500, detail="PDF processing utilities not initialized")
    
    return APIResponse(
        success=True,
        message="Supported paper types retrieved",
        data={
            "supported_types": pdf_extractor.get_supported_paper_types(),
            "description": "Use these paper types for better PDF processing accuracy"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.src.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )