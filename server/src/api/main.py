from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
import sys
import asyncio
import uuid
import time
import os
from contextlib import asynccontextmanager

from ..config import settings
from ..models.schemas import (
    ReferenceValidationRequest, 
    TaggingRequest,
    APIResponse,
    ReferenceData,
    JobStatus,
    JobSubmissionResponse
)
from ..utils.api_clients import CrossRefClient, OpenAlexClient, SemanticScholarClient, DOAJClient
from ..utils.pdf_processor import PDFReferenceExtractor
from ..utils.word_processor import WordDocumentProcessor
from ..utils.file_handler import FileHandler
from ..utils.enhanced_parser import EnhancedReferenceParser
from ..utils.job_manager import job_manager
from ..utils.validation_service import ValidationService
from ..utils.enrichment_cache import enrichment_cache
import xml.etree.ElementTree as ET
import json

logger.remove()

# Console logging
logger.add(
    sys.stdout,
    level=settings.log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# File logging
logger.add(
    "logs/research_paper_agent.log",
    level=settings.log_level,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="10 MB",
    retention="7 days",
    compression="zip"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pdf_extractor, word_processor, file_handler, enhanced_parser, validation_service
    
    logger.info("Starting Research Paper Reference Agent API")
    
    try:
        logger.info("Initializing utilities...")
        
        # Initialize file handler first (fastest)
        file_handler = FileHandler()
        logger.info("✅ File handler initialized")
        
        # GROBID removed - using LLM for parsing
        
        # Initialize processors in background
        logger.info("Initializing PDF and Word processors...")
        pdf_extractor = PDFReferenceExtractor()
        logger.info("✅ PDF processor initialized")
        
        word_processor = WordDocumentProcessor()
        logger.info("✅ Word processor initialized")
        
        # Initialize enhanced parser last (most complex)
        logger.info("Initializing enhanced parser...")
        enhanced_parser = EnhancedReferenceParser()
        logger.info("✅ Enhanced parser initialized")
        
        # Initialize validation service
        logger.info("Initializing validation service...")
        validation_service = ValidationService(enhanced_parser)
        logger.info("✅ Validation service initialized")
        
        logger.info("🎉 All utilities initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize utilities: {str(e)}")
        raise
    
    yield
    
    logger.info("Shutting down Research Paper Reference Agent API")


app = FastAPI(
    title="Research Paper Reference Agent API",
    description="API for extracting, validating, and tagging academic references from research papers",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pdf_extractor = None
word_processor = None
file_handler = None
enhanced_parser = None
validation_service = None


def _build_full_names(parsed_ref: dict) -> list:
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


@app.get("/")
async def root():
    return APIResponse(
        success=True,
        message="Research Paper Reference Agent API is running",
        data={
            "version": "1.0.0",
            "description": "API for extracting, validating, and tagging academic references",
            "endpoints": [
                "/",
                "/health",
                "/upload-pdf",
                "/extract-references-only",
                "/supported-paper-types"
            ],
            "supported_file_types": ["pdf", "docx", "doc"]
        }
    )


@app.get("/health")
async def health_check():
    return APIResponse(
        success=True,
        message="API is healthy",
        data={
            "status": "healthy",
            "utilities_initialized": pdf_extractor is not None and word_processor is not None and file_handler is not None and enhanced_parser is not None,
            "available_processors": {
                "pdf_processor": pdf_extractor is not None,
                "word_processor": word_processor is not None,
                "file_handler": file_handler is not None,
                "enhanced_parser": enhanced_parser is not None
            }
        }
    )


@app.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    process_references: bool = Form(True),
    validate_all: bool = Form(True),
    paper_type: str = Form("auto")
):
    try:
        start_time = time.time()
        
        if not file_handler or not pdf_extractor or not word_processor or not enhanced_parser:
            raise HTTPException(status_code=500, detail="Processors not initialized")
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        allowed_extensions = {'.pdf', '.docx', '.doc'}
        file_extension = '.' + file.filename.split('.')[-1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        file_path = await file_handler.save_uploaded_file(file)
        file_type = file_handler.get_file_type(file_path)
        
        try:
            if file_type == 'pdf':
                processing_result = await pdf_extractor.process_pdf_with_extraction(
                    file_path, paper_type
                )
            elif file_type == 'word':
                processing_result = await word_processor.process_word_document(
                    file_path, paper_type
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

            processing_results = []
            if process_references and enhanced_parser:
                for i, ref in enumerate(references):
                    try:
                        if isinstance(ref, dict) and "raw" in ref:
                            ref_text = ref["raw"]
                        elif isinstance(ref, str):
                            ref_text = ref
                        else:
                            ref_text = str(ref)

                        parsed_ref = await enhanced_parser.parse_reference_enhanced(
                            ref_text,
                            enable_api_enrichment=True
                        )

                        tagged_output = enhanced_parser.generate_tagged_output(parsed_ref, i)

                        processing_results.append({
                            "index": i,
                            "original_text": ref_text,
                            "parser_used": parsed_ref.get("parser_used", "unknown"),
                            "api_enrichment_used": parsed_ref.get("api_enrichment_used", False),
                            "enrichment_sources": parsed_ref.get("enrichment_sources", []),
                            "extracted_fields": {
                                "family_names": parsed_ref.get("family_names", []),
                                "given_names": parsed_ref.get("given_names", []),
                                "full_names": _build_full_names(parsed_ref),
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
                            "doi_metadata": parsed_ref.get("doi_metadata", {})
                        })
                    except Exception as e:
                        if isinstance(ref, dict) and "raw" in ref:
                            ref_text = ref["raw"]
                        elif isinstance(ref, str):
                            ref_text = ref
                        else:
                            ref_text = str(ref)

                        processing_results.append({
                            "index": i,
                            "original_text": ref_text,
                            "parser_used": "error",
                            "api_enrichment_used": False,
                            "error": str(e)
                        })

            successful_processing = len([r for r in processing_results if "error" not in r])
            total_extracted_fields = sum(len([v for v in r.get("extracted_fields", {}).values() if v]) for r in processing_results if "error" not in r)
            total_missing_fields = sum(len(r.get("missing_fields", [])) for r in processing_results if "error" not in r)
            enriched_count = len([r for r in processing_results if r.get("api_enrichment_used", False)])

            # Calculate processing time
            end_time = time.time()
            processing_time_seconds = end_time - start_time
            processing_time_formatted = f"{int(processing_time_seconds // 60)}m {int(processing_time_seconds % 60)}s"

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
                    "processing_time": processing_time_formatted,
                    "summary": {
                        "total_references": len(references),
                        "successfully_processed": successful_processing,
                        "total_extracted_fields": total_extracted_fields,
                        "total_missing_fields": total_missing_fields,
                        "enriched_count": enriched_count
                    },
                    "processing_results": processing_results
                }
            )
            
        finally:
            file_handler.cleanup_file(file_path)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF upload error: {str(e)}")
        return APIResponse(
            success=False,
            message=f"Failed to process {file_type.upper()} document: {str(e)}",
            data={"error": str(e)}
        )


async def process_file_with_progress(
    file_path: str,
    file_type: str,
    paper_type: str,
    process_references: bool,
    enhanced_parser,
    pdf_extractor,
    word_processor
):
    """Process file with progress updates for streaming response"""
    
    start_time = time.time()
    processing_start_time = start_time
    
    # Step 1: Document processing
    yield {
        "type": "progress",
        "data": {
            "job_id": str(uuid.uuid4()),
            "status": "processing",
            "progress": 10,
            "current_step": "Extracting references from document",
            "message": "Analyzing document structure and extracting reference sections"
        }
    }
    
    if file_type == 'pdf':
        processing_result = await pdf_extractor.process_pdf_with_extraction(file_path, paper_type)
    elif file_type == 'word':
        processing_result = await word_processor.process_word_document(file_path, paper_type)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    if not processing_result["success"]:
        yield {
            "type": "error",
            "message": f"Document processing failed: {processing_result['error']}"
        }
        return

    references = processing_result["references"]
    if not references:
        yield {
            "type": "error",
            "message": f"No references found in {file_type.upper()} document"
        }
        return

    # Step 2: Reference processing
    yield {
        "type": "progress",
        "data": {
            "job_id": str(uuid.uuid4()),
            "status": "processing",
            "progress": 30,
            "current_step": "Processing references",
            "message": f"Processing {len(references)} references with AI parsing and API enrichment",
            "total_references": len(references),
            "processed_references": 0
        }
    }

    processing_results = []
    if process_references and enhanced_parser:
        for i, ref in enumerate(references):
            try:
                if isinstance(ref, dict) and "raw" in ref:
                    ref_text = ref["raw"]
                elif isinstance(ref, str):
                    ref_text = ref
                else:
                    ref_text = str(ref)

                # Update progress
                progress_percent = 30 + (i / len(references)) * 60
                
                yield {
                    "type": "progress",
                    "data": {
                        "job_id": str(uuid.uuid4()),
                        "status": "processing",
                        "progress": int(progress_percent),
                        "current_step": "Processing references",
                        "message": f"Processing reference {i+1} of {len(references)}",
                        "total_references": len(references),
                        "processed_references": i
                    }
                }

                parsed_ref = await enhanced_parser.parse_reference_enhanced(
                    ref_text,
                    enable_api_enrichment=True
                )

                tagged_output = enhanced_parser.generate_tagged_output(parsed_ref, i)

                processing_results.append({
                    "index": i,
                    "original_text": ref_text,
                    "parser_used": parsed_ref.get("parser_used", "unknown"),
                    "api_enrichment_used": parsed_ref.get("api_enrichment_used", False),
                    "enrichment_sources": parsed_ref.get("enrichment_sources", []),
                    "extracted_fields": {
                        "family_names": parsed_ref.get("family_names", []),
                        "given_names": parsed_ref.get("given_names", []),
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
                    "doi_metadata": parsed_ref.get("doi_metadata", {})
                })
                
                
            except Exception as e:
                if isinstance(ref, dict) and "raw" in ref:
                    ref_text = ref["raw"]
                elif isinstance(ref, str):
                    ref_text = ref
                else:
                    ref_text = str(ref)

                processing_results.append({
                    "index": i,
                    "original_text": ref_text,
                    "parser_used": "error",
                    "api_enrichment_used": False,
                    "error": str(e)
                })

    # Step 3: Finalizing results
    yield {
        "type": "progress",
        "data": {
            "job_id": str(uuid.uuid4()),
            "status": "processing",
            "progress": 95,
            "current_step": "Finalizing results",
            "message": "Compiling processing results and generating summary",
            "total_references": len(references),
            "processed_references": len(references)
        }
    }

    successful_processing = len([r for r in processing_results if "error" not in r])
    total_extracted_fields = sum(len([v for v in r.get("extracted_fields", {}).values() if v]) for r in processing_results if "error" not in r)
    total_missing_fields = sum(len(r.get("missing_fields", [])) for r in processing_results if "error" not in r)
    enriched_count = len([r for r in processing_results if r.get("api_enrichment_used", False)])

    # Calculate processing time
    end_time = time.time()
    processing_time_seconds = end_time - start_time
    processing_time_formatted = f"{int(processing_time_seconds // 60)}m {int(processing_time_seconds % 60)}s"

    result = APIResponse(
        success=True,
        message=f"{file_type.upper()} document processed successfully. Found {len(references)} references, processed {successful_processing} successfully.",
        data={
            "file_info": {
                "filename": "processed_file",
                "size": 0,
                "type": file_type,
                "references_found": len(references),
                "successfully_processed": successful_processing
            },
            "paper_type": paper_type,
            "processing_time": processing_time_formatted,
            "summary": {
                "total_references": len(references),
                "successfully_processed": successful_processing,
                "total_extracted_fields": total_extracted_fields,
                "total_missing_fields": total_missing_fields,
                "enriched_count": enriched_count
            },
            "processing_results": processing_results
        }
    )

    # Send completion event
    completion_event = {
        "type": "complete",
        "data": result
    }
    logger.info(f"🎉 Sending completion event with {len(processing_results)} results")
    yield completion_event
    
    # Send a final confirmation to ensure frontend receives the data
    yield {
        "type": "final",
        "message": "Processing completed successfully"
    }


@app.post("/upload-pdf-async")
async def upload_pdf_async(
    file: UploadFile = File(...),
    process_references: bool = Form(True),
    validate_all: bool = Form(True),
    paper_type: str = Form("auto")
):
    """Upload file and start async processing - returns 202 with job ID"""
    try:
        if not file_handler or not pdf_extractor or not word_processor or not enhanced_parser:
            raise HTTPException(status_code=500, detail="Processors not initialized")
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        allowed_extensions = {'.pdf', '.docx', '.doc'}
        file_extension = '.' + file.filename.split('.')[-1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Save file and create job
        file_path = await file_handler.save_uploaded_file(file)
        file_type = file_handler.get_file_type(file_path)
        job_id = job_manager.create_job(file_path)
        
        # Start async processing
        asyncio.create_task(process_file_async(
            job_id, file_path, file_type, paper_type, process_references,
            enhanced_parser, pdf_extractor, word_processor
        ))
        
        # Return 202 with job ID
        return APIResponse(
            success=True,
            message="File uploaded successfully. Processing started.",
            data=JobSubmissionResponse(
                success=True,
                message="Processing started",
                job_id=job_id,
                status="pending",
                estimated_completion_time=300  # 5 minutes estimate
            )
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in async upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/job-status/{job_id}")
async def get_job_status(job_id: str):
    """Get job status by ID"""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return APIResponse(
        success=True,
        message="Job status retrieved",
        data=job
    )


async def process_file_async(
    job_id: str,
    file_path: str,
    file_type: str,
    paper_type: str,
    process_references: bool,
    enhanced_parser,
    pdf_extractor,
    word_processor
):
    """Async file processing function"""
    try:
        start_time = time.time()
        job_manager.update_job_status(
            job_id, "processing",
            progress=10,
            current_step="Extracting references from document",
            message="Analyzing document structure and extracting reference sections"
        )
        
        # Process document
        if file_type == 'pdf':
            processing_result = await pdf_extractor.process_pdf_with_extraction(
                file_path, paper_type
            )
        elif file_type == 'word':
            processing_result = await word_processor.process_word_document(
                file_path, paper_type
            )
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        references = processing_result.get("references", [])
        
        job_manager.update_job_status(
            job_id, "processing",
            progress=30,
            current_step="Processing references",
            message=f"Processing {len(references)} references with AI parsing and API enrichment",
        )
        
        # Process references
        processing_results = []
        if process_references and enhanced_parser:
            for i, ref in enumerate(references):
                try:
                    if isinstance(ref, dict) and "raw" in ref:
                        ref_text = ref["raw"]
                    elif isinstance(ref, str):
                        ref_text = ref
                    else:
                        ref_text = str(ref)

                    parsed_ref = await enhanced_parser.parse_reference_enhanced(
                        ref_text,
                        enable_api_enrichment=True
                    )

                    tagged_output = enhanced_parser.generate_tagged_output(parsed_ref, i)

                    processing_results.append({
                        "index": i,
                        "original_text": ref_text,
                        "parser_used": parsed_ref.get("parser_used", "unknown"),
                        "api_enrichment_used": parsed_ref.get("api_enrichment_used", False),
                        "enrichment_sources": parsed_ref.get("enrichment_sources", []),
                        "extracted_fields": {
                            "family_names": parsed_ref.get("family_names", []),
                            "given_names": parsed_ref.get("given_names", []),
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
                        "doi_metadata": parsed_ref.get("doi_metadata", {})
                    })
                    
                    # Update progress
                    progress_percent = 30 + (i / len(references)) * 60
                    job_manager.update_job_status(
                        job_id, "processing",
                        progress=int(progress_percent),
                        current_step="Processing references",
                        message=f"Processing reference {i+1} of {len(references)}"
                    )
                    
                except Exception as e:
                    if isinstance(ref, dict) and "raw" in ref:
                        ref_text = ref["raw"]
                    elif isinstance(ref, str):
                        ref_text = ref
                    else:
                        ref_text = str(ref)

                    processing_results.append({
                        "index": i,
                        "original_text": ref_text,
                        "parser_used": "error",
                        "api_enrichment_used": False,
                        "error": str(e)
                    })
        
        # Calculate summary
        successful_processing = len([r for r in processing_results if "error" not in r])
        total_extracted_fields = sum(len([v for v in r.get("extracted_fields", {}).values() if v]) for r in processing_results if "error" not in r)
        total_missing_fields = sum(len(r.get("missing_fields", [])) for r in processing_results if "error" not in r)
        enriched_count = len([r for r in processing_results if r.get("api_enrichment_used", False)])
        
        # Calculate processing time
        end_time = time.time()
        processing_time_seconds = end_time - start_time
        processing_time_formatted = f"{int(processing_time_seconds // 60)}m {int(processing_time_seconds % 60)}s"
        
        # Complete job
        result = {
            "file_info": {
                "filename": os.path.basename(file_path),
                "size": os.path.getsize(file_path),
                "type": file_type,
                "references_found": len(references),
                "successfully_processed": successful_processing
            },
            "paper_type": paper_type,
            "processing_time": processing_time_formatted,
            "summary": {
                "total_references": len(references),
                "successfully_processed": successful_processing,
                "total_extracted_fields": total_extracted_fields,
                "total_missing_fields": total_missing_fields,
                "enriched_count": enriched_count
            },
            "processing_results": processing_results,
            "file_path": file_path  # Include for cleanup
        }
        
        job_manager.update_job_status(
            job_id, "completed",
            progress=100,
            current_step="Completed",
            message=f"Processing completed successfully. Found {len(references)} references, processed {successful_processing} successfully.",
            result=result
        )
        
        # Schedule gentle cleanup
        job_manager.cleanup_job_file(job_id)
        
    except Exception as e:
        logger.error(f"Async processing error for job {job_id}: {str(e)}")
        job_manager.update_job_status(
            job_id, "failed",
            progress=0,
            current_step="Failed",
            message=f"Processing failed: {str(e)}",
            error=str(e)
        )
        # Cleanup on error
        if os.path.exists(file_path):
            os.remove(file_path)


@app.post("/upload-pdf-stream")
async def upload_pdf_stream(
    file: UploadFile = File(...),
    process_references: bool = Form(True),
    validate_all: bool = Form(True),
    paper_type: str = Form("auto")
):
    """Streaming version of upload endpoint for large files"""
    try:
        if not file_handler or not pdf_extractor or not word_processor or not enhanced_parser:
            raise HTTPException(status_code=500, detail="Processors not initialized")
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        allowed_extensions = {'.pdf', '.docx', '.doc'}
        file_extension = '.' + file.filename.split('.')[-1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        file_path = await file_handler.save_uploaded_file(file)
        file_type = file_handler.get_file_type(file_path)
        
        async def generate():
            try:
                async for progress_update in process_file_with_progress(
                    file_path, file_type, paper_type, process_references,
                    enhanced_parser, pdf_extractor, word_processor
                ):
                    logger.info(f"📤 Streaming event: {progress_update.get('type', 'unknown')}")
                    yield f"data: {progress_update}\n\n"
                    
                    # Only cleanup after we've sent the complete event
                    if progress_update.get("type") == "complete":
                        logger.info("✅ Complete event sent, waiting for stream to finish...")
                        # Give a moment for the frontend to receive the data
                        await asyncio.sleep(1)
                        break
                        
            except Exception as e:
                logger.error(f"❌ Streaming error: {str(e)}")
                # Cleanup on error
                file_handler.cleanup_file(file_path)
                raise
            finally:
                # Cleanup after streaming is complete
                logger.info("🧹 Cleaning up file after stream completion")
                file_handler.cleanup_file(file_path)
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Streaming upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")


@app.post("/extract-references-only", response_model=APIResponse)
async def extract_references_only(
    file: UploadFile = File(...),
    paper_type: str = Form("auto")
):
    try:
        if not file_handler or not pdf_extractor or not word_processor or not enhanced_parser:
            raise HTTPException(status_code=500, detail="Processors not initialized")
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        allowed_extensions = {'.pdf', '.docx', '.doc'}
        file_extension = '.' + file.filename.split('.')[-1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        file_path = await file_handler.save_uploaded_file(file)
        file_type = file_handler.get_file_type(file_path)
        
        try:
            if file_type == 'pdf':
                processing_result = await pdf_extractor.process_pdf_with_extraction(
                    file_path, paper_type
                )
            elif file_type == 'word':
                processing_result = await word_processor.process_word_document(
                    file_path, paper_type
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
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reference extraction error: {str(e)}")
        return APIResponse(
            success=False,
            message=f"Failed to extract references: {str(e)}",
            data={"error": str(e)}
        )


@app.get("/supported-paper-types", response_model=APIResponse)
async def get_supported_paper_types():
    return APIResponse(
        success=True,
        message="Supported paper types and file formats",
        data={
            "supported_paper_types": ["ACL", "IEEE", "ACM", "Elsevier", "Springer", "Generic", "auto"],
            "supported_file_types": ["pdf", "docx", "doc"],
            "description": "Auto-detection attempts to identify paper type from content"
        }
    )


# ===== NEW: Two-Step Workflow Endpoints =====

@app.post("/parse-references", response_model=APIResponse)
async def parse_references_only(
    file: UploadFile = File(...),
    paper_type: str = Form("auto")
):
    """
    Step 1: Extract and parse references without API enrichment
    Returns batch_id for later validation
    """
    try:
        start_time = time.time()
        
        if not file_handler or not pdf_extractor or not word_processor or not enhanced_parser:
            raise HTTPException(status_code=500, detail="Processors not initialized")
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        allowed_extensions = {'.pdf', '.docx', '.doc'}
        file_extension = '.' + file.filename.split('.')[-1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        logger.info(f"📄 Parsing references from {file.filename} (no enrichment)")
        
        file_path = await file_handler.save_uploaded_file(file)
        file_type = file_handler.get_file_type(file_path)
        
        try:
            # Extract references from document
            if file_type == 'pdf':
                processing_result = await pdf_extractor.process_pdf_with_extraction(
                    file_path, paper_type, enable_api_enrichment=False
                )
            elif file_type == 'word':
                processing_result = await word_processor.process_word_document(
                    file_path, paper_type
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
                        "paper_type": paper_type
                    }
                )
            
            # Format references for API response
            logger.info(f"📦 Formatting {len(references)} parsed references...")
            parsed_results = []
            
            for i, ref in enumerate(references):
                try:
                    # Check if reference is already parsed (from PDF processor)
                    if isinstance(ref, dict) and "parsed" in ref:
                        # Already parsed by PDF processor!
                        parsed_ref = ref["parsed"]
                        ref_text = ref.get("raw", "")
                        logger.debug(f"✅ Using pre-parsed ref #{i}")
                    else:
                        # Need to parse (for Word docs or other formats)
                        if isinstance(ref, dict) and "raw" in ref:
                            ref_text = ref["raw"]
                        elif isinstance(ref, str):
                            ref_text = ref
                        else:
                            ref_text = str(ref)
                        
                        logger.debug(f"📝 Parsing ref #{i} WITHOUT API enrichment")
                        parsed_ref = await enhanced_parser.parse_reference_enhanced(
                            ref_text,
                            enable_api_enrichment=False
                        )
                    
                    tagged_output = enhanced_parser.generate_tagged_output(parsed_ref, i)
                    
                    parsed_results.append({
                        "index": i,
                        "original_text": ref_text,
                        "parser_used": parsed_ref.get("parser_used", "unknown"),
                        "extracted_fields": {
                            "family_names": parsed_ref.get("family_names", []),
                            "given_names": parsed_ref.get("given_names", []),
                            "year": parsed_ref.get("year"),
                            "title": parsed_ref.get("title"),
                            "journal": parsed_ref.get("journal"),
                            "doi": parsed_ref.get("doi"),
                            "pages": parsed_ref.get("pages"),
                            "publisher": parsed_ref.get("publisher"),
                            "url": parsed_ref.get("url")
                        },
                        "quality_metrics": {
                            "initial_quality_score": parsed_ref.get("initial_quality_score", 0)
                        },
                        "missing_fields": parsed_ref.get("missing_fields", []),
                        "tagged_output": tagged_output
                    })
                    
                except Exception as e:
                    logger.error(f"Error formatting reference {i}: {str(e)}")
                    ref_text = ref.get("raw", "") if isinstance(ref, dict) else str(ref)
                    parsed_results.append({
                        "index": i,
                        "original_text": ref_text,
                        "parser_used": "error",
                        "error": str(e)
                    })
            
            # Calculate statistics
            end_time = time.time()
            processing_time = f"{int((end_time - start_time) // 60)}m {int((end_time - start_time) % 60)}s"
            
            successful_parsing = len([r for r in parsed_results if "error" not in r])
            total_extracted_fields = sum(
                len([v for v in r.get("extracted_fields", {}).values() if v])
                for r in parsed_results if "error" not in r
            )
            total_missing_fields = sum(
                len(r.get("missing_fields", []))
                for r in parsed_results if "error" not in r
            )
            
            # Create batch for validation
            file_info = {
                "filename": file.filename,
                "size": file.size,
                "type": file_type,
                "paper_type": paper_type
            }
            
            batch_id = job_manager.create_parsed_batch(file_info, parsed_results)
            
            return APIResponse(
                success=True,
                message=f"Successfully parsed {successful_parsing}/{len(references)} references",
                data={
                    "batch_id": batch_id,
                    "file_info": file_info,
                    "processing_time": processing_time,
                    "summary": {
                        "total_references": len(references),
                        "successfully_parsed": successful_parsing,
                        "total_extracted_fields": total_extracted_fields,
                        "total_missing_fields": total_missing_fields,
                        "needs_validation": sum(
                            1 for r in parsed_results
                            if validation_service.needs_validation(r.get("extracted_fields", {}))
                        )
                    },
                    "parsed_references": parsed_results
                }
            )
            
        finally:
            file_handler.cleanup_file(file_path)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Parse-only error: {str(e)}")
        return APIResponse(
            success=False,
            message=f"Failed to parse references: {str(e)}",
            data={"error": str(e)}
        )


@app.get("/batch/{batch_id}", response_model=APIResponse)
async def get_batch_info(batch_id: str):
    """
    Get information about a parsed batch
    """
    try:
        batch = job_manager.get_parsed_batch(batch_id)
        
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        return APIResponse(
            success=True,
            message="Batch information retrieved",
            data=batch.to_dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving batch: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/validate-batch/{batch_id}")
async def validate_batch_streaming(
    batch_id: str,
    mode: str = Form("standard"),  # quick, standard, thorough
    selected_indices: str = Form(None)  # JSON array of indices
):
    """
    Step 2: Validate/enrich references with API calls (streaming)
    
    Modes:
    - quick: Only validate references missing DOI
    - standard: Validate references that need enrichment (default)
    - thorough: Validate all references
    """
    try:
        if not validation_service:
            raise HTTPException(status_code=500, detail="Validation service not initialized")
        
        batch = job_manager.get_parsed_batch(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        logger.info(f"🔬 Starting validation for batch {batch_id} (mode: {mode})")
        
        # Parse selected indices if provided
        indices = None
        if selected_indices:
            try:
                indices = json.loads(selected_indices)
            except:
                pass
        
        # Update batch status
        job_manager.update_batch_validation_status(batch_id, "validating")
        
        # Stream validation progress
        async def generate():
            try:
                async for event in validation_service.validate_batch_with_progress(
                    batch.parsed_references,
                    mode=mode,
                    selected_indices=indices
                ):
                    # Send event as JSON
                    yield f"data: {json.dumps(event)}\n\n"
                    
                    # Store final results
                    if event.get("type") == "complete":
                        job_manager.update_batch_validation_status(
                            batch_id,
                            "validated",
                            event.get("results")
                        )
                        
            except Exception as e:
                logger.error(f"Validation streaming error: {str(e)}")
                job_manager.update_batch_validation_status(batch_id, "failed")
                error_event = {
                    "type": "error",
                    "message": f"Validation failed: {str(e)}"
                }
                yield f"data: {json.dumps(error_event)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cache-stats", response_model=APIResponse)
async def get_cache_stats():
    """Get enrichment cache statistics"""
    return APIResponse(
        success=True,
        message="Cache statistics",
        data=enrichment_cache.get_stats()
    )


@app.post("/cache-clear", response_model=APIResponse)
async def clear_cache():
    """Clear the enrichment cache"""
    enrichment_cache.clear()
    return APIResponse(
        success=True,
        message="Cache cleared successfully",
        data={}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)