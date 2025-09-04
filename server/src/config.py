"""
Application configuration settings
"""
import os
from typing import Optional


class Settings:
    """Application settings"""
    
    def __init__(self):
        # API Keys
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.crossref_api_key = os.getenv("CROSSREF_API_KEY")
        self.semantic_scholar_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        
        # Application Settings
        self.debug = os.getenv("DEBUG", "True").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))
        
        # Database
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./references.db")
        
        # API Endpoints
        self.crossref_base_url = "https://api.crossref.org"
        self.openalex_base_url = "https://api.openalex.org"
        self.semantic_scholar_base_url = "https://api.semanticscholar.org/graph/v1"
        self.grobid_base_url = "https://cloud.science-miner.com/grobid/api"


# Global settings instance
settings = Settings()
