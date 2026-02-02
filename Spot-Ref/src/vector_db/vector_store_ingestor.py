#!/usr/bin/env python3
"""
vector_store_ingestor.py

Provides QdrantIngestor: handles connection to Qdrant, embeddings via Azure OpenAI,
upserting chunks, and semantic search.
"""
import os
import logging
import threading
from typing import List, Dict, Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from langchain_openai import AzureOpenAIEmbeddings
from tqdm import tqdm

logger = logging.getLogger(__name__)


class QdrantIngestor:
    """
    Class to define the QdrantIngestor class.
    This class is used to ingest text chunks into a Qdrant collection,
    using Azure OpenAI for embeddings.
    It also provides a search method to find relevant chunks in the collection.
    """
    def __init__(
        self,
        collection_name: str,
        vector_size: int = 1536,
        host: str = os.getenv("QDRANT_HOST", "localhost"),
        port: int = int(os.getenv("QDRANT_PORT", "6333")),
    ):
        """
        Initialize Qdrant client and Azure OpenAI embeddings.

        Args:
            collection_name (str): Qdrant collection to use or create.
            vector_size (int): Dimensionality of embedding vectors.
            host (str): Qdrant host (hostname or URL) without scheme.
            port (int): Qdrant port number.
        """
        self.collection_name = collection_name
        self.vector_size = vector_size
        self._id_counter = 0
        self._id_lock = threading.Lock()

        # Build explicit HTTP URL for Qdrant
        base_url = f"http://{host}:{port}"
        try:
            self.client = QdrantClient(
                url=base_url,
                prefer_grpc=False
            )
        except Exception as e:
            raise ConnectionError(f"Cannot connect to Qdrant at {host}:{port}") from e

        # Azure OpenAI embeddings config
        embed_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        if not embed_deployment:
            raise RuntimeError("Missing AZURE_OPENAI_EMBEDDING_DEPLOYMENT in .env")
        self.embeddings = AzureOpenAIEmbeddings(
            azure_deployment=embed_deployment,
            openai_api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        )

        # Ensure collection exists
        self._create_collection_if_not_exists()

    def _create_collection_if_not_exists(self) -> None:
        """
        Create the Qdrant collection if it does not already exist.
        """
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in existing:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                )
            )

    def ingest_texts(self, texts: List[str], metadata: Optional[List[Dict[str, Any]]] = None, batch_size: int = 64) -> None:
        """
        Embed and upsert text chunks into Qdrant in batches.

        Args:
            texts (List[str]): List of chunk strings.
            metadata (Optional[List[Dict[str, Any]]]): Parallel list of metadata dicts.
            batch_size (int): Number of chunks per upsert call.
        """
        if metadata is None:
            metadata = [{} for _ in texts]

        total = len(texts)
        logger.info(f"🚥 Starting ingestion: {total} chunks.")
        with tqdm(total=total, desc="Ingestion into Qdrant", unit="chunk") as pbar:
            for i in range(0, total, batch_size):
                end = min(i + batch_size, total)
                batch_texts = texts[i:end]
                batch_meta = metadata[i:end]

                # Rename file_name -> doc_name if present
                clean_meta = []
                for m in batch_meta:
                    m2 = m.copy()
                    if 'file_name' in m2:
                        m2['doc_name'] = m2.pop('file_name')
                    clean_meta.append(m2)

                # Generate embeddings
                try:
                    vectors = self.embeddings.embed_documents(batch_texts)
                except Exception as e:
                    raise RuntimeError(f"Embedding error: {e}") from e

                # Generate thread-safe IDs
                with self._id_lock:
                    start_id = self._id_counter
                    self._id_counter += len(batch_texts)

                # Prepare Qdrant points
                points = [
                    PointStruct(
                        id=start_id + idx,
                        vector=vec,
                        payload={"text": txt, **meta}
                    )
                    for idx, (txt, vec, meta) in enumerate(zip(batch_texts, vectors, clean_meta))
                ]

                # Upsert to Qdrant
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                logger.debug(f"Indexed chunks {start_id} to {start_id + len(batch_texts) - 1}")
                pbar.update(len(batch_texts))

        logger.info("🎉 Ingestion complete!")

    def search(self, query: str, limit: int = 5, score_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        Perform a semantic search in Qdrant.

        Args:
            query (str): Query string.
            limit (int): Max number of results.
            score_threshold (float): Minimum similarity score.

        Returns:
            List of dicts with keys: 'text', 'score', 'metadata'
        """
        query_vec = self.embeddings.embed_query(query)
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vec,
            limit=limit,
            score_threshold=score_threshold,
        )
        formatted = []
        for r in results:
            payload = r.payload.copy()
            text = payload.pop('text', None)
            formatted.append({
                "text": text,
                "score": r.score,
                "metadata":{
                    "doc_name": payload['doc_name'],
                    "client": payload['client'],
                    "field": payload['field'],
                    "tech": payload['tech'],
                    "localisation": payload['localisation'],
                    "pptx_path": payload['pptx_path'],
                    "sharepoint_url": payload['sharepoint_url']                   
                }
            })
        return formatted

    def search_with_filters(self, query: str, filters: List[Dict[str, Any]], limit: int = 5, score_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        Perform a semantic search in Qdrant with metadata filters.
        Returns all chunks from documents that contain relevant chunks.

        Args:
            query (str): Query string.
            filters (List[Dict]): List of Qdrant filter dictionaries.
            limit (int): Max number of results for initial semantic search.
            score_threshold (float): Minimum similarity score.

        Returns:
            List of dicts with keys: 'text', 'score', 'metadata'
        """
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue, MatchText
        
        query_vec = self.embeddings.embed_query(query)
        
        # Construct Qdrant filter object
        qdrant_filter = None
        if filters:
            conditions = []
            for f in filters:
                if f.get("match", {}).get("value"):
                    conditions.append(
                        FieldCondition(
                            key=f["key"],
                            match=MatchValue(value=f["match"]["value"])
                        )
                    )
                elif f.get("match", {}).get("text"):
                    conditions.append(
                        FieldCondition(
                            key=f["key"],
                            match=MatchText(text=f["match"]["text"])
                        )
                    )
            
            if conditions:
                qdrant_filter = Filter(must=conditions)
        
        # First, perform semantic search to find relevant chunks
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vec,
            query_filter=qdrant_filter,
            limit=limit,
            score_threshold=score_threshold,
        )
        if not results:
            return []
        
        formatted = []
        for r in results:
            payload = r.payload.copy()
            text = payload.pop('text', None)
            formatted.append({
                "text": text,
                "score": r.score,
                "metadata":{
                    "doc_name": payload['doc_name'],
                    "client": payload['client'],
                    "field": payload['field'],
                    "tech": payload['tech'],
                    "localisation": payload['localisation'],
                    "pptx_path": payload['pptx_path'],
                    "sharepoint_url": payload['sharepoint_url']                  
                }
            })
        return formatted

    def find_extand_relevant_chunks(self, chunks : List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Find all chunks from documents that contain relevant chunks.
        This is used to find all chunks from documents that contain relevant chunks.
        
        args :
            chunks : List[Dict[str, Any]]: List of chunks to find relevant chunks from.
        
        returns :
            List[Dict[str, Any]]: List of chunks from documents that contain relevant chunks.
        """
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        # Extract unique doc_names from the semantic search results
        relevant_doc_names = set()
        for c in chunks:
            doc_name = c['metadata']['doc_name']
            if doc_name:
                relevant_doc_names.add(doc_name)
        print(f"relevant_doc_names: {relevant_doc_names}")
        if not relevant_doc_names:
            # Fallback: return initial results if no doc_name found
            formatted = []
            for c in chunks:
                text = c['text']
                formatted.append({
                    "text": text,
                    "metadata": c['metadata'],
                })
            return formatted
        
        # Add doc_name conditions (OR logic for different doc_names)
        doc_name_conditions = []
        for doc_name in relevant_doc_names:
            doc_name_conditions.append(
                FieldCondition(
                    key="doc_name",
                    match=MatchValue(value=doc_name)
                )
            )
        # Create combined filter: (original filters) AND (doc_name1 OR doc_name2 OR ...)
        if len(doc_name_conditions) == 1:
            doc_name_filter = Filter(must=doc_name_conditions)
        else:
            # For multiple doc_names, use should (OR) logic
            doc_name_filter = Filter(should=doc_name_conditions)
        # Retrieve all chunks from relevant documents
        all_results, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=doc_name_filter,
            limit=1000,  # Large limit to get all chunks from relevant documents
            with_payload=True,
            with_vectors=False
        )
        # Format results, preserving semantic scores where available
        formatted = []
        for r in all_results:
            payload = r.payload
            formatted.append({
                "text": payload['text'],
                "metadata":{
                    "doc_name": payload['doc_name'],
                    "client": payload['client'],
                    "field": payload['field'],
                    "pptx_path": payload['pptx_path'],
                    "tech": payload['tech'],
                    "localisation": payload['localisation'],
                    "sharepoint_url": payload['sharepoint_url']
                }
            })
        return formatted