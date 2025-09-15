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
from ..utils.word_processor import WordDocumentProcessor
from ..utils.file_handler import FileHandler

# GROBID imports
from grobid_client.grobid_client import GrobidClient
import xml.etree.ElementTree as ET


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
    global validator, enhanced_validator, parser, tagger, pdf_extractor, word_processor, file_handler, parallel_client, grobid_client
    
    logger.info("Starting Research Paper Reference Agent API")
    
    # Initialize utilities
    try:
        logger.info("Initializing utilities...")
        validator = ReferenceValidator()
        enhanced_validator = EnhancedReferenceValidator()
        parser = ReferenceParser()
        tagger = ReferenceTagger()
        pdf_extractor = PDFReferenceExtractor()
        word_processor = WordDocumentProcessor()
        file_handler = FileHandler()
        parallel_client = ParallelAPIClient()
        
        # Initialize GROBID client (lazy initialization - only connect when needed)
        # Try local first, fallback to web service if needed
        grobid_client = None  # Will be initialized when first used
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
word_processor = None
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
                "/supported-paper-types",
                "/health",
                "/apis/status",
                "/parallel-api-status"
            ],
            "supported_file_types": ["pdf", "docx", "doc"]
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
                "tagger": tagger is not None,
                "pdf_processor": pdf_extractor is not None,
                "word_processor": word_processor is not None
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
    """Upload PDF or Word document and extract/process references"""
    try:
        # Check if file type is supported
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_extension = file.filename.lower().split('.')[-1]
        if file_extension not in ['pdf', 'docx', 'doc']:
            raise HTTPException(status_code=400, detail="Only PDF and Word document files are allowed (.pdf, .docx, .doc)")
        
        if not file_handler:
            raise HTTPException(status_code=500, detail="File processing utilities not initialized")
        
        # Save uploaded file
        file_path = await file_handler.save_uploaded_file(file)
        
        try:
            # Determine file type and process accordingly
            file_type = file_handler.get_file_type(file_path)
            
            if file_type == 'pdf':
                if not pdf_extractor:
                    raise HTTPException(status_code=500, detail="PDF processing utilities not initialized")
                
                # Detect paper type if auto
                if paper_type == "auto":
                    paper_type = pdf_extractor.detect_paper_type(file_path)
                
                # Process PDF with simplified extractor
                processing_result = await pdf_extractor.process_pdf_with_extraction(
                    file_path, paper_type, use_ml
                )
                
            elif file_type == 'word':
                if not word_processor:
                    raise HTTPException(status_code=500, detail="Word document processing utilities not initialized")
                
                # Detect paper type if auto
                if paper_type == "auto":
                    paper_type = word_processor.detect_paper_type(file_path)
                
                # Process Word document
                processing_result = await word_processor.process_word_document(
                    file_path, paper_type, use_ml
                )
            
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}")
            
            if not processing_result["success"]:
                return APIResponse(
                    success=False,
                    message=f"Document processing failed: {processing_result['error']}",
                    data={"file_info": {"filename": file.filename, "size": file.size, "type": file_type}}
                )
            
            references = processing_result["references"]
            
            if not references:
                return APIResponse(
                    success=False,
                    message=f"No references found in {file_type.upper()} document",
                    data={
                        "file_info": {"filename": file.filename, "size": file.size, "type": file_type},
                        "paper_type": paper_type,
                        "paper_data": processing_result["paper_data"]
                    }
                )
            
            # Process references with tagging and simplified output
            processing_results = []
            if process_references and enhanced_validator and parser and tagger:
                # Handle both raw text references and structured references
                for i, ref in enumerate(references):
                    try:
                        # Extract text from reference (handle both formats)
                        if isinstance(ref, dict) and "raw" in ref:
                            ref_text = ref["raw"]
                        elif isinstance(ref, str):
                            ref_text = ref
                        else:
                            ref_text = str(ref)
                        
                        # Parse reference
                        reference_data = parser.parse_reference(ref_text)
                        
                        # Enhanced validation
                        validation_result = await enhanced_validator.validate_reference_enhanced(
                            reference_data, ref_text, enable_cross_checking=True
                        )
                        
                        # Generate tags
                        tagged_ref = tagger.tag_references([reference_data], "elsevier")[0]
                        
                        # Simplified output - only show what's extracted, tagged, and missing
                        extracted_fields = {}
                        missing_fields = []
                        
                        # Check what was extracted
                        if reference_data.title:
                            extracted_fields["title"] = reference_data.title
                        if reference_data.authors:
                            extracted_fields["authors"] = reference_data.authors
                        if reference_data.year:
                            extracted_fields["year"] = reference_data.year
                        if reference_data.journal:
                            extracted_fields["journal"] = reference_data.journal
                        if reference_data.doi:
                            extracted_fields["doi"] = reference_data.doi
                        if reference_data.pages:
                            extracted_fields["pages"] = reference_data.pages
                        
                        # Check what's missing
                        if validation_result.missing_fields:
                            missing_fields = validation_result.missing_fields
                        
                        processing_results.append({
                            "index": i,
                            "original_text": ref_text,
                            "extracted_fields": extracted_fields,
                            "tagged_reference": tagged_ref,
                            "missing_fields": missing_fields,
                            "confidence_score": validation_result.confidence_score,
                            "is_valid": validation_result.is_valid
                        })
                    except Exception as e:
                        # Handle reference text extraction for error case too
                        if isinstance(ref, dict) and "raw" in ref:
                            ref_text = ref["raw"]
                        elif isinstance(ref, str):
                            ref_text = ref
                        else:
                            ref_text = str(ref)
                        
                        processing_results.append({
                            "index": i,
                            "original_text": ref_text,
                            "error": str(e)
                        })
            
            # Calculate summary statistics
            successful_processing = len([r for r in processing_results if "error" not in r])
            total_extracted_fields = sum(len(r.get("extracted_fields", {})) for r in processing_results if "error" not in r)
            total_missing_fields = sum(len(r.get("missing_fields", [])) for r in processing_results if "error" not in r)
            
            return APIResponse(
                success=True,
                message=f"{file_type.upper()} document processed successfully. Found {len(references)} references, processed {successful_processing} successfully.",
                data={
                    "file_info": {
                        "filename": file.filename,
                        "size": file.size,
                        "type": file_type,
                        "references_found": len(references),
                        "successfully_processed": successful_processing
                    },
                    "paper_type": paper_type,
                    "summary": {
                        "total_references": len(references),
                        "successfully_processed": successful_processing,
                        "total_extracted_fields": total_extracted_fields,
                        "total_missing_fields": total_missing_fields
                    },
                    "processing_results": processing_results
                }
            )
        
        finally:
            # Clean up uploaded file
            file_handler.cleanup_file(file_path)
    
    except Exception as e:
        logger.error(f"Document processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract-references-only", response_model=APIResponse)
