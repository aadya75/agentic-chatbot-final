"""
Club Knowledge Retrieval
High-level interface for querying club knowledge
"""
from typing import List, Dict, Any, Optional
import numpy as np

from knowledge_engine.club.config import club_config
from knowledge_engine.club.vector_store import club_vector_store
from utils.logger import logger

# Import your existing embedding service
try:
    from knowledge_engine.embedding_service import EmbeddingService
    embedding_service = EmbeddingService()
except ImportError:
    logger.warning("embedding_service not found")
    embedding_service = None


class ClubKnowledgeRetriever:
    """
    High-level retrieval interface for club knowledge
    
    Usage:
        retriever = ClubKnowledgeRetriever()
        results = retriever.retrieve("What are the ongoing events?", category="events")
    """
    
    def __init__(self):
        self.embedding_service = embedding_service
        self.vector_store = club_vector_store
        
        # Try to load existing index
        self.is_ready = self.vector_store.load_index()
        
        if self.is_ready:
            logger.info("ClubKnowledgeRetriever initialized and ready")
        else:
            logger.warning("ClubKnowledgeRetriever initialized but index not loaded")
    
    def retrieve(
        self,
        query: str,
        top_k: int = None,
        category: str = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant club documents
        
        Args:
            query: User query text
            top_k: Number of results to return (default: from config)
            category: Optional filter - "events", "announcements", "coordinators"
            
        Returns:
            List of results:
            [
                {
                    "content": str,        # Chunk text
                    "metadata": {
                        "source": str,     # File path
                        "category": str,   # events/announcements/coordinators
                        "event_name": str, # Event name (if applicable)
                        ...
                    },
                    "score": float        # Similarity score (lower = more similar for L2)
                },
                ...
            ]
        """
        if not self.is_ready:
            logger.warning("Index not loaded, attempting to load...")
            self.is_ready = self.vector_store.load_index()
            
            if not self.is_ready:
                logger.error("Failed to load index. Run embedding generation first.")
                return []
        
        if not query or not query.strip():
            logger.warning("Empty query received")
            return []
        
        top_k = top_k or club_config.CLUB_TOP_K_RESULTS
        
        try:
            logger.info(f"Retrieving for query: '{query}' | category: {category} | top_k: {top_k}")
            
            # Step 1: Generate query embedding
            query_embedding = self._embed_query(query)
            
            if query_embedding is None:
                logger.error("Failed to generate query embedding")
                return []
            
            # Step 2: Search vector store
            results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                category=category
            )
            
            # Step 3: Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "content": result["text"],
                    "metadata": result["metadata"],
                    "score": result["score"]
                })
            
            logger.info(f"Retrieved {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error during retrieval: {e}")
            logger.exception(e)
            return []
    
    def _embed_query(self, query: str) -> Optional[np.ndarray]:
        """Generate embedding for query using your embedding service"""
        if self.embedding_service is None:
            logger.error("Embedding service not available")
            return None
        
        try:
            # Try different method names
            if hasattr(self.embedding_service, 'embed_texts'):
                embedding = self.embedding_service.embed_texts([query])
            elif hasattr(self.embedding_service, 'encode'):
                embedding = self.embedding_service.encode([query])
            elif hasattr(self.embedding_service, 'generate_embeddings'):
                embedding = self.embedding_service.generate_embeddings([query])
            else:
                logger.error("Embedding service method not found")
                return None
            
            # Convert to numpy if needed
            if not isinstance(embedding, np.ndarray):
                embedding = np.array(embedding)
            
            # Ensure correct shape (1, 384)
            if embedding.ndim == 1:
                embedding = embedding.reshape(1, -1)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error embedding query: {e}")
            return None
    
    def check_ready(self) -> Dict[str, Any]:
        """
        Check if retriever is ready to use
        
        Returns:
            {
                "ready": bool,
                "index_loaded": bool,
                "embedding_service_available": bool,
                "stats": dict
            }
        """
        embedding_available = self.embedding_service is not None
        
        stats = {}
        if self.is_ready:
            stats = self.vector_store.get_stats()
        
        return {
            "ready": self.is_ready and embedding_available,
            "index_loaded": self.is_ready,
            "embedding_service_available": embedding_available,
            "stats": stats
        }
    
    def get_last_updated(self) -> str:
        """Get timestamp of last knowledge refresh"""
        last_updated_file = club_config.CLUB_LAST_UPDATED_FILE
        
        if not last_updated_file.exists():
            return "Never"
        
        try:
            return last_updated_file.read_text().strip()
        except Exception as e:
            logger.error(f"Error reading last_updated: {e}")
            return "Unknown"


# Singleton
club_retriever = ClubKnowledgeRetriever()