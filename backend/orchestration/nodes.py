"""
backend/orchestration/nodes.py

Fixed nodes that RETURN state updates instead of mutating state directly.
"""

import re
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


# ============================================================================
# NODE 1: RED FLAG DETECTION
# ============================================================================

def red_flag_node(state: Dict, llm) -> Dict:
    """Detect unethical/destructive queries"""
    query = state["user_query"].lower()
    
    # Regex patterns
    destructive_patterns = [
        r'\bdelete\s+(all|everything|files?|emails?)\b',
        r'\bremove\s+(all|everything)\b',
        r'\bdestroy\b',
    ]
    
    # Quick check
    for pattern in destructive_patterns:
        if re.search(pattern, query):
            logger.warning(f"🚨 Red flag detected: {query[:50]}")
            # RETURN updates, don't mutate state
            return {
                "red_flag": True,
                "final_response": """I cannot assist with destructive operations. 

I'm here to help with:
• Answering technical questions
• Searching emails and documents
• Managing calendar events
• Retrieving knowledge from our database

How can I help you with these tasks?"""
            }
    
    # RETURN updates
    return {"red_flag": False}


# ============================================================================
# NODE 2: PLANNING (INTENT CLASSIFICATION)
# ============================================================================

def planning_node(state: Dict, llm) -> Dict:
    """Classify user intent"""
    try:
        prompt = f"""Classify the user's intent. Multiple intents can apply.

Available categories:
1. "gmail" - Email operations (search, read, send)
2. "calendar" - Calendar operations (events, scheduling)
3. "drive" - Google Drive operations (files, documents)
4. "rag" - Knowledge retrieval (technical questions, concepts)
5. "general" - Greetings, simple questions

Query: {state['user_query']}

Output JSON array: ["category1", "category2"]"""
        
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)
        
        # Parse JSON
        json_match = re.search(r'\[.*?\]', content, re.DOTALL)
        if json_match:
            intents = json.loads(json_match.group())
        else:
            intents = ["general"]
        
        logger.info(f"🎯 Intents: {intents}")
        
        # RETURN updates
        return {"intent_categories": intents}
        
    except Exception as e:
        logger.error(f"Planning failed: {e}")
        # RETURN updates including error
        return {
            "intent_categories": ["general"],
            "errors": [f"Intent classification failed: {str(e)}"]
        }


# ============================================================================
# AGENT NODES (USE MCP TOOLS)
# ============================================================================

async def gmail_agent_node(state: Dict, agent_manager, llm) -> Dict:
    """Handle Gmail operations"""
    if "gmail" not in state.get("intent_categories", []):
        return {}  # Return empty dict if not applicable
    
    try:
        query = state["user_query"]
        
        # Determine operation
        if "latest" in query.lower() or "recent" in query.lower():
            result = await agent_manager.get_latest_gmail_messages(count=5)
        elif "search" in query.lower():
            # Extract search term (simple)
            search_term = query.split("search")[-1].strip()
            result = await agent_manager.search_gmail(search_term, max_results=5)
        else:
            # Default: get latest
            result = await agent_manager.get_latest_gmail_messages(count=5)
        
        logger.info("✅ Gmail agent completed")
        
        # RETURN updates
        return {
            "gmail_results": result,
            "tools_used": ["gmail"]  # Return as list for Annotated reducer
        }
        
    except Exception as e:
        logger.error(f"Gmail agent failed: {e}")
        return {
            "errors": [f"Gmail: {str(e)}"]
        }


async def calendar_agent_node(state: Dict, agent_manager, llm) -> Dict:
    """Handle Calendar operations"""
    if "calendar" not in state.get("intent_categories", []):
        return {}
    
    try:
        # Fixed: removed 'days' parameter if not supported
        result = await agent_manager.get_upcoming_events()
        
        logger.info("✅ Calendar agent completed")
        
        # RETURN updates
        return {
            "calendar_results": result,
            "tools_used": ["calendar"]
        }
        
    except Exception as e:
        logger.error(f"Calendar agent failed: {e}")
        return {
            "errors": [f"Calendar: {str(e)}"]
        }


