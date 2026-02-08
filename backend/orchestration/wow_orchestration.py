# """
# smart_orchestrator.py
# Orchestrator with Wikipedia web search (temp) as context provider and Google Workspace integration
# """
# from __future__ import annotations

# from typing import TypedDict, List, Optional, Literal, Annotated, Union, Callable
# from langgraph.graph import StateGraph, START, END
# from langgraph.types import Send
# from pydantic import BaseModel, Field
# import operator
# import asyncio
# import json

# from langchain_groq import ChatGroq
# from langchain_core.messages import SystemMessage, HumanMessage
# from langchain_community.tools import WikipediaQueryRun
# from langchain_community.utilities import WikipediaAPIWrapper
# from langchain.agents import create_agent
# from langchain.tools import tool
# import os
# from dotenv import load_dotenv
# from pathlib import Path
# from knowledge_engine.club.retrieval import club_retriever

# load_dotenv()

# servers_dir = Path(__file__).resolve().parent.parent / 'mcp_servers'

# # ============================================================================
# # 1. MODELS WITH CONTEXT SUPPORT
# # ============================================================================
# class ContextItem(BaseModel):
#     """Context gathered from various sources"""
#     source: Literal["web_search", "rag", "conversation", "club_search"]
#     content: str
#     relevance_score: float = Field(ge=0, le=1)
#     metadata: dict = Field(default_factory=dict)


# class WorkerTask(BaseModel):
#     """Task for a specific worker"""
#     id: int
#     title: str
#     worker_type: Literal["github", "conversational", "calendar", "gmail", "drive", "docs", "sheets", "slides", "forms", "tasks", "chat", "search", "all_google", "rag_search", "club_search"] = "conversational"
#     description: str
#     parameters: dict = Field(default_factory=dict)
#     requires_context: bool = False  # Does this task need context?
#     context_type: Optional[Literal["web", "rag", "club"]] = None  # What type of context is needed
#     google_service: Optional[str] = None  # Specific Google service if needed


# class ExecutionPlan(BaseModel):
#     """Intelligent execution plan"""
#     needs_context: bool = False
#     context_type: Optional[Literal["web", "rag", "club", "mixed"]] = None
#     reasoning: str
#     tasks: List[WorkerTask] = Field(default_factory=list)
#     search_queries: List[str] = Field(default_factory=list)  # Queries for search
#     rag_queries: List[str] = Field(default_factory=list)  # Queries for RAG
#     club_queries: List[str] = Field(default_factory=list)  # Queries for Club search


# class TaskResult(BaseModel):
#     """Result from task execution"""
#     task_id: int
#     worker_type: str
#     success: bool
#     output: str
#     used_context: bool = False
#     error: Optional[str] = None


# # ============================================================================
# # 2. STATE WITH CONTEXT
# # ============================================================================
# class OrchestratorState(TypedDict):
#     """Enhanced state with context support"""
#     # Input
#     user_query: str
#     conversation_history: List[str]
    
#     # Planning
#     plan: Optional[ExecutionPlan]
    
#     # Context
#     web_context: List[ContextItem]
#     rag_context: List[ContextItem]
#     club_context: List[ContextItem]
#     combined_context: str
    
#     # Execution
#     tasks: List[WorkerTask]
#     results: Annotated[List[TaskResult], operator.add]
    
#     # Output
#     final_response: str


# # ============================================================================
# # 3. LLM & TOOLS INITIALIZATION
# # ============================================================================
# llm = ChatGroq(
#     model="llama-3.3-70b-versatile",
#     temperature=0.1,
#     api_key=os.getenv("GROQ_API_KEY")
# )

# # Initialize Wikipedia search tool (your existing code)
# search_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
# web_search_agent = create_agent(llm, tools=[search_tool])

# print("✅ LLM and Wikipedia search initialized")


# # ============================================================================
# # 4. INTELLIGENT PLANNING AGENT - Decides what context is needed
# # ============================================================================
# PLANNING_SYSTEM = """You are an intelligent planning agent that decides:
# 1. Does this query need context from web search, RAG, or club search?
# 2. Which workers are needed to execute the actual tasks?

# CONTEXT TYPES:
# - WEB SEARCH: For factual questions, explanations, definitions, historical information, concepts, theories
# - RAG SEARCH: documents provided by user, to provide more grouded response for vague ques
# - CLUB SEARCH: For robotics club information, club events, event details , coordinators contact, event timelines, announcements, rbotics club specific information

# WEB SEARCH is needed for:
# - Factual questions, explanations, definitions
# - Historical information, concepts, theories
# - Technical documentation, how-tos
# - General knowledge queries
# - "What is...", "Explain...", "How does...", "Tell me about..."

# RAG SEARCH is needed for:
# - Grounded response for user queries based on user-provided documents
# - "Search my documents for...", "What do my files say about...", "Find information in my docs about..."

# CLUB SEARCH is needed for:
# - Club events : timeline, about, coordinators, description
# - Club Announcements
# - Club coordinators and contact info

# NO CONTEXT needed for:
# - GitHub operations (create repo, PRs, files)
# - Google Workspace operations (Gmail, Calendar)
# - Simple greetings, casual conversation
# - Already known operational commands

# WORKERS:
# - GitHub Worker: For repository/file/PR operations (7 tools)
# - Google Workspace Worker: For Google services (Gmail, Calendar, Drive, Docs, Sheets, etc.)
# - Conversational Worker: For chat/questions


# GOOGLE WORKSPACE SERVICES:
# - gmail: Send/search emails, manage labels, attachments
# - calendar: Create/update events, list calendars

# RULES:
# 1. First decide if any context is needed (web, rag, club, or mixed)
# 2. Extract appropriate queries for each context type
# 3. Identify which Google service(s) are needed from the query
# 4. Create tasks for workers with appropriate parameters
# 5. Mark tasks that need context with needs_context=True and context_type

# Examples:
# - "What is API and create a GitHub repo" → Needs web search for "API"
# - "Create a file and say hello" → No context needed
# - "Send an email about the meeting tomorrow" → worker_type: gmail
# - "Based on docs provided, tell what are transformers" → Needs RAG search
# - "What are upcoming robotics club events?" → Needs club search
# - "Search the web for latest AI trends " → Needs web + RAG
# """


# def planning_agent_node(state: OrchestratorState) -> dict:
#     """Planning agent that decides what context is needed"""
#     print("\n" + "="*60)
#     print("🤖 SMART PLANNING AGENT: Analyzing query...")
#     print("="*60)
    
#     planner = llm.with_structured_output(ExecutionPlan)
    
#     plan = planner.invoke([
#         SystemMessage(content=PLANNING_SYSTEM),
#         HumanMessage(content=f"""
#         User Query: {state['user_query']}
        
#         Analyze what type of context is needed (web, rag, club, or none).
#         If context is needed, set needs_context=True and extract appropriate queries.
#         Identify which Google Workspace services are needed (if any).
#         Then create appropriate tasks for workers.
#         """)
#     ])
    
#     print(f"✅ Analysis:")
#     print(f"   Context Needed: {plan.needs_context}")
#     if plan.context_type:
#         print(f"   Context Type: {plan.context_type}")
#     print(f"   Reasoning: {plan.reasoning}")
    
#     if plan.search_queries:
#         print(f"   Web Search Queries: {plan.search_queries}")
#     if plan.rag_queries:
#         print(f"   RAG Queries: {plan.rag_queries}")
#     if plan.club_queries:
#         print(f"   Club Queries: {plan.club_queries}")
    
#     print(f"\n📋 Tasks ({len(plan.tasks)}):")
#     for task in plan.tasks:
#         context_marker = ""
#         if task.requires_context:
#             if task.context_type == "web":
#                 context_marker = "🌐"
#             elif task.context_type == "rag":
#                 context_marker = "📚"
#             elif task.context_type == "club":
#                 context_marker = "👥"
#             else:
#                 context_marker = "📚"
#         google_marker = f" [{task.google_service}]" if hasattr(task, 'google_service') and task.google_service else ""
#         print(f"  • {context_marker} Task: {task.title} → {task.worker_type}{google_marker}")
    
#     return {"plan": plan, "tasks": plan.tasks}


# def route_after_planning(state: OrchestratorState) -> str:
#     """Route based on context needs"""
#     plan = state.get("plan")
    
#     if not plan:
#         return "execute_tasks"
    
#     # Determine which context provider to use
#     if not plan.needs_context:
#         return "execute_tasks"
    
#     # Check context type and route accordingly
#     if plan.context_type == "web":
#         return "web_search"
#     elif plan.context_type == "rag":
#         return "rag_search"
#     elif plan.context_type == "club":
#         return "club_search"
#     elif plan.context_type == "mixed":
#         # For mixed context, we need to gather all types
#         # Let's start with web search as default
#         return "web_search"
    
#     # Default to execute tasks
#     return "execute_tasks"


# # ============================================================================
# # 5. CONTEXT PROVIDERS
# # ============================================================================

# # 5.1 Web Search Context Provider (existing)
# class WebSearchProvider:
#     """Gathers context from Wikipedia using your existing agent"""
    
#     def search(self, query: str) -> List[ContextItem]:
#         """Perform Wikipedia search using your existing agent"""
#         print(f"\n🌐 WEB SEARCH: Searching for '{query}'")
        
#         try:
#             # Use your existing web search agent
#             result = web_search_agent.invoke(
#                 {"messages": [{"role": "user", "content": query}]}
#             )
            
#             # Extract the AI message content
#             if "messages" in result:
#                 # Find the AI message in the response
#                 for msg in result["messages"]:
#                     if hasattr(msg, 'content'):
#                         content = msg.content
#                         break
#                 else:
#                     content = str(result)
#             else:
#                 content = str(result)
            
#             print(f"   ✅ Search completed")
            
#             # Create context item
#             return [ContextItem(
#                 source="web_search",
#                 content=content[:1000],  # Limit size
#                 relevance_score=0.9,
#                 metadata={
#                     "query": query,
#                     "source": "wikipedia",
#                     "agent_used": "WikipediaQueryRun"
#                 }
#             )]
            
#         except Exception as e:
#             print(f"   ❌ Web search error: {e}")
#             # Return minimal context
#             return [ContextItem(
#                 source="web_search",
#                 content=f"Wikipedia search failed for: {query}. Error: {str(e)[:100]}",
#                 relevance_score=0.1,
#                 metadata={"error": str(e), "query": query}
#             )]


# def web_search_node(state: OrchestratorState) -> dict:
#     """Gather web context before task execution"""
#     plan = state["plan"]
    
#     print("\n" + "="*60)
#     print("🌐 GATHERING WEB CONTEXT FROM WIKIPEDIA")
#     print("="*60)
    
#     provider = WebSearchProvider()
#     all_context = []
    
#     # Search for each query (limit to 2 queries)
#     for query in plan.search_queries[:2]:
#         context_items = provider.search(query)
#         all_context.extend(context_items)
#         print(f"   Search query: '{query}' → {len(context_items[0].content) if context_items else 0} chars")
    