async def extract_references_only(file: UploadFile = File(...)):
    """Upload PDF or Word document and extract references without processing"""
    try:
        # Check if file type is supported
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_extension = file.filename.lower().split('.')[-1]
        if file_extension not in ['pdf', 'docx', 'doc']:
            raise HTTPException(status_code=400, detail="Only PDF and Word document files are allowed (.pdf, .docx, .doc)")
        
        if not file_handler:
            raise HTTPException(status_code=500, detail="File processing utilities not initialized")
        
        file_path = await file_handler.save_uploaded_file(file)
        
        try:
            # Determine file type and process accordingly
            file_type = file_handler.get_file_type(file_path)
            
            if file_type == 'pdf':
                if not pdf_extractor:
                    raise HTTPException(status_code=500, detail="PDF processing utilities not initialized")
                
                # Detect paper type
                paper_type = pdf_extractor.detect_paper_type(file_path)
                
                # Process PDF with simplified extractor
                processing_result = await pdf_extractor.process_pdf_with_extraction(
                    file_path, paper_type, use_ml=True
                )
                
            elif file_type == 'word':
                if not word_processor:
                    raise HTTPException(status_code=500, detail="Word document processing utilities not initialized")
                
                # Detect paper type
                paper_type = word_processor.detect_paper_type(file_path)
                
                # Process Word document
                processing_result = await word_processor.process_word_document(
                    file_path, paper_type, use_ml=True
                )
            
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}")
            
            if not processing_result["success"]:
                return APIResponse(
                    success=False,
                    message=f"{file_type.upper()} processing failed: {processing_result['error']}",
                    data={"file_info": {"filename": file.filename, "size": file.size, "type": file_type}}
                )
            
            references = processing_result["references"]
            
            return APIResponse(
                success=True,
                message=f"Extracted {len(references)} references from {file_type.upper()} document",
                data={
                    "file_info": {"filename": file.filename, "size": file.size, "type": file_type},
                    "paper_type": paper_type,
                    "references": references,
                    "paper_data": processing_result["paper_data"]
                }
            )
        
        finally:
            file_handler.cleanup_file(file_path)
    
    except Exception as e:
        logger.error(f"Reference extraction error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/supported-paper-types")
