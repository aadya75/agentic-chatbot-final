# backend/api/routes/chat.py
#
# Extended with HITL (Human-in-the-Loop) support:
#   POST /message         — normal chat (may return interrupted=True)
#   POST /message/confirm — user approves or rejects a pending action

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging

from auth.dependencies import CurrentUser
from core.agent import agent_manager

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# REQUEST / RESPONSE MODELS
# ============================================================================

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


class ConfirmRequest(BaseModel):
    """Body for POST /message/confirm — user's approve/reject response."""
    thread_id: str
    response: str          # "approve" | "reject" (also accepts yes/no/ok/cancel)
    user_response: Optional[str] = None   # alias — frontend may send either field


class ConfirmationRequired(BaseModel):
    message: str           # The human-readable confirmation prompt
    thread_id: str


class ChatResponse(BaseModel):
    message: Optional[str] = None
    thread_id: str
    message_id: str
    execution_time: float
    # HITL fields
    interrupted: bool = False
    confirmation_required: Optional[ConfirmationRequired] = None


class ThreadResponse(BaseModel):
    thread_id: str


class Message(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str


# ============================================================================
# CHAT ENDPOINT  (now HITL-aware)
# ============================================================================

@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    user: CurrentUser,
):
    """
    Send a message to the AI.

    Normal case: returns { interrupted: false, message: "...", ... }

    When a Gmail/Calendar write action is detected:
    returns {
      interrupted: true,
      confirmation_required: {
        message: "⚠️ About to send email to ...",
        thread_id: "..."
      }
    }
    → Frontend should show the confirmation UI.
    → Then call POST /message/confirm with approve or reject.
    """
    try:
        if not agent_manager.is_initialized:
            raise HTTPException(status_code=503, detail="Agent not initialized. Please wait.")

        response = await agent_manager.chat(
            message=request.message,
            thread_id=request.thread_id,
            user_id=user["id"],
        )

        # ── HITL interrupted ──────────────────────────────────────────
        if response.get("interrupted"):
            conf = response["confirmation_required"]
            return ChatResponse(
                message=None,
                thread_id=response["thread_id"],
                message_id=response["message_id"],
                execution_time=response["execution_time"],
                interrupted=True,
                confirmation_required=ConfirmationRequired(
                    message=conf["message"],
                    thread_id=conf["thread_id"],
                ),
            )

        # ── Normal response ───────────────────────────────────────────
        return ChatResponse(
            message=response["message"],
            thread_id=response["thread_id"],
            message_id=response["message_id"],
            execution_time=response["execution_time"],
            interrupted=False,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CONFIRM ENDPOINT  (resume after HITL pause)
# ============================================================================

@router.post("/message/confirm", response_model=ChatResponse)
async def confirm_action(
    request: ConfirmRequest,
    user: CurrentUser,
):
    """
    Resume a paused graph after the user approves or rejects a confirmation.

    Send:
      { "thread_id": "...", "response": "approve" }
    or
      { "thread_id": "...", "response": "reject" }

    Returns the same shape as POST /message.
    May itself return interrupted=True if there are multiple write tasks to confirm.
    """
    try:
        if not agent_manager.is_initialized:
            raise HTTPException(status_code=503, detail="Agent not initialized. Please wait.")

        # Accept either `response` or `user_response` field from frontend
        user_response = request.response or request.user_response or "reject"

        if not agent_manager.orchestrator.is_pending_confirmation(request.thread_id):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No pending confirmation for thread_id='{request.thread_id}'. "
                    "It may have already been resumed, timed out, or never existed."
                ),
            )

        response = await agent_manager.resume(
            thread_id=request.thread_id,
            user_response=user_response,
            user_id=user["id"],
        )

        # Another HITL pause (multiple write tasks in one query)
        if response.get("interrupted"):
            conf = response["confirmation_required"]
            return ChatResponse(
                message=None,
                thread_id=response["thread_id"],
                message_id=response["message_id"],
                execution_time=response["execution_time"],
                interrupted=True,
                confirmation_required=ConfirmationRequired(
                    message=conf["message"],
                    thread_id=conf["thread_id"],
                ),
            )

        return ChatResponse(
            message=response["message"],
            thread_id=response["thread_id"],
            message_id=response["message_id"],
            execution_time=response["execution_time"],
            interrupted=False,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming action: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# EXISTING THREAD MANAGEMENT ENDPOINTS  (unchanged)
# ============================================================================

@router.post("/thread", response_model=ThreadResponse)
async def create_thread(
    user: CurrentUser,
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
    user: CurrentUser,
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
    user: CurrentUser,
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