#     # Combine context
#     combined = "\n\n".join([
#         f"[Web Search: '{item.metadata.get('query', 'unknown')}']\n{item.content}"
#         for item in sorted(all_context, key=lambda x: x.relevance_score, reverse=True)
#     ])
    
#     print(f"   Total web context gathered: {len(combined)} characters")
    
#     return {
#         "web_context": all_context,
#         "combined_context": combined
#     }


# # 5.2 RAG Search Context Provider
# class RagSearchProvider:
#     """Gathers context from RAG MCP server"""
    
#     async def search(self, query: str) -> List[ContextItem]:
#         """Perform RAG search using MCP server"""
#         print(f"\n📚 RAG SEARCH: Searching for '{query}'")
        
#         try:
#             # Import MCP client
#             from langchain_mcp_adapters.client import MultiServerMCPClient
#             from langchain.agents import create_agent
            
#             # Get RAG MCP server URL from environment
            
#             # Create MCP client for RAG server
#             client = MultiServerMCPClient({
#                 "rag_server": {
#                     "command": "python",
#                     "args": [str(servers_dir / "rag_server.py")],
#                     "transport": "stdio",
#                 }      
#             })
            
#             # Get tools from RAG MCP server
#             all_tools = await client.get_tools()
            
#             # Find the rag_retrieve tool
#             rag_tool = None
#             for tool_obj in all_tools:
#                 if tool_obj.name == "rag_retrieve":
#                     rag_tool = tool_obj
#                     break
            
#             if not rag_tool:
#                 print(f"   ❌ RAG tool not found on server")
#                 return [ContextItem(
#                     source="rag",
#                     content=f"RAG search tool not available",
#                     relevance_score=0.1,
#                     metadata={"error": "Tool not found", "query": query}
#                 )]
            
#             # Create agent with RAG tool
#             agent = create_agent(llm, [rag_tool])
            
#             # Execute search
#             response = await agent.ainvoke({
#                 "messages": [{"role": "user", "content": f"Search for: {query}"}]
#             })
            
#             # Extract output
#             output = ""
#             if "messages" in response:
#                 for msg in reversed(response["messages"]):
#                     if hasattr(msg, 'content'):
#                         output = msg.content
#                         break
            
#             if not output:
#                 output = str(response)
            
#             print(f"   ✅ RAG search completed")
            
#             # Create context item
#             return [ContextItem(
#                 source="rag",
#                 content=output[:1500],  # RAG content might be longer
#                 relevance_score=0.85,
#                 metadata={
#                     "query": query,
#                     "source": "rag_mcp",
#                 }
#             )]
            
#         except Exception as e:
#             error_msg = str(e)
#             print(f"   ❌ RAG search error: {error_msg[:100]}")
            
#             # Check if server is not running
#             if "connection" in error_msg.lower() or "refused" in error_msg.lower():
#                 help_text = "\n   RAG MCP server is not running. Start it with: rag-mcp-server"
#             else:
#                 help_text = ""
            
#             return [ContextItem(
#                 source="rag",
#                 content=f"RAG search failed for: {query}. Error: {error_msg[:200]}{help_text}",
#                 relevance_score=0.1,
#                 metadata={"error": error_msg, "query": query}
#             )]


# async def rag_search_async(plan: ExecutionPlan) -> List[ContextItem]:
#     """Async wrapper for RAG search"""
#     provider = RagSearchProvider()
#     all_context = []
    
#     # Search for each RAG query (limit to 2 queries)
#     for query in plan.rag_queries[:2]:
#         context_items = await provider.search(query)
#         all_context.extend(context_items)
    
#     return all_context


# def rag_search_node(state: OrchestratorState) -> dict:
#     """Gather RAG context before task execution"""
#     plan = state["plan"]
    
#     print("\n" + "="*60)
#     print("📚 GATHERING RAG CONTEXT")
#     print("="*60)
    
#     # Run async RAG search
#     all_context = asyncio.run(rag_search_async(plan))
    
#     # Combine context
#     combined = "\n\n".join([
#         f"[RAG Search: '{item.metadata.get('query', 'unknown')}']\n{item.content}"
#         for item in sorted(all_context, key=lambda x: x.relevance_score, reverse=True)
#     ])
    
#     print(f"   Total RAG context gathered: {len(combined)} characters")
    
#     return {
#         "rag_context": all_context,
#         "combined_context": combined
#     }




# class ClubSearchProvider:
#     """Gathers context from club search tool"""
    
#     def search(self, query: str) -> List[ContextItem]:
#         """Perform club search using the tool"""
#         print(f"\n👥 CLUB SEARCH: Searching for '{query}'")
        
#         try:
#             # Extract category using string prompt
#             category_prompt = f"""
#             Define the category from the following query for club search.
#             The category should be one of these: events, announcements, coordinators.
#             If not relevant to any category return 'none'.
            
#             Query: {query}
            
#             Category: """
            
#             # Get category from LLM
#             category_response = llm.invoke(category_prompt)
#             category = category_response.content.strip().lower()
            
#             # Validate category
#             valid_categories = ["events", "announcements", "coordinators", "none"]
#             if category not in valid_categories:
#                 category = "none"
            
#             print(f"   Response from category LLM: {category}")
            
#             # If category is "none", set to None for the search
#             search_category = None if category == "none" else category
            
#             # Use the club search tool - it returns a LIST of results
#             results = club_retriever.retrieve(
#                 query=query,
#                 category=search_category,  
#                 top_k=3
#             )
            
#             print(f"   ✅ Club search completed - found {len(results)} results")
            
#             # Handle the list of results
#             if not results:
#                 return [ContextItem(
#                     source="club_search",
#                     content="No club information found for this query.",
#                     relevance_score=0.0,
#                     metadata={
#                         "query": query,
#                         "source": "club_database",
#                         "tool_used": "club_search_tool",
#                         "category": category,
#                         "results_count": 0
#                     }
#                 )]
            
#             # Combine all results into one context item
#             combined_content = ""
#             total_score = 0.0
            
#             for i, result in enumerate(results):
#                 # Extract content and score based on your result structure
#                 # Adjust these based on your actual result format
#                 content = result.get('content', result.get('text', str(result)))
#                 score = result.get('score', result.get('relevance', 0.5))
                
#                 combined_content += f"Result {i+1} (Score: {score:.2f}):\n{content}\n\n"
#                 total_score += score
            
#             avg_score = total_score / len(results) if results else 0.5
            
#             return [ContextItem(
#                 source="club_search",
#                 content=combined_content.strip(),
#                 relevance_score=avg_score,
#                 metadata={
#                     "query": query,
#                     "source": "club_database",
#                     "tool_used": "club_search_tool",
#                     "category": category,
#                     "results_count": len(results)
#                 }
#             )]
            
#         except Exception as e:
#             error_msg = str(e)
#             print(f"   ❌ Club search error: {error_msg}")
            
#             return [ContextItem(
#                 source="club_search",
#                 content=f"Club search failed for: {query}. Error: {error_msg[:100]}",
#                 relevance_score=0.1,
#                 metadata={
#                     "error": error_msg, 
#                     "query": query,
#                     "results_count": 0
#                 }
#             )]


# def club_search_node(state: OrchestratorState) -> dict:
#     """Gather club context before task execution"""
#     plan = state["plan"]
    
#     print("\n" + "="*60)
#     print("👥 GATHERING CLUB CONTEXT")
#     print("="*60)
    
#     provider = ClubSearchProvider()
#     all_context = []
    
#     # Search for each club query (limit to 2 queries)
#     for query in plan.club_queries[:2]:
#         context_items = provider.search(query)
#         all_context.extend(context_items)
#         print(f"   Search query: '{query}' → {len(context_items[0].content) if context_items else 0} chars")
    
#     # Combine context
#     combined = "\n\n".join([
#         f"[Club Search: '{item.metadata.get('query', 'unknown')}']\n{item.content}"
#         for item in sorted(all_context, key=lambda x: x.relevance_score, reverse=True)
#     ])
    
#     print(f"   Total club context gathered: {len(combined)} characters")
    
#     return {
#         "club_context": all_context,
#         "combined_context": combined
#     }


# # ============================================================================
# # 6. GITHUB WORKER (existing - unchanged)
# # ============================================================================
# GITHUB_TOOLS = [
#     "create_repository",
#     "get_file_contents", 
#     "create_or_update_file",
#     "create_pull_request",
#     "list_pull_requests",
#     "update_pull_request",
#     "search_repositories",
#     "get_me"
# ]


# class GitHubWorker:
#     """Worker for GitHub operations with only 7 essential tools"""
    
#     async def execute(self, task: dict, context: str = "") -> TaskResult:
#         """Execute a GitHub task, optionally with context"""
#         from langchain_mcp_adapters.client import MultiServerMCPClient
#         from langchain.agents import create_agent
        
#         task_id = task["id"]
#         description = task.get("description", "")
        
#         print(f"\n  🛠️ GITHUB_WORKER: Executing Task {task_id}")
#         print(f"     Description: {description}")
        
#         if context:
#             print(f"     With context: {len(context)} chars")
        
#         try:
#             github_pat = os.getenv("GITHUB_PAT")
            
#             client = MultiServerMCPClient({
#                 "github": {
#                     "transport": "http",
#                     "url": "https://api.githubcopilot.com/mcp/",
#                     "headers": {"Authorization": f"Bearer {github_pat}"}
#                 }
#             })
            
#             # Get all tools from MCP
#             all_tools = await client.get_tools()
            
#             # Filter to only our 7 essential tools
#             filtered_tools = []
#             for tool in all_tools:
#                 if tool.name in GITHUB_TOOLS:
#                     filtered_tools.append(tool)
            
#             if not filtered_tools:
#                 return TaskResult(
#                     task_id=task_id,
#                     worker_type="github",
#                     success=False,
#                     output="No GitHub tools available",
#                     used_context=bool(context)
#                 )
            
#             # Create agent with filtered tools
#             agent = create_agent(llm, filtered_tools)
            
#             # Build prompt with context if available
#             if context:
#                 prompt = f"""
#                 GitHub Task: {description}
                
#                 Context from search (use if relevant):
#                 {context[:800]}
                
#                 Original query: {task.get('user_query', '')}
                
#                 Please use appropriate GitHub tools to complete this task.
#                 Use the context above if it helps understand what needs to be done.
#                 """
#             else:
#                 prompt = f"""
#                 GitHub Task: {description}
                
#                 Original query: {task.get('user_query', '')}
                
#                 Please use appropriate GitHub tools to complete this task.
#                 """
            
#             response = await agent.ainvoke({
#                 "messages": [{"role": "user", "content": prompt}]
#             })
            
#             # Extract output
#             if "messages" in response:
#                 # Find the last AI message
#                 for msg in reversed(response["messages"]):
#                     if hasattr(msg, 'content'):
#                         output = msg.content
#                         break
#                 else:
#                     output = str(response)
#             else:
#                 output = str(response)
            
