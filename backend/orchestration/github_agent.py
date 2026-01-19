
import logging
from typing import Dict, Any, List, Optional
from backend.orchestration.state import AgentState


from backend.orchestration.state import AgentState
import json
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from core.config import settings
from orchestration.state import AgentState  # Your state definition
logger = logging.getLogger(__name__)
from backend.orchestration.state import AgentState
import re


def github_agent(self, state: AgentState) -> AgentState:
    """Handle GitHub operations"""
    if "github" not in state["intent_categories"]:
        return state
    
    try:
        llm = self.llm.get_cheap()
        query = state["user_query"]
        
        tool_selection_prompt = f"""What GitHub operations are needed?

Query: {query}

Available tools:
- search_repositories: Find repos by topic
- search_code: Find code examples
- get_repository: Get repo details
- create_repository: Create new repo (needs approval)

Output JSON: {{"tool": "tool_name", "query": "search_query", "needs_approval": false}}"""
        
        response = llm.invoke(tool_selection_prompt)
        content = response.content if hasattr(response, 'content') else str(response)
        
        # Parse tool selection
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            tool_plan = json.loads(json_match.group())
            
            tool_name = tool_plan.get("tool")
            search_query = tool_plan.get("query", query)
            
            # Execute read operations via MCP
            if tool_name in ["search_repositories", "search_code", "get_repository"]:
                result = self.mcp.call_tool("github", tool_name, {
                    "query": search_query
                })
                state["github_results"] = result
                logger.info(f"GitHub tool executed: {tool_name}")
            
            # Write operations need approval
            elif tool_plan.get("needs_approval"):
                state["pending_human_approval"].append({
                    "agent": "github",
                    "action": tool_name,
                    "parameters": {"name": search_query},
                    "preview": f"Create GitHub repository: {search_query}"
                })
                logger.info(f"GitHub approval needed: {tool_name}")
        
    except Exception as e:
        logger.error(f"GitHub agent failed: {e}")
        state["errors"].append(f"GitHub operation failed: {str(e)}")
    
    return state
