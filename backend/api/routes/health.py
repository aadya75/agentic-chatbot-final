# backend/api/routes/health.py
from fastapi import APIRouter, Request
from typing import Dict, Any
import time
import logging

from core.agent import agent_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Module-level variable to track start time
_start_time = time.time()

@router.get("/health")
async def health_check(request: Request) -> Dict[str, Any]:
    """
    Health check endpoint
    
    Returns system status, uptime, and MCP server status
    """
    current_time = time.time()
    uptime = current_time - _start_time
    
    # Get MCP server status
    mcp_servers = {}
    if agent_manager.is_initialized:
        # Check which servers are configured
        if agent_manager._server_config:
            for server_name in agent_manager._server_config.keys():
                mcp_servers[server_name] = {
                    "status": "connected" if agent_manager.is_initialized else "disconnected",
                    "tool_count": len([t for t in agent_manager.tools if server_name in t.name.lower()])
                }
    
    return {
        "status": "healthy",
        "timestamp": current_time,
        "uptime_seconds": round(uptime, 2),
        "agent_initialized": agent_manager.is_initialized,
        "mcp_servers": mcp_servers,
        "active_threads": agent_manager.get_active_thread_count(),
        "total_threads": agent_manager.get_thread_count(),
        "total_tools": len(agent_manager.tools) if agent_manager.is_initialized else 0,
        "version": "1.0.0"
    }

@router.get("/status")
async def detailed_status() -> Dict[str, Any]:
    """
    Detailed status endpoint with more information
    """
    return {
        "agent": {
            "initialized": agent_manager.is_initialized,
            "llm_model": agent_manager.llm.model_name if agent_manager.llm else None,
            "tools_loaded": len(agent_manager.tools),
        },
        "threads": {
            "active": agent_manager.get_active_thread_count(),
            "total": agent_manager.get_thread_count(),
        },
        "mcp_servers": {
            name: {
                "enabled": True,
                "tool_count": len([t for t in agent_manager.tools if name in t.name.lower()])
            }
            for name in agent_manager._server_config.keys()
        } if agent_manager._server_config else {}
    }