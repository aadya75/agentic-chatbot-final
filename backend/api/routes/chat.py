# backend/api/routes/chat.py
#
# FIX: Use `user: CurrentUser` only — no `= Depends(get_current_user)` alongside it.

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging

from auth.dependencies import CurrentUser
from core.agent import agent_manager

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


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


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    user: CurrentUser,                  # ✅ just the type, Depends is inside Annotated
):
    try:
        if not agent_manager.is_initialized:
            raise HTTPException(status_code=503, detail="Agent not initialized. Please wait.")

        response = await agent_manager.chat(
            message=request.message,
            thread_id=request.thread_id,
            user_id=user["id"],
        )

        return ChatResponse(
            message=response["message"],
            thread_id=response["thread_id"],
            message_id=response["message_id"],
            execution_time=response["execution_time"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/thread", response_model=ThreadResponse)
async def create_thread(
    user: CurrentUser,                  # ✅
):
    try:
        thread_id = agent_manager.create_thread(user_id=user["id"])
        return ThreadResponse(thread_id=thread_id)
    except Exception as e:
        logger.error(f"Error creating thread: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/threads/{thread_id}/messages", response_model=List[Message])
async def get_thread_messages(
    thread_id: str,
    user: CurrentUser,                  # ✅
):
    try:
        messages = agent_manager.get_messages(
            thread_id=thread_id,
            user_id=user["id"],
        )
        if messages is None:
            raise HTTPException(status_code=404, detail="Thread not found")
        return [Message(**msg) for msg in messages]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/thread/{thread_id}")
async def delete_thread(
    thread_id: str,
    user: CurrentUser,                  # ✅
):
    try:
        success = agent_manager.delete_thread(
            thread_id=thread_id,
            user_id=user["id"],
        )
        if not success:
            raise HTTPException(status_code=404, detail="Thread not found")
        return {"message": "Thread deleted successfully", "thread_id": thread_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting thread: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
