"""
smart_orchestrator_improved.py
PRODUCTION VERSION - Fully Async Implementation

Key improvements:
- MCP clients initialized once and reused
- Connection pooling for better performance
- Proper async context management throughout
- Graceful cleanup on shutdown
- Production-ready async patterns
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
import atexit

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
# MCP CLIENT POOL - SINGLETON PATTERN
# ============================================================================
class MCPClientPool:
    """
    Singleton class to manage MCP client connections
    Clients are initialized once and reused across all nodes
    """
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MCPClientPool, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not MCPClientPool._initialized:
            self.github_client = None
            self.rag_client = None
            self.google_workspace_client = None
            self._lock = asyncio.Lock()
            MCPClientPool._initialized = True
            logger.info("MCPClientPool initialized")
    
    async def get_github_client(self):
        """Get or create GitHub MCP client"""
        if self.github_client is not None:
            logger.debug("Reusing existing GitHub client")
            return self.github_client
        
        async with self._lock:
            # Double-check after acquiring lock
            if self.github_client is not None:
                return self.github_client
            
            logger.info("Initializing GitHub MCP client...")
            from langchain_mcp_adapters.client import MultiServerMCPClient
            
            github_pat = os.getenv("GITHUB_PAT")
            if not github_pat:
                logger.error("GITHUB_PAT not set")
                raise ValueError("GITHUB_PAT environment variable not set")
            
            self.github_client = MultiServerMCPClient({
                "github": {
                    "transport": "http",
                    "url": "https://api.githubcopilot.com/mcp/",
                    "headers": {"Authorization": f"Bearer {github_pat}"}
                }
            })
            
            logger.info("✅ GitHub MCP client initialized and cached")
            return self.github_client
    
    async def get_rag_client(self):
        """Get or create RAG MCP client - STDIO transport for local RAG server"""
        if self.rag_client is not None:
            logger.debug("Reusing existing RAG client")
            return self.rag_client
        
        async with self._lock:
            if self.rag_client is not None:
                return self.rag_client
            
            logger.info("Initializing RAG MCP client with STDIO transport...")
            from langchain_mcp_adapters.client import MultiServerMCPClient
            
            # Use stdio transport, not HTTP
            self.rag_client = MultiServerMCPClient({
                "rag_server": {
                    "command": "python",
                    "args": ["-m", "mcp_servers.rag_server"],  # Use module path
                    "transport": "stdio",
                    "env": {
                        "SUPABASE_URL": os.getenv("SUPABASE_URL", ""),
                        "SUPABASE_SERVICE_KEY": os.getenv("SUPABASE_SERVICE_KEY", ""),
                        "EMBEDDING_DIM": os.getenv("EMBEDDING_DIM", "384"),
                        "PYTHONPATH": os.getenv("PYTHONPATH", os.getcwd())
                    }
                }
            })
            
            logger.info("✅ RAG MCP client initialized and cached with STDIO transport")
            return self.rag_client
        
    async def get_google_workspace_client(self):
        """Get or create Google Workspace MCP client"""
        if self.google_workspace_client is not None:
            logger.debug("Reusing existing Google Workspace client")
            return self.google_workspace_client
        
        async with self._lock:
            # Double-check after acquiring lock
            if self.google_workspace_client is not None:
                return self.google_workspace_client
            
            logger.info("Initializing Google Workspace MCP client...")
            from langchain_mcp_adapters.client import MultiServerMCPClient
            
            google_client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
            google_client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
            
            if not google_client_id or not google_client_secret:
                logger.error("Google OAuth credentials not configured")
                raise ValueError("GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set")
            
            self.google_workspace_client = MultiServerMCPClient({
                "google_workspace": {
                    "transport": "http",
                    "url": "http://localhost:8001/mcp/",
                    "headers": {}
                }
            })
            
            logger.info("✅ Google Workspace MCP client initialized and cached")
            return self.google_workspace_client
        
    async def ensure_rag_server_ready(self) -> bool:
        """Ensure RAG server is running and responsive"""
        try:
            client = await self.get_rag_client()
            
            # Test connection with a simple query
            all_tools = await asyncio.wait_for(client.get_tools(), timeout=5.0)
            
            if any(tool.name == "retrieve_context" for tool in all_tools):
                logger.info("✅ RAG server is ready")
                return True
            else:
                logger.warning("⚠️ RAG server running but retrieve_context tool not found")
                return False
                
        except Exception as e:
            logger.error(f"❌ RAG server not ready: {e}")
            return False
        
    async def cleanup(self):
        """Cleanup all client connections"""
        logger.info("Cleaning up MCP client connections...")
        
        # Close clients if they have cleanup methods
        clients = [
            ("GitHub", self.github_client),
            ("RAG", self.rag_client),
            ("Google Workspace", self.google_workspace_client)
        ]
        
        for name, client in clients:
            if client is not None:
                try:
                    if hasattr(client, 'close'):
                        await client.close()
                    elif hasattr(client, 'cleanup'):
                        await client.cleanup()
                    logger.info(f"✅ {name} client closed")
                except Exception as e:
                    logger.error(f"Error closing {name} client: {e}")
        
        # Reset clients
        self.github_client = None
        self.rag_client = None
        self.google_workspace_client = None
        
        logger.info("MCP clients cleanup complete")


# Global client pool instance
mcp_pool = MCPClientPool()


# Register cleanup on exit
def cleanup_on_exit():
    """Cleanup function to run on program exit"""
    try:
        asyncio.run(mcp_pool.cleanup())
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

atexit.register(cleanup_on_exit)


# ============================================================================
# MODELS
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
    requires_context: bool = False
    context_type: Optional[Literal["web", "rag", "club"]] = None
    google_service: Optional[str] = None


class ExecutionPlan(BaseModel):
    """Intelligent execution plan"""
    needs_context: bool = False
    context_type: Optional[Literal["web", "rag", "club", "mixed"]] = None
    reasoning: str
    tasks: List[WorkerTask] = Field(default_factory=list)
    search_queries: List[str] = Field(default_factory=list)
    rag_queries: List[str] = Field(default_factory=list)
    club_queries: List[str] = Field(default_factory=list)


class TaskResult(BaseModel):
    """Result from task execution"""
    task_id: int
    worker_type: str
    success: bool
    output: str
    used_context: bool = False
    error: Optional[str] = None


class OrchestratorState(TypedDict):
    """Enhanced state with context support"""
    user_query: str
    conversation_history: List[str]
    plan: Optional[ExecutionPlan]
    web_context: List[ContextItem]
    rag_context: List[ContextItem]
    club_context: List[ContextItem]
    combined_context: str
    tasks: List[WorkerTask]
    results: Annotated[List[TaskResult], operator.add]
    final_response: str


# ============================================================================
# LLM & TOOLS INITIALIZATION
# ============================================================================
llm = ChatGroq(
    model="moonshotai/kimi-k2-instruct-0905",
    temperature=0.1,
    api_key=os.getenv("GROQ_API_KEY")
)

search_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
web_search_agent = create_agent(llm, tools=[search_tool])

print("✅ LLM and Wikipedia search initialized")


# ============================================================================
# PLANNING AGENT
# ============================================================================
PLANNING_SYSTEM = """You are an intelligent planning agent that decides:
1. Does this query need context from web search, RAG, or club search?
2. Which workers are needed to execute the actual tasks?

Context Types:
- web: For general knowledge, Wikipedia-style information
- rag: For internal documents, research papers, uploaded content
- club: For club-specific information (events, announcements, coordinators)
- mixed: When multiple context sources are needed
- null: When no additional context is needed

Workers Available:
- conversational: General chat, explanations, analysis
- github: GitHub operations (repos, PRs, files)
- calendar/gmail: Google Workspace operations

Analyze the query and create an intelligent plan."""


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
        
        logger.info(f"Plan created: {plan.reasoning}")
        
        return {"plan": plan, "tasks": plan.tasks}
        
    except Exception as e:
        logger.error(f"Planning failed: {e}", exc_info=True)
        raise


def route_after_planning(state: OrchestratorState) -> str:
    """Route based on context needs"""
    plan = state.get("plan")
    
    if not plan or not plan.needs_context:
        return "execute_tasks"
    
    if plan.context_type == "web":
        return "web_search"
    elif plan.context_type == "rag":
        return "rag_search"
    elif plan.context_type == "club":
        return "club_search"
    elif plan.context_type == "mixed":
        return "gather_mixed_context"
    
    return "execute_tasks"


# ============================================================================
# CONTEXT PROVIDERS - ASYNC VERSIONS
# ============================================================================

class WebSearchProvider:
    """Gathers context from Wikipedia"""
    
    async def search(self, query: str) -> List[ContextItem]:
        """Perform Wikipedia search - ASYNC"""
        print(f"\n🌐 WEB SEARCH: Searching for '{query}'")
        logger.info(f"Web search for: {query}")
        
        try:
            # Run sync agent in executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: web_search_agent.invoke(
                    {"messages": [{"role": "user", "content": query}]}
                )
            )
            
            content = ""
            if "messages" in result:
                for msg in result["messages"]:
                    if hasattr(msg, 'content') and msg.content:
                        content = msg.content
                        break
            
            if not content:
                content = str(result)
            
            print(f"   ✅ Search completed: {len(content)} chars")
            
            return [ContextItem(
                source="web_search",
                content=content[:1000],
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
            
            return [ContextItem(
                source="web_search",
                content=f"Wikipedia search failed for: {query}. Error: {error_msg[:100]}",
                relevance_score=0.1,
                metadata={"error": error_msg, "query": query}
            )]


async def web_search_node(state: OrchestratorState) -> dict:
    """Gather web context before task execution - ASYNC"""
    plan = state["plan"]
    
    print("\n" + "="*60)
    print("🌐 GATHERING WEB CONTEXT FROM WIKIPEDIA")
    print("="*60)
    
    provider = WebSearchProvider()
    all_context = []
    
    # Search concurrently
    tasks = [provider.search(query) for query in plan.search_queries[:2]]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Web search error: {result}")
        else:
            all_context.extend(result)
    
    combined = "\n\n".join([
        f"[Web Search: '{item.metadata.get('query', 'unknown')}']\n{item.content}"
        for item in sorted(all_context, key=lambda x: x.relevance_score, reverse=True)
    ])
    
    print(f"   Total web context gathered: {len(combined)} characters")
    
    return {
        "web_context": all_context,
        "combined_context": combined
    }


class RagSearchProvider:
    """Gathers context from RAG MCP server - ASYNC with connection reuse and retry logic"""
    
    async def search(self, query: str, retries: int = 2) -> List[ContextItem]:
        """Perform RAG search using cached MCP client with retry logic"""
        print(f"\n📚 RAG SEARCH: Searching for '{query}'")
        logger.info(f"RAG search for: {query}")
        
        for attempt in range(retries + 1):
            try:
                # Get cached client from pool
                client = await mcp_pool.get_rag_client()
                
                # Get tools with timeout
                try:
                    all_tools = await asyncio.wait_for(client.get_tools(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"RAG client.get_tools() timeout (attempt {attempt + 1})")
                    if attempt < retries:
                        # Force reconnection on next attempt
                        mcp_pool.rag_client = None
                        continue
                    raise
                
                # Find retrieve_context tool
                retrieve_tool = None
                for tool_obj in all_tools:
                    if tool_obj.name == "retrieve_context":
                        retrieve_tool = tool_obj
                        break
                
                if not retrieve_tool:
                    logger.warning(f"RAG tool not found. Available: {[t.name for t in all_tools]}")
                    return [ContextItem(
                        source="rag",
                        content=f"RAG search tool not available. Please ensure the RAG server is running.",
                        relevance_score=0.1,
                        metadata={"error": "Tool not found", "query": query}
                    )]
                
                # Execute search with timeout
                try:
                    result = await asyncio.wait_for(
                        retrieve_tool.ainvoke({
                            "query": query, 
                            "top_k": 3,
                            "include_citations": False
                        }),
                        timeout=10.0
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"RAG search timeout (attempt {attempt + 1})")
                    if attempt < retries:
                        continue
                    raise
                
                # Extract output (your existing parsing logic)
                output = ""
                if isinstance(result, dict):
                    output = result.get("content") or result.get("text") or json.dumps(result, indent=2)
                elif hasattr(result, "content"):
                    output = result.content
                elif hasattr(result, "text"):
                    output = result.text
                else:
                    output = str(result)
                
                # Parse JSON if needed
                if output.startswith('{') and output.endswith('}'):
                    try:
                        response_data = json.loads(output)
                        if "chunks" in response_data:
                            chunks = response_data["chunks"]
                            formatted_chunks = []
                            for i, chunk in enumerate(chunks, 1):
                                formatted_chunks.append(
                                    f"Result {i} (score: {chunk.get('score', 0):.3f}):\n"
                                    f"Source: {chunk.get('source', 'unknown')}\n"
                                    f"{chunk.get('text', '')}\n"
                                )
                            output = "\n---\n".join(formatted_chunks)
                    except json.JSONDecodeError:
                        pass
                
                print(f"   ✅ RAG search completed: {len(output)} chars")
                
                return [ContextItem(
                    source="rag",
                    content=output[:1500],
                    relevance_score=0.85,
                    metadata={
                        "query": query,
                        "source": "rag_mcp",
                        "tool_used": "retrieve_context"
                    }
                )]
                
            except Exception as e:
                error_msg = str(e)
                if attempt < retries:
                    logger.warning(f"RAG search attempt {attempt + 1} failed: {error_msg[:100]}. Retrying...")
                    # Exponential backoff
                    await asyncio.sleep(1 * (2 ** attempt))
                    continue
                else:
                    print(f"   ❌ RAG search error after {retries + 1} attempts: {error_msg[:100]}")
                    logger.error(f"RAG search error: {error_msg}")
                    
                    return [ContextItem(
                        source="rag",
                        content=f"RAG search failed for: {query}. Please try again later.",
                        relevance_score=0.1,
                        metadata={"error": error_msg, "query": query}
                    )]

async def rag_search_node(state: OrchestratorState) -> dict:
    """Gather RAG context before task execution - ASYNC"""
    plan = state["plan"]
    
    print("\n" + "="*60)
    print("📚 GATHERING RAG CONTEXT")
    print("="*60)
    
    provider = RagSearchProvider()
    
    # Search concurrently
    tasks = [provider.search(query) for query in plan.rag_queries[:2]]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_context = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"RAG search error: {result}")
        else:
            all_context.extend(result)
    
    combined = "\n\n".join([
        f"[RAG Search: '{item.metadata.get('query', 'unknown')}']\n{item.content}"
        for item in sorted(all_context, key=lambda x: x.relevance_score, reverse=True)
    ])
    
    print(f"   Total RAG context gathered: {len(combined)} characters")
    
    return {
        "rag_context": all_context,
        "combined_context": combined
    }


class ClubSearchProvider:
    """Gathers context from club search tool"""
    
    async def search(self, query: str) -> List[ContextItem]:
        """Perform club search using the tool - ASYNC"""
        print(f"\n👥 CLUB SEARCH: Searching for '{query}'")
        logger.info(f"Club search for: {query}")
        
        try:
            # Extract category using LLM
            loop = asyncio.get_event_loop()
            category_response = await loop.run_in_executor(
                None,
                lambda: llm.invoke([
                    SystemMessage(content="You are a category classifier. Respond with only one word."),
                    HumanMessage(content=f"""Define the category from the following query for club search.
The category should be one of these: events, announcements, coordinators.
If not relevant to any category, respond with 'general'.

Query: {query}

Respond with ONLY the category name (one word).""")
                ])
            )
            
            category = category_response.content.strip().lower()
            valid_categories = ["events", "announcements", "coordinators", "general"]
            if category not in valid_categories:
                category = "general"
            
            print(f"   🏷️ Identified category: {category}")
            
            search_category = None if category == "general" else category
            
            # Use club search tool (run in executor if it's sync)
            results = await loop.run_in_executor(
                None,
                lambda: club_retriever.retrieve(
                    query=query,
                    category=search_category,  
                    top_k=3
                )
            )
            
            print(f"   ✅ Club search completed - found {len(results) if isinstance(results, list) else 'N/A'} results")
            
            if not results:
                return [ContextItem(
                    source="club_search",
                    content="No club information found for this query.",
                    relevance_score=0.0,
                    metadata={"query": query, "category": category, "results_count": 0}
                )]
            
            # Handle results
            if isinstance(results, dict):
                content = results.get('content', results.get('text', str(results)))
                score = results.get('score', results.get('relevance', 0.5))
                
                return [ContextItem(
                    source="club_search",
                    content=content,
                    relevance_score=score,
                    metadata={"query": query, "category": category, "results_count": 1}
                )]
            
            elif isinstance(results, list):
                combined_content = ""
                total_score = 0.0
                
                for i, result in enumerate(results):
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
                    metadata={"query": query, "category": category, "results_count": len(results)}
                )]
            
            else:
                return [ContextItem(
                    source="club_search",
                    content=str(results),
                    relevance_score=0.5,
                    metadata={"query": query, "category": category, "results_count": 1}
                )]
            
        except Exception as e:
            error_msg = str(e)
            print(f"   ❌ Club search error: {error_msg[:100]}")
            logger.error(f"Club search error: {error_msg}")
            
            return [ContextItem(
                source="club_search",
                content=f"Club search failed for: {query}. Error: {error_msg[:100]}",
                relevance_score=0.1,
                metadata={"error": error_msg, "query": query, "results_count": 0}
            )]


async def club_search_node(state: OrchestratorState) -> dict:
    """Gather club context before task execution - ASYNC"""
    plan = state["plan"]
    
    print("\n" + "="*60)
    print("👥 GATHERING CLUB CONTEXT")
    print("="*60)
    
    provider = ClubSearchProvider()
    
    # Search concurrently
    tasks = [provider.search(query) for query in plan.club_queries[:2]]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_context = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Club search error: {result}")
        else:
            all_context.extend(result)
    
    combined = "\n\n".join([
        f"[Club Search: '{item.metadata.get('query', 'unknown')}']\n{item.content}"
        for item in sorted(all_context, key=lambda x: x.relevance_score, reverse=True)
    ])
    
    print(f"   Total club context gathered: {len(combined)} characters")
    
    return {
        "club_context": all_context,
        "combined_context": combined
    }


async def gather_mixed_context_node(state: OrchestratorState) -> dict:
    """Gather context from multiple sources for mixed queries - ASYNC"""
    plan = state["plan"]
    
    print("\n" + "="*60)
    print("🔀 GATHERING MIXED CONTEXT")
    print("="*60)
    
    # Gather all contexts concurrently
    tasks = []
    
    if plan.search_queries:
        print("\n  → Gathering web context...")
        tasks.append(("web", web_search_node(state)))
    
    if plan.rag_queries:
        print("\n  → Gathering RAG context...")
        tasks.append(("rag", rag_search_node(state)))
    
    if plan.club_queries:
        print("\n  → Gathering club context...")
        tasks.append(("club", club_search_node(state)))
    
    # Execute all searches concurrently
    results = await asyncio.gather(*[task[1] for task in tasks], return_exceptions=True)
    
    all_contexts = []
    combined_parts = []
    web_ctx = []
    rag_ctx = []
    club_ctx = []
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Mixed context search error: {result}")
            continue
        
        source_type = tasks[i][0]
        
        if source_type == "web":
            web_ctx = result.get("web_context", [])
            all_contexts.extend(web_ctx)
        elif source_type == "rag":
            rag_ctx = result.get("rag_context", [])
            all_contexts.extend(rag_ctx)
        elif source_type == "club":
            club_ctx = result.get("club_context", [])
            all_contexts.extend(club_ctx)
        
        if result.get("combined_context"):
            combined_parts.append(result["combined_context"])
    
    all_contexts.sort(key=lambda x: x.relevance_score, reverse=True)
    combined = "\n\n".join(combined_parts)[:3000]
    
    print(f"\n   ✅ Total mixed context gathered: {len(combined)} characters")
    
    return {
        "web_context": web_ctx,
        "rag_context": rag_ctx,
        "club_context": club_ctx,
        "combined_context": combined
    }


# ============================================================================
# WORKERS - ASYNC VERSIONS
# ============================================================================

GITHUB_TOOLS = [
    "create_repository", "get_file_contents", "create_or_update_file",
    "create_pull_request", "list_pull_requests", "update_pull_request",
    "search_repositories", "get_me"
]


class GitHubWorker:
    """Worker for GitHub operations - ASYNC with connection reuse"""
    
    async def execute(self, task: dict, context: str = "") -> TaskResult:
        """Execute a GitHub task using cached MCP client"""
        from langchain.agents import create_agent
        
        task_id = task["id"]
        description = task.get("description", "")
        
        print(f"\n  🛠️ GITHUB_WORKER: Executing Task {task_id}")
        logger.info(f"GitHub worker executing task {task_id}")
        
        try:
            # Get cached client from pool
            client = await mcp_pool.get_github_client()
            
            # Get tools
            all_tools = await client.get_tools()
            
            # Filter to essential tools
            filtered_tools = [tool for tool in all_tools if tool.name in GITHUB_TOOLS]
            
            if not filtered_tools:
                logger.warning("No GitHub tools available")
                return TaskResult(
                    task_id=task_id,
                    worker_type="github",
                    success=False,
                    output="No GitHub tools available",
                    used_context=bool(context)
                )
            
            # Create agent
            agent = create_agent(llm, filtered_tools)
            
            # Build prompt
            if context:
                prompt = f"""
GitHub Task: {description}

Context from search (use if relevant):
{context[:800]}

Original query: {task.get('user_query', '')}

Please use appropriate GitHub tools to complete this task.
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


async def github_worker_node(payload: dict) -> dict:
    """GitHub worker node - ASYNC"""
    task_data = payload["task"]
    context = payload.get("context", "")
    task_data["user_query"] = payload.get("user_query", "")
    
    worker = GitHubWorker()
    result = await worker.execute(task_data, context)
    
    return {"results": [result]}


class GoogleWorkspaceWorker:
    """Worker for Google Workspace - ASYNC with connection reuse"""
    
    async def execute(self, task: dict, context: str = "") -> TaskResult:
        """Execute a Google Workspace task using cached MCP client"""
        from langchain.agents import create_agent
        
        task_id = task["id"]
        description = task.get("description", "")
        google_service = task.get("google_service", "")
        
        print(f"\n  🚀 GOOGLE_WORKSPACE_WORKER: Executing Task {task_id}")
        print(f"     Service: {google_service}")
        
        logger.info(f"Google Workspace worker executing task {task_id} for service {google_service}")
        
        try:
            # Get cached client from pool
            client = await mcp_pool.get_google_workspace_client()
            
            # Get tools
            all_tools = await client.get_tools()
            
            if not all_tools:
                logger.warning("No Google Workspace tools available")
                return TaskResult(
                    task_id=task_id,
                    worker_type=f"google_{google_service}",
                    success=False,
                    output="No Google Workspace tools available. Ensure the server is running.",
                    used_context=bool(context)
                )
            
            # Filter tools by service
            if google_service and google_service != "all_google":
                filtered_tools = []
                for tool in all_tools:
                    tool_name_lower = tool.name.lower()
                    service_lower = google_service.lower()
                    
                    if service_lower == "calendar":
                        if any(keyword in tool_name_lower for keyword in ["calendar", "event"]):
                            filtered_tools.append(tool)
                    elif service_lower == "gmail":
                        if service_lower in tool_name_lower:
                            filtered_tools.append(tool)
            else:
                filtered_tools = all_tools
            
            if not filtered_tools:
                return TaskResult(
                    task_id=task_id,
                    worker_type=f"google_{google_service}",
                    success=False,
                    output=f"No tools available for Google service: {google_service}",
                    used_context=bool(context)
                )
            
            # Create agent
            agent = create_agent(llm, filtered_tools)
            
            # Build prompt
            if context:
                prompt = f"""
Google Workspace Task ({google_service}): {description}

Context from search (use if relevant):
{context[:800]}

Original query: {task.get('user_query', '')}

Please use appropriate Google Workspace tools to complete this task.
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


async def google_workspace_worker_node(payload: dict) -> dict:
    """Google Workspace worker node - ASYNC"""
    task_data = payload["task"]
    context = payload.get("context", "")
    task_data["user_query"] = payload.get("user_query", "")
    
    worker = GoogleWorkspaceWorker()
    result = await worker.execute(task_data, context)
    
    return {"results": [result]}


class ConversationalWorker:
    """Worker for conversational tasks with context support"""
    
    async def execute(self, task: dict, user_query: str, context: str = "") -> TaskResult:
        """Execute a conversational task - ASYNC"""
        task_id = task["id"]
        
        print(f"\n  💬 CONVERSATIONAL_WORKER: Executing Task {task_id}")
        if context:
            print(f"     With context: {len(context)} chars")
        
        logger.info(f"Conversational worker executing task {task_id}")
        
        try:
            if context:
                prompt = f"""
User Query: {user_query}

Context from search:
{context}

Task: {task.get('description', 'Respond conversationally')}

Please respond using this context if helpful.
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
            
            # Run LLM in executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: llm.invoke(messages)
            )
            
            print(f"     ✅ Response generated")
            
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


async def conversational_worker_node(payload: dict) -> dict:
    """Conversational worker node - ASYNC"""
    task_data = payload["task"]
    user_query = payload["user_query"]
    context = payload.get("context", "")
    
    worker = ConversationalWorker()
    result = await worker.execute(task_data, user_query, context)
    
    return {"results": [result]}


# ============================================================================
# TASK EXECUTOR & AGGREGATOR
# ============================================================================

def fanout_to_workers(state: OrchestratorState):
    """Execute tasks, providing context where needed"""
    print(f"\n⚡ EXECUTING TASKS")
    print("="*40)
    
    logger.info(f"Fanning out {len(state['tasks'])} tasks to workers")
    
    sends = []
    context = state.get("combined_context", "")
    
    for task in state["tasks"]:
        payload = {
            "task": task.model_dump(),
            "user_query": state["user_query"]
        }
        
        if task.requires_context and context:
            payload["context"] = context
        
        if task.worker_type == "github":
            sends.append(Send("github_worker", payload))
        elif task.worker_type.startswith("google_") or task.google_service:
            sends.append(Send("google_workspace_worker", payload))
        else:
            sends.append(Send("conversational_worker", payload))
    
    return sends


async def results_aggregator_node(state: OrchestratorState) -> dict:
    """Aggregate results from all workers - ASYNC"""
    results = state.get("results", [])
    
    print("\n" + "="*60)
    print("📦 AGGREGATING RESULTS")
    print("="*60)
    
    print(f"Total tasks executed: {len(results)}")
    
    if not results:
        return {"final_response": "No tasks were executed."}
    
    if len(results) == 1:
        return {"final_response": results[0].output}
    
    results_text = "\n\n".join([
        f"[{r.worker_type.upper()}] {r.output[:400]}..."
        for r in results
    ])
    
    prompt = f"""
Original Query: {state['user_query']}

Results from different workers:
{results_text}

Provide a coherent final response that addresses the user's original query.
"""
    
    messages = [
        SystemMessage(content="You are a helpful assistant that integrates results from multiple sources."),
        HumanMessage(content=prompt)
    ]
    
    # Run LLM in executor
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: llm.invoke(messages)
    )
    
    return {"final_response": response.content}


# ============================================================================
# BUILD GRAPH
# ============================================================================

def build_smart_orchestrator():
    """Build the intelligent graph"""
    g = StateGraph(OrchestratorState)
    
    g.add_node("planning", planning_agent_node)
    g.add_node("web_search", web_search_node)
    g.add_node("rag_search", rag_search_node)
    g.add_node("club_search", club_search_node)
    g.add_node("gather_mixed_context", gather_mixed_context_node)
    g.add_node("execute_tasks", lambda s: s)
    g.add_node("github_worker", github_worker_node)
    g.add_node("google_workspace_worker", google_workspace_worker_node)
    g.add_node("conversational_worker", conversational_worker_node)
    g.add_node("aggregator", results_aggregator_node)
    
    g.add_edge(START, "planning")
    
    g.add_conditional_edges(
        "planning",
        route_after_planning,
        {
            "web_search": "web_search",
            "rag_search": "rag_search",
            "club_search": "club_search",
            "gather_mixed_context": "gather_mixed_context",
            "execute_tasks": "execute_tasks"
        }
    )
    
    g.add_edge("web_search", "execute_tasks")
    g.add_edge("rag_search", "execute_tasks")
    g.add_edge("club_search", "execute_tasks")
    g.add_edge("gather_mixed_context", "execute_tasks")
    
    g.add_conditional_edges(
        "execute_tasks",
        fanout_to_workers, 
        {
            "github_worker": "github_worker",
            "google_workspace_worker": "google_workspace_worker",
            "conversational_worker": "conversational_worker"
        }
    )
    
    g.add_edge("github_worker", "aggregator")
    g.add_edge("google_workspace_worker", "aggregator")
    g.add_edge("conversational_worker", "aggregator")
    g.add_edge("aggregator", END)
    
    return g.compile()


# ============================================================================
# ORCHESTRATOR CLASS - PRODUCTION ASYNC VERSION
# ============================================================================

class SmartOrchestrator:
    """Smart orchestrator with MCP client pooling - PRODUCTION ASYNC"""
    
    def __init__(self):
        self.graph = build_smart_orchestrator()
        print("\n" + "="*60)
        print("✅ ENHANCED SMART ORCHESTRATOR INITIALIZED (ASYNC)")
        print("="*60)
        print("🔧 Performance Improvements:")
        print("  • MCP client connection pooling")
        print("  • Clients initialized once and reused")
        print("  • Reduced connection overhead")
        print("  • Better resource management")
        print("  • Fully async execution")
        print("\n📋 Features:")
        print("  • Wikipedia web search")
        print("  • RAG search (internal docs)")
        print("  • Club search (club info)")
        print("  • Mixed context support")
        print("  • GitHub worker")
        print("  • Google Workspace worker")
        print("  • Conversational worker")
        print("="*60)
        logger.info("SmartOrchestrator initialized with async execution")
    
    async def process(self, user_query: str, conversation_history: List[str] = None) -> dict:
        """Process a query through the orchestrator - FULLY ASYNC"""
        print(f"\n🚀 PROCESSING: {user_query}")
        logger.info(f"Processing query: {user_query}")
        
        if not user_query or not user_query.strip():
            return {
                "success": False,
                "response": "Please provide a valid query.",
                "metadata": {"error": "Empty query"}
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
            # ✅ ASYNC: Use ainvoke instead of invoke
            final_state = await self.graph.ainvoke(initial_state)
            
            print("\n" + "="*60)
            print("🎉 PROCESSING COMPLETE!")
            print("="*60)
            
            results = final_state.get("results", [])
            successful = [r for r in results if r.success]
            used_context = [r for r in results if r.used_context]
            
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
            
            return {
                "success": False,
                "response": f"Orchestrator error: {error_msg}",
                "metadata": {"error": error_msg}
            }
    
    async def cleanup(self):
        """Cleanup MCP connections - ASYNC"""
        await mcp_pool.cleanup()


# ============================================================================
# INTERACTIVE MODE (CLI)
# ============================================================================

def interactive_mode():
    """Interactive mode - CLI wrapper around async orchestrator"""
    print("\n" + "="*60)
    print("🤖 ENHANCED SMART ORCHESTRATOR (PRODUCTION ASYNC)")
    print("="*60)
    print("✨ Now with full async execution for better performance!")
    print("="*60)
    
    orchestrator = SmartOrchestrator()
    conversation = []
    
    try:
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
            
            # Run async process in sync CLI context
            result = asyncio.run(orchestrator.process(query, conversation))
            
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
                print(f"  Workers: {', '.join(meta['workers_used'])}")
                print(f"  Tasks: {meta['total_tasks']} total, {meta['successful_tasks']} successful")
    
    finally:
        print("\n🧹 Cleaning up connections...")
        asyncio.run(orchestrator.cleanup())
        print("✅ Cleanup complete")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Run tests
        pass
    else:
        interactive_mode()
        
orchestrator = SmartOrchestrator()