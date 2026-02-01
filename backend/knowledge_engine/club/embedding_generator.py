"""
Club Knowledge Embedding Generation
Uses your existing embedding_service to generate embeddings for club documents
"""
import json
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
from datetime import datetime

from knowledge_engine.club.config import club_config
from knowledge_engine.club.vector_store import club_vector_store
from utils.logger import logger

# Import your existing embedding service
try:
    from knowledge_engine.embedding_service import EmbeddingService
    embedding_service = EmbeddingService()
    logger.info("✓ Embedding service loaded successfully")
except ImportError as e:
    logger.warning(f"embedding_service import failed: {e}")
    embedding_service = None


class ClubEmbeddingGenerator:
    """
    Generate embeddings for club knowledge chunks
    
    Uses your existing EmbeddingService (hash-based 384-dim)
    Creates separate FAISS index for club knowledge
    """
    
    def __init__(self):
        self.embedding_service = embedding_service
        self.vector_store = club_vector_store
        self.metadata_dir = club_config.CLUB_METADATA_DIR
        
        logger.info("ClubEmbeddingGenerator initialized")
    
    def generate_embeddings_from_chunks(
        self,
        chunks_file: Path = None
    ) -> Dict[str, Any]:
        """
        Generate embeddings from ingested chunks
        
        Args:
            chunks_file: Path to chunks JSON (default: chunks_latest.json)
            
        Returns:
            {
                "status": "success" | "failed",
                "num_chunks": int,
                "num_embeddings": int,
                "index_info": dict
            }
        """
        logger.info("="*80)
        logger.info("GENERATING CLUB KNOWLEDGE EMBEDDINGS")
        logger.info("="*80)
        
        result = {
            "status": "failed",
            "num_chunks": 0,
            "num_embeddings": 0,
            "index_info": {},
            "errors": []
        }
        
        try:
            # Step 1: Load chunks
            logger.info("Step 1: Loading chunks...")
            chunks = self._load_chunks(chunks_file)
            
            if not chunks:
                result["errors"].append("No chunks found")
                return result
            
            result["num_chunks"] = len(chunks)
            logger.info(f"✓ Loaded {len(chunks)} chunks")
            
            # Step 2: Generate embeddings
            logger.info("Step 2: Generating embeddings...")
            embeddings = self._generate_embeddings(chunks)
            
            if embeddings is None or len(embeddings) == 0:
                result["errors"].append("Failed to generate embeddings")
                return result
            
            result["num_embeddings"] = len(embeddings)
            logger.info(f"✓ Generated {len(embeddings)} embeddings (dim={embeddings.shape[1]})")
            
            # Step 3: Create FAISS index
            logger.info("Step 3: Creating FAISS index...")
            
            # Delete old index first (overwrite strategy)
            self.vector_store.delete_index()
            
            index_result = self.vector_store.create_index(embeddings, chunks)
            
            if index_result["status"] != "success":
                result["errors"].append(f"Index creation failed: {index_result.get('error')}")
                return result
            
            result["index_info"] = index_result
            logger.info(f"✓ Created index with {index_result['num_vectors']} vectors")
            
            # Step 4: Save embedding metadata
            self._save_embedding_metadata(len(chunks), len(embeddings))
            
            result["status"] = "success"
            
            logger.info("="*80)
            logger.info("EMBEDDING GENERATION COMPLETE")
            logger.info(f"Chunks: {result['num_chunks']}")
            logger.info(f"Embeddings: {result['num_embeddings']}")
            logger.info(f"Index: {index_result['index_path']}")
            logger.info("="*80)
            
            return result
            
        except Exception as e:
            logger.error(f"Fatal error during embedding generation: {e}")
            logger.exception(e)
            result["errors"].append(str(e))
            return result
    
    def _load_chunks(self, chunks_file: Path = None) -> List[Dict[str, Any]]:
        """Load chunks from JSON file"""
        if chunks_file is None:
            chunks_file = self.metadata_dir / "chunks_latest.json"
        
        if not chunks_file.exists():
            logger.error(f"Chunks file not found: {chunks_file}")
            logger.info("Run ingestion first: python -m knowledge_engine.club.scripts.ingest_club_knowledge")
            return []
        
        try:
            with open(chunks_file, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            
            logger.info(f"Loaded {len(chunks)} chunks from {chunks_file}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error loading chunks: {e}")
            return []
    
    def _generate_embeddings(self, chunks: List[Dict[str, Any]]) -> np.ndarray:
        """
        Generate embeddings using your existing EmbeddingService
        """
        if self.embedding_service is None:
            logger.error("Embedding service not available")
            logger.info("Check that knowledge_engine/embedding_service.py exists")
            return None
        
        try:
            # Extract text from chunks
            texts = [chunk["text"] for chunk in chunks]
            
            logger.info(f"Generating embeddings for {len(texts)} texts...")
            
            # Use embed_texts method (from your EmbeddingService)
            embeddings = self.embedding_service.embed_texts(texts)
            
            # Verify it's a numpy array
            if not isinstance(embeddings, np.ndarray):
                embeddings = np.array(embeddings)
            
            # Verify shape
            if embeddings.ndim != 2:
                logger.error(f"Invalid embedding shape: {embeddings.shape}")
                return None
            
            if embeddings.shape[1] != 384:
                logger.warning(
                    f"Embedding dimension is {embeddings.shape[1]}, expected 384. "
                    f"This may cause issues."
                )
            
            logger.info(f"✓ Generated embeddings with shape: {embeddings.shape}")
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            logger.exception(e)
            return None
    
    def _save_embedding_metadata(self, num_chunks: int, num_embeddings: int):
        """Save metadata about embedding generation"""
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "num_chunks": num_chunks,
            "num_embeddings": num_embeddings,
            "embedding_model": club_config.CLUB_EMBEDDING_MODEL,
            "dimension": 384
        }
        
        metadata_file = self.metadata_dir / "embedding_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Saved embedding metadata to: {metadata_file}")
    
    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get statistics about embeddings"""
        metadata_file = self.metadata_dir / "embedding_metadata.json"
        
        if not metadata_file.exists():
            return {
                "status": "no_embeddings",
                "message": "No embeddings generated yet"
            }
        
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Also get vector store stats
            index_stats = self.vector_store.get_stats()
            
            return {
                "status": "ready",
                "embedding_metadata": metadata,
                "index_stats": index_stats
            }
            
        except Exception as e:
            logger.error(f"Error reading embedding stats: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


# Singleton
embedding_generator = ClubEmbeddingGenerator()