async def drive_agent_node(state: Dict, agent_manager, llm) -> Dict:
    """Handle Drive operations"""
    if "drive" not in state.get("intent_categories", []):
        return {}
    
    try:
        result = await agent_manager.list_drive_files(max_results=10)
        
        logger.info("✅ Drive agent completed")
        
        # RETURN updates
        return {
            "drive_results": result,
            "tools_used": ["drive"]
        }
        
    except Exception as e:
        logger.error(f"Drive agent failed: {e}")
        return {
            "errors": [f"Drive: {str(e)}"]
        }


async def rag_agent_node(state: Dict, agent_manager, llm) -> Dict:
    """Handle RAG/knowledge retrieval"""
    if "rag" not in state.get("intent_categories", []):
        return {}
    
    try:
        result = await agent_manager.rag_retrieve(
            query=state["user_query"],
            top_k=5
        )
        
        logger.info("✅ RAG agent completed")
        
        # RETURN updates
        return {
            "rag_results": result,
            "tools_used": ["rag"]
        }
        
    except Exception as e:
        logger.error(f"RAG agent failed: {e}")
        return {
            "errors": [f"RAG: {str(e)}"]
        }


# ============================================================================
# NODE: RESPONSE GENERATION
# ============================================================================

def response_generation_node(state: Dict, llm) -> Dict:
    """Synthesize all results into final response"""
    try:
        # Gather results
        context_parts = []
        
        if state.get("gmail_results"):
            context_parts.append(f"Gmail: {json.dumps(state['gmail_results'], indent=2)[:500]}")
        
        if state.get("calendar_results"):
            context_parts.append(f"Calendar: {json.dumps(state['calendar_results'], indent=2)[:500]}")
        
        if state.get("drive_results"):
            context_parts.append(f"Drive: {json.dumps(state['drive_results'], indent=2)[:500]}")
        
        if state.get("rag_results"):
            context_parts.append(f"Knowledge: {json.dumps(state['rag_results'], indent=2)[:500]}")
        
        if state.get("errors"):
            context_parts.append(f"Errors: {', '.join(state['errors'][:3])}")
        
        context = "\n\n".join(context_parts)
        
        # Generate response
        prompt = f"""Generate a helpful response for the user.

User query: {state['user_query']}

Available information:
{context}

Requirements:
- Be concise and helpful
- Cite sources when available
- If errors occurred, explain what went wrong
- If no information available, say so politely

Response:"""
        
        response = llm.invoke(prompt)
        final_response = response.content if hasattr(response, 'content') else str(response)
        
        logger.info("✅ Response generated")
        
        # RETURN updates
        return {"final_response": final_response}
        
    except Exception as e:
        logger.error(f"Response generation failed: {e}")
        return {
            "final_response": "I encountered an error generating the response.",
            "errors": [f"Response generation: {str(e)}"]
        }


# ============================================================================
# NODE: CONFIDENCE CHECK
# ============================================================================

def confidence_check_node(state: Dict, llm) -> Dict:
    """Check response quality"""
    if state.get("iteration_count", 0) >= 2:
        return {"confidence_score": 0.5}
    
    try:
        prompt = f"""Evaluate this response quality on a scale of 0.0 to 1.0.

Query: {state['user_query']}
Response: {state.get('final_response', '')[:300]}

Is the response:
1. Complete (addresses query)?
2. Accurate (based on data)?
3. Helpful (actionable)?

Output JSON: {{"score": 0.0-1.0, "retry_needed": bool}}"""
        
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)
        
        json_match = re.search(r'\{.*?\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            confidence_score = result.get("score", 0.9)
            
            updates = {"confidence_score": confidence_score}
            
            if result.get("retry_needed") and state.get("iteration_count", 0) < 2:
                updates["iteration_count"] = state.get("iteration_count", 0) + 1
                logger.info(f"🔄 Retrying (iteration {updates['iteration_count']})")
            
            # RETURN updates
            return updates
        else:
            return {"confidence_score": 0.9}
        
    except Exception as e:
        logger.error(f"Confidence check failed: {e}")
        return {"confidence_score": 0.5}

