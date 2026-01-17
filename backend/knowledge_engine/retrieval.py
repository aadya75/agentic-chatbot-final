"""
Hybrid Retrieval Service
Combines vector search with optional citation graph
"""

from typing import List, Dict, Optional
import numpy as np

from .embedding_service import EmbeddingService
from .vector_store import VectorStore
from .graph_store import GraphStore


class HybridRetrieval:
    """
    Retrieval service combining vector search and citation graph
    """
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        graph_store: Optional[GraphStore] = None
    ):
        """
        Initialize retrieval service
        
        Args:
            embedding_service: Embedding service
            vector_store: Vector store
            graph_store: Optional graph store
        """
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.graph_store = graph_store
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        include_citations: bool = False
    ) -> Dict:
        """
        Retrieve relevant chunks for a query
        
        Args:
            query: Search query
            top_k: Number of results to return
            include_citations: Whether to include citation information
            
        Returns:
            Dictionary with chunks and optional citation info
        """
        # Generate query embedding
        query_embedding = self.embedding_service.embed_text(query)
        
        # Vector search
        results = self.vector_store.search(query_embedding, k=top_k)
        
        # Prepare response
        response = {
            'query': query,
            'chunks': [],
            'citations': {} if include_citations else None
        }
        
        # Process results
        seen_papers = set()
        
        for result in results:
            chunk_data = {
                'text': result['chunk']['text'],
                'score': result['score'],
                'metadata': result['chunk']['metadata'],
                'paper_id': result['paper_id']
            }
            response['chunks'].append(chunk_data)
            
            # Track unique papers
            seen_papers.add(result['paper_id'])
        
        # Add citation information if requested
        if include_citations and self.graph_store and self.graph_store.enabled:
            for paper_id in seen_papers:
                citations = self.graph_store.get_citations(paper_id)
                response['citations'][paper_id] = citations
        
        return response
    
    def get_all_resources(self) -> List[Dict]:
        """
        Get list of all indexed resources
        
        Returns:
            List of resource dictionaries
        """
        papers = self.vector_store.get_all_papers()
        
        resources = []
        for paper_id in papers:
            # Find first chunk to get metadata
            for chunk in self.vector_store.metadata:
                if chunk.get('metadata', {}).get('paper_id') == paper_id:
                    resources.append({
                        'paper_id': paper_id,
                        'filename': chunk['metadata'].get('filename', 'unknown')
                    })
                    break
        
        return resources