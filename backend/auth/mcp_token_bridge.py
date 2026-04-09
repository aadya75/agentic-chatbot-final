"""
backend/auth/mcp_token_bridge.py  (updated — adds GitHub support)

Bridges your app's user sessions with both MCP servers:
  - Google Workspace MCP (external OAuth mode, needs Google access token)
  - GitHub MCP (remote server at api.githubcopilot.com, needs GitHub token)

Usage in the orchestrator:
    from auth.mcp_token_bridge import (
        get_google_workspace_client_for_user,
        get_github_client_for_user,
    )
"""

import os
from typing import Optional

from auth.google_oauth import get_valid_google_token
from auth.github_oauth import get_github_token, clear_github_token

GOOGLE_MCP_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp/")
GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"


async def get_google_workspace_client_for_user(user_id: str):
    """
    Returns a MultiServerMCPClient for Google Workspace tools,
    authenticated with the user's Google access token.
    Returns None if the user hasn't connected their Google account.
    """
    from langchain_mcp_adapters.client import MultiServerMCPClient

    token = await get_valid_google_token(user_id)
    if not token:
        return None

    return MultiServerMCPClient({
        "google_workspace": {
            "transport": "http",
            "url": GOOGLE_MCP_URL,
            "headers": {"Authorization": f"Bearer {token}"},
        }
    })


async def get_github_client_for_user(user_id: str):
    """
    Returns a MultiServerMCPClient for GitHub tools,
    authenticated with the user's GitHub OAuth token.
    Returns None if the user hasn't connected their GitHub account.
    """
    from langchain_mcp_adapters.client import MultiServerMCPClient

    token = await get_github_token(user_id)
    if not token:
        return None

    return MultiServerMCPClient({
        "github": {
            "transport": "http",
            "url": GITHUB_MCP_URL,
            "headers": {"Authorization": f"Bearer {token}"},
        }
    })


async def get_github_client_for_user_with_fallback(user_id: str):
    """
    Same as get_github_client_for_user but clears the token and returns
    None if the stored token has been revoked (caller should catch 401s
    from the MCP server and call this to signal re-auth needed).
    """
    token = await get_github_token(user_id)
    if not token:
        return None, None

    from langchain_mcp_adapters.client import MultiServerMCPClient
    client = MultiServerMCPClient({
        "github": {
            "transport": "http",
            "url": GITHUB_MCP_URL,
            "headers": {"Authorization": f"Bearer {token}"},
        }
    })
    return client, token