#             print(f"     ✅ Task completed")
            
#             return TaskResult(
#                 task_id=task_id,
#                 worker_type="github",
#                 success=True,
#                 output=output,
#                 used_context=bool(context)
#             )
            
#         except Exception as e:
#             error_msg = str(e)
#             print(f"     ❌ Error: {error_msg[:100]}")
            
#             return TaskResult(
#                 task_id=task_id,
#                 worker_type="github",
#                 success=False,
#                 output=f"GitHub operation failed: {error_msg}",
#                 used_context=bool(context),
#                 error=error_msg
#             )


# def github_worker_node(payload: dict) -> dict:
#     """GitHub worker node"""
#     import asyncio
    
#     task_data = payload["task"]
#     context = payload.get("context", "")
#     task_data["user_query"] = payload.get("user_query", "")
    
#     worker = GitHubWorker()
#     result = asyncio.run(worker.execute(task_data, context))
    
#     return {"results": [result]}


# # ============================================================================
# # 7. GOOGLE WORKSPACE WORKER (existing - unchanged)
# # ============================================================================
# class GoogleWorkspaceWorker:
#     """Worker for Google Workspace operations"""
    
#     async def execute(self, task: dict, context: str = "") -> TaskResult:
#         """Execute a Google Workspace task"""
#         task_id = task["id"]
#         description = task.get("description", "")
#         google_service = task.get("google_service", "")
        
#         print(f"\n  🚀 GOOGLE_WORKSPACE_WORKER: Executing Task {task_id}")
#         print(f"     Service: {google_service}")
#         print(f"     Description: {description}")
        
#         if context:
#             print(f"     With context: {len(context)} chars")
        
#         try:
#             from langchain_mcp_adapters.client import MultiServerMCPClient
#             from langchain.agents import create_agent
            
#             # Check required environment variables
#             google_client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
#             google_client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
            
#             if not google_client_id or not google_client_secret:
#                 return TaskResult(
#                     task_id=task_id,
#                     worker_type=f"google_{google_service}",
#                     success=False,
#                     output="Google OAuth credentials not configured.",
#                     used_context=bool(context)
#                 )
            
#             # Create MCP client for HTTP transport
#             client = MultiServerMCPClient({
#                 "google_workspace": {
#                     "transport": "http",
#                     "url": "http://localhost:8000/mcp/",
#                     "headers": {}
#                 }
#             })
            
#             # Get all tools from Google Workspace MCP
#             all_tools = await client.get_tools()
            
#             if not all_tools:
#                 return TaskResult(
#                     task_id=task_id,
#                     worker_type=f"google_{google_service}",
#                     success=False,
#                     output="No Google Workspace tools available",
#                     used_context=bool(context)
#                 )
            
#             # Filter tools by service if specified
#             if google_service and google_service != "all_google":
#                 filtered_tools = []
#                 for tool in all_tools:
#                     if google_service in tool.name:
#                         filtered_tools.append(tool)
#             else:
#                 filtered_tools = all_tools
            
#             if not filtered_tools:
#                 return TaskResult(
#                     task_id=task_id,
#                     worker_type=f"google_{google_service}",
#                     success=False,
#                     output=f"No tools available for Google service: {google_service}",
#                     used_context=bool(context)
#                 )
            
#             # Create agent with filtered tools
#             agent = create_agent(llm, filtered_tools)
            
#             # Build prompt with context if available
#             if context:
#                 prompt = f"""
#                 Google Workspace Task ({google_service}): {description}
                
#                 Context from search (use if relevant):
#                 {context[:800]}
                
#                 Original query: {task.get('user_query', '')}
                
#                 Please use appropriate Google Workspace tools to complete this task.
#                 Use the context above if it helps understand what needs to be done.
#                 """
#             else:
#                 prompt = f"""
#                 Google Workspace Task ({google_service}): {description}
                
#                 Original query: {task.get('user_query', '')}
                
#                 Please use appropriate Google Workspace tools to complete this task.
#                 """
            
#             response = await agent.ainvoke({
#                 "messages": [{"role": "user", "content": prompt}]
#             })
            
#             # Extract output
#             if "messages" in response:
#                 for msg in reversed(response["messages"]):
#                     if hasattr(msg, 'content'):
#                         output = msg.content
#                         break
#                 else:
#                     output = str(response)
#             else:
#                 output = str(response)
            
#             print(f"     ✅ Task completed")
            
#             return TaskResult(
#                 task_id=task_id,
#                 worker_type=f"google_{google_service}",
#                 success=True,
#                 output=output,
#                 used_context=bool(context)
#             )
            
#         except Exception as e:
#             error_msg = str(e)
#             print(f"     ❌ Error: {error_msg[:100]}")
            
#             return TaskResult(
#                 task_id=task_id,
#                 worker_type=f"google_{google_service}",
#                 success=False,
#                 output=f"Google Workspace operation failed: {error_msg}",
#                 used_context=bool(context),
#                 error=error_msg
#             )


# def google_workspace_worker_node(payload: dict) -> dict:
#     """Google Workspace worker node"""
#     import asyncio
    
#     task_data = payload["task"]
#     context = payload.get("context", "")
#     task_data["user_query"] = payload.get("user_query", "")
    
#     worker = GoogleWorkspaceWorker()
#     result = asyncio.run(worker.execute(task_data, context))
    
#     return {"results": [result]}


# # ============================================================================
# # 8. CONVERSATIONAL WORKER (existing - unchanged)
# # ============================================================================
# class ConversationalWorker:
#     """Worker for conversational tasks with context support"""
    
#     def execute(self, task: dict, user_query: str, context: str = "") -> TaskResult:
#         """Execute a conversational task, optionally with context"""
#         task_id = task["id"]
        
#         print(f"\n  💬 CONVERSATIONAL_WORKER: Executing Task {task_id}")
#         if context:
#             print(f"     With context: {len(context)} chars")
        
#         # Build prompt with context if available
#         if context:
#             prompt = f"""
#             User Query: {user_query}
            
#             Context from search:
#             {context}
            
#             Task: {task.get('description', 'Respond conversationally')}
            
#             Please respond using this context if helpful.
#             If context isn't relevant to the conversation, you can ignore it.
#             """
#         else:
#             prompt = f"""
#             User Query: {user_query}
            
#             Task: {task.get('description', 'Respond conversationally')}
            
#             Provide a helpful, conversational response.
#             """
        
#         messages = [
#             SystemMessage(content="You are a helpful assistant."),
#             HumanMessage(content=prompt)
#         ]
        
#         response = llm.invoke(messages)
        
#         print(f"     ✅ Response generated")
        
#         return TaskResult(
#             task_id=task_id,
#             worker_type="conversational",
#             success=True,
#             output=response.content,
#             used_context=bool(context)
#         )


# def conversational_worker_node(payload: dict) -> dict:
#     """Conversational worker node"""
#     task_data = payload["task"]
#     user_query = payload["user_query"]
#     context = payload.get("context", "")
    
#     worker = ConversationalWorker()
#     result = worker.execute(task_data, user_query, context)
    
#     return {"results": [result]}


# # ============================================================================
# # 9. TASK EXECUTOR - Routes tasks to workers with context
# # ============================================================================
# def fanout_to_workers(state: OrchestratorState):
#     """Execute tasks, providing context where needed"""
#     print(f"\n⚡ EXECUTING TASKS")
#     print("="*40)
    
#     sends = []
#     context = state.get("combined_context", "")
    
#     for task in state["tasks"]:
#         # Prepare payload
#         payload = {
#             "task": task.model_dump(),
#             "user_query": state["user_query"]
#         }
        
#         # Add context if task requires it and we have context
#         if task.requires_context and context:
#             payload["context"] = context
        
#         # Route to appropriate worker
#         if task.worker_type == "github":
#             sends.append(Send("github_worker", payload))
#             print(f"  → Task {task.id}: {task.title}")
#             print(f"     Worker: GitHub | Context: {'Yes' if task.requires_context and context else 'No'}")
#         elif task.worker_type.startswith("google_") or task.google_service:
#             sends.append(Send("google_workspace_worker", payload))
#             print(f"  → Task {task.id}: {task.title}")
#             print(f"     Worker: Google Workspace | Service: {task.google_service or task.worker_type}")
#             print(f"     Context: {'Yes' if task.requires_context and context else 'No'}")
        
#         else:
#             sends.append(Send("conversational_worker", payload))
#             print(f"  → Task {task.id}: {task.title}")
#             print(f"     Worker: Conversational | Context: {'Yes' if task.requires_context and context else 'No'}")
    
#     return sends


# # ============================================================================
# # 10. RESULTS AGGREGATOR
# # ============================================================================
# def results_aggregator_node(state: OrchestratorState) -> dict:
#     """Aggregate results from all workers"""
#     results = state.get("results", [])
    
#     print("\n" + "="*60)
#     print("📦 AGGREGATING RESULTS")
#     print("="*60)
    
#     print(f"Total tasks executed: {len(results)}")
    
#     for result in results:
#         status = "✅" if result.success else "❌"
#         context_marker = "📚" if result.used_context else ""
#         print(f"  {status}{context_marker} Task {result.task_id} ({result.worker_type}): ", end="")
#         print(f"{len(result.output)} chars")
#         if not result.success and result.error:
#             print(f"     Error: {result.error[:100]}...")
    
#     if not results:
#         return {"final_response": "No tasks were executed."}
    
#     # If only one result, use it directly
#     if len(results) == 1:
#         return {"final_response": results[0].output}
    
#     # Combine multiple results
#     results_text = "\n\n".join([
#         f"[{r.worker_type.upper()}] {r.output[:400]}..."
#         for r in results
#     ])
    
#     prompt = f"""
#     Original Query: {state['user_query']}
    
#     Results from different workers:
#     {results_text}
    
#     Provide a coherent final response that addresses the user's original query.
#     Integrate information from different services smoothly.
#     """
    
#     messages = [
#         SystemMessage(content="You are a helpful assistant."),
#         HumanMessage(content=prompt)
#     ]
    
#     response = llm.invoke(messages)
    
#     return {"final_response": response.content}


# # ============================================================================
# # 11. BUILD THE SMART GRAPH
# # ============================================================================
# def build_smart_orchestrator():
#     """Build the intelligent graph with multiple context providers"""
#     g = StateGraph(OrchestratorState)
    
#     # Add nodes
#     g.add_node("planning", planning_agent_node)
#     g.add_node("web_search", web_search_node)
#     g.add_node("rag_search", rag_search_node)
#     g.add_node("club_search", club_search_node)
#     g.add_node("execute_tasks", lambda s: s)  # Pass-through node
#     g.add_node("github_worker", github_worker_node)
#     g.add_node("google_workspace_worker", google_workspace_worker_node)
#     g.add_node("conversational_worker", conversational_worker_node)
#     g.add_node("aggregator", results_aggregator_node)
    
#     # Start with planning
#     g.add_edge(START, "planning")
    
