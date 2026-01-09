# backend/api/main.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time

from core.config import settings, validate_setup
from core.agent import agent_manager
from api.routes import chat, health, tools


# Lifespan context manager - runs code at startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events for FastAPI.
    
    Why? Ensures agent initializes before accepting requests
    and cleans up properly on shutdown.
    """
    # Startup
    print("\n" + "="*60)
    print("🚀 Starting Agentic Chatbot API")
    print("="*60 + "\n")
    
    # Validate configuration
    validate_setup()
    
    # Initialize agent
    await agent_manager.initialize()
    
    print("\n" + "="*60)
    print(f"✅ Server ready on http://{settings.host}:{settings.port}")
    print("="*60 + "\n")
    
    # Record start time for uptime tracking
    app.state.start_time = time.time()
    
    yield  # Server runs here
    
    # Shutdown
    print("\n" + "="*60)
    print("🛑 Shutting down Agentic Chatbot API")
    print("="*60 + "\n")
    
    await agent_manager.shutdown()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI agent with MCP server integration for Gmail, Drive, and Calendar",
    lifespan=lifespan,
    docs_url="/docs",  # Swagger UI at /docs
    redoc_url="/redoc",  # ReDoc at /redoc
)


# CORS Middleware - allows frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Which domains can access
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch all unhandled exceptions and return proper error response.
    
    Prevents server crashes and provides useful error messages.
    """
    print(f"❌ Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(exc),
                "details": {"type": type(exc).__name__}
            }
        }
    )


# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(tools.router, prefix="/api", tags=["Tools"])


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint - basic API information.
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    """
    Run with: python -m backend.api.main
    
    For development, use: uvicorn backend.api.main:app --reload
    """
    import uvicorn
    uvicorn.run(
        "backend.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )