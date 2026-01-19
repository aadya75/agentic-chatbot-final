"""
backend/orchestration/routing.py

Routing functions for LangGraph conditional edges.
These determine which path the graph should take based on state.
"""

import logging
from typing import Dict, Any, Literal

logger = logging.getLogger(__name__)


# ============================================================================
# ROUTING FUNCTION 1: Red Flag Check
# ============================================================================

def should_continue_to_agents(state: Dict[str, Any]) -> Literal["end", "agents"]:
    """
    Determine if query should continue to agents or end immediately.
    
    Called after red_flag node.
    
    Args:
        state: Current graph state
    
    Returns:
        "end" if red flag detected, "agents" to continue
    """
    if state.get("red_flag", False):
        logger.warning("🚨 Red flag detected - routing to END")
        return "end"
    
    logger.info("✅ No red flags - routing to agents")
    return "agents"


# ============================================================================
# ROUTING FUNCTION 2: Confidence Check / Retry Logic
# ============================================================================

def should_retry(state: Dict[str, Any]) -> Literal["retry", "end"]:
    """
    Determine if response should be retried or is good enough.
    
    Called after confidence_check node.
    
    Args:
        state: Current graph state with confidence_score and iteration_count
    
    Returns:
        "retry" to loop back to planning, "end" to finish
    """
    confidence = state.get("confidence_score", 0.0)
    iterations = state.get("iteration_count", 0)
    max_iterations = 2  # Maximum retries
    confidence_threshold = 0.6
    
    # Check if we've hit max iterations
    if iterations >= max_iterations:
        logger.info(f"⏹️  Max iterations ({max_iterations}) reached - routing to END")
        return "end"
    
    # Check confidence score
    if confidence < confidence_threshold:
        logger.warning(
            f"🔄 Low confidence ({confidence:.2f} < {confidence_threshold}) "
            f"- retrying (iteration {iterations + 1}/{max_iterations})"
        )
        return "retry"
    
    logger.info(f"✅ High confidence ({confidence:.2f}) - routing to END")
    return "end"


# ============================================================================
# ROUTING FUNCTION 3: Intent-Based Parallel Routing (Optional)
# ============================================================================

def route_to_parallel_agents(state: Dict[str, Any]) -> list[str]:
    """
    Determine which agents should be activated based on intents.
    
    This is used if you want dynamic parallel routing instead of
    always running all agents.
    
    Args:
        state: Current graph state with intent_categories
    
    Returns:
        List of agent node names to execute
    """
    intents = state.get("intent_categories", [])
    agents = []
    
    # Map intents to agent nodes
    if "gmail" in intents:
        agents.append("gmail_agent")
    
    if "calendar" in intents:
        agents.append("calendar_agent")
    
    if "drive" in intents:
        agents.append("drive_agent")
    
    if "rag" in intents or "knowledge" in intents:
        agents.append("rag_agent")
    
    # Fallback: if no specific intent, check all
    if not agents:
        logger.info("ℹ️  No specific intents - activating all agents")
        agents = ["gmail_agent", "calendar_agent", "drive_agent", "rag_agent"]
    else:
        logger.info(f"🎯 Routing to agents: {agents}")
    
    return agents


# ============================================================================
# ROUTING FUNCTION 4: Error Handling (Optional)
# ============================================================================

def check_for_fatal_errors(state: Dict[str, Any]) -> Literal["continue", "error_end"]:
    """
    Check if there are fatal errors that should stop the graph.
    
    Optional: Use this if you want to short-circuit on certain errors.
    
    Args:
        state: Current graph state
    
    Returns:
        "error_end" to stop immediately, "continue" to keep going
    """
    errors = state.get("errors", [])
    
    # Define what constitutes a "fatal" error
    fatal_keywords = ["authentication", "authorization", "critical", "fatal"]
    
    for error in errors:
        error_lower = error.lower()
        if any(keyword in error_lower for keyword in fatal_keywords):
            logger.error(f"❌ Fatal error detected: {error}")
            return "error_end"
    
    return "continue"


# ============================================================================
# ROUTING FUNCTION 5: Response Quality Gate (Optional)
# ============================================================================

def check_response_completeness(state: Dict[str, Any]) -> Literal["complete", "incomplete"]:
    """
    Check if response has sufficient information.
    
    Optional: Use this for more sophisticated quality control.
    
    Args:
        state: Current graph state
    
    Returns:
        "complete" if response is good, "incomplete" if needs more info
    """
    response = state.get("final_response", "")
    
    # Check minimum response length
    if len(response) < 50:
        logger.warning("⚠️  Response too short - marked as incomplete")
        return "incomplete"
    
    # Check if response acknowledges lack of information
    no_info_phrases = [
        "i don't have",
        "no information",
        "unable to find",
        "couldn't retrieve"
    ]
    
    response_lower = response.lower()
    if any(phrase in response_lower for phrase in no_info_phrases):
        # Check if any agents actually returned results
        has_results = any([
            state.get("gmail_results"),
            state.get("calendar_results"),
            state.get("drive_results"),
            state.get("rag_results")
        ])
        
        if not has_results:
            logger.warning("⚠️  No results from any agent - marked as incomplete")
            return "incomplete"
    
    logger.info("✅ Response is complete")
    return "complete"


# ============================================================================
# ROUTING FUNCTION 6: Tool-Based Routing (Advanced)
# ============================================================================

