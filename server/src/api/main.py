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
    ReferenceData
)
from ..utils.api_clients import CrossRefClient, OpenAlexClient, SemanticScholarClient, DOAJClient, GROBIDClient
from ..utils.pdf_processor import PDFReferenceExtractor
from ..utils.word_processor import WordDocumentProcessor
from ..utils.file_handler import FileHandler
from ..utils.enhanced_parser import EnhancedReferenceParser
import xml.etree.ElementTree as ET

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
    global pdf_extractor, word_processor, file_handler, grobid_client, enhanced_parser
    
    logger.info("Starting Research Paper Reference Agent API")
    
    try:
        logger.info("Initializing utilities...")
        pdf_extractor = PDFReferenceExtractor()
        word_processor = WordDocumentProcessor()
        file_handler = FileHandler()
        grobid_client = GROBIDClient()
        enhanced_parser = EnhancedReferenceParser()
        logger.info("Utilities initialized successfully")
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
grobid_client = None
enhanced_parser = None


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
            "utilities_initialized": pdf_extractor is not None and word_processor is not None and file_handler is not None and grobid_client is not None and enhanced_parser is not None,
            "available_processors": {
                "pdf_processor": pdf_extractor is not None,
                "word_processor": word_processor is not None,
                "file_handler": file_handler is not None,
                "grobid_client": grobid_client is not None,
                "enhanced_parser": enhanced_parser is not None
            }
        }
    )


@app.post("/upload-pdf", response_model=APIResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    process_references: bool = Form(True),
    validate_all: bool = Form(True),
    paper_type: str = Form("auto"),
    use_ml: bool = Form(True)
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
                    file_path, paper_type, use_ml
                )
            elif file_type == 'word':
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
                            use_ollama=use_ml,
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


@app.post("/extract-references-only", response_model=APIResponse)
async def extract_references_only(
    file: UploadFile = File(...),
    paper_type: str = Form("auto"),
    use_ml: bool = Form(True)
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
                    file_path, paper_type, use_ml
                )
            elif file_type == 'word':
                processing_result = await word_processor.process_word_document(
                    file_path, paper_type, use_ml
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)