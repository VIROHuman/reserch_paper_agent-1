# Research Paper Reference Agent

A comprehensive system for validating, enhancing, and tagging research paper references using LangChain, FastAPI, and multiple academic APIs.

## Features

### Task 1: Reference Validation & Enhancement
- **Missing Field Detection**: Identifies missing fields in research paper references
- **Multi-API Integration**: Uses CrossRef, OpenAlex, Semantic Scholar, and GROBID APIs
- **AI-Powered Enhancement**: LangChain agents to fetch missing information
- **Hallucination Prevention**: Transparent reporting of what data could not be found

### Task 2: HTML Tagging
- **Multiple Formats**: Support for Elsevier, Sage Publishing, and custom styles
- **Structured Output**: Generates properly formatted XML/HTML tags
- **Batch Processing**: Handles large datasets efficiently

## Project Structure

```
server/
├── src/
│   ├── agents/
│   │   └── reference_agent.py      # LangChain agents for reference processing
│   ├── utils/
│   │   ├── tools.py               # Custom LangChain tools
│   │   ├── api_clients.py         # API clients for academic databases
│   │   ├── validation.py          # Reference validation logic
│   │   ├── tagging.py             # HTML tagging system
│   │   └── db_utils.py            # Database utilities
│   ├── models/
│   │   └── schemas.py             # Pydantic models
│   ├── api/
│   │   └── main.py                # FastAPI application
│   └── config.py                  # Configuration settings
├── requirements.txt
└── README.md
```

## Installation

### Prerequisites
- Python 3.8+
- System dependencies for lxml

### Setup

1. **Install system dependencies** (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install -y libxml2-dev libxslt1-dev python3-dev
```

2. **Clone and setup the project**:
```bash
git clone <repository-url>
cd reserch_paper_agent
pip install -r requirements.txt
```

3. **Configure environment variables**:
Create a `.env` file in the project root:
```env
# API Keys
OPENAI_API_KEY=your_openai_api_key_here
CROSSREF_API_KEY=your_crossref_api_key_here
SEMANTIC_SCHOLAR_API_KEY=your_semantic_scholar_api_key_here

# Application Settings
DEBUG=True
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
```

## Usage

### Starting the Server

```bash
cd server
python -m src.api.main
```

The API will be available at `http://localhost:8000`

### API Endpoints

#### 1. Validate References
```bash
curl -X POST "http://localhost:8000/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "references": [
      "Hu, J. (2020). Student-centered Teaching Studying Community: Exploration on the Index of Reconstructing the Evaluation Standard of Teaching in Universities. Educational Teaching Forum, 2020 (18), 5–7.",
      "Mireshghallah F, Taram M, Vepakomma P, Singh A, Raskar R, Esmaeilzadeh H. Privacy in deep learning: A survey. 2020, arXiv preprint arXiv:2004.12254."
    ]
  }'
```

#### 2. Enhance References
```bash
curl -X POST "http://localhost:8000/enhance" \
  -H "Content-Type: application/json" \
  -d '{
    "references": [
      "Incomplete reference with missing fields..."
    ]
  }'
```

#### 3. Tag References
```bash
curl -X POST "http://localhost:8000/tag" \
  -H "Content-Type: application/json" \
  -d '{
    "references": [
      {
        "title": "Sample Title",
        "authors": [{"first_name": "John", "surname": "Doe"}],
        "year": 2023,
        "journal": "Sample Journal"
      }
    ],
    "style": "elsevier"
  }'
```

#### 4. Complete Processing Pipeline
```bash
curl -X POST "http://localhost:8000/process" \
  -H "Content-Type: application/json" \
  -d '{
    "references": [
      "Your reference text here..."
    ],
    "validate_all": true
  }'
```

### Example Output

#### Validation Result
```json
{
  "success": true,
  "message": "Validated 2 references",
  "data": {
    "processed_count": 2,
    "total_count": 2,
    "results": [
      {
        "index": 0,
        "original_text": "Hu, J. (2020)...",
        "is_valid": true,
        "missing_fields": ["volume", "issue"],
        "confidence_score": 0.85,
        "suggestions": {
          "volume": {
            "candidates": ["2020"],
            "confidence": 0.7
          }
        },
        "warnings": []
      }
    ]
  }
}
```

#### Tagged Reference (Elsevier Style)
```xml
<reference id="ref1">
<label>Hu, 2020</label>
<authors>
<author>
<fnm>J.</fnm>
<surname>Hu</surname>
</author>
</authors>
<title><maintitle>Student-centered Teaching Studying Community: Exploration on the Index of Reconstructing the Evaluation Standard of Teaching in Universities</maintitle></title>
<host>
<issue>
<series>
<title><maintitle>Educational Teaching Forum</maintitle></title>
<volume>2020</volume>
</series>
<issue>18</issue>
<date>2020</date>
</issue>
<pages>
<fpage>5</fpage>
<lpage>7</lpage>
</pages>
</host>
</reference>
```

## Configuration

### API Keys
- **OpenAI**: Required for LangChain agents
- **CrossRef**: Optional, for enhanced API access
- **Semantic Scholar**: Optional, for enhanced API access

### Supported Tagging Styles
- `elsevier`: Elsevier publishing format
- `sage`: Sage Publishing format  
- `custom`: Basic custom format

## Development

### Running Tests
```bash
pytest
```

### Code Structure
- **Agents**: LangChain-based AI agents for reference processing
- **API Clients**: Async clients for external academic APIs
- **Validation**: Rule-based and AI-powered reference validation
- **Tagging**: XML/HTML generation for various publishing formats
- **Database**: SQLite-based logging and statistics

### Adding New APIs
1. Create a new client class in `api_clients.py`
2. Add configuration in `config.py`
3. Integrate with agents in `reference_agent.py`

## Troubleshooting

### Common Issues

1. **lxml Installation Error**:
   ```bash
   sudo apt-get install libxml2-dev libxslt1-dev python3-dev
   pip install lxml
   ```

2. **API Key Issues**:
   - Ensure all required API keys are set in `.env`
   - Check API key validity and permissions

3. **Memory Issues with Large Datasets**:
   - Process references in smaller batches
   - Monitor memory usage and adjust batch sizes

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- CrossRef API for reference metadata
- OpenAlex for open academic data
- Semantic Scholar for AI-powered research
- GROBID for reference parsing
- LangChain for AI agent framework
- FastAPI for the web framework
