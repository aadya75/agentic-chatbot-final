import logging
from typing import Dict, Any, List, Optional
from backend.orchestration.state import AgentState
import json
import re
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph
from core.config import settings
from orchestration.state import AgentState  # Your state definition
logger = logging.getLogger(__name__)

def planning_node(self, state: AgentState) -> AgentState:
        """Classify intent and route to appropriate agents"""
        try:
            llm = self.llm.get_cheap()
            
            classification_prompt = f"""Classify the user's intent. Multiple intents can apply.

Available categories:
1. "github" - Repository search, code examples
2. "knowledge" - Technical/conceptual questions (use RAG or web search)
3. "collaboration" - Email, scheduling, calendar
4. "general" - Greetings, general info

Query: {state['user_query']}
Context: {state['global_memory'][:150]}

Output JSON array: ["category1", "category2"]"""
            
            response = llm.invoke(classification_prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON
            try:
                # Extract JSON from response
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    intents = json.loads(json_match.group())
                else:
                    intents = ["knowledge"]  # Default
            except:
                intents = ["knowledge"]
            
            state["intent_categories"] = intents
            logger.info(f"Intents classified: {intents}")
            
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            state["intent_categories"] = ["knowledge"]
            state["errors"].append(f"Intent classification failed: {str(e)}")
        
        return state