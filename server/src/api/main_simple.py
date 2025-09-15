from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys
from contextlib import asynccontextmanager
import re
from typing import List, Dict, Any, Optional

from ..config import settings
from ..models.schemas import APIResponse
from ..utils.pdf_processor import PDFReferenceExtractor
from ..utils.word_processor import WordDocumentProcessor
from ..utils.file_handler import FileHandler
from ..utils.enhanced_parser import EnhancedReferenceParser

logger.remove()
logger.add(
    sys.stdout,
    level="DEBUG",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)




@asynccontextmanager
async def lifespan(app: FastAPI):
    global pdf_extractor, word_processor, file_handler, enhanced_parser
    
    logger.info("Starting Enhanced Research Paper Reference Agent API")
    
    try:
        logger.info("Initializing utilities...")
        pdf_extractor = PDFReferenceExtractor()
        word_processor = WordDocumentProcessor()
        file_handler = FileHandler()
        enhanced_parser = EnhancedReferenceParser()
        logger.info("Utilities initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize utilities: {str(e)}")
        raise
    
    yield
    
    logger.info("Shutting down Enhanced Research Paper Reference Agent API")


# Create FastAPI app
app = FastAPI(
    title="Simplified Research Paper Reference Agent API",
    description="Simple reference extraction from PDFs",
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


@app.get("/")
async def root():
    """Root endpoint"""
    return APIResponse(
        success=True,
        message="Simplified Research Paper Reference Agent API is running",
        data={
            "version": "1.0.0",
            "endpoints": ["/upload-pdf", "/parse-reference", "/debug-parse", "/health"],
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
            "utilities_initialized": pdf_extractor is not None and word_processor is not None and file_handler is not None and enhanced_parser is not None,
            "parsers_available": {
                "enhanced_parser": enhanced_parser is not None,
                "simple_parser": enhanced_parser.simple_parser is not None if enhanced_parser else False,
                "ollama_parser": enhanced_parser.ollama_parser is not None and enhanced_parser.ollama_parser.client is not None if enhanced_parser else False,
                "api_clients": {
                    "crossref": enhanced_parser.crossref_client is not None if enhanced_parser else False,
                    "openalex": enhanced_parser.openalex_client is not None if enhanced_parser else False,
                    "semantic_scholar": enhanced_parser.semantic_client is not None if enhanced_parser else False,
                    "doaj": enhanced_parser.doaj_client is not None if enhanced_parser else False
                },
                "document_processors": {
                    "pdf_processor": pdf_extractor is not None,
                    "word_processor": word_processor is not None
                }
            }
        }
    )


@app.post("/upload-pdf", response_model=APIResponse)
async def upload_and_process_pdf(
    file: UploadFile = File(...),
    paper_type: str = Form("auto"),
    use_ml: bool = Form(True),
    use_ollama: bool = Form(True),
    enable_api_enrichment: bool = Form(True)
):
    """Upload PDF or Word document and extract/process references with enhanced parsing and API enrichment"""
    try:
        # Check if file type is supported
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_extension = file.filename.lower().split('.')[-1]
        if file_extension not in ['pdf', 'docx', 'doc']:
            raise HTTPException(status_code=400, detail="Only PDF and Word document files are allowed (.pdf, .docx, .doc)")
        
        if not file_handler or not enhanced_parser:
            raise HTTPException(status_code=500, detail="Document processing utilities not initialized")
        
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
            
            # Process references with enhanced parser
            processing_results = []
            
            for i, ref_data in enumerate(references):
                try:
                    # Extract raw text from the reference data (handle both formats)
                    if isinstance(ref_data, dict) and "raw" in ref_data:
                        ref_text = ref_data["raw"]
                    elif isinstance(ref_data, str):
                        ref_text = ref_data
                    else:
                        ref_text = str(ref_data)
                    
                    # Use enhanced parser with API enrichment
                    parsed_ref = await enhanced_parser.parse_reference_enhanced(
                        ref_text, 
                        use_ollama=use_ollama,
                        enable_api_enrichment=enable_api_enrichment
                    )
                    
                    # Generate tagged output
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
                    # Handle reference text extraction for error case too
                    if isinstance(ref_data, dict) and "raw" in ref_data:
                        ref_text = ref_data["raw"]
                    elif isinstance(ref_data, str):
                        ref_text = ref_data
                    else:
                        ref_text = str(ref_data)
                    
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
                        "total_missing_fields": total_missing_fields,
                        "enriched_count": enriched_count
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


@app.post("/parse-reference", response_model=APIResponse)
async def parse_single_reference(
    reference_text: str = Form(...),
    use_ollama: bool = Form(True),
    enable_api_enrichment: bool = Form(True)
):
    """Parse a single reference with enhanced parsing and API enrichment"""
    try:
        if not enhanced_parser:
            raise HTTPException(status_code=500, detail="Enhanced parser not initialized")
        
        # Parse reference with enhanced parser
        parsed_ref = await enhanced_parser.parse_reference_enhanced(
            reference_text,
            use_ollama=use_ollama,
            enable_api_enrichment=enable_api_enrichment
        )
        
        # Generate tagged output
        tagged_output = enhanced_parser.generate_tagged_output(parsed_ref, 0)
        
        return APIResponse(
            success=True,
            message="Reference parsed successfully",
            data={
                "original_text": reference_text,
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
            }
        )
        
    except Exception as e:
        logger.error(f"Reference parsing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/debug-parse", response_model=APIResponse)
async def debug_parse_reference(
    reference_text: str = Form(...),
    use_ollama: bool = Form(True),
    enable_api_enrichment: bool = Form(True)
):
    """Debug endpoint for single reference parsing with detailed logging"""
    try:
        if not enhanced_parser:
            raise HTTPException(status_code=500, detail="Enhanced parser not initialized")
        
        logger.info(f"🐛 DEBUG ENDPOINT: Starting debug parsing")
        logger.info(f"📝 Reference text: {reference_text}")
        logger.info(f"🤖 Use Ollama: {use_ollama}")
        logger.info(f"🌐 API Enrichment: {enable_api_enrichment}")
        
        # Parse reference with enhanced parser
        parsed_ref = await enhanced_parser.parse_reference_enhanced(
            reference_text,
            use_ollama=use_ollama,
            enable_api_enrichment=enable_api_enrichment
        )
        
        # Generate tagged output
        tagged_output = enhanced_parser.generate_tagged_output(parsed_ref, 0)
        
        logger.info(f"🐛 DEBUG ENDPOINT: Parsing completed")
        
        return APIResponse(
            success=True,
            message="Debug parsing completed - check logs for detailed output",
            data={
                "original_text": reference_text,
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
            }
        )
        
    except Exception as e:
        logger.error(f"🐛 DEBUG ENDPOINT: Error - {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract-doi-metadata", response_model=APIResponse)
async def extract_doi_metadata(doi: str = Form(...)):
    """Extract metadata for a specific DOI"""
    try:
        if not enhanced_parser:
            raise HTTPException(status_code=500, detail="Enhanced parser not initialized")
        
        logger.info(f"🔍 DOI METADATA EXTRACTION: {doi}")
        
        # Extract DOI metadata
        doi_metadata = await enhanced_parser.doi_extractor.extract_metadata(doi)
        
        if doi_metadata.get("error"):
            return APIResponse(
                success=False,
                message=f"DOI metadata extraction failed: {doi_metadata['error']}",
                data={"doi": doi, "error": doi_metadata["error"]}
            )
        
        return APIResponse(
            success=True,
            message=f"DOI metadata extracted successfully from {doi_metadata.get('source_api', 'unknown')}",
            data={
                "doi": doi,
                "metadata": doi_metadata,
                "source_api": doi_metadata.get("source_api", "unknown")
            }
        )
        
    except Exception as e:
        logger.error(f"DOI metadata extraction error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.src.api.main_simple:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
