#!/usr/bin/env python3
"""
Example usage script for the Research Paper Reference Agent API
"""
import asyncio
import httpx
import json
from typing import List, Dict, Any


class ReferenceAgentClient:
    """Client for interacting with the Reference Agent API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def validate_references(self, references: List[str]) -> Dict[str, Any]:
        """Validate a list of references"""
        response = await self.client.post(
            f"{self.base_url}/validate",
            json={"references": references}
        )
        response.raise_for_status()
        return response.json()
    
    async def enhance_references(self, references: List[str]) -> Dict[str, Any]:
        """Enhance references with missing data"""
        response = await self.client.post(
            f"{self.base_url}/enhance",
            json={"references": references}
        )
        response.raise_for_status()
        return response.json()
    
    async def tag_references(self, references: List[Dict[str, Any]], style: str = "elsevier") -> Dict[str, Any]:
        """Tag references with HTML"""
        response = await self.client.post(
            f"{self.base_url}/tag",
            json={"references": references, "style": style}
        )
        response.raise_for_status()
        return response.json()
    
    async def process_references(self, references: List[str], validate_all: bool = True) -> Dict[str, Any]:
        """Complete processing pipeline"""
        response = await self.client.post(
            f"{self.base_url}/process",
            json={"references": references, "validate_all": validate_all}
        )
        response.raise_for_status()
        return response.json()
    
    async def check_api_status(self) -> Dict[str, Any]:
        """Check status of external APIs"""
        response = await self.client.get(f"{self.base_url}/apis/status")
        response.raise_for_status()
        return response.json()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()


async def main():
    """Main example function"""
    # Sample references from the user's examples
    sample_references = [
        "Hu, J. (2020). \"Student-centered\" Teaching Studying Community: Exploration on the Index of Reconstructing the Evaluation Standard of Teaching in Universities. Educational Teaching Forum, 2020 (18), 5–7.",
        "Mireshghallah F, Taram M, Vepakomma P, Singh A, Raskar R, Esmaeilzadeh H. Privacy in deep learning: A survey. 2020, arXiv preprint arXiv:2004.12254.",
        "Shokri R, Stronati M, Song C, Shmatikov V. Membership inference attacks against machine learning models. In: 2017 IEEE symposium on security and privacy. IEEE; 2017, p. 3–18."
    ]
    
    client = ReferenceAgentClient()
    
    try:
        print("🔍 Research Paper Reference Agent - Example Usage")
        print("=" * 60)
        
        # Check API health
        print("\n1. Checking API health...")
        health = await client.health_check()
        print(f"✅ API Status: {health['data']['status']}")
        print(f"✅ Agents Initialized: {health['data']['agents_initialized']}")
        
        # Check external API status
        print("\n2. Checking external API status...")
        api_status = await client.check_api_status()
        for api_name, status in api_status['data'].items():
            print(f"   {api_name}: {status['status']}")
        
        # Validate references
        print("\n3. Validating references...")
        validation_result = await client.validate_references(sample_references)
        print(f"✅ Processed: {validation_result['data']['processed_count']}/{validation_result['data']['total_count']}")
        
        for i, result in enumerate(validation_result['data']['results']):
            print(f"\n   Reference {i+1}:")
            print(f"   - Valid: {result['is_valid']}")
            print(f"   - Missing Fields: {result['missing_fields']}")
            print(f"   - Confidence: {result['confidence_score']:.2f}")
            if result['warnings']:
                print(f"   - Warnings: {result['warnings']}")
        
        # Enhance references
        print("\n4. Enhancing references...")
        enhancement_result = await client.enhance_references(sample_references)
        print(f"✅ Enhanced: {enhancement_result['data']['processed_count']}/{enhancement_result['data']['total_count']}")
        
        for i, result in enumerate(enhancement_result['data']['results']):
            if 'enhanced_data' in result:
                print(f"\n   Reference {i+1}:")
                print(f"   - Sources Used: {result['sources_used']}")
                print(f"   - Fields Found: {result['missing_fields_found']}")
        
        # Create sample reference data for tagging
        sample_reference_data = [
            {
                "title": "Student-centered Teaching Studying Community: Exploration on the Index of Reconstructing the Evaluation Standard of Teaching in Universities",
                "authors": [{"first_name": "J.", "surname": "Hu"}],
                "year": 2020,
                "journal": "Educational Teaching Forum",
                "volume": "2020",
                "issue": "18",
                "pages": "5-7"
            },
            {
                "title": "Privacy in deep learning: A survey",
                "authors": [
                    {"first_name": "F.", "surname": "Mireshghallah"},
                    {"first_name": "M.", "surname": "Taram"},
                    {"first_name": "P.", "surname": "Vepakomma"},
                    {"first_name": "A.", "surname": "Singh"},
                    {"first_name": "R.", "surname": "Raskar"},
                    {"first_name": "H.", "surname": "Esmaeilzadeh"}
                ],
                "year": 2020,
                "doi": "arXiv:2004.12254"
            }
        ]
        
        # Tag references
        print("\n5. Tagging references (Elsevier style)...")
        tagging_result = await client.tag_references(sample_reference_data, "elsevier")
        print(f"✅ Tagged: {len(tagging_result['data']['tagged_references'])} references")
        
        for i, tagged_ref in enumerate(tagging_result['data']['tagged_references']):
            print(f"\n   Reference {i+1} (Elsevier style):")
            print(f"   {tagged_ref}")
        
        # Complete processing pipeline
        print("\n6. Complete processing pipeline...")
        process_result = await client.process_references(sample_references[:2])  # Process first 2 for demo
        print(f"✅ Processed: {process_result['data']['processed_count']}/{process_result['data']['total_count']}")
        
        print("\n🎉 Example completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("\nMake sure the API server is running:")
        print("cd server && python -m src.api.main")
    
    finally:
        await client.close()


async def test_individual_apis():
    """Test individual API endpoints"""
    client = ReferenceAgentClient()
    
    try:
        print("\n🧪 Testing Individual API Endpoints")
        print("=" * 40)
        
        # Test validation with incomplete reference
        incomplete_ref = "Smith, J. (2023). Some title. Journal Name."
        print(f"\nTesting validation with incomplete reference:")
        print(f"Input: {incomplete_ref}")
        
        result = await client.validate_references([incomplete_ref])
        validation = result['data']['results'][0]
        print(f"Missing fields: {validation['missing_fields']}")
        print(f"Suggestions: {validation.get('suggestions', {})}")
        
        # Test enhancement
        print(f"\nTesting enhancement...")
        enhancement = await client.enhance_references([incomplete_ref])
        if enhancement['data']['results']:
            enhanced = enhancement['data']['results'][0]
            print(f"Sources used: {enhanced.get('sources_used', [])}")
            print(f"Fields found: {enhanced.get('missing_fields_found', [])}")
        
    except Exception as e:
        print(f"❌ Test error: {str(e)}")
    
    finally:
        await client.close()


if __name__ == "__main__":
    print("Starting Research Paper Reference Agent Example...")
    print("Make sure the API server is running on http://localhost:8000")
    print()
    
    # Run main example
    asyncio.run(main())
    
    # Run individual API tests
    asyncio.run(test_individual_apis())
