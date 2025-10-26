import os
from langchain_ollama import OllamaLLM

class Settings:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.crossref_api_key = os.getenv("CROSSREF_API_KEY")
        self.semantic_scholar_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        self.unpaywall_email = os.getenv("UNPAYWALL_EMAIL", "user@example.com")
        self.debug = os.getenv("DEBUG", "True").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./references.db")
        self.crossref_base_url = "https://api.crossref.org"
        self.openalex_base_url = "https://api.openalex.org"
        self.semantic_scholar_base_url = "https://api.semanticscholar.org/graph/v1"
        self.arxiv_base_url = "https://export.arxiv.org/api/query"
        self.pubmed_base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        # GROBID removed - using LLM for parsing
        
        # API timeout and retry settings
        self.api_timeout = int(os.getenv("API_TIMEOUT", "30"))
        self.api_retry_count = int(os.getenv("API_RETRY_COUNT", "3"))
        self.api_retry_delay = float(os.getenv("API_RETRY_DELAY", "2.0"))
        self.rate_limit_delay = float(os.getenv("RATE_LIMIT_DELAY", "1.5"))
settings = Settings()

def get_llm() -> OllamaLLM:
    llm = OllamaLLM(
    model="phi:latest",
    temperature=0.7,
    )
    return llm