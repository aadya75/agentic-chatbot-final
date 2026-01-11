# backend/api/routes/chat.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging

from core.agent import agent_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Request/Response models
class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None
    user_id: Optional[str] = None

class ChatResponse(BaseModel):
    message: str
    thread_id: str
    message_id: str
    execution_time: float

class ThreadResponse(BaseModel):
    thread_id: str

class Message(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str

# Routes
@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Process a chat message through the agent."""
    try:
        # Check if agent is initialized
        if not agent_manager.is_initialized:
            raise HTTPException(
                status_code=503, 
                detail="Agent not initialized. Please wait."
            )
        
        # Use provided thread_id or let agent create one
        response = await agent_manager.chat(
            message=request.message,
            thread_id=request.thread_id
        )
        
        return ChatResponse(
            message=response["message"],
            thread_id=response["thread_id"],
            message_id=response["message_id"],
            execution_time=response["execution_time"]
        )
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/thread", response_model=ThreadResponse)
async def create_thread():
    """Create a new chat thread."""
    try:
        thread_id = agent_manager.create_thread()
        return ThreadResponse(thread_id=thread_id)
    except Exception as e:
        logger.error(f"Error creating thread: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/threads/{thread_id}/messages", response_model=List[Message])
async def get_thread_messages(thread_id: str):
    """Get all messages for a thread."""
    try:
        messages = agent_manager.get_messages(thread_id)
        if messages is None:
            raise HTTPException(status_code=404, detail="Thread not found")
        return [Message(**msg) for msg in messages]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/thread/{thread_id}")
async def delete_thread(thread_id: str):
    """Delete a thread."""
    try:
        success = agent_manager.delete_thread(thread_id)
        if not success:
            raise HTTPException(status_code=404, detail="Thread not found")
        return {"message": "Thread deleted successfully", "thread_id": thread_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting thread: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))