def route_by_available_tools(state: Dict[str, Any]) -> list[str]:
    """
    Route based on which tools are actually available/enabled.
    
    Advanced: Use this if you have dynamic tool availability.
    
    Args:
        state: Current graph state
    
    Returns:
        List of agent nodes that have their tools available
    """
    available_agents = []
    
    # Get enabled tools from metadata (you'd set this during initialization)
    enabled_tools = state.get("metadata", {}).get("enabled_tools", [])
    
    if "gmail" in enabled_tools or not enabled_tools:
        available_agents.append("gmail_agent")
    
    if "calendar" in enabled_tools or not enabled_tools:
        available_agents.append("calendar_agent")
    
    if "drive" in enabled_tools or not enabled_tools:
        available_agents.append("drive_agent")
    
    if "rag" in enabled_tools or not enabled_tools:
        available_agents.append("rag_agent")
    
    logger.info(f"📋 Available agents: {available_agents}")
    return available_agents


# ============================================================================
# ROUTING FUNCTION 7: Human-in-the-Loop (Advanced)
# ============================================================================

def check_approval_needed(state: Dict[str, Any]) -> Literal["needs_approval", "proceed"]:
    """
    Check if any operation needs human approval.
    
    Advanced: Use this for operations that modify data.
    
    Args:
        state: Current graph state
    
    Returns:
        "needs_approval" to pause for human input, "proceed" to continue
    """
    # Check if any results indicate a write operation
    approval_keywords = ["send", "delete", "create", "update", "schedule"]
    
    query_lower = state.get("user_query", "").lower()
    
    if any(keyword in query_lower for keyword in approval_keywords):
        logger.warning("⚠️  Query requires approval - routing to approval flow")
        return "needs_approval"
    
    logger.info("✅ No approval needed - proceeding")
    return "proceed"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def log_routing_decision(
    state: Dict[str, Any],
    node_name: str,
    decision: str,
    reason: str = ""
):
    """
    Helper to log routing decisions consistently.
    
    Args:
        state: Current graph state
        node_name: Name of the node making the routing decision
        decision: The routing decision made
        reason: Optional reason for the decision
    """
    iteration = state.get("iteration_count", 0)
    
    log_msg = f"🔀 [{node_name}] Routing decision: {decision}"
    if reason:
        log_msg += f" - Reason: {reason}"
    if iteration > 0:
        log_msg += f" (iteration {iteration})"
    
    logger.info(log_msg)


def get_state_summary(state: Dict[str, Any]) -> str:
    """
    Get a summary of current state for debugging.
    
    Args:
        state: Current graph state
    
    Returns:
        Human-readable state summary
    """
    summary = []
    
    summary.append(f"Query: {state.get('user_query', 'N/A')[:50]}...")
    summary.append(f"Intents: {state.get('intent_categories', [])}")
    summary.append(f"Red Flag: {state.get('red_flag', False)}")
    summary.append(f"Confidence: {state.get('confidence_score', 0.0):.2f}")
    summary.append(f"Iteration: {state.get('iteration_count', 0)}")
    summary.append(f"Errors: {len(state.get('errors', []))}")
    summary.append(f"Tools Used: {state.get('tools_used', [])}")
    
    return " | ".join(summary)


# ============================================================================
# EXAMPLE USAGE IN GRAPH
# ============================================================================

"""
Example of how to use these routing functions in your orchestrator.py:

from orchestration.routing import (
    should_continue_to_agents,
    should_retry,
    route_to_parallel_agents,
    check_approval_needed
)

# In your _create_graph() method:

# Conditional routing after red flag
workflow.add_conditional_edges(
    "red_flag",
    should_continue_to_agents,
    {
        "end": END,
        "agents": "planning"
    }
)

# Conditional routing after confidence check
workflow.add_conditional_edges(
    "confidence_check",
    should_retry,
    {
        "retry": "planning",  # Loop back to planning
        "end": END
    }
)

# Optional: Dynamic parallel routing based on intents
# (Instead of always running all agents)
workflow.add_conditional_edges(
    "planning",
    route_to_parallel_agents,
    {
        "gmail_agent": "gmail_agent",
        "calendar_agent": "calendar_agent",
        "drive_agent": "drive_agent",
        "rag_agent": "rag_agent"
    }
)

# Optional: Human approval check
workflow.add_conditional_edges(
    "planning",
    check_approval_needed,
    {
        "needs_approval": "approval_node",
        "proceed": "gmail_agent"
    }
)
"""


# ============================================================================
# ROUTING CONFIGURATION (Optional)
# ============================================================================

class RoutingConfig:
    """
    Configuration for routing behavior.
    Allows easy tuning without changing code.
    """
    
    # Confidence threshold for retry
    CONFIDENCE_THRESHOLD = 0.6
    
    # Maximum iterations before giving up
    MAX_ITERATIONS = 2
    
    # Minimum response length
    MIN_RESPONSE_LENGTH = 50
    
    # Enable/disable specific routing features
    ENABLE_DYNAMIC_ROUTING = False  # Route only to needed agents
    ENABLE_APPROVAL_CHECKS = False  # Check for operations needing approval
    ENABLE_ERROR_GATING = False     # Stop on fatal errors
    
    @classmethod
    def should_retry_with_config(cls, state: Dict[str, Any]) -> Literal["retry", "end"]:
        """Retry check using config values"""
        confidence = state.get("confidence_score", 0.0)
        iterations = state.get("iteration_count", 0)
        
        if iterations >= cls.MAX_ITERATIONS:
            return "end"
        
        if confidence < cls.CONFIDENCE_THRESHOLD:
            return "retry"
        
        return "end"


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Primary routing functions (required)
    "should_continue_to_agents",
    "should_retry",
    
    # Optional routing functions
    "route_to_parallel_agents",
    "check_for_fatal_errors",
    "check_response_completeness",
    "route_by_available_tools",
    "check_approval_needed",
    
    # Helper functions
    "log_routing_decision",
    "get_state_summary",
    
    # Configuration
    "RoutingConfig"
]