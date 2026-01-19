
import logging
from typing import Dict, Any, List, Optional
from backend.orchestration.state import AgentState
import json
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from core.config import settings
from orchestration.state import AgentState  # Your state definition
logger = logging.getLogger(__name__)
from backend.orchestration.state import AgentState
import re

def knowledge_agent(self, state: AgentState) -> AgentState:
        """Route to RAG or web search"""
        if "knowledge" not in state["intent_categories"]:
            return state
        
        try:
            llm = self.llm.get_cheap()
            
            routing_prompt = f"""Determine if this query needs:
1. RAG search - Technical docs, concepts, club knowledge
2. Web search - Latest news, recent developments
3. Both

Query: {state['user_query']}

Output JSON: {{"use_rag": bool, "use_web": bool}}"""
            
            response = llm.invoke(routing_prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse routing decision
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            route = {"use_rag": True, "use_web": False}  # Default
            
            if json_match:
                route = json.loads(json_match.group())
            
            results = {}
            
            # RAG search via MCP server
            if route.get("use_rag"):
                try:
                    rag_result = self.mcp.call_tool("research_rag", "retrieve", {
                        "query": state["user_query"],
                        "top_k": 5
                    })
                    results["rag"] = rag_result
                    logger.info("RAG retrieval completed")
                except Exception as e:
                    logger.error(f"RAG retrieval failed: {e}")
                    results["rag"] = {"error": str(e)}
            
            # Web search (if you have web search MCP server)
            if route.get("use_web"):
                # Implement web search if available
                pass
            
            state["knowledge_results"] = results
            
        except Exception as e:
            logger.error(f"Knowledge agent failed: {e}")
            state["errors"].append(f"Knowledge retrieval failed: {str(e)}")
        
        return state