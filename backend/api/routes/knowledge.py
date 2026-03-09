"""
API Routes for Knowledge Base Management with Supabase
Handles resource upload, listing, and deletion
"""

import os
import tempfile
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from typing import List, Dict, Optional
from pathlib import Path
import asyncio
from knowledge_engine.vector_store import SupabaseVectorStore
from dotenv import load_dotenv

load_dotenv()

# Import appropriate vector store based on configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_ANON_KEY"))

if SUPABASE_URL and SUPABASE_KEY:
    USE_SUPABASE = True
else:
    USE_SUPABASE = False

from knowledge_engine.embedding_service import EmbeddingService
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
        UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./data/uploads")
        EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
        CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
        CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
        
        # Initialize embedding service
        _embedding_service = EmbeddingService(embedding_dim=EMBEDDING_DIM)
        
        # Initialize vector store (Supabase or FAISS)
        try:
            print("🔵 Initializing Supabase vector store")
            _vector_store = SupabaseVectorStore(
                supabase_url=SUPABASE_URL,
                supabase_key=SUPABASE_KEY,
                embedding_dim=EMBEDDING_DIM
            )
        except Exception as e:
            print(e)
            print(f"⚠️ Failed to initialize Supabase vector store: {str(e)}")
            print("Falling back to FAISS vector store")
            

        
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
        
        # Initialize other services
        _chunker = DocumentChunker(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        
        # Initialize ingestion service with appropriate parameters
        if USE_SUPABASE:
            _ingestion_service = DocumentIngestion(
                upload_dir=UPLOAD_DIR,
                supabase_url=SUPABASE_URL,
                supabase_key=SUPABASE_KEY,
                embedding_service=_embedding_service,
                chunker=_chunker,
                graph_store=_graph_store
            )
        else:
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


# Dependency to get user ID from request (you can implement your own auth)
async def get_current_user() -> Dict:
    """Get current user from request (placeholder - implement your auth)"""
    # This is a placeholder - replace with your actual authentication
    return {'user_id': 'default_user', 'email': 'user@example.com'}


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user)
):
    """
    Upload a PDF document for indexing
    
    Returns immediately with a task ID for tracking progress
    """
    # Validate file type
    if not file.filename or not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    services = get_services()
    
    # Generate task ID and paper ID
    task_id = str(uuid.uuid4())
    paper_id = str(uuid.uuid4())  # Generate proper UUID for the paper
    
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
            'paper_id': paper_id,  # Include paper_id in status
            'user_id': current_user.get('user_id'),
            'message': 'Queued for processing'
        }
        
        # Process in background with user context
        background_tasks.add_task(
            process_document_background,
            task_id,
            temp_file.name,
            file.filename,
            paper_id,
            current_user.get('user_id'),
            services['ingestion']
        )
        
        return JSONResponse({
            'task_id': task_id,
            'paper_id': paper_id,  # Return paper_id to client
            'filename': file.filename,
            'message': 'Upload successful, processing started'
        })
        
    except Exception as e:
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


async def process_document_background(
    task_id: str,
    file_path: str,
    filename: str,
    paper_id: str,  # Proper UUID passed from upload
    user_id: Optional[str],
    ingestion_service: DocumentIngestion
):
    """Background task for document processing with user context"""
    def update_progress(status: str, progress: int):
        _processing_status[task_id] = {
            'status': 'processing',
            'progress': progress,
            'filename': filename,
            'paper_id': paper_id,
            'user_id': user_id,
            'message': status
        }
    
    try:
        # For Supabase integration, we need to ensure the ingestion service
        # can pass user_id to the vector store
        if USE_SUPABASE and hasattr(ingestion_service.vector_store, 'add_documents'):
            # Store user_id in metadata for retrieval
            result = ingestion_service.process_pdf(
                file_path, 
                filename, 
                update_progress
            )
            
            # If Supabase vector store, we need to attach user_id
            # This assumes your ingestion service can handle user context
            # You may need to modify process_pdf method to accept user_id
            if result['success'] and user_id:
                # Update the paper with user_id in Supabase
                services = get_services()
                if hasattr(services['vector_store'], 'update_paper_user'):
                    services['vector_store'].update_paper_user(paper_id, user_id)
        else:
            # Original processing for FAISS
            result = ingestion_service.process_pdf(file_path, filename, update_progress)
        
        if result['success']:
            _processing_status[task_id] = {
                'status': 'completed',
                'progress': 100,
                'filename': filename,
                'paper_id': paper_id,
                'user_id': user_id,
                'chunks_created': result.get('chunks_created', 0),
                'message': result['message']
            }
        else:
            _processing_status[task_id] = {
                'status': 'failed',
                'progress': 0,
                'filename': filename,
                'paper_id': paper_id,
                'user_id': user_id,
                'error': result.get('error', 'Unknown error'),
                'message': result['message']
            }
    
    except Exception as e:
        _processing_status[task_id] = {
            'status': 'failed',
            'progress': 0,
            'filename': filename,
            'paper_id': paper_id,
            'user_id': user_id,
            'error': str(e),
            'message': f'Processing failed: {str(e)}'
        }
    
    finally:
        # Clean up temp file
        if os.path.exists(file_path):
            os.unlink(file_path)


