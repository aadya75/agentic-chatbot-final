import sys
import asyncio
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from duckduckgo_search import DDGS

# Initialize FastMCP server
mcp = FastMCP("ddgs")

@mcp.tool()
async def web_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search the web using DuckDuckGo.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        List of search results with title, link, and snippet
    """
    try:
        # Run the synchronous DDGS call in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _sync_web_search, query, max_results)
        return results
    except Exception as e:
        return [{"error": f"Search failed: {str(e)}"}]

def _sync_web_search(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Synchronous helper for web search"""
    results = []
    try:
        # Use DDGS without context manager for better compatibility
        ddgs = DDGS()
        for result in ddgs.text(query, max_results=max_results):
            results.append({
                "title": result.get("title", ""),
                "link": result.get("href", ""),
                "snippet": result.get("body", "")
            })
    except Exception as e:
        results.append({"error": f"Search execution failed: {str(e)}"})
    return results

@mcp.tool()
async def search_news(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search for news using DuckDuckGo.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        List of news search results
    """
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _sync_news_search, query, max_results)
        return results
    except Exception as e:
        return [{"error": f"News search failed: {str(e)}"}]

def _sync_news_search(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Synchronous helper for news search"""
    results = []
    try:
        ddgs = DDGS()
        for result in ddgs.news(query, max_results=max_results):
            results.append({
                "title": result.get("title", ""),
                "link": result.get("url", ""),
                "source": result.get("source", ""),
                "date": result.get("date", ""),
                "snippet": result.get("body", "")
            })
    except Exception as e:
        results.append({"error": f"News execution failed: {str(e)}"})
    return results

@mcp.tool()
async def search_images(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search for images using DuckDuckGo.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        List of image search results
    """
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _sync_image_search, query, max_results)
        return results
    except Exception as e:
        return [{"error": f"Image search failed: {str(e)}"}]

def _sync_image_search(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Synchronous helper for image search"""
    results = []
    try:
        ddgs = DDGS()
        for result in ddgs.images(query, max_results=max_results):
            results.append({
                "title": result.get("title", ""),
                "image": result.get("image", ""),
                "thumbnail": result.get("thumbnail", ""),
                "source": result.get("source", ""),
                "url": result.get("url", "")
            })
    except Exception as e:
        results.append({"error": f"Image execution failed: {str(e)}"})
    return results

if __name__ == "__main__":
    # Install required package: pip install duckduckgo-search
    mcp.run(transport="stdio")