#     # After planning, decide which context provider to use
#     g.add_conditional_edges(
#         "planning",
#         route_after_planning,
#         {
#             "web_search": "web_search",
#             "rag_search": "rag_search",
#             "club_search": "club_search",
#             "execute_tasks": "execute_tasks"
#         }
#     )
    
#     # After context gathering, go to task execution
#     g.add_edge("web_search", "execute_tasks")
#     g.add_edge("rag_search", "execute_tasks")
#     g.add_edge("club_search", "execute_tasks")
    
#     # From execution, fanout to workers
#     g.add_conditional_edges(
#         "execute_tasks",
#         fanout_to_workers, 
#         {
#             "github_worker": "github_worker",
#             "google_workspace_worker": "google_workspace_worker",
#             "conversational_worker": "conversational_worker"
#         }
#     )
    
#     # Workers to aggregator
#     g.add_edge("github_worker", "aggregator")
#     g.add_edge("google_workspace_worker", "aggregator")
#     g.add_edge("conversational_worker", "aggregator")
    
#     # Aggregator to end
#     g.add_edge("aggregator", END)
    
#     return g.compile()


# # ============================================================================
# # 12. MAIN ORCHESTRATOR CLASS
# # ============================================================================
# class SmartOrchestrator:
#     """Smart orchestrator with multiple context providers"""
    
#     def __init__(self):
#         self.graph = build_smart_orchestrator()
#         print("\n" + "="*60)
#         print("✅ ENHANCED SMART ORCHESTRATOR INITIALIZED")
#         print("="*60)
#         print("Features:")
#         print("  • Wikipedia web search for factual context")
#         print("  • RAG search for internal documentation")
#         print("  • Club search for social/club information")
#         print("  • GitHub worker with 7 essential tools")
#         print("  • Google Workspace worker (Gmail, Calendar, Drive, Docs, etc.)")
#         print("  • Conversational worker with context support")
#         print("  • Intelligent planning agent")
#         print("\n📋 Required environment variables:")
#         print("  • GROQ_API_KEY: For LLM")
#         print("  • GITHUB_PAT: For GitHub operations")
#         print("  • GOOGLE_OAUTH_CLIENT_ID: For Google Workspace")
#         print("  • GOOGLE_OAUTH_CLIENT_SECRET: For Google Workspace")
#         print("  • RAG_MCP_SERVER_URL: For RAG search (optional)")
#         print("="*60)
    
#     def process(self, user_query: str, conversation_history: List[str] = None) -> dict:
#         """Process a query through the orchestrator"""
#         print(f"\n🚀 PROCESSING: {user_query}")
        
#         initial_state: OrchestratorState = {
#             "user_query": user_query,
#             "conversation_history": conversation_history or [],
#             "plan": None,
#             "web_context": [],
#             "rag_context": [],
#             "club_context": [],
#             "combined_context": "",
#             "tasks": [],
#             "results": [],
#             "final_response": ""
#         }
        
#         try:
#             final_state = self.graph.invoke(initial_state)
            
#             print("\n" + "="*60)
#             print("🎉 PROCESSING COMPLETE!")
#             print("="*60)
            
#             # Analyze results
#             results = final_state.get("results", [])
#             successful = [r for r in results if r.success]
#             used_context = [r for r in results if r.used_context]
            
#             return {
#                 "success": True,
#                 "response": final_state["final_response"],
#                 "metadata": {
#                     "total_tasks": len(results),
#                     "successful_tasks": len(successful),
#                     "tasks_with_context": len(used_context),
#                     "web_search_used": len(final_state.get("web_context", [])) > 0,
#                     "rag_search_used": len(final_state.get("rag_context", [])) > 0,
#                     "club_search_used": len(final_state.get("club_context", [])) > 0,
#                     "workers_used": list(set([r.worker_type for r in results]))
#                 }
#             }
            
#         except Exception as e:
#             print(f"\n❌ Error: {e}")
#             import traceback
#             traceback.print_exc()
#             return {
#                 "success": False,
#                 "response": f"Orchestrator error: {str(e)}",
#                 "metadata": {"error": str(e)}
#             }


# # ============================================================================
# # 13. TEST FUNCTION
# # ============================================================================
# def test_queries():
#     """Test different query types"""
#     orchestrator = SmartOrchestrator()
    
#     test_cases = [
#         # Web search queries
#         ("What is LangGraph and create a GitHub repo?", 
#          "Should use web search + github worker"),
        
#         # RAG search queries
#         ("Search our documentation for API guidelines and create a Google Doc", 
#          "Should use RAG search + docs worker"),
        
#         ("What are our company's security policies?", 
#          "Should use RAG search"),
        
#         # Club search queries
#         ("When is the next club meeting? Send an email reminder", 
#          "Should use club search + gmail worker"),
        
#         ("Who are the club members? Create a spreadsheet with their info", 
#          "Should use club search + sheets worker"),
        
#         # Mixed queries
#         ("Search the web for AI trends, check our internal docs, and schedule a club meeting", 
#          "Should use web + RAG + club + calendar workers"),
        
#         # Google Workspace queries
#         ("Send an email about tomorrow's team meeting", 
#          "Should use gmail worker"),
        
#         ("Create a presentation about quarterly results", 
#          "Should use slides worker"),
        
#         # Pure conversation
#         ("Hello, how are you today?", 
#          "Should use conversational worker"),
#     ]
    
#     print("\n" + "="*60)
#     print("🧪 TESTING ENHANCED ORCHESTRATOR")
#     print("="*60)
    
#     for query, description in test_cases:
#         print(f"\n📝 Query: {query}")
#         print(f"   Expected: {description}")
#         print("-" * 40)
        
#         result = orchestrator.process(query)
        
#         if result["success"]:
#             meta = result["metadata"]
#             print(f"   ✅ Success!")
#             print(f"   Web search used: {meta['web_search_used']}")
#             print(f"   RAG search used: {meta['rag_search_used']}")
#             print(f"   Club search used: {meta['club_search_used']}")
#             print(f"   Workers used: {meta['workers_used']}")
#             print(f"   Tasks: {meta['total_tasks']} total, {meta['successful_tasks']} successful")
#             print(f"   Response: {result['response'][:100]}...")
#         else:
#             print(f"   ❌ Failed: {result['response']}")


# # ============================================================================
# # 14. INTERACTIVE MODE
# # ============================================================================
# def interactive_mode():
#     """Interactive mode"""
#     print("\n" + "="*60)
#     print("🤖 ENHANCED SMART ORCHESTRATOR")
#     print("="*60)
#     print("Flow: Planning → Context Search → Workers → Response")
#     print("Context Providers:")
#     print("  • 🌐 Web Search (Wikipedia)")
#     print("  • 📚 RAG Search (Internal docs)")
#     print("  • 👥 Club Search (Club info)")
#     print("Workers:")
#     print("  • 🛠️  GitHub")
#     print("  • 🚀 Google Workspace")
#     print("  • 💬 Conversational")
#     print("="*60)
#     print("Commands: 'test', 'quit', 'exit', 'q'")
#     print("="*60)
    
#     orchestrator = SmartOrchestrator()
#     conversation = []
    
#     while True:
#         query = input("\n💬 Query: ").strip()
        
#         if not query:
#             continue
            
#         if query.lower() in ['quit', 'exit', 'q']:
#             print("\n👋 Goodbye!")
#             break
        
#         if query.lower() == 'test':
#             test_queries()
#             continue
        
#         result = orchestrator.process(query, conversation)
        
#         # Update conversation
#         conversation.append(f"User: {query}")
#         if result["success"]:
#             conversation.append(f"Assistant: {result['response'][:100]}...")
        
#         print(f"\n{'='*60}")
#         print("🤖 FINAL RESPONSE:")
#         print(f"{'='*60}")
#         print(result["response"])
#         print(f"{'='*60}")
        
#         if result["success"]:
#             meta = result["metadata"]
#             print(f"\n📊 Metadata:")
#             print(f"  Web search: {'Yes' if meta['web_search_used'] else 'No'}")
#             print(f"  RAG search: {'Yes' if meta['rag_search_used'] else 'No'}")
#             print(f"  Club search: {'Yes' if meta['club_search_used'] else 'No'}")
#             print(f"  Workers: {', '.join(meta['workers_used'])}")
#             print(f"  Tasks: {meta['total_tasks']} total, {meta['successful_tasks']} successful")


# # ============================================================================
# # MAIN EXECUTION
# # ============================================================================
# if __name__ == "__main__":
#     import sys
    
    
#     if len(sys.argv) > 1 and sys.argv[1] == "test":
#         test_queries()
#     else:
#         interactive_mode()


"""
smart_orchestrator.py
Orchestrator with Wikipedia web search, RAG, and Club search as context providers
with Google Workspace integration

Fixed version with:
- Corrected async/sync issues
- Fixed mixed context handling
- Better error handling
- Improved category extraction
- Better result handling
"""
from __future__ import annotations

from typing import TypedDict, List, Optional, Literal, Annotated, Union, Callable
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from pydantic import BaseModel, Field
import operator
import asyncio
import json
import logging
from datetime import datetime

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain.agents import create_agent
import os
from dotenv import load_dotenv
from pathlib import Path
from knowledge_engine.club.retrieval import club_retriever

load_dotenv()

servers_dir = Path(__file__).resolve().parent.parent / 'mcp_servers'

# ============================================================================
# LOGGING SETUP
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'orchestrator_{datetime.now():%Y%m%d}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# 1. MODELS WITH CONTEXT SUPPORT
# ============================================================================
class ContextItem(BaseModel):
    """Context gathered from various sources"""
    source: Literal["web_search", "rag", "conversation", "club_search"]
    content: str
    relevance_score: float = Field(ge=0, le=1)
    metadata: dict = Field(default_factory=dict)


class WorkerTask(BaseModel):
    """Task for a specific worker"""
    id: int
    title: str
    worker_type: Literal["github", "conversational", "calendar", "gmail"] = "conversational"
    description: str
    parameters: dict = Field(default_factory=dict)
    requires_context: bool = False  # Does this task need context?
    context_type: Optional[Literal["web", "rag", "club"]] = None  # What type of context is needed
    google_service: Optional[str] = None  # Specific Google service if needed


class ExecutionPlan(BaseModel):
    """Intelligent execution plan"""
    needs_context: bool = False
    context_type: Optional[Literal["web", "rag", "club", "mixed"]] = None
    reasoning: str
    tasks: List[WorkerTask] = Field(default_factory=list)
    search_queries: List[str] = Field(default_factory=list)  # Queries for web search
    rag_queries: List[str] = Field(default_factory=list)  # Queries for RAG
    club_queries: List[str] = Field(default_factory=list)  # Queries for Club search


class TaskResult(BaseModel):
    """Result from task execution"""
    task_id: int
    worker_type: str
    success: bool
    output: str
    used_context: bool = False
    error: Optional[str] = None