@router.get("/status/{task_id}")
async def get_processing_status(
    task_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Get the status of a document processing task"""
    if task_id not in _processing_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Optional: Check if user owns this task
    status = _processing_status[task_id]
    user_id = current_user.get('user_id')
    
    # Add authorization check (optional)
    if status.get('user_id') and status['user_id'] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this task")
    
    return status


@router.get("/resources")
async def list_resources(
    current_user: Dict = Depends(get_current_user)
):
    """List all indexed resources for the current user"""
    services = get_services()
    user_id = current_user.get('user_id')
    
    # Get resources with user filtering for Supabase
    if USE_SUPABASE:
        resources = services['vector_store'].get_all_papers(user_id=user_id)
        formatted_resources = [
            {
                'paper_id': r.get('id'),
                'filename': r.get('filename'),
                'upload_date': r.get('upload_date'),
                'user_id': r.get('user_id')
            }
            for r in resources
        ]
    else:
        # FAISS doesn't support user filtering natively
        resources = services['retrieval'].get_all_resources()
        formatted_resources = resources
    
    return {
        'resources': formatted_resources,
        'total': len(formatted_resources),
        'user_id': user_id
    }


@router.delete("/resources/{paper_id}")
async def delete_resource(
    paper_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Delete a resource from the knowledge base"""
    # Validate paper_id is a proper UUID
    try:
        uuid_obj = uuid.UUID(paper_id, version=4)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid paper ID format. Must be a valid UUID.")
    
    services = get_services()
    user_id = current_user.get('user_id')
    
    # For Supabase, verify ownership before deletion
    if USE_SUPABASE:
        # First, check if paper exists and belongs to user
        papers = services['vector_store'].get_all_papers(user_id=user_id)
        paper_exists = any(p.get('id') == paper_id for p in papers)
        
        if not paper_exists:
            raise HTTPException(status_code=404, detail="Paper not found or you don't have permission to delete it")
    
    result = services['ingestion'].delete_document(paper_id)
    
    if result.get('success'):
        return {
            'success': True,
            'paper_id': paper_id,
            'message': result.get('message', 'Resource deleted successfully'),
            'user_id': user_id
        }
    else:
        raise HTTPException(
            status_code=500, 
            detail=result.get('message', 'Failed to delete resource')
        )


@router.get("/stats")
async def get_stats(
    current_user: Dict = Depends(get_current_user)
):
    """Get statistics about the knowledge base"""
    services = get_services()
    user_id = current_user.get('user_id')
    
    if USE_SUPABASE:
        # Get user-specific stats for Supabase
        stats = services['vector_store'].get_stats(user_id=user_id)
        stats['storage_backend'] = 'Supabase PostgreSQL'
    else:
        stats = services['vector_store'].get_stats()
        stats['storage_backend'] = 'FAISS (local)'
    
    stats['neo4j_enabled'] = services['graph_store'] is not None and services['graph_store'].enabled
    stats['user_id'] = user_id
    
    return stats


@router.post("/search")
async def search_documents(
    query: str,
    top_k: int = 5,
    include_citations: bool = False,
    current_user: Dict = Depends(get_current_user)
):
    """Search for documents in the knowledge base"""
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    services = get_services()
    user_id = current_user.get('user_id')
    
    try:
        results = services['retrieval'].retrieve(
            query=query,
            top_k=top_k,
            # user_id=user_id if USE_SUPABASE else None,
            include_citations=include_citations
        )
        
        return {
            'query': query,
            'num_results': len(results.get('chunks', [])),
            'chunks': results.get('chunks', []),
            'citations': results.get('citations'),
            # 'user_id': user_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/system/info")
async def get_system_info():
    """Get system information and configuration"""
    return {
        'supabase_enabled': USE_SUPABASE,
        'supabase_url': SUPABASE_URL if USE_SUPABASE else None,
        'upload_dir': os.getenv("UPLOAD_DIR", "./data/uploads"),
        'embedding_dim': int(os.getenv("EMBEDDING_DIM", "384")),
        'chunk_size': int(os.getenv("CHUNK_SIZE", "500")),
        'chunk_overlap': int(os.getenv("CHUNK_OVERLAP", "50"))
    }