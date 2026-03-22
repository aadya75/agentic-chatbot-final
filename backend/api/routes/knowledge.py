"""
API Routes for Knowledge Base Management (Supabase backend)
Handles resource upload, listing, and deletion
"""

import os
import tempfile
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

from knowledge_engine.embedding_service import EmbeddingService
from knowledge_engine.vector_store import SupabaseVectorStore
from knowledge_engine.graph_store import GraphStore
from knowledge_engine.chunking import DocumentChunker
from knowledge_engine.ingestion import DocumentIngestion
from knowledge_engine.retrieval import HybridRetrieval

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_ANON_KEY", ""))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./data/uploads")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

# ---------------------------------------------------------------------------
# Singleton services
# ---------------------------------------------------------------------------
_services_initialized = False
_embedding_service: Optional[EmbeddingService] = None
_vector_store: Optional[SupabaseVectorStore] = None
_graph_store: Optional[GraphStore] = None
_chunker: Optional[DocumentChunker] = None
_ingestion_service: Optional[DocumentIngestion] = None
_retrieval_service: Optional[HybridRetrieval] = None
_processing_status: Dict[str, Dict] = {}


def get_services() -> Dict:
    """Lazily initialise and return knowledge engine services."""
    global _services_initialized
    global _embedding_service, _vector_store, _graph_store
    global _chunker, _ingestion_service, _retrieval_service

    if _services_initialized:
        return {
            "embedding": _embedding_service,
            "vector_store": _vector_store,
            "graph_store": _graph_store,
            "chunker": _chunker,
            "ingestion": _ingestion_service,
            "retrieval": _retrieval_service,
        }

    _embedding_service = EmbeddingService(embedding_dim=EMBEDDING_DIM)

    if not USE_SUPABASE:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY (or SUPABASE_ANON_KEY) must be set."
        )

    _vector_store = SupabaseVectorStore(
        supabase_url=SUPABASE_URL,
        supabase_key=SUPABASE_KEY,
        embedding_dim=EMBEDDING_DIM,
    )

    # Optional Neo4j graph store
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER")
    neo4j_password = os.getenv("NEO4J_PASSWORD")
    if neo4j_uri and neo4j_user and neo4j_password:
        _graph_store = GraphStore(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password,
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
        )

    _chunker = DocumentChunker(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    _ingestion_service = DocumentIngestion(
        upload_dir=UPLOAD_DIR,
        supabase_url=SUPABASE_URL,
        supabase_key=SUPABASE_KEY,
        embedding_service=_embedding_service,
        chunker=_chunker,
        graph_store=_graph_store,
    )

    _retrieval_service = HybridRetrieval(
        embedding_service=_embedding_service,
        vector_store=_vector_store,
        graph_store=_graph_store,
    )

    _services_initialized = True
    return {
        "embedding": _embedding_service,
        "vector_store": _vector_store,
        "graph_store": _graph_store,
        "chunker": _chunker,
        "ingestion": _ingestion_service,
        "retrieval": _retrieval_service,
    }


# ---------------------------------------------------------------------------
# Auth dependency (placeholder — replace with your real auth)
# ---------------------------------------------------------------------------
async def get_current_user() -> Dict:
    return {"user_id": "default_user", "email": "user@example.com"}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user),
):
    """Upload a PDF for indexing. Returns task_id for progress tracking."""
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    services = get_services()

    task_id = str(uuid.uuid4())
    paper_id = str(uuid.uuid4())

    # Save to temp file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    try:
        content = await file.read()
        temp_file.write(content)
        temp_file.close()

        _processing_status[task_id] = {
            "status": "queued",
            "progress": 0,
            "filename": file.filename,
            "paper_id": paper_id,
            "user_id": current_user.get("user_id"),
            "message": "Queued for processing",
        }

        background_tasks.add_task(
            _process_document_background,
            task_id,
            temp_file.name,
            file.filename,
            paper_id,
            current_user.get("user_id"),
            services["ingestion"],
        )

        return JSONResponse({
            "task_id": task_id,
            "paper_id": paper_id,
            "filename": file.filename,
            "message": "Upload successful, processing started",
        })

    except Exception as e:
        import os as _os
        if _os.path.exists(temp_file.name):
            _os.unlink(temp_file.name)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


