"""
backend/orchestration/orchestrator.py - BEST FIX

Solution: Create sync wrapper methods that LangGraph can call directly.
LangGraph handles async internally, so nodes should be sync functions.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional

from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END

from core.config import settings

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Main orchestrator using LangGraph"""
    
    def __init__(self, agent_manager):
        self.agent_manager = agent_manager
        
        # Initialize LLMs
        self.cheap_llm = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=1000,
            api_key=settings.groq_api_key
        )
        
        self.smart_llm = ChatGroq(
            model_name=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.groq_api_key
        )
        
        # Build graph
        self.graph = self._create_graph()
        logger.info("✅ Orchestrator initialized")
    
    # ========================================================================
    # SYNC WRAPPER METHODS - These call async nodes properly
    # ========================================================================
    
    def _gmail_agent_wrapper(self, state: Dict) -> Dict:
        """Sync wrapper for async gmail_agent_node"""
        from orchestration.nodes import gmail_agent_node
        
        # Get current event loop or create new one
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use run_until_complete won't work
                # Create a new task instead
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        gmail_agent_node(state, self.agent_manager, self.cheap_llm)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    gmail_agent_node(state, self.agent_manager, self.cheap_llm)
                )
        except RuntimeError:
            # No event loop, create new one
            return asyncio.run(
                gmail_agent_node(state, self.agent_manager, self.cheap_llm)
            )
    
    def _calendar_agent_wrapper(self, state: Dict) -> Dict:
        """Sync wrapper for async calendar_agent_node"""
        from orchestration.nodes import calendar_agent_node
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        calendar_agent_node(state, self.agent_manager, self.cheap_llm)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    calendar_agent_node(state, self.agent_manager, self.cheap_llm)
                )
        except RuntimeError:
            return asyncio.run(
                calendar_agent_node(state, self.agent_manager, self.cheap_llm)
            )
    
    def _drive_agent_wrapper(self, state: Dict) -> Dict:
        """Sync wrapper for async drive_agent_node"""
        from orchestration.nodes import drive_agent_node
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        drive_agent_node(state, self.agent_manager, self.cheap_llm)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    drive_agent_node(state, self.agent_manager, self.cheap_llm)
                )
        except RuntimeError:
            return asyncio.run(
                drive_agent_node(state, self.agent_manager, self.cheap_llm)
            )
    
    def _rag_agent_wrapper(self, state: Dict) -> Dict:
        """Sync wrapper for async rag_agent_node"""
        from orchestration.nodes import rag_agent_node
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        rag_agent_node(state, self.agent_manager, self.cheap_llm)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    rag_agent_node(state, self.agent_manager, self.cheap_llm)
                )
        except RuntimeError:
            return asyncio.run(
                rag_agent_node(state, self.agent_manager, self.cheap_llm)
            )
    
    # ========================================================================
    # GRAPH CREATION
    # ========================================================================
    
    def _create_graph(self):
        """Create LangGraph workflow"""
        from orchestration.nodes import (
            red_flag_node,
            planning_node,
            response_generation_node,
            confidence_check_node
        )
        from orchestration.routing import should_continue_to_agents, should_retry
        from orchestration.state import AgentState
        
        workflow = StateGraph(AgentState)
        
        # Add sync nodes directly
        workflow.add_node("red_flag", 
            lambda state: red_flag_node(state, self.cheap_llm))
        
        workflow.add_node("planning", 
            lambda state: planning_node(state, self.cheap_llm))
        
        # Add async nodes via sync wrappers
        workflow.add_node("gmail_agent", self._gmail_agent_wrapper)
        workflow.add_node("calendar_agent", self._calendar_agent_wrapper)
        workflow.add_node("drive_agent", self._drive_agent_wrapper)
        workflow.add_node("rag_agent", self._rag_agent_wrapper)
        
        # Add sync nodes
        workflow.add_node("response_generation", 
            lambda state: response_generation_node(state, self.smart_llm))
        
        workflow.add_node("confidence_check", 
            lambda state: confidence_check_node(state, self.cheap_llm))
        
        # Set entry point
        workflow.set_entry_point("red_flag")
        
        # Conditional edges
        workflow.add_conditional_edges(
            "red_flag",
            should_continue_to_agents,
            {
                "end": END,
                "agents": "planning"
            }
        )
        
        # Planning to parallel agents
        workflow.add_edge("planning", "gmail_agent")
        workflow.add_edge("planning", "calendar_agent")
        workflow.add_edge("planning", "drive_agent")
        workflow.add_edge("planning", "rag_agent")
        
        # All agents to response
        workflow.add_edge("gmail_agent", "response_generation")
        workflow.add_edge("calendar_agent", "response_generation")
        workflow.add_edge("drive_agent", "response_generation")
        workflow.add_edge("rag_agent", "response_generation")
        
        workflow.add_edge("response_generation", "confidence_check")
        
        # Confidence check
        workflow.add_conditional_edges(
            "confidence_check",
            should_retry,
            {
                "retry": "planning",
                "end": END
            }
        )
        
        return workflow.compile()
    
    async def process_message(
        self,
        user_query: str,
        thread_id: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Process message through orchestration graph"""
        
        # Initialize state
        initial_state = {
            "user_query": user_query,
            "conversation_history": conversation_history or [],
            "thread_id": thread_id,
            "red_flag": False,
            "intent_categories": [],
            "gmail_results": None,
            "calendar_results": None,
            "drive_results": None,
            "rag_results": None,
            "final_response": "",
            "confidence_score": 0.0,
            "iteration_count": 0,
            "errors": [],
            "tools_used": []
        }
        
        try:
            logger.info(f"🎯 Processing through orchestration graph")
            final_state = await self.graph.ainvoke(initial_state)
            
            return {
                "response": final_state["final_response"],
                "confidence": final_state["confidence_score"],
                "tools_used": final_state.get("tools_used", []),
                "errors": final_state.get("errors", []),
                "metadata": {
                    "intents": final_state.get("intent_categories", []),
                    "iteration_count": final_state["iteration_count"],
                    "red_flag": final_state.get("red_flag", False)
                }
            }
        
        except Exception as e:
            logger.error(f"❌ Orchestration failed: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "response": "I encountered an error processing your request. Please try again.",
                "confidence": 0.0,
                "tools_used": [],
                "errors": [str(e)],
                "metadata": {}
            }


def create_orchestrator(agent_manager):
    """Factory function"""
    return AgentOrchestrator(agent_manager)