# ============================================================================
# 2. STATE WITH CONTEXT
# ============================================================================
class OrchestratorState(TypedDict):
    """Enhanced state with context support"""
    # Input
    user_query: str
    conversation_history: List[str]
    
    # Planning
    plan: Optional[ExecutionPlan]
    
    # Context
    web_context: List[ContextItem]
    rag_context: List[ContextItem]
    club_context: List[ContextItem]
    combined_context: str
    
    # Execution
    tasks: List[WorkerTask]
    results: Annotated[List[TaskResult], operator.add]
    
    # Output
    final_response: str


# ============================================================================
# 3. LLM & TOOLS INITIALIZATION
# ============================================================================
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.1,
    api_key=os.getenv("GROQ_API_KEY")
)

# Initialize Wikipedia search tool
search_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
web_search_agent = create_agent(llm, tools=[search_tool])

print("✅ LLM and Wikipedia search initialized")


# ============================================================================
# 4. INTELLIGENT PLANNING AGENT
# ============================================================================
PLANNING_SYSTEM = """You are an intelligent planning agent that decides:
1. Does this query need context from web search, RAG, or club search?
2. Which workers are needed to execute the actual tasks?

ANALYSIS FRAMEWORK:
1. What information is needed to answer this query?
2. Where should that information come from?
3. What actions need to be taken?

CONTEXT DECISION TREE:
├─ Factual knowledge (definitions, history, concepts) → WEB
├─ User's documents/data → RAG
├─ Club-specific information → CLUB
└─ Multiple sources needed → MIXED

CONTEXT TYPES:

WEB SEARCH is needed for:
- Factual questions, explanations, definitions
- Historical information, concepts, theories
- Technical documentation, how-tos
- General knowledge queries
- "What is...", "Explain...", "How does...", "Tell me about..."
- Current facts: "Latest...", "Current status of..."

RAG SEARCH is needed for:
- Grounded response for user queries based on user-provided documents
- "Search my documents for...", "What do my files say about...", "Find information in my docs about..."
- User documents: "In my files...", "According to our docs..."
- Personal data: "My notes on...", "Our company policy for..."

CLUB SEARCH is needed for:
- Club events: timeline, about, coordinators, description
- Club Announcements
- Club coordinators and contact info
- Events: "Next club meeting", "Upcoming events"
- People: "Club coordinators", "Member contact"
- Announcements: "Latest club news", "Recent updates"

NO CONTEXT needed for:
- GitHub operations (create repo, PRs, files)
- Google Workspace operations (Gmail, Calendar)
- Simple greetings, casual conversation
- Already known operational commands
- Greetings: "Hello", "Hi", "How are you"
- Operations: "Create a repo", "Send an email"

WORKERS:
- github: For repository/file/PR operations (7 tools)
- gmail/calendar/drive/docs/sheets/slides: For Google Workspace services
- conversational: For chat/questions

GOOGLE WORKSPACE SERVICES:
- gmail: Send/search emails, manage labels, attachments
- calendar: Create/update events, list calendars
- drive: File management
- docs: Document creation/editing
- sheets: Spreadsheet operations
- slides: Presentation creation

RULES:
1. First decide if any context is needed (web, rag, club, or mixed)
2. Extract appropriate queries for each context type
3. Identify which Google service(s) are needed from the query
4. Create tasks for workers with appropriate parameters
5. Mark tasks that need context with requires_context=True and context_type

OUTPUT REQUIREMENTS:
- Set needs_context: true/false
- Set context_type: web/rag/club/mixed/null
- Extract specific search queries (be precise!)
- List all required tasks with correct worker types
- Mark which tasks need context

EXAMPLES:
Query: "What is API and create a GitHub repo"
→ needs_context: true
→ context_type: web
→ search_queries: ["API definition and types"]
→ tasks: [
    {id: 1, worker_type: "conversational", requires_context: true, context_type: "web"},
    {id: 2, worker_type: "github", requires_context: false}
  ]

Query: "What is GraphRAG and create a doc about it"
→ needs_context: true
→ context_type: web
→ search_queries: ["GraphRAG definition and architecture"]
→ tasks: [
    {id: 1, worker_type: "conversational", requires_context: true, context_type: "web"},
    {id: 2, worker_type: "docs", google_service: "docs", requires_context: true, context_type: "web"}
  ]

Query: "When is the next robotics club event?"
→ needs_context: true
→ context_type: club
→ club_queries: ["upcoming robotics club events"]
→ tasks: [
    {id: 1, worker_type: "conversational", requires_context: true, context_type: "club"}
  ]

Query: "Search the web for AI trends and check our internal docs about it"
→ needs_context: true
→ context_type: mixed
→ search_queries: ["latest AI trends"]
→ rag_queries: ["AI trends in our documents"]
→ tasks: [
    {id: 1, worker_type: "conversational", requires_context: true, context_type: "web"}
  ]
"""


def planning_agent_node(state: OrchestratorState) -> dict:
    """Planning agent that decides what context is needed"""
    print("\n" + "="*60)
    print("🤖 SMART PLANNING AGENT: Analyzing query...")
    print("="*60)
    
    logger.info(f"Planning for query: {state['user_query']}")
    
    try:
        planner = llm.with_structured_output(ExecutionPlan)
        
        plan = planner.invoke([
            SystemMessage(content=PLANNING_SYSTEM),
            HumanMessage(content=f"""
            User Query: {state['user_query']}
            
            Analyze what type of context is needed (web, rag, club, mixed, or none).
            If context is needed, set needs_context=True and extract appropriate queries.
            Identify which Google Workspace services are needed (if any).
            Then create appropriate tasks for workers.
            """)
        ])
        
        print(f"✅ Analysis:")
        print(f"   Context Needed: {plan.needs_context}")
        if plan.context_type:
            print(f"   Context Type: {plan.context_type}")
        print(f"   Reasoning: {plan.reasoning}")
        
        if plan.search_queries:
            print(f"   Web Search Queries: {plan.search_queries}")
        if plan.rag_queries:
            print(f"   RAG Queries: {plan.rag_queries}")
        if plan.club_queries:
            print(f"   Club Queries: {plan.club_queries}")
        
        print(f"\n📋 Tasks ({len(plan.tasks)}):")
        for task in plan.tasks:
            context_marker = ""
            if task.requires_context:
                if task.context_type == "web":
                    context_marker = "🌐"
                elif task.context_type == "rag":
                    context_marker = "📚"
                elif task.context_type == "club":
                    context_marker = "👥"
                else:
                    context_marker = "📚"
            google_marker = f" [{task.google_service}]" if task.google_service else ""
            print(f"  • {context_marker} Task {task.id}: {task.title} → {task.worker_type}{google_marker}")
        
        logger.info(f"Plan created: {plan.reasoning}")
        
        return {"plan": plan, "tasks": plan.tasks}
        
    except Exception as e:
        logger.error(f"Planning failed: {e}", exc_info=True)
        raise


def route_after_planning(state: OrchestratorState) -> str:
    """Route based on context needs - FIXED for mixed context"""
    plan = state.get("plan")
    
    if not plan:
        logger.warning("No plan found, routing to execute_tasks")
        return "execute_tasks"
    
    # Determine which context provider to use
    if not plan.needs_context:
        logger.info("No context needed, routing to execute_tasks")
        return "execute_tasks"
    
    # Check context type and route accordingly
    if plan.context_type == "web":
        logger.info("Routing to web_search")
        return "web_search"
    elif plan.context_type == "rag":
        logger.info("Routing to rag_search")
        return "rag_search"
    elif plan.context_type == "club":
        logger.info("Routing to club_search")
        return "club_search"
    elif plan.context_type == "mixed":
        # For mixed context, route to a context aggregator
        # For now, we'll gather contexts sequentially
        # You can enhance this to parallel gathering
        logger.info("Mixed context detected, routing to web_search first")
        return "gather_mixed_context"
    
    # Default to execute tasks
    logger.info("Default routing to execute_tasks")
    return "execute_tasks"


# ============================================================================
# 5. CONTEXT PROVIDERS
# ============================================================================

# 5.1 Web Search Context Provider
class WebSearchProvider:
    """Gathers context from Wikipedia"""
    
    def search(self, query: str) -> List[ContextItem]:
        """Perform Wikipedia search"""
        print(f"\n🌐 WEB SEARCH: Searching for '{query}'")
        logger.info(f"Web search for: {query}")
        
        try:
            # Use web search agent
            result = web_search_agent.invoke(
                {"messages": [{"role": "user", "content": query}]}
            )
            
            # Extract the AI message content
            content = ""
            if "messages" in result:
                for msg in result["messages"]:
                    if hasattr(msg, 'content') and msg.content:
                        content = msg.content
                        break
            
            if not content:
                content = str(result)
            
            print(f"   ✅ Search completed: {len(content)} chars")
            logger.info(f"Web search completed successfully")
            
            # Create context item
            return [ContextItem(
                source="web_search",
                content=content[:1000],  # Limit size
                relevance_score=0.9,
                metadata={
                    "query": query,
                    "source": "wikipedia",
                    "agent_used": "WikipediaQueryRun"
                }
            )]
            
        except Exception as e:
            error_msg = str(e)
            print(f"   ❌ Web search error: {error_msg[:100]}")
            logger.error(f"Web search error: {error_msg}")
            
            # Return error context
            return [ContextItem(
                source="web_search",
                content=f"Wikipedia search failed for: {query}. Error: {error_msg[:100]}",
                relevance_score=0.1,
                metadata={"error": error_msg, "query": query}
            )]


def web_search_node(state: OrchestratorState) -> dict:
    """Gather web context before task execution"""
    plan = state["plan"]
    
    print("\n" + "="*60)
    print("🌐 GATHERING WEB CONTEXT FROM WIKIPEDIA")
    print("="*60)
    
    provider = WebSearchProvider()
    all_context = []
    
    # Search for each query (limit to 2 queries)
    queries_to_search = plan.search_queries[:2]
    for query in queries_to_search:
        context_items = provider.search(query)
        all_context.extend(context_items)
        if context_items:
            print(f"   Search query: '{query}' → {len(context_items[0].content)} chars")
    
    # Combine context
    combined = "\n\n".join([
        f"[Web Search: '{item.metadata.get('query', 'unknown')}']\n{item.content}"
        for item in sorted(all_context, key=lambda x: x.relevance_score, reverse=True)
    ])
    
    print(f"   Total web context gathered: {len(combined)} characters")
    logger.info(f"Web context gathered: {len(all_context)} items, {len(combined)} chars")
    
    return {
        "web_context": all_context,
        "combined_context": combined
    }


# 5.2 RAG Search Context Provider
class RagSearchProvider:
    """Gathers context from RAG MCP server"""
    
    async def search(self, query: str) -> List[ContextItem]:
        """Perform RAG search using MCP server"""
        print(f"\n📚 RAG SEARCH: Searching for '{query}'")
        logger.info(f"RAG search for: {query}")
        
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            from langchain.agents import create_agent
            
            # Create MCP client for RAG server
            client = MultiServerMCPClient({
                "rag_server": {
                    "command": "python",
                    "args": [str(servers_dir / "rag_server.py")],
                    "transport": "stdio",
                }      
            })
            
            # Get tools from RAG MCP server
            all_tools = await client.get_tools()
            
            # Find the rag_retrieve tool
            rag_tool = None
            for tool_obj in all_tools:
                if tool_obj.name == "rag_retrieve":
                    rag_tool = tool_obj
                    break
            
            if not rag_tool:
                print(f"   ❌ RAG tool not found on server")
                logger.warning("RAG tool not found")
                return [ContextItem(
                    source="rag",
                    content=f"RAG search tool not available",
                    relevance_score=0.1,
                    metadata={"error": "Tool not found", "query": query}
                )]
            
            # Create agent with RAG tool
            agent = create_agent(llm, [rag_tool])
            
            # Execute search
            response = await agent.ainvoke({
                "messages": [{"role": "user", "content": f"Search for: {query}"}]
            })
            
            # Extract output
            output = ""
            if "messages" in response:
                for msg in reversed(response["messages"]):
                    if hasattr(msg, 'content') and msg.content:
                        output = msg.content
                        break
            
            if not output:
                output = str(response)
            
            print(f"   ✅ RAG search completed: {len(output)} chars")
            logger.info(f"RAG search completed successfully")
            
            # Create context item
            return [ContextItem(
                source="rag",
                content=output[:1500],  # RAG content might be longer
                relevance_score=0.85,
                metadata={
                    "query": query,
                    "source": "rag_mcp",
                }
            )]
            
        except Exception as e:
            error_msg = str(e)
            print(f"   ❌ RAG search error: {error_msg[:100]}")
            logger.error(f"RAG search error: {error_msg}")
            
            # Check if server is not running
            help_text = ""
            if "connection" in error_msg.lower() or "refused" in error_msg.lower():
                help_text = "\n   💡 RAG MCP server is not running. Start it with: rag-mcp-server"
            
            return [ContextItem(
                source="rag",
                content=f"RAG search failed for: {query}. Error: {error_msg[:200]}{help_text}",
                relevance_score=0.1,
                metadata={"error": error_msg, "query": query}
            )]


async def rag_search_async(plan: ExecutionPlan) -> List[ContextItem]:
    """Async wrapper for RAG search"""
    provider = RagSearchProvider()
    all_context = []
    
    # Search for each RAG query (limit to 2 queries)
    for query in plan.rag_queries[:2]:
        context_items = await provider.search(query)
        all_context.extend(context_items)
    
    return all_context


def rag_search_node(state: OrchestratorState) -> dict:
    """Gather RAG context before task execution"""
    plan = state["plan"]
    
    print("\n" + "="*60)
    print("📚 GATHERING RAG CONTEXT")
    print("="*60)
    
    # Run async RAG search
    all_context = asyncio.run(rag_search_async(plan))
    
    # Combine context
    combined = "\n\n".join([
        f"[RAG Search: '{item.metadata.get('query', 'unknown')}']\n{item.content}"
        for item in sorted(all_context, key=lambda x: x.relevance_score, reverse=True)
    ])
    
    print(f"   Total RAG context gathered: {len(combined)} characters")
    logger.info(f"RAG context gathered: {len(all_context)} items, {len(combined)} chars")
    
    return {
        "rag_context": all_context,
        "combined_context": combined
    }


# 5.3 Club Search Context Provider - FIXED
class ClubSearchProvider:
    """Gathers context from club search tool"""
    
    def search(self, query: str) -> List[ContextItem]:
        """Perform club search using the tool"""
        print(f"\n👥 CLUB SEARCH: Searching for '{query}'")
        logger.info(f"Club search for: {query}")
        
        try:
            # FIXED: Extract category using synchronous invoke with proper schema
            category_prompt = f"""Define the category from the following query for club search.
The category should be one of these: events, announcements, coordinators.
If not relevant to any category, respond with 'general'.

Query: {query}

Respond with ONLY the category name (one word)."""
            
            # Get category from LLM (synchronous)
            category_response = llm.invoke([
                SystemMessage(content="You are a category classifier. Respond with only one word."),
                HumanMessage(content=category_prompt)
            ])
            
            # Extract category
            category = category_response.content.strip().lower()
            
            # Validate category
            valid_categories = ["events", "announcements", "coordinators", "general"]
            if category not in valid_categories:
                category = "general"
            
            print(f"   🏷️ Identified category: {category}")
            logger.info(f"Category identified: {category}")
            
            # If category is "general", set to None for the search
            search_category = None if category == "general" else category
            
            # FIXED: Use the club search tool - handle list of results properly
            results = club_retriever.retrieve(
                query=query,
                category=search_category,  
                top_k=3
            )
            
            print(f"   ✅ Club search completed - found {len(results) if isinstance(results, list) else 'N/A'} results")
            logger.info(f"Club search completed with {len(results) if isinstance(results, list) else 'unknown'} results")
            
            # Handle the results properly
            if not results:
                return [ContextItem(
                    source="club_search",
                    content="No club information found for this query.",
                    relevance_score=0.0,
                    metadata={
                        "query": query,
                        "source": "club_database",
                        "tool_used": "club_search_tool",
                        "category": category,
                        "results_count": 0
                    }
                )]
            
            # Handle both dict and list results
            if isinstance(results, dict):
                # Single result in dict format
                content = results.get('content', results.get('text', str(results)))
                score = results.get('score', results.get('relevance', 0.5))
                
                return [ContextItem(
                    source="club_search",
                    content=content,
                    relevance_score=score,
                    metadata={
                        "query": query,
                        "source": "club_database",
                        "tool_used": "club_search_tool",
                        "category": category,
                        "results_count": 1
                    }
                )]
            
            elif isinstance(results, list):
                # Multiple results in list format
                combined_content = ""
                total_score = 0.0
                
                for i, result in enumerate(results):
                    # Extract content and score
                    if isinstance(result, dict):
                        content = result.get('content', result.get('text', str(result)))
                        score = result.get('score', result.get('relevance', 0.5))
                    else:
                        content = str(result)
                        score = 0.5
                    
                    combined_content += f"Result {i+1} (Relevance: {score:.2f}):\n{content}\n\n"
                    total_score += score
                
                avg_score = total_score / len(results) if results else 0.5
                
                return [ContextItem(
                    source="club_search",
                    content=combined_content.strip(),
                    relevance_score=avg_score,
                    metadata={
                        "query": query,
                        "source": "club_database",
                        "tool_used": "club_search_tool",
                        "category": category,
                        "results_count": len(results)
                    }
                )]
            
            else:
                # Unknown result format
                return [ContextItem(
                    source="club_search",
                    content=str(results),
                    relevance_score=0.5,
                    metadata={
                        "query": query,
                        "source": "club_database",
                        "tool_used": "club_search_tool",
                        "category": category,
                        "results_count": 1
                    }
                )]
            
        except Exception as e:
            error_msg = str(e)
            print(f"   ❌ Club search error: {error_msg[:100]}")
            logger.error(f"Club search error: {error_msg}")
            
            return [ContextItem(
                source="club_search",
                content=f"Club search failed for: {query}. Error: {error_msg[:100]}",
                relevance_score=0.1,
                metadata={
                    "error": error_msg, 
                    "query": query,
                    "results_count": 0
                }
            )]


def club_search_node(state: OrchestratorState) -> dict:
    """Gather club context before task execution"""
    plan = state["plan"]
    
    print("\n" + "="*60)
    print("👥 GATHERING CLUB CONTEXT")
    print("="*60)
    
    provider = ClubSearchProvider()
    all_context = []
    
    # Search for each club query (limit to 2 queries)
    for query in plan.club_queries[:2]:
        context_items = provider.search(query)
        all_context.extend(context_items)
        if context_items:
            print(f"   Search query: '{query}' → {len(context_items[0].content)} chars")
    
    # Combine context
    combined = "\n\n".join([
        f"[Club Search: '{item.metadata.get('query', 'unknown')}']\n{item.content}"
        for item in sorted(all_context, key=lambda x: x.relevance_score, reverse=True)
    ])
    
    print(f"   Total club context gathered: {len(combined)} characters")
    logger.info(f"Club context gathered: {len(all_context)} items, {len(combined)} chars")
    
    return {
        "club_context": all_context,
        "combined_context": combined
    }


# 5.4 Mixed Context Gathering - NEW
def gather_mixed_context_node(state: OrchestratorState) -> dict:
    """Gather context from multiple sources for mixed queries"""
    plan = state["plan"]
    
    print("\n" + "="*60)
    print("🔀 GATHERING MIXED CONTEXT")
    print("="*60)
    
    all_contexts = []
    combined_parts = []
    
    # Gather web context if needed
    if plan.search_queries:
        print("\n  → Gathering web context...")
        web_result = web_search_node(state)
        all_contexts.extend(web_result.get("web_context", []))
        if web_result.get("combined_context"):
            combined_parts.append(web_result["combined_context"])
    
    # Gather RAG context if needed
    if plan.rag_queries:
        print("\n  → Gathering RAG context...")
        rag_result = rag_search_node(state)
        all_contexts.extend(rag_result.get("rag_context", []))
        if rag_result.get("combined_context"):
            combined_parts.append(rag_result["combined_context"])
    
    # Gather club context if needed
    if plan.club_queries:
        print("\n  → Gathering club context...")
        club_result = club_search_node(state)
        all_contexts.extend(club_result.get("club_context", []))
        if club_result.get("combined_context"):
            combined_parts.append(club_result["combined_context"])
    
    # Sort by relevance and combine
    all_contexts.sort(key=lambda x: x.relevance_score, reverse=True)
    
    # Take top contexts within budget (limit to 3000 chars total)
    combined = "\n\n".join(combined_parts)[:3000]
    
    print(f"\n   ✅ Total mixed context gathered: {len(combined)} characters")
    logger.info(f"Mixed context gathered: {len(all_contexts)} items from {len(combined_parts)} sources")
    
    return {
        "web_context": [c for c in all_contexts if c.source == "web_search"],
        "rag_context": [c for c in all_contexts if c.source == "rag"],
        "club_context": [c for c in all_contexts if c.source == "club_search"],
        "combined_context": combined
    }


# ============================================================================
# 6. GITHUB WORKER
# ============================================================================
GITHUB_TOOLS = [
    "create_repository",
    "get_file_contents", 
    "create_or_update_file",
    "create_pull_request",
    "list_pull_requests",
    "update_pull_request",
    "search_repositories",
    "get_me"
]


class GitHubWorker:
    """Worker for GitHub operations with only 7 essential tools"""
    
    async def execute(self, task: dict, context: str = "") -> TaskResult:
        """Execute a GitHub task, optionally with context"""
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from langchain.agents import create_agent
        
        task_id = task["id"]
        description = task.get("description", "")
        
        print(f"\n  🛠️ GITHUB_WORKER: Executing Task {task_id}")
        print(f"     Description: {description}")
        
        if context:
            print(f"     With context: {len(context)} chars")
        
        logger.info(f"GitHub worker executing task {task_id}")
        
        try:
            github_pat = os.getenv("GITHUB_PAT")
            
            if not github_pat:
                logger.error("GITHUB_PAT not set")
                return TaskResult(
                    task_id=task_id,
                    worker_type="github",
                    success=False,
                    output="GitHub PAT not configured. Set GITHUB_PAT environment variable.",
                    used_context=bool(context)
                )
            
            client = MultiServerMCPClient({
                "github": {
                    "transport": "http",
                    "url": "https://api.githubcopilot.com/mcp/",
                    "headers": {"Authorization": f"Bearer {github_pat}"}
                }
            })
            
            # Get all tools from MCP
            all_tools = await client.get_tools()
            
            # Filter to only our 7 essential tools
            filtered_tools = []
            for tool in all_tools:
                if tool.name in GITHUB_TOOLS:
                    filtered_tools.append(tool)
            
            if not filtered_tools:
                logger.warning("No GitHub tools available")
                return TaskResult(
                    task_id=task_id,
                    worker_type="github",
                    success=False,
                    output="No GitHub tools available",
                    used_context=bool(context)
                )
            
            # Create agent with filtered tools
            agent = create_agent(llm, filtered_tools)
            
            # Build prompt with context if available
            if context:
                prompt = f"""
GitHub Task: {description}

Context from search (use if relevant):
{context[:800]}

Original query: {task.get('user_query', '')}

Please use appropriate GitHub tools to complete this task.
Use the context above if it helps understand what needs to be done.
"""
            else:
                prompt = f"""
GitHub Task: {description}

Original query: {task.get('user_query', '')}

Please use appropriate GitHub tools to complete this task.
"""
            
            response = await agent.ainvoke({
                "messages": [{"role": "user", "content": prompt}]
            })
            
            # Extract output
            output = ""
            if "messages" in response:
                for msg in reversed(response["messages"]):
                    if hasattr(msg, 'content') and msg.content:
                        output = msg.content
                        break
            
            if not output:
                output = str(response)
            
            print(f"     ✅ Task completed")
            logger.info(f"GitHub task {task_id} completed successfully")
            
            return TaskResult(
                task_id=task_id,
                worker_type="github",
                success=True,
                output=output,
                used_context=bool(context)
            )
            
        except Exception as e:
            error_msg = str(e)
            print(f"     ❌ Error: {error_msg[:100]}")
            logger.error(f"GitHub task {task_id} failed: {error_msg}")
            
            return TaskResult(
                task_id=task_id,
                worker_type="github",
                success=False,
                output=f"GitHub operation failed: {error_msg}",
                used_context=bool(context),
                error=error_msg
            )


def github_worker_node(payload: dict) -> dict:
    """GitHub worker node"""
    import asyncio
    
    task_data = payload["task"]
    context = payload.get("context", "")
    task_data["user_query"] = payload.get("user_query", "")
    
    worker = GitHubWorker()
    result = asyncio.run(worker.execute(task_data, context))
    
    return {"results": [result]}


# ============================================================================
# 7. GOOGLE WORKSPACE WORKER
# ============================================================================
class GoogleWorkspaceWorker:
    """Worker for Google Workspace operations"""
    
    async def execute(self, task: dict, context: str = "") -> TaskResult:
        """Execute a Google Workspace task"""
        task_id = task["id"]
        description = task.get("description", "")
        google_service = task.get("google_service", "")
        
        print(f"\n  🚀 GOOGLE_WORKSPACE_WORKER: Executing Task {task_id}")
        print(f"     Service: {google_service}")
        print(f"     Description: {description}")
        
        if context:
            print(f"     With context: {len(context)} chars")
        
        logger.info(f"Google Workspace worker executing task {task_id} for service {google_service}")
        
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            from langchain.agents import create_agent
            
            # Check required environment variables
            google_client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
            google_client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
            
            if not google_client_id or not google_client_secret:
                logger.error("Google OAuth credentials not configured")
                return TaskResult(
                    task_id=task_id,
                    worker_type=f"google_{google_service}",
                    success=False,
                    output="Google OAuth credentials not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET.",
                    used_context=bool(context)
                )
            
            # Create MCP client for HTTP transport
            client = MultiServerMCPClient({
                "google_workspace": {
                    "transport": "http",
                    "url": "http://localhost:8000/mcp/",
                    "headers": {}
                }
            })
            
            # Get all tools from Google Workspace MCP
            all_tools = await client.get_tools()
            
            if not all_tools:
                logger.warning("No Google Workspace tools available")
                return TaskResult(
                    task_id=task_id,
                    worker_type=f"google_{google_service}",
                    success=False,
                    output="No Google Workspace tools available. Ensure the Google Workspace MCP server is running.",
                    used_context=bool(context)
                )
            
            # Filter tools by service if specified
            if google_service and google_service != "all_google":
                filtered_tools = []
                for tool in all_tools:
                    if google_service in tool.name:
                        filtered_tools.append(tool)
            else:
                filtered_tools = all_tools
            
            if not filtered_tools:
                logger.warning(f"No tools available for service: {google_service}")
                return TaskResult(
                    task_id=task_id,
                    worker_type=f"google_{google_service}",
                    success=False,
                    output=f"No tools available for Google service: {google_service}",
                    used_context=bool(context)
                )
            
            # Create agent with filtered tools
            agent = create_agent(llm, filtered_tools)
            
            # Build prompt with context if available
            if context:
                prompt = f"""
Google Workspace Task ({google_service}): {description}

Context from search (use if relevant):
{context[:800]}

Original query: {task.get('user_query', '')}

Please use appropriate Google Workspace tools to complete this task.
Use the context above if it helps understand what needs to be done.
"""
            else:
                prompt = f"""
Google Workspace Task ({google_service}): {description}

Original query: {task.get('user_query', '')}

Please use appropriate Google Workspace tools to complete this task.
"""
            
            response = await agent.ainvoke({
                "messages": [{"role": "user", "content": prompt}]
            })
            
            # Extract output
            output = ""
            if "messages" in response:
                for msg in reversed(response["messages"]):
                    if hasattr(msg, 'content') and msg.content:
                        output = msg.content
                        break
            
            if not output:
                output = str(response)
            
            print(f"     ✅ Task completed")
            logger.info(f"Google Workspace task {task_id} completed successfully")
            
            return TaskResult(
                task_id=task_id,
                worker_type=f"google_{google_service}",
                success=True,
                output=output,
                used_context=bool(context)
            )
            
        except Exception as e:
            error_msg = str(e)
            print(f"     ❌ Error: {error_msg[:100]}")
            logger.error(f"Google Workspace task {task_id} failed: {error_msg}")
            
            return TaskResult(
                task_id=task_id,
                worker_type=f"google_{google_service}",
                success=False,
                output=f"Google Workspace operation failed: {error_msg}",
                used_context=bool(context),
                error=error_msg
            )


def google_workspace_worker_node(payload: dict) -> dict:
    """Google Workspace worker node"""
    import asyncio
    
    task_data = payload["task"]
    context = payload.get("context", "")
    task_data["user_query"] = payload.get("user_query", "")
    
    worker = GoogleWorkspaceWorker()
    result = asyncio.run(worker.execute(task_data, context))
    
    return {"results": [result]}


# ============================================================================
# 8. CONVERSATIONAL WORKER
# ============================================================================
class ConversationalWorker:
    """Worker for conversational tasks with context support"""
    
    def execute(self, task: dict, user_query: str, context: str = "") -> TaskResult:
        """Execute a conversational task, optionally with context"""
        task_id = task["id"]
        
        print(f"\n  💬 CONVERSATIONAL_WORKER: Executing Task {task_id}")
        if context:
            print(f"     With context: {len(context)} chars")
        
        logger.info(f"Conversational worker executing task {task_id}")
        
        try:
            # Build prompt with context if available
            if context:
                prompt = f"""
User Query: {user_query}

Context from search:
{context}

Task: {task.get('description', 'Respond conversationally')}

Please respond using this context if helpful.
If context isn't relevant to the conversation, you can ignore it.
"""
            else:
                prompt = f"""
User Query: {user_query}

Task: {task.get('description', 'Respond conversationally')}

Provide a helpful, conversational response.
"""
            
            messages = [
                SystemMessage(content="You are a helpful assistant. Provide clear, concise, and accurate responses."),
                HumanMessage(content=prompt)
            ]
            
            response = llm.invoke(messages)
            
            print(f"     ✅ Response generated")
            logger.info(f"Conversational task {task_id} completed successfully")
            
            return TaskResult(
                task_id=task_id,
                worker_type="conversational",
                success=True,
                output=response.content,
                used_context=bool(context)
            )
            
        except Exception as e:
            error_msg = str(e)
            print(f"     ❌ Error: {error_msg[:100]}")
            logger.error(f"Conversational task {task_id} failed: {error_msg}")
            
            return TaskResult(
                task_id=task_id,
                worker_type="conversational",
                success=False,
                output=f"Failed to generate response: {error_msg}",
                used_context=bool(context),
                error=error_msg
            )


def conversational_worker_node(payload: dict) -> dict:
    """Conversational worker node"""
    task_data = payload["task"]
    user_query = payload["user_query"]
    context = payload.get("context", "")
    
    worker = ConversationalWorker()
    result = worker.execute(task_data, user_query, context)
    
    return {"results": [result]}


# ============================================================================
# 9. TASK EXECUTOR - Routes tasks to workers with context
# ============================================================================
def fanout_to_workers(state: OrchestratorState):
    """Execute tasks, providing context where needed"""
    print(f"\n⚡ EXECUTING TASKS")
    print("="*40)
    
    logger.info(f"Fanning out {len(state['tasks'])} tasks to workers")
    
    sends = []
    context = state.get("combined_context", "")
    
    for task in state["tasks"]:
        # Prepare payload
        payload = {
            "task": task.model_dump(),
            "user_query": state["user_query"]
        }
        
        # Add context if task requires it and we have context
        if task.requires_context and context:
            payload["context"] = context
        
        # Route to appropriate worker
        if task.worker_type == "github":
            sends.append(Send("github_worker", payload))
            print(f"  → Task {task.id}: {task.title}")
            print(f"     Worker: GitHub | Context: {'Yes' if task.requires_context and context else 'No'}")
        elif task.worker_type.startswith("google_") or task.google_service:
            sends.append(Send("google_workspace_worker", payload))
            print(f"  → Task {task.id}: {task.title}")
            print(f"     Worker: Google Workspace | Service: {task.google_service or task.worker_type}")
            print(f"     Context: {'Yes' if task.requires_context and context else 'No'}")
        else:
            sends.append(Send("conversational_worker", payload))
            print(f"  → Task {task.id}: {task.title}")
            print(f"     Worker: Conversational | Context: {'Yes' if task.requires_context and context else 'No'}")
    
    logger.info(f"Created {len(sends)} send operations")
    
    return sends


