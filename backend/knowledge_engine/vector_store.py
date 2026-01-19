"""
FAISS Vector Store
Manages vector search index with persistence
"""

import logging
import os
import json
import faiss
import numpy as np
from typing import List, Dict, Tuple, Optional
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VectorStore:
    """
    FAISS-based vector store with metadata management
    """
    
    def __init__(self, index_dir: str, embedding_dim: int = 384, index_type: str = "FlatL2"):
        """
        Initialize vector store
        
        Args:
            index_dir: Directory to store FAISS index
            embedding_dim: Dimension of embeddings
            index_type: Type of FAISS index (FlatL2, IVFFlat, etc.)
        """
        self.index_dir = Path(index_dir)
        if self.index_dir.exists() and not self.index_dir.is_dir():
            # If it exists but is not a directory, remove it
            self.index_dir.unlink()
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        self.embedding_dim = embedding_dim
        self.index_type = index_type
        
        self.index_path = self.index_dir / "faiss.index"
        self.metadata_path = self.index_dir / "metadata.json"
        
        # Initialize or load index
        self.index = None
        self.metadata = []  # List of chunk metadata
        self.id_to_paper = {}  # Map chunk ID to paper ID
        
        self._load_or_create_index()
    
    def _load_or_create_index(self):
        """Load existing index or create new one"""
        if self.index_path.exists() and self.metadata_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
                with open(self.metadata_path, 'r') as f:
                    data = json.load(f)
                    self.metadata = data.get('chunks', [])
                    self.id_to_paper = data.get('id_to_paper', {})
                logger.info(f"Loaded existing index with {self.index.ntotal} vectors")
            except Exception as e:
                logger.info(f"Error loading index: {e}. Creating new index.")
                self._create_new_index()
        else:
            self._create_new_index()
    
    def _create_new_index(self):
        """Create a new FAISS index"""
        if self.index_type == "FlatL2":
            self.index = faiss.IndexFlatL2(self.embedding_dim)
        elif self.index_type == "FlatIP":
            self.index = faiss.IndexFlatIP(self.embedding_dim)
        else:
            # Default to FlatL2
            self.index = faiss.IndexFlatL2(self.embedding_dim)
        
        self.metadata = []
        self.id_to_paper = {}
        logger.info(f"Created new {self.index_type} index")
    
    def add_documents(self, embeddings: np.ndarray, chunks: List[Dict], paper_id: str):
        """
        Add documents to the index
        
        Args:
            embeddings: Matrix of embeddings (n_chunks, embedding_dim)
            chunks: List of chunk dictionaries
            paper_id: ID of the paper these chunks belong to
        """
        if embeddings.shape[0] != len(chunks):
            raise ValueError("Number of embeddings must match number of chunks")
        
        # Get current index size
        start_id = self.index.ntotal
        
        # Add to FAISS index
        self.index.add(embeddings.astype(np.float32))
        
        # Add metadata
        for i, chunk in enumerate(chunks):
            chunk_id = start_id + i
            self.metadata.append(chunk)
            self.id_to_paper[str(chunk_id)] = paper_id
        
        # Persist
        self._save_index()
        
        logger.info(f"Added {len(chunks)} chunks for paper {paper_id}")
    
    def search(self, query_embedding: np.ndarray, k: int = 5) -> List[Dict]:
        """
        Search for similar chunks
        
        Args:
            query_embedding: Query embedding vector
            k: Number of results to return
            
        Returns:
            List of dictionaries with chunk data and scores
        """
        if self.index.ntotal == 0:
            return []
        
        # Ensure query is 2D
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        # Search
        k = min(k, self.index.ntotal)
        distances, indices = self.index.search(query_embedding.astype(np.float32), k)
        
        # Prepare results
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(self.metadata):
                result = {
                    'chunk': self.metadata[idx],
                    'score': float(1 / (1 + dist)),  # Convert distance to similarity score
                    'distance': float(dist),
                    'paper_id': self.id_to_paper.get(str(idx), 'unknown')
                }
                results.append(result)
        
        return results
    
    def delete_paper(self, paper_id: str) -> int:
        """
        Delete all chunks belonging to a paper
        
        Args:
            paper_id: ID of the paper to delete
            
        Returns:
            Number of chunks deleted
        """
        # Find chunks to keep
        chunks_to_keep = []
        embeddings_to_keep = []
        new_id_to_paper = {}
        
        deleted_count = 0
        
        for i in range(len(self.metadata)):
            if self.id_to_paper.get(str(i)) != paper_id:
                chunks_to_keep.append(self.metadata[i])
                new_id_to_paper[str(len(chunks_to_keep) - 1)] = self.id_to_paper[str(i)]
                
                # Get embedding from index
                embedding = self.index.reconstruct(i)
                embeddings_to_keep.append(embedding)
            else:
                deleted_count += 1
        
        if deleted_count > 0:
            # Rebuild index
            self._create_new_index()
            
            if embeddings_to_keep:
                embeddings_array = np.vstack(embeddings_to_keep)
                self.index.add(embeddings_array.astype(np.float32))
            
            self.metadata = chunks_to_keep
            self.id_to_paper = new_id_to_paper
            
            self._save_index()
            logger.info(f"Deleted {deleted_count} chunks for paper {paper_id}")
        
        return deleted_count
    
    def get_all_papers(self) -> List[str]:
        """
        Get list of all paper IDs in the index
        
        Returns:
            List of unique paper IDs
        """
        return list(set(self.id_to_paper.values()))
    
    def _save_index(self):
        """Save index and metadata to disk"""
        faiss.write_index(self.index, str(self.index_path))
        
        data = {
            'chunks': self.metadata,
            'id_to_paper': self.id_to_paper
        }
        
        with open(self.metadata_path, 'w') as f:
            json.dump(data, f)
    
    def get_stats(self) -> Dict:
        """Get statistics about the index"""
        return {
            'total_chunks': self.index.ntotal,
            'total_papers': len(self.get_all_papers()),
            'embedding_dim': self.embedding_dim,
            'index_type': self.index_type
        }