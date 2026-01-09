# chat endpoints
from fastapi import APIRouter, HTTPException
from ..models.request import ChatRequest
from ..models.response import ChatResponse
from core.agent import AgentManager

router = APIRouter()
agent_manager = AgentManager()

@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Process a chat message through the agent."""
    try:
        response = await agent_manager.process_message(
            message=request.message,
            thread_id=request.thread_id,
            user_id=request.user_id
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/thread")
async def create_thread():
    """Create a new chat thread."""
    thread_id = agent_manager.create_thread()
    return {"thread_id": thread_id}

@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str):
    """Get all messages for a thread."""
    messages = agent_manager.get_thread_messages(thread_id)
    return {"messages": messages}