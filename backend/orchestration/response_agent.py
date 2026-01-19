import logging
from typing import Dict, Any, List, Optional
from backend.orchestration.state import AgentState
import json
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from core.config import settings
from orchestration.state import AgentState  # Your state definition
logger = logging.getLogger(__name__)

def response_generation_node(self, state: AgentState) -> AgentState:
        """Synthesize all results into final response"""
        try:
            llm = self.llm.get_smart()
            
            # Gather all results
            context_parts = []
            
            if state.get("github_results"):
                context_parts.append(f"GitHub: {json.dumps(state['github_results'], indent=2)[:500]}")
            
            if state.get("knowledge_results"):
                context_parts.append(f"Knowledge: {json.dumps(state['knowledge_results'], indent=2)[:500]}")
            
            if state.get("collaboration_results"):
                context_parts.append(f"Collaboration: {json.dumps(state['collaboration_results'], indent=2)[:500]}")
            
            if state.get("errors"):
                context_parts.append(f"Errors: {', '.join(state['errors'][:3])}")
            
            context = "\n\n".join(context_parts)
            
            # Summarized history
            history_summary = self._summarize_history(state["conversation_history"])
            
            generation_prompt = f"""Generate a helpful response for the robotics club member.

User query: {state['user_query']}

Conversation context: {history_summary}

Available information:
{context}

Requirements:
- Be concise and technical when appropriate
- Cite sources when available
- If operations need approval, clearly state what needs confirmation
- If errors occurred, explain and suggest alternatives

Response:"""
            
            response = llm.invoke(generation_prompt)
            final_response = response.content if hasattr(response, 'content') else str(response)
            
            state["final_response"] = final_response
            logger.info("Response generated successfully")
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            state["final_response"] = "I encountered an error generating the response. Please try again."
            state["errors"].append(f"Response generation failed: {str(e)}")
        
        return state