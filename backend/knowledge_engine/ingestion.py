"""
Document Ingestion Service
Handles PDF processing, chunking, and indexing
"""

import os
import uuid
import shutil
from pathlib import Path
from typing import Dict, Optional, Callable
import PyPDF2

from .embedding_service import EmbeddingService
from .vector_store import VectorStore
from .graph_store import GraphStore
from .chunking import DocumentChunker


class DocumentIngestion:
    """
    Manages the full ingestion pipeline: PDF -> chunks -> embeddings -> index
    """
    
    def __init__(
        self,
        upload_dir: str,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        chunker: DocumentChunker,
        graph_store: Optional[GraphStore] = None
    ):
        """
        Initialize ingestion service
        
        Args:
            upload_dir: Directory to store uploaded PDFs
            vector_store: Vector store instance
            embedding_service: Embedding service instance
            chunker: Document chunker instance
            graph_store: Optional graph store instance
        """
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.chunker = chunker
        self.graph_store = graph_store
    
    def process_pdf(
        self,
        file_path: str,
        filename: str,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> Dict:
        """
        Process a PDF file and add it to the index
        
        Args:
            file_path: Path to the PDF file
            filename: Original filename
            progress_callback: Optional callback(status, progress_percent)
            
        Returns:
            Dictionary with processing results
        """
        paper_id = str(uuid.uuid4())
        
        try:
            # Update progress
            if progress_callback:
                progress_callback("Extracting text from PDF", 10)
            
            # Extract text from PDF
            text = self._extract_text_from_pdf(file_path)
            
            if not text or len(text.strip()) < 100:
                raise ValueError("PDF contains insufficient text")
            
            # Update progress
            if progress_callback:
                progress_callback("Chunking document", 30)
            
            # Create chunks
            metadata = {
                'filename': filename,
                'paper_id': paper_id
            }
            chunks = self.chunker.chunk_text(text, metadata)
            
            if not chunks:
                raise ValueError("No chunks created from PDF")
            
            # Update progress
            if progress_callback:
                progress_callback("Generating embeddings", 50)
            
            # Generate embeddings
            chunk_texts = [chunk['text'] for chunk in chunks]
            embeddings = self.embedding_service.embed_texts(chunk_texts)
            
            # Update progress
            if progress_callback:
                progress_callback("Adding to vector store", 70)
            
            # Add to vector store
            self.vector_store.add_documents(embeddings, chunks, paper_id)
            
            # Update progress
            if progress_callback:
                progress_callback("Saving PDF", 85)
            
            # Save PDF to permanent storage
            saved_path = self.upload_dir / f"{paper_id}.pdf"
            shutil.copy(file_path, saved_path)
            
            # Add to graph store if available
            if self.graph_store and self.graph_store.enabled:
                if progress_callback:
                    progress_callback("Adding to citation graph", 95)
                self.graph_store.add_paper(paper_id, filename, metadata)
            
            # Complete
            if progress_callback:
                progress_callback("Complete", 100)
            
            return {
                'success': True,
                'paper_id': paper_id,
                'filename': filename,
                'chunks_created': len(chunks),
                'message': f'Successfully processed {filename}'
            }
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error: {str(e)}", 0)
            
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to process {filename}: {str(e)}'
            }
    
    def delete_document(self, paper_id: str) -> Dict:
        """
        Delete a document from all stores
        
        Args:
            paper_id: Paper identifier
            
        Returns:
            Dictionary with deletion results
        """
        try:
            # Delete from vector store
            chunks_deleted = self.vector_store.delete_paper(paper_id)
            
            # Delete from graph store
            if self.graph_store and self.graph_store.enabled:
                self.graph_store.delete_paper(paper_id)
            
            # Delete PDF file
            pdf_path = self.upload_dir / f"{paper_id}.pdf"
            if pdf_path.exists():
                pdf_path.unlink()
            
            return {
                'success': True,
                'paper_id': paper_id,
                'chunks_deleted': chunks_deleted,
                'message': f'Successfully deleted document {paper_id}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to delete document {paper_id}: {str(e)}'
            }
    
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extract text from a PDF file
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Extracted text
        """
        text = ""
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n\n"
            
            return text.strip()
            
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")
    
    def get_document_info(self, paper_id: str) -> Optional[Dict]:
        """
        Get information about a document
        
        Args:
            paper_id: Paper identifier
            
        Returns:
            Document information or None
        """
        # Check if PDF exists
        pdf_path = self.upload_dir / f"{paper_id}.pdf"
        if not pdf_path.exists():
            return None
        
        # Get from vector store metadata
        for chunk in self.vector_store.metadata:
            if chunk.get('metadata', {}).get('paper_id') == paper_id:
                return {
                    'paper_id': paper_id,
                    'filename': chunk['metadata'].get('filename', 'unknown'),
                    'pdf_path': str(pdf_path)
                }
        
        return None