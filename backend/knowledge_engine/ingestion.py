"""
Document Ingestion Service
Handles PDF processing, chunking, and indexing into Supabase
"""

import uuid
import shutil
from pathlib import Path
from typing import Dict, Optional, Callable
import PyPDF2

from .embedding_service import EmbeddingService
from .vector_store import SupabaseVectorStore
from .graph_store import GraphStore
from .chunking import DocumentChunker


class DocumentIngestion:
    """
    Full ingestion pipeline: PDF -> chunks -> embeddings -> Supabase
    """

    def __init__(
        self,
        upload_dir: str,
        supabase_url: str,
        supabase_key: str,
        embedding_service: EmbeddingService,
        chunker: DocumentChunker,
        graph_store: Optional[GraphStore] = None,
    ):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        self.vector_store = SupabaseVectorStore(
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            embedding_dim=embedding_service.get_embedding_dimension(),
        )

        self.embedding_service = embedding_service
        self.chunker = chunker
        self.graph_store = graph_store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_pdf(
        self,
        file_path: str,
        filename: str,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        user_id: Optional[str] = None,
        paper_id: Optional[str] = None,
    ) -> Dict:
        """
        Process a PDF file and store it in Supabase.

        Args:
            file_path: Path to the PDF file
            filename: Original filename
            progress_callback: Optional callback(status, progress_percent)
            user_id: Owner of this document (Supabase per-user filtering)
            paper_id: Pre-generated UUID; auto-generated if omitted

        Returns:
            Result dict with keys: success, paper_id, filename, chunks_created, message
        """
        if paper_id is None:
            paper_id = str(uuid.uuid4())

        try:
            if progress_callback:
                progress_callback("Extracting text from PDF", 10)

            text = self._extract_text_from_pdf(file_path)
            if not text or len(text.strip()) < 100:
                raise ValueError("PDF contains insufficient text")

            if progress_callback:
                progress_callback("Chunking document", 30)

            metadata = {"filename": filename, "paper_id": paper_id}
            chunks = self.chunker.chunk_text(text, metadata)
            if not chunks:
                raise ValueError("No chunks created from PDF")

            if progress_callback:
                progress_callback("Generating embeddings", 50)

            chunk_texts = [c["text"] for c in chunks]
            embeddings = self.embedding_service.embed_texts(chunk_texts)

            if progress_callback:
                progress_callback("Adding to vector store", 70)

            self.vector_store.add_documents(embeddings, chunks, paper_id, user_id=user_id)

            if progress_callback:
                progress_callback("Saving PDF", 85)

            saved_path = self.upload_dir / f"{paper_id}.pdf"
            shutil.copy(file_path, saved_path)

            if self.graph_store and self.graph_store.enabled:
                if progress_callback:
                    progress_callback("Adding to citation graph", 95)
                self.graph_store.add_paper(paper_id, filename, metadata)

            if progress_callback:
                progress_callback("Complete", 100)

            return {
                "success": True,
                "paper_id": paper_id,
                "filename": filename,
                "chunks_created": len(chunks),
                "message": f"Successfully processed {filename}",
            }

        except Exception as e:
            if progress_callback:
                progress_callback(f"Error: {str(e)}", 0)
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to process {filename}: {str(e)}",
            }

    def delete_document(self, paper_id: str) -> Dict:
        """Delete a document and all its chunks from Supabase + local disk."""
        try:
            self.vector_store.delete_paper(paper_id)

            if self.graph_store and self.graph_store.enabled:
                self.graph_store.delete_paper(paper_id)

            pdf_path = self.upload_dir / f"{paper_id}.pdf"
            if pdf_path.exists():
                pdf_path.unlink()

            return {
                "success": True,
                "paper_id": paper_id,
                "message": f"Successfully deleted document {paper_id}",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to delete document {paper_id}: {str(e)}",
            }

    def get_document_info(self, paper_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """
        Look up a document record in Supabase.

        Returns a dict with paper_id, filename, pdf_path — or None if not found.
        """
        papers = self.vector_store.get_all_papers(user_id=user_id)
        for paper in papers:
            if isinstance(paper, dict) and paper.get("id") == paper_id:
                pdf_path = self.upload_dir / f"{paper_id}.pdf"
                return {
                    "paper_id": paper_id,
                    "filename": paper.get("filename", "unknown"),
                    "pdf_path": str(pdf_path) if pdf_path.exists() else None,
                }
        return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_text_from_pdf(self, file_path: str) -> str:
        text = ""
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n\n"
            return text.strip()
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")
