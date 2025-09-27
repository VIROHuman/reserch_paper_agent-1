# Research Paper Reference Agent - Full Stack

A comprehensive full-stack application for extracting and parsing research paper references from PDFs with AI-powered parsing, external API enrichment, and a modern Next.js frontend.

## Features

### Backend (FastAPI)
- **PDF Reference Extraction**: Extract references from academic PDFs using multiple methods
- **Word Document Processing**: Support for DOCX and DOC files
- **Dual Parsing**: Simple regex-based parser and Ollama AI-powered parser
- **API Enrichment**: Automatically fill missing fields using external academic APIs
- **Reference Tagging**: Generate structured XML output for references with enhanced information
- **Multiple Paper Types**: Support for various academic paper formats
- **External API Integration**: CrossRef, OpenAlex, Semantic Scholar, and DOAJ
- **Clean Architecture**: Modular, maintainable codebase

### Frontend (Next.js + TypeScript)
- **Modern UI/UX**: Clean, responsive design with Tailwind CSS
- **File Upload**: Drag-and-drop interface for PDF, DOCX, and DOC files
- **Real-time Processing**: Live progress tracking and status updates
- **Rich Results Display**: Detailed view of extracted references with quality metrics
- **API Integration**: Seamless connection to the backend FastAPI service
- **TypeScript**: Full type safety and excellent developer experience
- **Responsive Design**: Works perfectly on desktop, tablet, and mobile devices

## Project Structure

```
├── server/                      # Backend FastAPI application
│   ├── src/
│   │   ├── api/
│   │   │   └── main.py          # FastAPI application
│   │   ├── utils/
│   │   │   ├── pdf_processor.py # PDF extraction and processing
│   │   │   ├── word_processor.py # Word document processing
│   │   │   ├── enhanced_parser.py # Enhanced parser with API integration
│   │   │   ├── file_handler.py  # File upload management
│   │   │   └── api_clients.py   # External API clients
│   │   ├── models/
│   │   │   └── schemas.py       # Pydantic data models
│   │   └── config.py            # Configuration settings
│   ├── requirements.txt
│   └── run_server.py
├── frontend/                    # Frontend Next.js application
│   ├── app/                     # Next.js app directory
│   ├── components/              # React components
│   ├── lib/                     # API client and utilities
│   ├── hooks/                   # Custom React hooks
│           └── package.json
├── uploads/                     # Temporary file storage
├── logs/                        # Application logs
├── setup_fullstack.bat         # Windows setup script
├── setup_fullstack.sh          # Linux/Mac setup script
└── README.md
```

## Installation

### Option 1: Docker Setup (Recommended)

The easiest way to get started is with Docker, which includes Grobid for enhanced PDF processing:

#### Prerequisites
- Docker Desktop installed and running
- At least 4GB of available RAM

#### Quick Start with Docker
```bash
# Windows
setup_docker.bat

# Linux/Mac
./setup_docker.sh
```

#### Manual Docker Setup
```bash
# Start all services (Frontend, Backend, Grobid)
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

#### Development with Docker
```bash
# Start development environment with hot reloading
docker-compose -f docker-compose.dev.yml up --build -d
```

**Access Points:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Grobid Service: http://localhost:8070

For detailed Docker setup instructions, see [DOCKER_SETUP.md](DOCKER_SETUP.md).

### Option 2: Local Setup

#### Prerequisites
- Python 3.8+ (for backend)
- Node.js 18+ (for frontend)
- Ollama (optional, for AI-powered parsing)

#### Quick Start

1. **Clone the repository**:
```bash
git clone <repository-url>
cd reserch_paper_agent-1
```

2. **Run the setup script**:
```bash
# Windows
setup_fullstack.bat

# Linux/Mac
chmod +x setup_fullstack.sh
./setup_fullstack.sh
```

3. **Manual setup** (if scripts don't work):
```bash
# Backend setup
pip install -r requirements.txt
python run_server.py

# Frontend setup (in new terminal)
cd frontend
npm install
npm run dev
```

4. **Access the application**:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Detailed Setup

1. **Install Python dependencies**:
```bash
pip install -r requirements.txt
```

2. **Install GROBID (optional, for enhanced PDF processing)**:
```bash
# Follow the setup guide in setup_local_grobid.md
```

3. **Install Ollama (optional, for AI-powered parsing)**:
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model (e.g., Gemma)
ollama pull gemma3:1b
```

4. **Configure environment variables** (optional):
Create a `.env` file in the project root:
```env
# Application Settings
DEBUG=True
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
```

## Usage

### Using the Web Interface

1. **Start both servers** (use setup scripts or manual commands above)
2. **Open your browser** and go to `http://localhost:3000`
3. **Upload a research paper**:
   - Drag and drop a PDF, DOCX, or DOC file
   - Select processing options (paper type, validation settings)
   - Click "Process References"
4. **View results**:
   - See summary statistics
   - Expand individual references for detailed information
   - Export results as JSON

### Using the API Directly

The backend API is available at `http://localhost:8000` with documentation at `http://localhost:8000/docs`

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


## Development

### Backend Development

#### Running Tests
```bash
pytest
```

#### Code Structure
- **PDF Processing**: `pdf_processor.py` handles PDF extraction
- **Word Processing**: `word_processor.py` handles DOCX/DOC files
- **Reference Parsing**: `enhanced_parser.py` handles reference parsing with API integration
- **File Management**: `file_handler.py` manages file uploads
- **API Clients**: `api_clients.py` provides external API integration

#### Adding New Parsers
1. Create a new parser class in `utils/`
2. Implement `parse_reference()` and `generate_tagged_output()` methods
3. Add the parser to `main.py`


## Deployment

1. Install dependencies: `pip install -r requirements.txt`
2. Configure environment variables
3. Start server: `python run_server.py`

## Troubleshooting

### Common Issues

1. **File upload fails**:
   - Check file size limits
   - Ensure file type is supported (PDF, DOCX, DOC)
   - Verify file is not password-protected

2. **Processing takes too long**:
   - Large files may take several minutes
   - Check logs for errors
   - Consider processing smaller files

3. **API enrichment not working**:
   - Check internet connection
   - Verify external API availability
   - Review API rate limits

### Backend Issues

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

- **Ollama** for AI model integration
- **pdfplumber and PyMuPDF** for PDF processing
- **FastAPI** for the web framework
- **CrossRef, OpenAlex, Semantic Scholar, and DOAJ** for academic data enrichment