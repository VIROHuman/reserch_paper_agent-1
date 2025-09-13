# Research Paper Reference Agent - Enhanced

A comprehensive FastAPI application for extracting and parsing research paper references from PDFs with AI-powered parsing and external API enrichment.

## Features

- **PDF Reference Extraction**: Extract references from academic PDFs using multiple methods
- **Dual Parsing**: Simple regex-based parser and Ollama AI-powered parser
- **API Enrichment**: Automatically fill missing fields using external academic APIs
- **Reference Tagging**: Generate structured XML output for references with enhanced information
- **Multiple Paper Types**: Support for various academic paper formats
- **External API Integration**: CrossRef, OpenAlex, Semantic Scholar, and DOAJ
- **Clean Architecture**: Modular, maintainable codebase

## Project Structure

```
server/
├── src/
│   ├── api/
│   │   ├── main.py              # Full-featured API (legacy)
│   │   └── main_simple.py       # Simplified API (recommended)
│   ├── utils/
│   │   ├── pdf_processor.py     # PDF extraction and processing
│   │   ├── simple_parser.py     # Regex-based reference parser
│   │   ├── ollama_parser.py     # AI-powered reference parser
│   │   ├── enhanced_parser.py   # Enhanced parser with API integration
│   │   ├── file_handler.py      # File upload management
│   │   └── api_clients.py       # External API clients
│   ├── models/
│   │   └── schemas.py           # Pydantic data models
│   └── config.py                # Configuration settings
├── requirements.txt
└── run_server.py
```

## Installation

### Prerequisites
- Python 3.8+
- Ollama (optional, for AI-powered parsing)

### Setup

1. **Clone and setup the project**:
```bash
git clone <repository-url>
cd reserch_paper_agent
pip install -r requirements.txt
```

2. **Install Ollama (optional)**:
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model (e.g., Gemma)
ollama pull gemma3:1b
```

3. **Configure environment variables** (optional):
Create a `.env` file in the project root:
```env
# Application Settings
DEBUG=True
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
```

## Usage

### Starting the Server

```bash
python run_server.py
```

The API will be available at `http://localhost:8000`

### API Endpoints

#### 1. Health Check
```bash
curl http://localhost:8000/health
```

#### 2. Upload and Process PDF
```bash
curl -X POST "http://localhost:8000/upload-pdf" \
  -F "file=@your_paper.pdf" \
  -F "paper_type=auto" \
  -F "use_ml=true" \
  -F "use_ollama=true" \
  -F "enable_api_enrichment=true"
```

**Parameters:**
- `file`: PDF file to process
- `paper_type`: Type of paper (auto, ACL, AAAI, IEEE, Generic)
- `use_ml`: Enable ML-based processing (default: true)
- `use_ollama`: Use Ollama AI parser (default: true)
- `enable_api_enrichment`: Enable API enrichment for missing fields (default: true)

#### 3. Parse Single Reference
```bash
curl -X POST "http://localhost:8000/parse-reference" \
  -F "reference_text=Smith, J. (2023). Machine Learning in Healthcare. Nature Medicine, 15(3), 123-130." \
  -F "use_ollama=true" \
  -F "enable_api_enrichment=true"
```

### Example Response

```json
{
  "success": true,
  "message": "PDF processed successfully. Found 25 references, processed 25 successfully. 18 references enriched with API data.",
  "data": {
    "file_info": {
      "filename": "research_paper.pdf",
      "size": 2048576,
      "references_found": 25,
      "successfully_processed": 25
    },
    "paper_type": "ACL",
    "parser_used": "enhanced",
    "api_enrichment_enabled": true,
    "summary": {
      "total_references": 25,
      "successfully_processed": 25,
      "enriched_with_apis": 18,
      "total_extracted_fields": 150,
      "total_missing_fields": 12
    },
    "processing_results": [
      {
        "index": 0,
        "original_text": "Smith, J. (2023). Machine Learning in Healthcare. Nature Medicine, 15(3), 123-130.",
        "parser_used": "ollama",
        "api_enrichment_used": true,
        "enrichment_sources": ["crossref", "openalex"],
        "extracted_fields": {
          "family_names": ["Smith"],
          "given_names": ["J"],
          "year": "2023",
          "title": "Machine Learning in Healthcare",
          "journal": "Nature Medicine",
          "doi": "10.1038/s41591-023-02456-7",
          "pages": "123-130",
          "publisher": "Nature Publishing Group",
          "url": "https://www.nature.com/articles/s41591-023-02456-7",
          "abstract": "Machine learning applications in healthcare have shown..."
        },
        "missing_fields": [],
        "tagged_output": "<reference id=\"ref1\">...</reference>"
      }
    ]
  }
}
```

## Parsers

### Enhanced Parser (Recommended)
- Combines local parsing with API enrichment
- Automatically fills missing fields using external APIs
- Supports both simple and Ollama parsing
- Provides comprehensive reference information

### Simple Parser
- Uses regex patterns to extract reference fields
- Fast and lightweight
- Good for well-formatted references
- No external dependencies

### Ollama Parser
- Uses AI models (Gemma) for intelligent parsing
- Better handling of complex reference formats
- Requires Ollama to be running
- More accurate but slower

## API Enrichment

The enhanced parser automatically enriches references using multiple academic APIs:

- **CrossRef**: Academic metadata and DOI information
- **OpenAlex**: Open academic data and abstracts
- **Semantic Scholar**: AI-powered research information
- **DOAJ**: Directory of Open Access Journals

### Enrichment Features
- Automatically fills missing fields (DOI, publisher, URL, abstract)
- Cross-references information across multiple APIs
- Maintains data quality by only filling missing fields
- Provides source attribution for enriched data

## Configuration

### Paper Types
- `auto`: Automatically detect paper type
- `ACL`: ACL-style papers
- `AAAI`: AAAI/IJCAI papers
- `IEEE`: IEEE papers
- `Generic`: Generic academic papers

### Parsing Options
- `use_ml`: Enable ML-based PDF processing
- `use_ollama`: Use Ollama AI parser (requires Ollama)

## Development

### Running Tests
```bash
pytest
```

### Code Structure
- **PDF Processing**: `pdf_processor.py` handles PDF extraction
- **Reference Parsing**: `simple_parser.py` and `ollama_parser.py` handle reference parsing
- **File Management**: `file_handler.py` manages file uploads
- **API Clients**: `api_clients.py` provides external API integration

### Adding New Parsers
1. Create a new parser class in `utils/`
2. Implement `parse_reference()` and `generate_tagged_output()` methods
3. Add the parser to `main_simple.py`

## Troubleshooting

### Common Issues

1. **Ollama not found**:
   - Install Ollama: `curl -fsSL https://ollama.ai/install.sh | sh`
   - Pull a model: `ollama pull gemma3:1b`

2. **PDF processing errors**:
   - Ensure PDF is not password-protected
   - Check file size limits
   - Verify PDF contains text (not just images)

3. **Memory issues**:
   - Process smaller PDFs
   - Reduce concurrent processing

## License

This project is licensed under the MIT License.

## Acknowledgments

- Ollama for AI model integration
- pdfplumber and PyMuPDF for PDF processing
- FastAPI for the web framework