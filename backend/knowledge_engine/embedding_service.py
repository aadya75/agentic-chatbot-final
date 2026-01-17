"""
Hash-based Embedding Service
Generates 384-dimensional embeddings using SHA-256 hashing
"""

import hashlib
import numpy as np
from typing import List, Union


class EmbeddingService:
    """
    Generates deterministic 384-dimensional embeddings using SHA-256 hash
    """
    
    def __init__(self, embedding_dim: int = 384):
        self.embedding_dim = embedding_dim
    
    def _text_to_hash_embedding(self, text: str) -> np.ndarray:
        """
        Convert text to 384-dimensional embedding using SHA-256 hash
        
        Args:
            text: Input text
            
        Returns:
            384-dimensional numpy array
        """
        # Generate SHA-256 hash
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        
        # Convert hex to bytes
        hash_bytes = bytes.fromhex(text_hash)
        
        # Extend to 384 dimensions by repeating and normalizing
        # SHA-256 gives 32 bytes = 256 bits
        # We need 384 dimensions, so we repeat and slice
        extended = np.frombuffer(hash_bytes, dtype=np.uint8)
        
        # Repeat to get at least 384 values
        repetitions = (self.embedding_dim // len(extended)) + 1
        extended = np.tile(extended, repetitions)[:self.embedding_dim]
        
        # Normalize to unit vector
        embedding = extended.astype(np.float32)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
            
        return embedding
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text
        
        Args:
            text: Input text
            
        Returns:
            384-dimensional embedding
        """
        return self._text_to_hash_embedding(text)
    
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of input texts
            
        Returns:
            Matrix of embeddings (n_texts, 384)
        """
        embeddings = [self._text_to_hash_embedding(text) for text in texts]
        return np.vstack(embeddings)
    
    def get_embedding_dimension(self) -> int:
        """Return the embedding dimension"""
        return self.embedding_dim