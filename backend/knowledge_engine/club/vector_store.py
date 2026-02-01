"""
Club Knowledge Vector Store
FAISS-based vector store for club documents (separate from user docs)
"""
import json
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

# FAISS import
try:
    import faiss
except ImportError:
    faiss = None

from knowledge_engine.club.config import club_config
from utils.logger import logger


class ClubVectorStore:
    """
    FAISS vector store for club knowledge
    
    Separate from user document store to:
    - Isolate club vs user queries
    - Enable independent refresh cycles
    - Maintain different metadata structures
    """
    
    def __init__(self):
        self.indices_dir = club_config.CLUB_INDICES_DIR
        self.metadata_dir = club_config.CLUB_METADATA_DIR
        
        # FAISS index
        self.index = None
        self.index_to_id = []  # Maps FAISS index position to document ID
        self.documents = {}    # Document ID -> full document metadata
        
        # Dimension should match your existing embedding service (384 for all-MiniLM-L6-v2)
        self.dimension = 384
        
        logger.info("ClubVectorStore initialized")
    
    def create_index(
        self,
        embeddings: np.ndarray,
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create FAISS index from embeddings and chunks
        
        Args:
            embeddings: numpy array of shape (n_chunks, 384)
            chunks: List of chunk dicts with 'text' and 'metadata'
            
        Returns:
            {
                "status": "success" | "failed",
                "num_vectors": int,
                "index_path": str,
                "metadata_path": str
            }
        """
        if faiss is None:
            raise ImportError("FAISS not installed. Install with: pip install faiss-cpu")
        
        logger.info(f"Creating FAISS index with {len(embeddings)} vectors (dim={self.dimension})")
        
        try:
            # Verify shapes
            if embeddings.shape[1] != self.dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self.dimension}, got {embeddings.shape[1]}"
                )
            
            if len(embeddings) != len(chunks):
                raise ValueError(
                    f"Mismatch: {len(embeddings)} embeddings but {len(chunks)} chunks"
                )
            
            # Create FAISS index (using IndexFlatL2 for exact search)
            # For large datasets, consider IndexIVFFlat for faster approximate search
            self.index = faiss.IndexFlatL2(self.dimension)
            
            # Normalize vectors for cosine similarity (optional but recommended)
            faiss.normalize_L2(embeddings)
            
            # Add vectors to index
            self.index.add(embeddings)
            
            # Build mapping and document store
            self.index_to_id = []
            self.documents = {}
            
            for idx, chunk in enumerate(chunks):
                doc_id = f"chunk_{idx}"
                self.index_to_id.append(doc_id)
                self.documents[doc_id] = {
                    "text": chunk["text"],
                    "metadata": chunk["metadata"]
                }
            
            # Save index and metadata
            index_path, metadata_path = self._save_index()
            
            logger.info(f"✓ Created FAISS index with {self.index.ntotal} vectors")
            logger.info(f"✓ Saved to: {index_path}")
            
            return {
                "status": "success",
                "num_vectors": self.index.ntotal,
                "index_path": str(index_path),
                "metadata_path": str(metadata_path)
            }
            
        except Exception as e:
            logger.error(f"Error creating FAISS index: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def load_index(self) -> bool:
        """
        Load existing FAISS index from disk
        
        Returns:
            True if loaded successfully, False otherwise
        """
        if faiss is None:
            logger.error("FAISS not installed")
            return False
        
        index_path = self.indices_dir / "club_knowledge.index"
        metadata_path = self.indices_dir / "club_knowledge_metadata.pkl"
        
        if not index_path.exists() or not metadata_path.exists():
            logger.warning("No existing index found")
            return False
        
        try:
            # Load FAISS index
            self.index = faiss.read_index(str(index_path))
            
            # Load metadata
            with open(metadata_path, 'rb') as f:
                metadata = pickle.load(f)
                self.index_to_id = metadata['index_to_id']
                self.documents = metadata['documents']
            
            logger.info(f"✓ Loaded FAISS index with {self.index.ntotal} vectors")
            return True
            
        except Exception as e:
            logger.error(f"Error loading FAISS index: {e}")
            return False
    
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = None,
        category: str = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents
        
        Args:
            query_embedding: Query embedding vector (shape: (1, 384))
            top_k: Number of results to return
            category: Optional filter (events, announcements, coordinators)
            
        Returns:
            List of results:
            [
                {
                    "text": str,
                    "metadata": dict,
                    "score": float  # L2 distance (lower = more similar)
                },
                ...
            ]
        """
        if self.index is None:
            logger.warning("Index not loaded, attempting to load...")
            if not self.load_index():
                logger.error("Failed to load index")
                return []
        
        top_k = top_k or club_config.CLUB_TOP_K_RESULTS
        
        try:
            # Ensure query embedding is 2D
            if query_embedding.ndim == 1:
                query_embedding = query_embedding.reshape(1, -1)
            
            # Normalize query embedding
            faiss.normalize_L2(query_embedding)
            
            # Search
            # Get more results initially if we need to filter by category
            search_k = top_k * 3 if category else top_k
            distances, indices = self.index.search(query_embedding, search_k)
            
            # Build results
            results = []
            for i, idx in enumerate(indices[0]):
                if idx == -1:  # FAISS returns -1 for empty slots
                    continue
                
                doc_id = self.index_to_id[idx]
                doc = self.documents[doc_id]
                
                # Apply category filter if specified
                if category and doc["metadata"].get("category") != category:
                    continue
                
                results.append({
                    "text": doc["text"],
                    "metadata": doc["metadata"],
                    "score": float(distances[0][i])
                })
                
                # Stop if we have enough results
                if len(results) >= top_k:
                    break
            
            logger.debug(f"Found {len(results)} results (category: {category})")
            return results
            
        except Exception as e:
            logger.error(f"Error during search: {e}")
            return []
    
    def _save_index(self) -> tuple[Path, Path]:
        """Save FAISS index and metadata to disk"""
        # Save FAISS index
        index_path = self.indices_dir / "club_knowledge.index"
        faiss.write_index(self.index, str(index_path))
        
        # Save metadata
        metadata = {
            'index_to_id': self.index_to_id,
            'documents': self.documents,
            'dimension': self.dimension
        }
        
        metadata_path = self.indices_dir / "club_knowledge_metadata.pkl"
        with open(metadata_path, 'wb') as f:
            pickle.dump(metadata, f)
        
        return index_path, metadata_path
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        if self.index is None:
            if not self.load_index():
                return {"status": "no_index"}
        
        # Count by category
        category_counts = {}
        for doc in self.documents.values():
            cat = doc["metadata"].get("category", "unknown")
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        return {
            "status": "ready",
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "category_counts": category_counts,
            "index_path": str(self.indices_dir / "club_knowledge.index")
        }
    
    def delete_index(self):
        """Delete existing index (for fresh rebuild)"""
        index_path = self.indices_dir / "club_knowledge.index"
        metadata_path = self.indices_dir / "club_knowledge_metadata.pkl"
        
        if index_path.exists():
            index_path.unlink()
            logger.info(f"Deleted index: {index_path}")
        
        if metadata_path.exists():
            metadata_path.unlink()
            logger.info(f"Deleted metadata: {metadata_path}")
        
        self.index = None
        self.index_to_id = []
        self.documents = {}


# Singleton
club_vector_store = ClubVectorStore()