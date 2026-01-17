"""
API Routes for Knowledge Base Management
Handles resource upload, listing, and deletion
"""

import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Dict
from pathlib import Path
import asyncio

from knowledge_engine.embedding_service import EmbeddingService
from knowledge_engine.vector_store import VectorStore
from knowledge_engine.graph_store import GraphStore
from knowledge_engine.chunking import DocumentChunker
from knowledge_engine.ingestion import DocumentIngestion
from knowledge_engine.retrieval import HybridRetrieval

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# Initialize services (singleton pattern)
_services_initialized = False
_embedding_service = None
_vector_store = None
_graph_store = None
_chunker = None
_ingestion_service = None
_retrieval_service = None
_processing_status = {}


def get_services():
    """Initialize and return knowledge engine services"""
    global _services_initialized, _embedding_service, _vector_store, _graph_store
    global _chunker, _ingestion_service, _retrieval_service
    
    if not _services_initialized:
        # Get configuration from environment
        FAISS_INDEX_DIR = os.getenv("FAISS_INDEX_DIR", "./data/indices")
        UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./data/uploads")
        EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
        CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
        CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
        
        # Initialize services
        _embedding_service = EmbeddingService(embedding_dim=EMBEDDING_DIM)
        _vector_store = VectorStore(
            index_dir=FAISS_INDEX_DIR,
            embedding_dim=EMBEDDING_DIM,
            index_type=os.getenv("FAISS_INDEX_TYPE", "FlatL2")
        )
        
        # Initialize graph store (optional)
        NEO4J_URI = os.getenv("NEO4J_URI")
        NEO4J_USER = os.getenv("NEO4J_USER")
        NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
        NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
        
        if NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD:
            _graph_store = GraphStore(
                uri=NEO4J_URI,
                user=NEO4J_USER,
                password=NEO4J_PASSWORD,
                database=NEO4J_DATABASE
            )
        
        _chunker = DocumentChunker(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        _ingestion_service = DocumentIngestion(
            upload_dir=UPLOAD_DIR,
            vector_store=_vector_store,
            embedding_service=_embedding_service,
            chunker=_chunker,
            graph_store=_graph_store
        )
        _retrieval_service = HybridRetrieval(
            embedding_service=_embedding_service,
            vector_store=_vector_store,
            graph_store=_graph_store
        )
        
        _services_initialized = True
    
    return {
        'embedding': _embedding_service,
        'vector_store': _vector_store,
        'graph_store': _graph_store,
        'chunker': _chunker,
        'ingestion': _ingestion_service,
        'retrieval': _retrieval_service
    }


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload a PDF document for indexing
    
    Returns immediately with a task ID for tracking progress
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    services = get_services()
    
    # Generate task ID
    import uuid
    task_id = str(uuid.uuid4())
    
    # Save uploaded file to temp location
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    try:
        content = await file.read()
        temp_file.write(content)
        temp_file.close()
        
        # Initialize processing status
        _processing_status[task_id] = {
            'status': 'queued',
            'progress': 0,
            'filename': file.filename,
            'message': 'Queued for processing'
        }
        
        # Process in background
        background_tasks.add_task(
            process_document_background,
            task_id,
            temp_file.name,
            file.filename,
            services['ingestion']
        )
        
        return JSONResponse({
            'task_id': task_id,
            'filename': file.filename,
            'message': 'Upload successful, processing started'
        })
        
    except Exception as e:
        os.unlink(temp_file.name)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


async def process_document_background(
    task_id: str,
    file_path: str,
    filename: str,
    ingestion_service: DocumentIngestion
):
    """Background task for document processing"""
    def update_progress(status: str, progress: int):
        _processing_status[task_id] = {
            'status': 'processing',
            'progress': progress,
            'filename': filename,
            'message': status
        }
    
    try:
        result = ingestion_service.process_pdf(file_path, filename, update_progress)
        
        if result['success']:
            _processing_status[task_id] = {
                'status': 'completed',
                'progress': 100,
                'filename': filename,
                'paper_id': result['paper_id'],
                'chunks_created': result['chunks_created'],
                'message': result['message']
            }
        else:
            _processing_status[task_id] = {
                'status': 'failed',
                'progress': 0,
                'filename': filename,
                'error': result.get('error', 'Unknown error'),
                'message': result['message']
            }
    
    except Exception as e:
        _processing_status[task_id] = {
            'status': 'failed',
            'progress': 0,
            'filename': filename,
            'error': str(e),
            'message': f'Processing failed: {str(e)}'
        }
    
    finally:
        # Clean up temp file
        if os.path.exists(file_path):
            os.unlink(file_path)


@router.get("/status/{task_id}")
async def get_processing_status(task_id: str):
    """Get the status of a document processing task"""
    if task_id not in _processing_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return _processing_status[task_id]


@router.get("/resources")
async def list_resources():
    """List all indexed resources"""
    services = get_services()
    resources = services['retrieval'].get_all_resources()
    
    return {
        'resources': resources,
        'total': len(resources)
    }


@router.delete("/resources/{paper_id}")
async def delete_resource(paper_id: str):
    """Delete a resource from the knowledge base"""
    services = get_services()
    
    result = services['ingestion'].delete_document(paper_id)
    
    if result['success']:
        return result
    else:
        raise HTTPException(status_code=500, detail=result['message'])


@router.get("/stats")
async def get_stats():
    """Get statistics about the knowledge base"""
    services = get_services()
    
    stats = services['vector_store'].get_stats()
    stats['neo4j_enabled'] = services['graph_store'] is not None and services['graph_store'].enabled
    
    return stats