# backend/api/routes/health.py

from fastapi import APIRouter, Request
from api.models.response import HealthResponse
from core.config import settings
from core.agent import agent_manager
import time

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """
    Health check endpoint.
    
    Returns:
        - API status
        - Uptime
        - MCP server statuses
        
    Frontend can poll this to show system status.
    """
    # Calculate uptime
    start_time = request.app.state.start_time
    uptime = time.time() - start_time
    
    # Check MCP server statuses
    mcp_servers = {}
    if agent_manager.is_initialized:
        # Check which servers are configured
        if settings.enable_gmail:
            mcp_servers["gmail"] = "active" if agent_manager.mcp_client else "inactive"
        if settings.enable_google_drive:
            mcp_servers["google_drive"] = "active" if agent_manager.mcp_client else "inactive"
        if settings.enable_google_calendar:
            mcp_servers["google_calendar"] = "active" if agent_manager.mcp_client else "inactive"
    else:
        mcp_servers = {"status": "not_initialized"}
    
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        uptime_seconds=uptime,
        mcp_servers=mcp_servers
    )


@router.get("/health/ready")
async def readiness_check():
    """
    Kubernetes-style readiness check.
    
    Returns 200 only if agent is ready to handle requests.
    """
    if agent_manager.is_initialized:
        return {"status": "ready"}
    else:
        return {"status": "not_ready"}, 503


@router.get("/health/live")
async def liveness_check():
    """
    Kubernetes-style liveness check.
    
    Returns 200 if server is running (even if not fully initialized).
    """
    return {"status": "alive"}