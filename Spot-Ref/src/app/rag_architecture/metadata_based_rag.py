# src/app/rag_architecture/metadata_based_rag.py

import os
from typing import List, Dict, Any
from dotenv import load_dotenv
import json
import re

# LangChain / LangGraph / Chainlit imports
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage

# Import the QdrantIngestor class
from src.vector_db.vector_store_ingestor import QdrantIngestor
from src.utils.prompt_list import METADATA_EXTRACTION_PROMPT

load_dotenv()

AZURE_API_KEY     = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_ENDPOINT    = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt4o")
QDRANT_HOST       = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT       = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "spot-ref-docs")

# ─── METADATA-BASED RAG IMPLEMENTATION ─────────────────────────────────────
class MetadataBasedRAG:
    """
    Metadata-based RAG architecture:
    1. User question → analysis to extract relevant metadata
    2. Metadata search in Qdrant (filtering)
    3. Vectorial search on filtered chunks
    4. Combine results
    5. Send to LLM for synthesis
    """
    
    def __init__(self):
        self.ingestor = QdrantIngestor(
            collection_name=QDRANT_COLLECTION,
            host=QDRANT_HOST,
            port=QDRANT_PORT
        )
        self.llm = AzureChatOpenAI(
            model_name=AZURE_OPENAI_DEPLOYMENT,
            temperature=0,
            openai_api_key=AZURE_API_KEY,
            azure_endpoint=AZURE_ENDPOINT
        )
        
    def extract_metadata_filters(self, query: str) -> Dict[str, Any]:
        """
        Analyzes the question to extract relevant metadata filters
        
        Args:
            query: User question
            
        Returns:
            Dictionary of metadata filters
        """
        try:
            prompt = METADATA_EXTRACTION_PROMPT.format(query=query)
            response = self.llm.invoke([HumanMessage(content=prompt)])
            # Try to parse the response as JSON
            # Nettoyage des balises ```json ``` éventuelles
            clean = re.sub(r"^```(?:json)?\s*", "", response.content.strip())
            clean = re.sub(r"\s*```$", "", clean)
            filters = json.loads(clean)
            return filters if isinstance(filters, dict) else {}
        except Exception as e:
            # In case of error, return empty dictionary
            print(f"\U0001F198 [EXTRACT_METADATA_FILTERS] {e}")
            return {}
    
    def search_by_metadata(self, filters: Dict[str, Any], limit: int = 10, query: str = "") -> List[Dict]:
        """
        Search by metadata in Qdrant
        
        Args:
            filters: Dictionary of metadata filters
            limit: Maximum number of results
            
        Returns:
            List of documents found with metadata
        """
        try:
            # Build Qdrant filters according to real available metadata
            qdrant_filters = []
            
            # Filters based on real metadata: client, tech, localisation, field, doc_name
            if "client" in filters:
                qdrant_filters.append({
                    "key": "client",
                    "match": {"text": filters["client"]}
                })
            
            if "tech" in filters:
                qdrant_filters.append({
                    "key": "tech", 
                    "match": {"text": filters["tech"]}
                })
                
            if "localisation" in filters:
                qdrant_filters.append({
                    "key": "localisation",
                    "match": {"text": filters["localisation"]}
                })
                
            if "field" in filters:
                qdrant_filters.append({
                    "key": "field",
                    "match": {"value": filters["field"]}
                })
                
            if "doc_name" in filters:
                qdrant_filters.append({
                    "key": "doc_name",
                    "match": {"text": filters["doc_name"]}
                })
            # Use search method with filters if available
            # Otherwise, use classic search and filter manually
            results = []
            if hasattr(self.ingestor, 'search_with_filters'):
                results = self.ingestor.search_with_filters(filters=qdrant_filters, limit=limit, query=query)
            if results == []:
                # Fallback: classic search then manual filtering
                # This part should be adapted according to QdrantIngestor implementation
                print("🔍 [SEARCH_BY_METADATA] No results found with filters, using classic search")
                results = self.ingestor.search(query, limit=limit)
            return results
        except Exception as e:
            print(f"Error during metadata search: {e}")
            return []
    
    def vector_search_on_filtered_chunks(self, query: str, metadata_results: List[Dict], limit: int = 5) -> List[Dict]:
        """
        Vectorial search on chunks filtered by metadata
        
        Args:
            query: User question
            metadata_results: Results from metadata search
            limit: Maximum number of results
            
        Returns:
            List of most relevant chunks
        """
        try:
            # If we have metadata results, do a restricted vectorial search
            if metadata_results:
                # Extract IDs of documents found by metadata
                filtered_ids = [result.get("id") for result in metadata_results if result.get("id")]
                
                # Vectorial search restricted to filtered documents
                # Note: This implementation depends on availability of a restricted search method
                if hasattr(self.ingestor, 'search_with_id_filter'):
                    return self.ingestor.search_with_id_filter(query, filtered_ids, limit=limit)
                else:
                    # Fallback: classic vectorial search then filtering
                    all_results = self.ingestor.search(query, limit=limit*2)
                    return [r for r in all_results if r.get("id") in filtered_ids][:limit]
            else:
                # No metadata filtering, classic vectorial search
                return self.ingestor.search(query, limit=limit)
                
        except Exception as e:
            print(f"Error during filtered vectorial search: {e}")
            return self.ingestor.search(query, limit=limit)
    
    def combine_results(self, results: List[Dict]) -> List[Dict]:
        """
        Concatenate text field and propagate sharepoint_url if present.
        """
        doc_groups = {}
        for result in results:
            meta = result['metadata']
            doc_name = meta['doc_name']
            if doc_name not in doc_groups:
                doc_groups[doc_name] = {
                    "client": meta.get("client"),
                    "tech": meta.get("tech"), 
                    "localisation": meta.get("localisation"),
                    "field": meta.get("field"),
                    "doc_name": doc_name,
                    "description": result["text"],
                    "pptx_path": meta.get("pptx_path"),
                    "sharepoint_url": meta.get("sharepoint_url"),
                }
            else:
                doc_groups[doc_name]["description"] += ";" + result["text"]
        return list(doc_groups.values())
    
    def search_and_synthesize(self, query: str, top_k: int = 5) -> List[Dict] | None:
        """
        Complete implementation of metadata-based RAG
        
        Args:
            query: User question
            top_k: Number of projects to retrieve for synthesis
            
        Returns:
            list of projects with at least one chunk relevant to the user question
        """
        
        try:
            # 1) Extract metadata filters from the question
            filters = self.extract_metadata_filters(query)
            if filters:
                results = self.search_by_metadata(filters, limit=10, query=query)
            else:
                results = self.ingestor.search(query, limit=10)
            extanded_results = self.ingestor.find_extand_relevant_chunks(results)
            # 4) Combine results
            combined_results = self.combine_results(extanded_results)
            # 5) Check results
            if not combined_results:
                return []

            projects = combined_results[:top_k]
            return projects

        except Exception as e:
            print(f"❌ Error during metadata-based RAG search: {e}")
            return None