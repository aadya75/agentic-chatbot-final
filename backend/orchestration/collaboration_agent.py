
import logging
from typing import Dict, Any, List, Optional
from backend import orchestration
from backend.orchestration.state import AgentState
import json
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from core.config import settings
from orchestration.state import AgentState  # Your state definition
logger = logging.getLogger(__name__)
from backend.orchestration.state import AgentState
import re
from orchestration.state import AgentState
import json
import re

def collaboration_agent(self, state: AgentState) -> AgentState:
        """Handle Gmail and Calendar operations"""
        if "collaboration" not in state["intent_categories"]:
            return state
        
        try:
            llm = self.llm.get_cheap()
            query = state["user_query"]
            
            collab_prompt = f"""What collaboration operations are needed?

Query: {query}

Available:
- search_gmail: Search emails (read)
- get_latest_gmail_messages: Get recent emails (read)
- send_gmail_message: Send email (needs approval)
- get_upcoming_events: Check calendar (read)
- create_calendar_event: Schedule meeting (needs approval)

Output JSON: {{"operations": [{{"tool": "name", "params": {{}}, "needs_approval": bool}}]}}"""
            
            response = llm.invoke(collab_prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse operations
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                ops_plan = json.loads(json_match.group())
                results = {}
                
                for op in ops_plan.get("operations", []):
                    tool_name = op["tool"]
                    params = op.get("params", {})
                    
                    # Determine server
                    if "gmail" in tool_name:
                        server = "gmail"
                    elif "calendar" in tool_name or "event" in tool_name:
                        server = "google_calendar"
                    else:
                        continue
                    
                    # Execute read operations
                    if not op.get("needs_approval"):
                        result = self.mcp.call_tool(server, tool_name, params)
                        results[tool_name] = result
                        logger.info(f"Collaboration tool executed: {tool_name}")
                    else:
                        # Add to approval queue
                        state["pending_human_approval"].append({
                            "agent": "collaboration",
                            "action": tool_name,
                            "parameters": params,
                            "preview": f"{tool_name}: {params}"
                        })
                        logger.info(f"Collaboration approval needed: {tool_name}")
                
                state["collaboration_results"] = results
            
        except Exception as e:
            logger.error(f"Collaboration agent failed: {e}")
            state["errors"].append(f"Collaboration operation failed: {str(e)}")
        
        return state