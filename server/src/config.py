import os


class Settings:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.crossref_api_key = os.getenv("CROSSREF_API_KEY")
        self.semantic_scholar_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        self.debug = os.getenv("DEBUG", "True").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./references.db")
        self.crossref_base_url = "https://api.crossref.org"
        self.openalex_base_url = "https://api.openalex.org"
        self.semantic_scholar_base_url = "https://api.semanticscholar.org/graph/v1"
        self.grobid_base_url = "https://cloud.science-miner.com/grobid/api"
settings = Settings()
