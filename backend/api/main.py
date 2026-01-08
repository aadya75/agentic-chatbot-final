 # FastAPI app entry point
 # backend/api/main.py
"""
FastAPI main application for Agentic Chatbot
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent import AgentManager
from api.routes import chat, health, tools
from utils.logger import setup_logger

# Initialize logger
logger = setup_logger(__name__)

# Global agent manager
agent_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global agent_manager
    
    # Startup
    logger.info("🚀 Starting Agentic Chatbot Backend...")
    try:
        agent_manager = AgentManager()
        await agent_manager.initialize()
        logger.info("✅ Agent initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize agent: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Agentic Chatbot Backend...")
    if agent_manager:
        await agent_manager.cleanup()


# Create FastAPI app
app = FastAPI(
    title="Agentic Chatbot API",
    description="Backend API for the Agentic Chatbot with MCP servers",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(tools.router, prefix="/api/tools", tags=["tools"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Agentic Chatbot API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat"""
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message = data.get("message", "")
            
            if not message:
                await websocket.send_json({"error": "Empty message"})
                continue
            
            logger.info(f"Received: {message}")
            
            # Process with agent
            try:
                response = await agent_manager.process_message(message)
                await websocket.send_json({
                    "type": "response",
                    "content": response,
                    "timestamp": response.get("timestamp")
                })
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send_json({
                    "type": "error",
                    "content": str(e)
                })
                
    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )