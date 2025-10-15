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

## 🚀 Quick Start

**New to this project?** See [QUICK_START.md](QUICK_START.md) for a 5-minute setup guide!

**Need detailed instructions?** See [SETUP_GUIDE.md](SETUP_GUIDE.md) for comprehensive setup documentation.

## Installation

### Prerequisites
- **Python 3.8+** (Recommended: Python 3.10 or 3.11)
- **Node.js 18+** (for the frontend)
- **pip** and **npm** (package managers)

### Option 1: Automated Setup (Recommended)

#### Step 1: Install Dependencies

**Windows:**
```bash
setup_dependencies.bat
```

**Linux/Mac:**
```bash
chmod +x setup_dependencies.sh
./setup_dependencies.sh
```

Or run the Python script directly:
```bash
python setup_dependencies.py
```

This will:
- ✅ Install all Python dependencies from requirements.txt
- ✅ Download SpaCy language model (en_core_web_sm)
- ✅ Verify installations
- ✅ Create necessary directories

#### Step 2: Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

#### Step 3: Run the Application

**Windows:**
```bash
setup_fullstack.bat
```

**Linux/Mac:**
```bash
chmod +x setup_fullstack.sh
./setup_fullstack.sh
```

#### Step 4: Access the Application
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs

### Option 2: Manual Setup

If the automated scripts don't work, follow these manual steps:

1. **Install Python dependencies**:
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

2. **Install Frontend dependencies**:
```bash
cd frontend
npm install
cd ..
```

3. **Start the Backend** (Terminal 1):
```bash
python run_server.py
```

4. **Start the Frontend** (Terminal 2):
```bash
cd frontend
npm run dev
```

5. **Access the application**:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Option 3: Docker Setup

If you prefer Docker (includes all dependencies):

```bash
# Build and start all services
docker-compose up --build

# Access the application
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
```

### Optional: Install Ollama (for LLM features)

1. Download Ollama from: https://ollama.ai/
2. Install and start: `ollama serve`
3. Pull the model: `ollama pull phi:latest`

### Environment Variables (Optional)

Create a `.env` file in the project root for custom configuration:

```env
# API Keys (Optional - for enhanced features)
OPENAI_API_KEY=your_key_here
CROSSREF_API_KEY=your_key_here
SEMANTIC_SCHOLAR_API_KEY=your_key_here

# Server Configuration
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
DEBUG=True
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