async def _process_document_background(
    task_id: str,
    file_path: str,
    filename: str,
    paper_id: str,
    user_id: Optional[str],
    ingestion_service: DocumentIngestion,
):
    """Background task — processes and indexes the PDF, then cleans up."""
    import os as _os

    def _progress(status: str, progress: int):
        _processing_status[task_id] = {
            "status": "processing",
            "progress": progress,
            "filename": filename,
            "paper_id": paper_id,
            "user_id": user_id,
            "message": status,
        }

    try:
        result = ingestion_service.process_pdf(
            file_path=file_path,
            filename=filename,
            progress_callback=_progress,
            user_id=user_id,
            paper_id=paper_id,
        )

        if result["success"]:
            _processing_status[task_id] = {
                "status": "completed",
                "progress": 100,
                "filename": filename,
                "paper_id": paper_id,
                "user_id": user_id,
                "chunks_created": result.get("chunks_created", 0),
                "message": result["message"],
            }
        else:
            _processing_status[task_id] = {
                "status": "failed",
                "progress": 0,
                "filename": filename,
                "paper_id": paper_id,
                "user_id": user_id,
                "error": result.get("error", "Unknown error"),
                "message": result["message"],
            }

    except Exception as e:
        _processing_status[task_id] = {
            "status": "failed",
            "progress": 0,
            "filename": filename,
            "paper_id": paper_id,
            "user_id": user_id,
            "error": str(e),
            "message": f"Processing failed: {str(e)}",
        }

    finally:
        if _os.path.exists(file_path):
            _os.unlink(file_path)


@router.get("/status/{task_id}")
async def get_processing_status(
    task_id: str,
    current_user: Dict = Depends(get_current_user),
):
    """Get the status of a document processing task."""
    if task_id not in _processing_status:
        raise HTTPException(status_code=404, detail="Task not found")

    status = _processing_status[task_id]
    user_id = current_user.get("user_id")

    if status.get("user_id") and status["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this task")

    return status


@router.get("/resources")
async def list_resources(current_user: Dict = Depends(get_current_user)):
    """List all indexed resources for the current user."""
    services = get_services()
    user_id = current_user.get("user_id")

    papers = services["vector_store"].get_all_papers(user_id=user_id)
    resources = [
        {
            "paper_id": p.get("id"),
            "filename": p.get("filename"),
            "upload_date": p.get("upload_date"),
            "user_id": p.get("user_id"),
        }
        for p in papers
    ]

    return {"resources": resources, "total": len(resources), "user_id": user_id}


@router.delete("/resources/{paper_id}")
async def delete_resource(
    paper_id: str,
    current_user: Dict = Depends(get_current_user),
):
    """Delete a resource from the knowledge base."""
    try:
        uuid.UUID(paper_id, version=4)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid paper ID format.")

    services = get_services()
    user_id = current_user.get("user_id")

    # Verify ownership
    papers = services["vector_store"].get_all_papers(user_id=user_id)
    if not any(p.get("id") == paper_id for p in papers):
        raise HTTPException(
            status_code=404,
            detail="Paper not found or you don't have permission to delete it",
        )

    result = services["ingestion"].delete_document(paper_id)

    if result.get("success"):
        return {"success": True, "paper_id": paper_id, "message": result.get("message")}
    raise HTTPException(status_code=500, detail=result.get("message", "Deletion failed"))


@router.get("/stats")
async def get_stats(current_user: Dict = Depends(get_current_user)):
    """Get knowledge-base statistics for the current user."""
    services = get_services()
    user_id = current_user.get("user_id")

    stats = services["vector_store"].get_stats(user_id=user_id)
    stats["storage_backend"] = "Supabase PostgreSQL"
    stats["neo4j_enabled"] = (
        services["graph_store"] is not None and services["graph_store"].enabled
    )
    stats["user_id"] = user_id
    return stats


@router.post("/search")
async def search_documents(
    query: str,
    top_k: int = 5,
    include_citations: bool = False,
    current_user: Dict = Depends(get_current_user),
):
    """Search the knowledge base."""
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    services = get_services()
    user_id = current_user.get("user_id")

    try:
        results = services["retrieval"].retrieve(
            query=query,
            top_k=top_k,
            user_id=user_id,
            include_citations=include_citations,
        )
        return {
            "query": query,
            "num_results": len(results.get("chunks", [])),
            "chunks": results.get("chunks", []),
            "citations": results.get("citations"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/system/info")
async def get_system_info():
    """Return system configuration info."""
    return {
        "supabase_enabled": USE_SUPABASE,
        "supabase_url": SUPABASE_URL if USE_SUPABASE else None,
        "upload_dir": UPLOAD_DIR,
        "embedding_dim": EMBEDDING_DIM,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
    }
