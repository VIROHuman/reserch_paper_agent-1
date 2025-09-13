"""
Ollama-based reference parser using Gemma model
"""
import ollama
import json
import re
from typing import Dict, List, Any, Optional
from loguru import logger


class OllamaReferenceParser:
    """Reference parser using Ollama with Gemma model"""
    
    def __init__(self, model_name: str = "gemma3:1b"):
        self.model_name = model_name
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Ollama client"""
        try:
            # Test if Ollama is running and model is available
            models_response = ollama.list()
            available_models = [model.model for model in models_response.models]
            
            if self.model_name not in available_models:
                logger.warning(f"Model {self.model_name} not found. Available models: {available_models}")
                # Try to use any available gemma model
                gemma_models = [model for model in available_models if 'gemma' in model.lower()]
                if gemma_models:
                    self.model_name = gemma_models[0]
                    logger.info(f"Using model: {self.model_name}")
                else:
                    logger.error("No Gemma models available")
                    return
            
            self.client = ollama
            logger.info(f"✅ Ollama client initialized with model: {self.model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Ollama client: {e}")
            self.client = None
    
    def parse_reference(self, ref_text: str) -> Dict[str, Any]:
        """Parse reference text using Ollama Gemma model"""
        logger.info(f"🤖 OLLAMA PARSING START")
        logger.info(f"📝 Input text: {ref_text[:100]}{'...' if len(ref_text) > 100 else ''}")
        
        if not self.client:
            logger.error("❌ Ollama client not initialized")
            return self._get_empty_result()
        
        try:
            # Create a structured prompt for the model
            prompt = self._create_parsing_prompt(ref_text)
            logger.info(f"🤖 Ollama prompt created (length: {len(prompt)} chars)")
            logger.info(f"📋 Ollama prompt preview: {prompt[:200]}...")
            
            # Call the model
            logger.info(f"🚀 Calling Ollama model: {self.model_name}")
            response = self.client.chat(
                model=self.model_name,
                messages=[
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                options={
                    'temperature': 0.1,  # Low temperature for consistent parsing
                    'top_p': 0.9
                }
            )
            
            # Extract the JSON response
            model_output = response['message']['content']
            logger.info(f"📊 Ollama raw response: {model_output}")
            
            # Parse the JSON response
            parsed_result = self._parse_model_response(model_output)
            logger.info(f"📋 Ollama parsed result: {parsed_result}")
            
            # Validate and clean the result
            validated_result = self._validate_and_clean_result(parsed_result)
            logger.info(f"✅ Ollama final result: {validated_result}")
            
            return validated_result
            
        except Exception as e:
            logger.error(f"❌ Error parsing reference with Ollama: {e}")
            return self._get_empty_result()
    
    def _create_parsing_prompt(self, ref_text: str) -> str:
        """Create a structured prompt for reference parsing"""
        prompt = f"""
You are a reference parsing expert. Parse the following academic reference and extract the specified fields in JSON format.

Reference: "{ref_text}"

Extract the following fields and return ONLY a valid JSON object:
{{
    "family_names": ["list of author surnames"],
    "given_names": ["list of author given names"],
    "year": "publication year",
    "title": "article/chapter title",
    "journal": "journal/conference name",
    "doi": "DOI or arXiv ID if present",
    "pages": "page numbers if present"
}}

Rules:
1. Extract ALL authors, not just the first one
2. For family_names and given_names, maintain the same order as they appear in the reference
3. If multiple authors, return arrays with corresponding entries
4. Extract the full title, including quotes if present
5. For journal, extract the publication venue name
6. For DOI, include full DOI or arXiv ID
7. For pages, extract page range (e.g., "5-7" or "123-130")
8. If a field is not present, use null
9. Return ONLY the JSON object, no additional text