# ============================================================================
# 10. RESULTS AGGREGATOR
# ============================================================================
def results_aggregator_node(state: OrchestratorState) -> dict:
    """Aggregate results from all workers"""
    results = state.get("results", [])
    
    print("\n" + "="*60)
    print("📦 AGGREGATING RESULTS")
    print("="*60)
    
    print(f"Total tasks executed: {len(results)}")
    logger.info(f"Aggregating {len(results)} task results")
    
    for result in results:
        status = "✅" if result.success else "❌"
        context_marker = "📚" if result.used_context else ""
        print(f"  {status}{context_marker} Task {result.task_id} ({result.worker_type}): {len(result.output)} chars")
        if not result.success and result.error:
            print(f"     Error: {result.error[:100]}...")
    
    if not results:
        logger.warning("No task results to aggregate")
        return {"final_response": "No tasks were executed."}
    
    # If only one result, use it directly
    if len(results) == 1:
        logger.info("Single result, using directly")
        return {"final_response": results[0].output}
    
    # Combine multiple results
    results_text = "\n\n".join([
        f"[{r.worker_type.upper()}] {r.output[:400]}..."
        for r in results
    ])
    
    prompt = f"""
Original Query: {state['user_query']}

Results from different workers:
{results_text}

Provide a coherent final response that addresses the user's original query.
Integrate information from different services smoothly.
Be concise and helpful.
"""
    
    messages = [
        SystemMessage(content="You are a helpful assistant that integrates results from multiple sources."),
        HumanMessage(content=prompt)
    ]
    
    response = llm.invoke(messages)
    
    logger.info("Results aggregated successfully")
    
    return {"final_response": response.content}


# ============================================================================
# 11. BUILD THE SMART GRAPH - FIXED
# ============================================================================
def build_smart_orchestrator():
    """Build the intelligent graph with multiple context providers"""
    g = StateGraph(OrchestratorState)
    
    # Add nodes
    g.add_node("planning", planning_agent_node)
    g.add_node("web_search", web_search_node)
    g.add_node("rag_search", rag_search_node)
    g.add_node("club_search", club_search_node)
    g.add_node("gather_mixed_context", gather_mixed_context_node)  # NEW
    g.add_node("execute_tasks", lambda s: s)  # Pass-through node
    g.add_node("github_worker", github_worker_node)
    g.add_node("google_workspace_worker", google_workspace_worker_node)
    g.add_node("conversational_worker", conversational_worker_node)
    g.add_node("aggregator", results_aggregator_node)
    
    # Start with planning
    g.add_edge(START, "planning")
    
    # After planning, decide which context provider to use
    g.add_conditional_edges(
        "planning",
        route_after_planning,
        {
            "web_search": "web_search",
            "rag_search": "rag_search",
            "club_search": "club_search",
            "gather_mixed_context": "gather_mixed_context",  # NEW
            "execute_tasks": "execute_tasks"
        }
    )
    
    # After context gathering, go to task execution
    g.add_edge("web_search", "execute_tasks")
    g.add_edge("rag_search", "execute_tasks")
    g.add_edge("club_search", "execute_tasks")
    g.add_edge("gather_mixed_context", "execute_tasks")  # NEW
    
    # From execution, fanout to workers
    g.add_conditional_edges(
        "execute_tasks",
        fanout_to_workers, 
        {
            "github_worker": "github_worker",
            "google_workspace_worker": "google_workspace_worker",
            "conversational_worker": "conversational_worker"
        }
    )
    
    # Workers to aggregator
    g.add_edge("github_worker", "aggregator")
    g.add_edge("google_workspace_worker", "aggregator")
    g.add_edge("conversational_worker", "aggregator")
    
    # Aggregator to end
    g.add_edge("aggregator", END)
    
    logger.info("Smart orchestrator graph built successfully")
    
    return g.compile()


# ============================================================================
# 12. MAIN ORCHESTRATOR CLASS
# ============================================================================
class SmartOrchestrator:
    """Smart orchestrator with multiple context providers"""
    
    def __init__(self):
        self.graph = build_smart_orchestrator()
        print("\n" + "="*60)
        print("✅ ENHANCED SMART ORCHESTRATOR INITIALIZED")
        print("="*60)
        print("Features:")
        print("  • Wikipedia web search for factual context")
        print("  • RAG search for internal documentation")
        print("  • Club search for social/club information")
        print("  • Mixed context support for complex queries")
        print("  • GitHub worker with 7 essential tools")
        print("  • Google Workspace worker (Gmail, Calendar, Drive, Docs, etc.)")
        print("  • Conversational worker with context support")
        print("  • Intelligent planning agent")
        print("  • Comprehensive logging")
        print("\n📋 Required environment variables:")
        print("  • GROQ_API_KEY: For LLM (required)")
        print("  • GITHUB_PAT: For GitHub operations (optional)")
        print("  • GOOGLE_OAUTH_CLIENT_ID: For Google Workspace (optional)")
        print("  • GOOGLE_OAUTH_CLIENT_SECRET: For Google Workspace (optional)")
        print("="*60)
        logger.info("SmartOrchestrator initialized")
    
    def process(self, user_query: str, conversation_history: List[str] = None) -> dict:
        """Process a query through the orchestrator"""
        print(f"\n🚀 PROCESSING: {user_query}")
        logger.info(f"Processing query: {user_query}")
        
        # Validate query
        if not user_query or not user_query.strip():
            logger.warning("Empty query received")
            return {
                "success": False,
                "response": "Please provide a valid query.",
                "metadata": {"error": "Empty query"}
            }
        
        if len(user_query) > 5000:
            logger.warning("Query too long")
            return {
                "success": False,
                "response": "Query is too long. Please keep it under 5000 characters.",
                "metadata": {"error": "Query too long"}
            }
        
        initial_state: OrchestratorState = {
            "user_query": user_query.strip(),
            "conversation_history": conversation_history or [],
            "plan": None,
            "web_context": [],
            "rag_context": [],
            "club_context": [],
            "combined_context": "",
            "tasks": [],
            "results": [],
            "final_response": ""
        }
        
        try:
            final_state = self.graph.invoke(initial_state)
            
            print("\n" + "="*60)
            print("🎉 PROCESSING COMPLETE!")
            print("="*60)
            
            # Analyze results
            results = final_state.get("results", [])
            successful = [r for r in results if r.success]
            used_context = [r for r in results if r.used_context]
            
            logger.info(f"Processing complete: {len(successful)}/{len(results)} tasks successful")
            
            return {
                "success": True,
                "response": final_state["final_response"],
                "metadata": {
                    "total_tasks": len(results),
                    "successful_tasks": len(successful),
                    "tasks_with_context": len(used_context),
                    "web_search_used": len(final_state.get("web_context", [])) > 0,
                    "rag_search_used": len(final_state.get("rag_context", [])) > 0,
                    "club_search_used": len(final_state.get("club_context", [])) > 0,
                    "workers_used": list(set([r.worker_type for r in results]))
                }
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"\n❌ Error: {error_msg}")
            logger.error(f"Processing error: {error_msg}", exc_info=True)
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "response": f"Orchestrator error: {error_msg}",
                "metadata": {"error": error_msg}
            }


# ============================================================================
# 13. TEST FUNCTION
# ============================================================================
def test_queries():
    """Test different query types"""
    orchestrator = SmartOrchestrator()
    
    test_cases = [
        # Web search queries
        ("What is LangGraph?", 
         "Should use web search only"),
        
        # RAG search queries
        ("What are our company's security policies?", 
         "Should use RAG search"),
        
        # Club search queries
        ("When is the next robotics club event?", 
         "Should use club search"),
        
        ("Who are the club coordinators?",
         "Should use club search"),
        
        # Mixed queries
        ("Search the web for AI trends and check our internal docs about it", 
         "Should use web + RAG (mixed)"),
        
        # Pure conversation
        ("Hello, how are you today?", 
         "Should use conversational worker"),
        
        # No context needed
        ("Say hello", 
         "Should use conversational worker, no context"),
    ]
    
    print("\n" + "="*60)
    print("🧪 TESTING ENHANCED ORCHESTRATOR")
    print("="*60)
    
    for query, description in test_cases:
        print(f"\n📝 Query: {query}")
        print(f"   Expected: {description}")
        print("-" * 40)
        
        result = orchestrator.process(query)
        
        if result["success"]:
            meta = result["metadata"]
            print(f"   ✅ Success!")
            print(f"   Web search used: {meta['web_search_used']}")
            print(f"   RAG search used: {meta['rag_search_used']}")
            print(f"   Club search used: {meta['club_search_used']}")
            print(f"   Workers used: {meta['workers_used']}")
            print(f"   Tasks: {meta['total_tasks']} total, {meta['successful_tasks']} successful")
            print(f"   Response: {result['response'][:100]}...")
        else:
            print(f"   ❌ Failed: {result['response']}")


# ============================================================================
# 14. INTERACTIVE MODE
# ============================================================================
def interactive_mode():
    """Interactive mode"""
    print("\n" + "="*60)
    print("🤖 ENHANCED SMART ORCHESTRATOR")
    print("="*60)
    print("Flow: Planning → Context Search → Workers → Response")
    print("\nContext Providers:")
    print("  • 🌐 Web Search (Wikipedia)")
    print("  • 📚 RAG Search (Internal docs)")
    print("  • 👥 Club Search (Club info)")
    print("  • 🔀 Mixed Context (Multiple sources)")
    print("\nWorkers:")
    print("  • 🛠️  GitHub")
    print("  • 🚀 Google Workspace")
    print("  • 💬 Conversational")
    print("="*60)
    print("Commands: 'test', 'quit', 'exit', 'q'")
    print("="*60)
    
    orchestrator = SmartOrchestrator()
    conversation = []
    
    while True:
        try:
            query = input("\n💬 Query: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 Goodbye!")
            break
        
        if not query:
            continue
            
        if query.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        
        if query.lower() == 'test':
            test_queries()
            continue
        
        result = orchestrator.process(query, conversation)
        
        # Update conversation
        conversation.append(f"User: {query}")
        if result["success"]:
            conversation.append(f"Assistant: {result['response'][:100]}...")
        
        print(f"\n{'='*60}")
        print("🤖 FINAL RESPONSE:")
        print(f"{'='*60}")
        print(result["response"])
        print(f"{'='*60}")
        
        if result["success"]:
            meta = result["metadata"]
            print(f"\n📊 Metadata:")
            print(f"  Web search: {'Yes' if meta['web_search_used'] else 'No'}")
            print(f"  RAG search: {'Yes' if meta['rag_search_used'] else 'No'}")
            print(f"  Club search: {'Yes' if meta['club_search_used'] else 'No'}")
            print(f"  Workers: {', '.join(meta['workers_used'])}")
            print(f"  Tasks: {meta['total_tasks']} total, {meta['successful_tasks']} successful")


# ============================================================================
# MAIN EXECUTION
# ============================================================================
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_queries()
    else:
        interactive_mode()