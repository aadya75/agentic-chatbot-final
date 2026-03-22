"""
Embedding Service — sentence-transformers backend (drop-in replacement)

Replaces the old SHA-256 hash stub with real semantic embeddings using
the 'all-MiniLM-L6-v2' model (384-dim, ~80 MB, runs on CPU).

The public interface (embed_text / embed_texts / get_embedding_dimension)
is identical to the previous hash-based implementation so every caller
(ingestion, retrieval, club embedding_generator, MCP server) works
without any changes.

Install dependency once:
    pip install sentence-transformers
"""

import logging
import numpy as np
from typing import List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model name — change here if you want a different HuggingFace model.
# Must produce 384-dim embeddings to match EMBEDDING_DIM=384 in .env and
# the Supabase VECTOR(384) column.
# ---------------------------------------------------------------------------
_MODEL_NAME = "all-MiniLM-L6-v2"


class EmbeddingService:
    """
    Semantic embedding service backed by sentence-transformers.

    Lazy-loads the model on first call so the MCP server starts instantly.
    Thread-safe: SentenceTransformer.encode() releases the GIL.
    """

    def __init__(self, embedding_dim: int = 384, model_name: str = _MODEL_NAME):
        self.embedding_dim = embedding_dim
        self.model_name = model_name
        self._model = None  # loaded lazily

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate a (384,) float32 embedding for a single text.

        Args:
            text: Input string (may be empty — returns zero vector).

        Returns:
            np.ndarray of shape (384,), dtype float32, unit-normalised.
        """
        if not text or not text.strip():
            return np.zeros(self.embedding_dim, dtype=np.float32)

        model = self._get_model()
        embedding = model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,   # unit-norm → cosine ≡ dot product
            show_progress_bar=False,
        )
        return embedding.astype(np.float32)

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Generate a (N, 384) float32 embedding matrix for a list of texts.

        Args:
            texts: List of input strings.

        Returns:
            np.ndarray of shape (N, 384), dtype float32, unit-normalised.
        """
        if not texts:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)

        model = self._get_model()
        embeddings = model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=64,
        )
        return embeddings.astype(np.float32)

    def get_embedding_dimension(self) -> int:
        """Return the embedding dimension (always 384)."""
        return self.embedding_dim

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _get_model(self):
        """Lazy-load the sentence-transformers model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers is required for real embeddings.\n"
                    "Install it with:  pip install sentence-transformers"
                ) from exc

            logger.info(f"Loading embedding model '{self.model_name}' …")
            self._model = SentenceTransformer(self.model_name)
            actual_dim = self._model.get_sentence_embedding_dimension()

            if actual_dim != self.embedding_dim:
                raise ValueError(
                    f"Model '{self.model_name}' produces {actual_dim}-dim embeddings "
                    f"but EMBEDDING_DIM={self.embedding_dim} is set. "
                    "Either change the model or update EMBEDDING_DIM in .env "
                    "and re-run the Supabase migration with the new vector size."
                )

            logger.info(f"✓ Embedding model loaded (dim={actual_dim})")

        return self._model