Example output:
{{
    "family_names": ["Smith", "Jones"],
    "given_names": ["J", "M"],
    "year": "2023",
    "title": "Machine Learning in Healthcare",
    "journal": "Nature Medicine",
    "doi": "10.1038/s41591-023-02456-7",
    "pages": "123-130"
}}
"""
        return prompt
    
    def _parse_model_response(self, model_output: str) -> Dict[str, Any]:
        """Parse the model's JSON response"""
        try:
            # Try to extract JSON from the response
            # Remove any markdown formatting
            cleaned_output = model_output.strip()
            if cleaned_output.startswith('```json'):
                cleaned_output = cleaned_output[7:]
            if cleaned_output.endswith('```'):
                cleaned_output = cleaned_output[:-3]
            cleaned_output = cleaned_output.strip()
            
            # Parse JSON
            result = json.loads(cleaned_output)
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from model output: {e}")
            logger.error(f"Model output: {model_output}")
            
            # Try to extract fields using regex as fallback
            return self._extract_fields_with_regex(model_output)
    
    def _extract_fields_with_regex(self, text: str) -> Dict[str, Any]:
        """Fallback method to extract fields using regex if JSON parsing fails"""
        result = {
            "family_names": [],
            "given_names": [],
            "year": None,
            "title": None,
            "journal": None,
            "doi": None,
            "pages": None
        }
        
        # Extract year
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        if year_match:
            result["year"] = year_match.group()
        
        # Extract DOI
        doi_match = re.search(r'10\.\d+/[^\s,)]+', text)
        if doi_match:
            result["doi"] = doi_match.group()
        
        # Extract arXiv
        arxiv_match = re.search(r'arXiv:\s*([0-9]+\.[0-9]+)', text)
        if arxiv_match:
            result["doi"] = f"arXiv:{arxiv_match.group(1)}"
        
        return result
    
    def _validate_and_clean_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean the parsed result"""
        # Ensure required fields exist
        validated_result = {
            "family_names": [],
            "given_names": [],
            "year": None,
            "title": None,
            "journal": None,
            "doi": None,
            "pages": None,
            "missing_fields": []
        }
        
        # Validate and clean each field
        for field in ["family_names", "given_names"]:
            if field in result and isinstance(result[field], list):
                validated_result[field] = [str(item).strip() for item in result[field] if item]
            else:
                validated_result[field] = []
        
        for field in ["year", "title", "journal", "doi", "pages"]:
            if field in result and result[field]:
                validated_result[field] = str(result[field]).strip()
            else:
                validated_result[field] = None
        
        # Determine missing fields
        validated_result["missing_fields"] = self._get_missing_fields(validated_result)
        
        return validated_result
    
    def _get_missing_fields(self, result: Dict[str, Any]) -> List[str]:
        """Determine which required fields are missing"""
        missing = []
        required_fields = ["family_names", "year", "title"]
        
        for field in required_fields:
            if not result.get(field) or (isinstance(result[field], list) and len(result[field]) == 0):
                missing.append(field)
        
        return missing
    
    def _get_empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            "family_names": [],
            "given_names": [],
            "year": None,
            "title": None,
            "journal": None,
            "doi": None,
            "pages": None,
            "missing_fields": ["family_names", "year", "title"]
        }
    
    def generate_tagged_output(self, parsed_ref: Dict[str, Any], index: int) -> str:
        """Generate XML-like tagged output"""
        ref_id = f"ref{index + 1}"
        
        # Build authors section
        authors_xml = "<authors>"
        for i, (family, given) in enumerate(zip(parsed_ref["family_names"], parsed_ref["given_names"])):
            if family and given:  # Only add if both are present
                authors_xml += f'<author><fnm>{given}</fnm><surname>{family}</surname></author>'
        authors_xml += "</authors>"
        
        # Build title section
        title_xml = ""
        if parsed_ref["title"]:
            title_xml = f'<title><maintitle>{parsed_ref["title"]}</maintitle></title>'
        
        # Build year section
        year_xml = ""
        if parsed_ref["year"]:
            year_xml = f'<date>{parsed_ref["year"]}</date>'
        
        # Build journal section
        journal_xml = ""
        if parsed_ref["journal"]:
            journal_xml = f'<host><issue><series><title><maintitle>{parsed_ref["journal"]}</maintitle></title></series>{year_xml}</issue></host>'
        
        # Build pages section
        pages_xml = ""
        if parsed_ref["pages"]:
            if '-' in parsed_ref["pages"] or '–' in parsed_ref["pages"]:
                page_parts = re.split(r'[-–]', parsed_ref["pages"])
                if len(page_parts) == 2:
                    pages_xml = f'<pages><fpage>{page_parts[0]}</fpage><lpage>{page_parts[1]}</lpage></pages>'
                else:
                    pages_xml = f'<pages>{parsed_ref["pages"]}</pages>'
            else:
                pages_xml = f'<pages><fpage>{parsed_ref["pages"]}</fpage></pages>'
        
        # Build DOI section
        doi_xml = ""
        if parsed_ref["doi"]:
            doi_xml = f'<comment>DOI: {parsed_ref["doi"]}</comment>'
        
        # Create label
        label = ""
        if parsed_ref["family_names"]:
            if len(parsed_ref["family_names"]) == 1:
                label = f"{parsed_ref['family_names'][0]}, {parsed_ref['year']}"
            else:
                label = f"{parsed_ref['family_names'][0]} et al., {parsed_ref['year']}"
        
        # Combine everything
        tagged_output = f'<reference id="{ref_id}">'
        if label:
            tagged_output += f'<label>{label}</label>'
        tagged_output += authors_xml
        tagged_output += title_xml
        tagged_output += journal_xml
        tagged_output += pages_xml
        tagged_output += doi_xml
        tagged_output += '</reference>'
        
        return tagged_output


# Test function
def test_ollama_parser():
    """Test the Ollama parser with sample references"""
    parser = OllamaReferenceParser()
    
    test_cases = [
        'Hu, J. (2020). "Student-centered" Teaching Studying Community: Exploration on the Index of Reconstructing the Evaluation Standard of Teaching in Universities. Educational Teaching Forum, 2020 (18), 5–7.',
        "Mireshghallah F, Taram M, Vepakomma P, Singh A, Raskar R, Esmaeilzadeh H. Privacy in deep learning: A survey. 2020, arXiv preprint arXiv:2004.12254.",
        "Shokri R, Stronati M, Song C, Shmatikov V. Membership inference attacks against machine learning models. In: 2017 IEEE symposium on security and privacy. IEEE; 2017, p. 3–18."
    ]
    
    print("Testing Ollama Reference Parser")
    print("=" * 50)
    
    for i, ref_text in enumerate(test_cases, 1):
        print(f"\nTest Case {i}:")
        print(f"Input: {ref_text}")
        print("-" * 30)
        
        try:
            result = parser.parse_reference(ref_text)
            print(f"Extracted Fields:")
            print(f"  Family Names: {result['family_names']}")
            print(f"  Given Names: {result['given_names']}")
            print(f"  Year: {result['year']}")
            print(f"  Title: {result['title']}")
            print(f"  Journal: {result['journal']}")
            print(f"  DOI: {result['doi']}")
            print(f"  Pages: {result['pages']}")
            print(f"  Missing Fields: {result['missing_fields']}")
            
            # Generate tagged output
            tagged = parser.generate_tagged_output(result, i-1)
            print(f"\nTagged Output:")
            print(tagged)
            
        except Exception as e:
            print(f"Error: {e}")
        
        print("=" * 50)


if __name__ == "__main__":
    test_ollama_parser()
