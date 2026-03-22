"""
Hybrid Retrieval Service
Combines vector search with optional citation graph
"""

from typing import List, Dict, Optional
import numpy as np

from .embedding_service import EmbeddingService
from .vector_store import SupabaseVectorStore
from .graph_store import GraphStore


class HybridRetrieval:
    """
    Retrieval service combining vector search and citation graph
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: SupabaseVectorStore,
        graph_store: Optional[GraphStore] = None
    ):
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.graph_store = graph_store

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        include_citations: bool = False,
        filter_paper_id: Optional[List[str]] = None,
        user_id: Optional[str] = None,
    ) -> Dict:
        """
        Retrieve relevant chunks for a query.

        Args:
            query: Search query
            top_k: Number of results to return
            include_citations: Whether to include citation information
            filter_paper_id: Optional list of paper IDs to filter results
            user_id: Optional user ID for Supabase row-level filtering

        Returns:
            Dictionary with chunks and optional citation info
        """
        # Generate query embedding
        query_embedding = self.embedding_service.embed_text(query)

        # Vector search — pass user_id through so Supabase can filter per-user
        results = self.vector_store.search(
            query_embedding,
            k=top_k,
            user_id=user_id,
            filter_paper_id=filter_paper_id[0] if filter_paper_id else None,
        )

        response = {
            "query": query,
            "chunks": [],
            "citations": {} if include_citations else None,
        }

        seen_papers = set()

        for result in results:
            chunk_data = {
                "text": result["chunk"]["text"],
                "score": result["score"],
                "metadata": result["chunk"]["metadata"],
                "paper_id": result["paper_id"],
            }
            response["chunks"].append(chunk_data)
            seen_papers.add(result["paper_id"])

        # Add citation information if requested
        if include_citations and self.graph_store and self.graph_store.enabled:
            for paper_id in seen_papers:
                citations = self.graph_store.get_citations(paper_id)
                response["citations"][paper_id] = citations

        return response

    def get_all_resources(self, user_id: Optional[str] = None) -> List[Dict]:
        """
        Get list of all indexed resources.

        Args:
            user_id: Optional user filter (Supabase only)

        Returns:
            List of resource dictionaries
        """
        papers = self.vector_store.get_all_papers(user_id=user_id)

        resources = []
        for paper in papers:
            # Supabase returns full paper dicts; FAISS returns bare IDs.
            if isinstance(paper, dict):
                resources.append({
                    "paper_id": paper.get("id"),
                    "filename": paper.get("filename", "unknown"),
                })
            else:
                # Fallback: bare paper_id string
                resources.append({"paper_id": paper, "filename": "unknown"})

        return resources
