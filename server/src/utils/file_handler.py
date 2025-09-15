"""
File upload and management utilities
"""
import aiofiles
import os
import uuid
from pathlib import Path
from typing import Optional
from loguru import logger
from fastapi import UploadFile


class FileHandler:
    """Handle file uploads and cleanup"""
    
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)
    
    async def save_uploaded_file(self, file: UploadFile) -> str:
        """Save uploaded file to temporary directory"""
        try:
            # Generate unique filename with proper extension
            file_extension = Path(file.filename).suffix if file.filename else ".pdf"
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = self.upload_dir / unique_filename
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            logger.info(f"File saved: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            raise
    
    def get_file_type(self, file_path: str) -> str:
        """Determine file type based on extension"""
        try:
            file_extension = Path(file_path).suffix.lower()
            
            if file_extension == '.pdf':
                return 'pdf'
            elif file_extension in ['.docx', '.doc']:
                return 'word'
            else:
                return 'unknown'
                
        except Exception as e:
            logger.warning(f"Error determining file type: {e}")
            return 'unknown'
    
    def is_supported_file_type(self, file_path: str) -> bool:
        """Check if file type is supported"""
        file_type = self.get_file_type(file_path)
        return file_type in ['pdf', 'word']
    
    def cleanup_file(self, file_path: str):
        """Clean up temporary file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"File cleaned up: {file_path}")
        except Exception as e:
            logger.warning(f"Error cleaning up file {file_path}: {e}")
    
    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes"""
        try:
            return os.path.getsize(file_path)
        except Exception:
            return 0
