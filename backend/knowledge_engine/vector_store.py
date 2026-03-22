"""
Supabase Vector Store — User RAG
Stores per-user document chunks in PostgreSQL + pgvector.

Fixes vs the original:
  • search() now passes user_id and paper_id to the RPC correctly.
  • ClubVectorStore singletons are NOT created here; each store is
    instantiated explicitly so missing env vars don't crash the whole app.
"""

import logging
from typing import List, Dict, Optional
import numpy as np
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class SupabaseVectorStore:
    """
    Supabase-backed vector store for user-uploaded documents.

    Schema (shared with club RAG):
        papers(id, filename, user_id, source, processed, upload_date)
        document_chunks(id, paper_id, chunk_text, chunk_index,
                        start_char, end_char, embedding, metadata)

    User rows always have  source = 'user'.
    """

    SOURCE_TAG = "user"

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        embedding_dim: int = 384,
    ):
        if not supabase_url or not supabase_key:
            raise ValueError(
                "supabase_url and supabase_key must be non-empty strings."
            )
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.embedding_dim = embedding_dim
        logger.info("SupabaseVectorStore (user RAG) initialised")

    # ------------------------------------------------------------------ #
    # Write path                                                           #
    # ------------------------------------------------------------------ #

    def add_documents(
        self,
        embeddings: np.ndarray,
        chunks: List[Dict],
        paper_id: str,
        user_id: Optional[str] = None,
    ) -> Dict:
        """
        Insert embeddings + chunks for one paper into Supabase.

        Args:
            embeddings : (N, D) float32 numpy array
            chunks     : list of {"text": str, "metadata": dict, ...}
            paper_id   : UUID string for this paper
            user_id    : Optional owner identifier

        Returns:
            {"success": bool, "chunks_inserted": int, "paper_id": str}
        """
        if embeddings.shape[0] != len(chunks):
            raise ValueError(
                f"Embedding count ({embeddings.shape[0]}) != chunk count ({len(chunks)})"
            )

        try:
            # Upsert paper record
            self.supabase.table("papers").upsert(
                {
                    "id": paper_id,
                    "filename": chunks[0]["metadata"].get("filename", "unknown"),
                    "user_id": user_id,
                    "source": self.SOURCE_TAG,
                    "processed": True,
                }
            ).execute()

            # Build chunk records
            records = []
            for i, (emb, chunk) in enumerate(zip(embeddings, chunks)):
                records.append(
                    {
                        "paper_id": paper_id,
                        "chunk_text": chunk["text"],
                        "chunk_index": i,
                        "start_char": chunk.get("start_char", 0),
                        "end_char": chunk.get("end_char", 0),
                        "embedding": emb.tolist(),
                        "metadata": chunk.get("metadata", {}),
                    }
                )

            if records:
                self.supabase.table("document_chunks").insert(records).execute()

            logger.info(f"Inserted {len(records)} chunks for paper {paper_id}")
            return {
                "success": True,
                "chunks_inserted": len(records),
                "paper_id": paper_id,
            }

        except Exception as exc:
            logger.error(f"Error adding documents to Supabase: {exc}")
            return {"success": False, "error": str(exc), "chunks_inserted": 0}

    # ------------------------------------------------------------------ #
    # Read path                                                            #
    # ------------------------------------------------------------------ #

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        user_id: Optional[str] = None,
        filter_paper_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Cosine-similarity search via the match_document_chunks RPC.

        Args:
            query_embedding : (D,) or (1, D) float32 array
            k               : max results to return
            user_id         : filter to one user's documents
            filter_paper_id : filter to one specific paper

        Returns:
            [{"chunk": {"text": str, "metadata": dict},
              "score": float, "paper_id": str}, ...]
        """
        # Normalise to 1-D list
        if isinstance(query_embedding, np.ndarray):
            if query_embedding.ndim == 2:
                query_embedding = query_embedding[0]
            embedding_list = query_embedding.tolist()
        else:
            embedding_list = list(query_embedding)

        try:
            resp = self.supabase.rpc(
                "match_document_chunks",
                {
                    "query_embedding": embedding_list,
                    "match_count": k,
                    "user_id_filter": user_id,          # None → no filter
                    "paper_id_filter": filter_paper_id, # None → no filter
                    "source_filter": self.SOURCE_TAG,   # always scope to user docs
                    "category_filter": None,
                },
            ).execute()

            results = []
            for row in resp.data or []:
                results.append(
                    {
                        "chunk": {
                            "text": row["chunk_text"],
                            "metadata": row.get("metadata") or {},
                        },
                        "score": row["similarity"],
                        "paper_id": row["paper_id"],
                    }
                )
            return results

        except Exception as exc:
            logger.error(f"Error searching Supabase: {exc}")
            return []

    # ------------------------------------------------------------------ #
    # Delete                                                               #
    # ------------------------------------------------------------------ #

    def delete_paper(self, paper_id: str) -> Dict:
        """Delete a paper and all its chunks (cascade via FK)."""
        try:
            self.supabase.table("papers").delete().eq("id", paper_id).execute()
            return {"success": True, "paper_id": paper_id}
        except Exception as exc:
            logger.error(f"Error deleting paper {paper_id}: {exc}")
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------ #
    # Utility                                                              #
    # ------------------------------------------------------------------ #

    def update_paper_user(self, paper_id: str, user_id: str) -> Dict:
        """Assign / reassign a user to a paper."""
        try:
            self.supabase.table("papers").update(
                {"user_id": user_id}
            ).eq("id", paper_id).execute()
            return {"success": True, "paper_id": paper_id}
        except Exception as exc:
            logger.error(f"Error updating paper user: {exc}")
            return {"success": False, "error": str(exc)}

    def get_all_papers(self, user_id: Optional[str] = None) -> List[Dict]:
        """Return all user-source papers, optionally filtered by user_id."""
        try:
            query = (
                self.supabase.table("papers")
                .select("*")
                .eq("source", self.SOURCE_TAG)
            )
            if user_id:
                query = query.eq("user_id", user_id)
            resp = query.execute()
            return resp.data or []
        except Exception as exc:
            logger.error(f"Error fetching papers: {exc}")
            return []

    def get_stats(self, user_id: Optional[str] = None) -> Dict:
        """Return basic statistics for the user RAG."""
        try:
            paper_q = (
                self.supabase.table("papers")
                .select("id", count="exact")
                .eq("source", self.SOURCE_TAG)
            )
            if user_id:
                paper_q = paper_q.eq("user_id", user_id)
            paper_resp = paper_q.execute()

            chunk_resp = (
                self.supabase.table("document_chunks")
                .select("id", count="exact")
                .execute()
            )

            return {
                "total_papers": paper_resp.count or 0,
                "total_chunks": chunk_resp.count or 0,
                "embedding_dim": self.embedding_dim,
            }
        except Exception as exc:
            logger.error(f"Error getting stats: {exc}")
            return {"error": str(exc)}
