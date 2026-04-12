"""
backend/auth/mcp_token_bridge.py

Per-user MCP client cache — one client per user_id, reused across requests.
Rebuilds only when token changes (Google auto-refresh) or explicit invalidation.
"""

import os
import logging
from typing import Dict, Optional, Tuple

from auth.google_oauth import get_valid_google_token
from auth.github_oauth import get_github_token

logger = logging.getLogger(__name__)

GOOGLE_MCP_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp").rstrip("/")
GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp"

# user_id → (client, token_used_to_build_it)
_google_clients: Dict[str, Tuple] = {}
_github_clients: Dict[str, Tuple] = {}


async def get_google_workspace_client_for_user(user_id: str):
    """
    Returns a cached MultiServerMCPClient for Google Workspace.
    Rebuilds if token was refreshed since last build.
    Returns None if user hasn't connected Google.
    """
    from langchain_mcp_adapters.client import MultiServerMCPClient

    token = await get_valid_google_token(user_id)
    if not token:
        return None

    cached = _google_clients.get(user_id)
    if cached and cached[1] == token:
        return cached[0]  # token unchanged — reuse client

    logger.info(f"Building new Google MCP client for user {user_id}")
    client = MultiServerMCPClient({
        "google_workspace": {
            "transport": "http",
            "url": GOOGLE_MCP_URL,
            "headers": {"Authorization": f"Bearer {token}"},
            "timeout": 120,
        }
    })
    _google_clients[user_id] = (client, token)
    return client


async def get_github_client_for_user(user_id: str):
    """
    Returns a cached MultiServerMCPClient for GitHub.
    GitHub tokens don't expire — only rebuilds on invalidation.
    Returns None if user hasn't connected GitHub.
    """
    from langchain_mcp_adapters.client import MultiServerMCPClient

    token = await get_github_token(user_id)
    if not token:
        return None

    cached = _github_clients.get(user_id)
    if cached and cached[1] == token:
        return cached[0]

    logger.info(f"Building new GitHub MCP client for user {user_id}")
    client = MultiServerMCPClient({
        "github": {
            "transport": "http",
            "url": GITHUB_MCP_URL,
            "headers": {"Authorization": f"Bearer {token}"},
            "timeout": 60,
        }
    })
    _github_clients[user_id] = (client, token)
    return client


def invalidate_github_client(user_id: str) -> None:
    """Call when GitHub returns 401 — forces rebuild on next request."""
    _github_clients.pop(user_id, None)
    logger.info(f"Invalidated GitHub MCP client for user {user_id}")


def invalidate_google_client(user_id: str) -> None:
    """Call when Google returns 401 — forces token refresh + client rebuild."""
    _google_clients.pop(user_id, None)
    logger.info(f"Invalidated Google MCP client for user {user_id}")


# Back-compat wrapper used by some older call sites
async def get_github_client_for_user_with_fallback(user_id: str):
    token = await get_github_token(user_id)
    if not token:
        return None, None
    client = await get_github_client_for_user(user_id)
    return client, token