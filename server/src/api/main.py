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
from ..utils.api_clients import CrossRefClient, OpenAlexClient, SemanticScholarClient, DOAJClient
from ..utils.pdf_processor import PDFReferenceExtractor
from ..utils.word_processor import WordDocumentProcessor
from ..utils.file_handler import FileHandler

from grobid_client.grobid_client import GrobidClient
import xml.etree.ElementTree as ET

logger.remove()
logger.add(
    sys.stdout,
    level=settings.log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pdf_extractor, word_processor, file_handler, grobid_client
    
    logger.info("Starting Research Paper Reference Agent API")
    
    try:
        logger.info("Initializing utilities...")
        pdf_extractor = PDFReferenceExtractor()
        word_processor = WordDocumentProcessor()
        file_handler = FileHandler()
        grobid_client = None
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
            "utilities_initialized": pdf_extractor is not None and word_processor is not None and file_handler is not None,
            "available_processors": {
                "pdf_processor": pdf_extractor is not None,
                "word_processor": word_processor is not None,
                "file_handler": file_handler is not None
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
        if not file_handler or not pdf_extractor or not word_processor:
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
                result = await pdf_extractor.process_pdf_with_extraction(
                    file_path, paper_type, use_ml
                )
            elif file_type == 'word':
                result = await word_processor.process_word_document(
                    file_path, paper_type, use_ml
                )
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}")
            
            if not result.get('success', False):
                raise HTTPException(status_code=400, detail=result.get('message', 'Processing failed'))
            
            references = result.get('references', [])
            
            file_info = {
                "filename": file.filename,
                "size": file_handler.get_file_size(file_path),
                "type": file_type
            }
            
            return APIResponse(
                success=True,
                message=f"Successfully processed {file_type.upper()} document",
                data={
                    "file_info": file_info,
                    "paper_type": result.get('paper_type', 'Unknown'),
                    "paper_data": result.get('paper_data', {}),
                    "references": references,
                    "reference_count": len(references)
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
        if not file_handler or not pdf_extractor or not word_processor:
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
                result = await pdf_extractor.process_pdf_with_extraction(
                    file_path, paper_type, use_ml
                )
            elif file_type == 'word':
                result = await word_processor.process_word_document(
                    file_path, paper_type, use_ml
                )
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}")
            
            if not result.get('success', False):
                raise HTTPException(status_code=400, detail=result.get('message', 'Processing failed'))
            
            references = result.get('references', [])
            
            return APIResponse(
                success=True,
                message=f"Successfully extracted references from {file_type.upper()} document",
                data={
                    "references": references,
                    "reference_count": len(references)
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