async def get_supported_paper_types():
    """Get list of supported paper types for document processing"""
    if not pdf_extractor or not word_processor:
        raise HTTPException(status_code=500, detail="Document processing utilities not initialized")
    
    return APIResponse(
        success=True,
        message="Supported paper types retrieved",
        data={
            "supported_types": pdf_extractor.get_supported_paper_types(),
            "supported_file_types": ["pdf", "docx", "doc"],
            "description": "Use these paper types for better document processing accuracy. Supports both PDF and Word documents."
        }
    )


@app.post("/extract-references-grobid", response_model=APIResponse)
async def extract_references_with_grobid(file: UploadFile = File(...)):
    """Upload PDF and extract references using GROBID with structured field extraction"""
    try:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        if not file_handler:
            raise HTTPException(status_code=500, detail="File handler not initialized")
        
        # Initialize GROBID client if not already done
        global grobid_client
        if grobid_client is None:
            # Try local GROBID first, then fallback to web service
            grobid_servers = [
                "http://localhost:8070",
                "https://cloud.science-miner.com/grobid/api"
            ]
            
            for server_url in grobid_servers:
                try:
                    grobid_client = GrobidClient(config_path="./config.json")
                    logger.info(f"GROBID client initialized successfully with server: {server_url}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to connect to GROBID server {server_url}: {str(e)}")
                    if server_url == grobid_servers[-1]:  # Last server in list
                        raise HTTPException(
                            status_code=503, 
                            detail=f"No GROBID servers available. Tried: {', '.join(grobid_servers)}. Please ensure at least one GROBID server is running."
                        )
        
        # Save uploaded file
        file_path = await file_handler.save_uploaded_file(file)
        
        try:
            # Process PDF with GROBID
            logger.info(f"Processing PDF with GROBID: {file.filename}")
            result = grobid_client.process_pdf(file_path, "processReferences", generateIDs=True, consolidate_citations=True, include_raw_citations=True)
            
            if not result:
                return APIResponse(
                    success=False,
                    message="GROBID processing failed - no results returned",
                    data={"file_info": {"filename": file.filename, "size": file.size}}
                )
            
            # Parse the XML result
            root = ET.fromstring(result)
            
            # Extract references
            references = []
            reference_elements = root.findall('.//{http://www.tei-c.org/ns/1.0}ref')
            
            for i, ref_elem in enumerate(reference_elements):
                ref_data = extract_reference_fields(ref_elem, i)
                if ref_data:
                    references.append(ref_data)
            
            # Also try to get raw citations if available
            raw_citations = []
            raw_citation_elements = root.findall('.//{http://www.tei-c.org/ns/1.0}cit')
            for cit_elem in raw_citation_elements:
                raw_text = cit_elem.text
                if raw_text and raw_text.strip():
                    raw_citations.append(raw_text.strip())
            
            return APIResponse(
                success=True,
                message=f"GROBID processing completed. Found {len(references)} structured references and {len(raw_citations)} raw citations.",
                data={
                    "file_info": {
                        "filename": file.filename,
                        "size": file.size,
                        "structured_references": len(references),
                        "raw_citations": len(raw_citations)
                    },
                    "structured_references": references,
                    "raw_citations": raw_citations
                }
            )
        
        finally:
            # Clean up uploaded file
            file_handler.cleanup_file(file_path)
    
    except Exception as e:
        logger.error(f"GROBID processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def extract_reference_fields(ref_elem, index):
    """Extract specific fields from a GROBID reference element"""
    try:
        ref_data = {
            "index": index,
            "family_name": None,
            "given_name": None,
            "year": None,
            "journal": None,
            "doi": None,
            "page": None,
            "title": None
        }
        
        # Extract author information
        author_elem = ref_elem.find('.//{http://www.tei-c.org/ns/1.0}author')
        if author_elem is not None:
            # Family name (surname)
            surname_elem = author_elem.find('.//{http://www.tei-c.org/ns/1.0}surname')
            if surname_elem is not None and surname_elem.text:
                ref_data["family_name"] = surname_elem.text.strip()
            
            # Given name (forename)
            forename_elem = author_elem.find('.//{http://www.tei-c.org/ns/1.0}forename')
            if forename_elem is not None and forename_elem.text:
                ref_data["given_name"] = forename_elem.text.strip()
        
        # Extract title
        title_elem = ref_elem.find('.//{http://www.tei-c.org/ns/1.0}title')
        if title_elem is not None and title_elem.text:
            ref_data["title"] = title_elem.text.strip()
        
        # Extract journal (container title)
        journal_elem = ref_elem.find('.//{http://www.tei-c.org/ns/1.0}title[@level="j"]')
        if journal_elem is not None and journal_elem.text:
            ref_data["journal"] = journal_elem.text.strip()
        
        # Extract year
        date_elem = ref_elem.find('.//{http://www.tei-c.org/ns/1.0}date')
        if date_elem is not None and date_elem.text:
            # Try to extract year from date
            date_text = date_elem.text.strip()
            import re
            year_match = re.search(r'\b(19|20)\d{2}\b', date_text)
            if year_match:
                ref_data["year"] = year_match.group()
        
        # Extract DOI
        idno_elem = ref_elem.find('.//{http://www.tei-c.org/ns/1.0}idno[@type="DOI"]')
        if idno_elem is not None and idno_elem.text:
            ref_data["doi"] = idno_elem.text.strip()
        
        # Extract page information
        biblscope_elem = ref_elem.find('.//{http://www.tei-c.org/ns/1.0}biblScope')
        if biblscope_elem is not None:
            # Try to get page range or single page
            if biblscope_elem.text:
                ref_data["page"] = biblscope_elem.text.strip()
            # Also check for 'from' and 'to' attributes
            elif biblscope_elem.get('from') or biblscope_elem.get('to'):
                from_page = biblscope_elem.get('from', '')
                to_page = biblscope_elem.get('to', '')
                if from_page and to_page:
                    ref_data["page"] = f"{from_page}-{to_page}"
                elif from_page:
                    ref_data["page"] = from_page
        
        # Only return if we have at least some data
        if any(v for v in ref_data.values() if v is not None and v != index):
            return ref_data
        
        return None
    
    except Exception as e:
        logger.warning(f"Error extracting reference fields for index {index}: {str(e)}")
        return None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.src.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )