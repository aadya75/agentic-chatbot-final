"""
Smart Orchestrator — Production Async Implementation

Key fixes in this version:
  1. RAG search now calls HybridRetrieval DIRECTLY instead of spawning
     an MCP subprocess. The subprocess approach was for Claude Desktop
     integration only — internally we just use the Python objects directly,
     exactly the same pattern already used for club search.
  2. fanout_to_workers now ALWAYS injects combined_context into every
     worker payload when context exists. Previously it only did so when
     task.requires_context=True, but the planner never reliably set that
     flag, so context was silently dropped.
  3. create_agent → create_react_agent (LangChain ≥ 0.2).
  4. atexit cleanup is safe on Windows when the event loop is closed.
"""

from __future__ import annotations

import asyncio
import atexit
import json
import logging
import operator
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated, List, Literal, Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper

try:
    from langgraph.prebuilt import create_react_agent
except ImportError:
    from langchain.agents import create_react_agent  # older fallback

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field

load_dotenv()

servers_dir = Path(__file__).resolve().parent.parent / "mcp_servers"

# ============================================================================
# LOGGING
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"orchestrator_{datetime.now():%Y%m%d}.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================================
# MCP CLIENT POOL — only used for GitHub and Google Workspace
# RAG is now called directly (no subprocess).
# ============================================================================


class MCPClientPool:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not MCPClientPool._initialized:
            self.github_client = None
            self.google_workspace_client = None
            self._lock = asyncio.Lock()
            MCPClientPool._initialized = True

    async def get_github_client(self):
        if self.github_client is not None:
            return self.github_client
        async with self._lock:
            if self.github_client is not None:
                return self.github_client
            from langchain_mcp_adapters.client import MultiServerMCPClient
            github_pat = os.getenv("GITHUB_PAT")
            if not github_pat:
                raise ValueError("GITHUB_PAT environment variable not set")
            self.github_client = MultiServerMCPClient({
                "github": {
                    "transport": "http",
                    "url": "https://api.githubcopilot.com/mcp/",
                    "headers": {"Authorization": f"Bearer {github_pat}"},
                }
            })
            logger.info("✅ GitHub MCP client initialised")
            return self.github_client

    async def get_google_workspace_client(self):
        if self.google_workspace_client is not None:
            return self.google_workspace_client
        async with self._lock:
            if self.google_workspace_client is not None:
                return self.google_workspace_client
            from langchain_mcp_adapters.client import MultiServerMCPClient
            if not os.getenv("GOOGLE_OAUTH_CLIENT_ID"):
                raise ValueError("GOOGLE_OAUTH_CLIENT_ID must be set")
            self.google_workspace_client = MultiServerMCPClient({
                "google_workspace": {
                    "transport": "http",
                    "url": "http://localhost:8001/mcp/",
                    "headers": {},
                }
            })
            logger.info("✅ Google Workspace MCP client initialised")
            return self.google_workspace_client

    async def cleanup(self):
        for name, client in [
            ("GitHub", self.github_client),
            ("Google Workspace", self.google_workspace_client),
        ]:
            if client is not None:
                try:
                    if hasattr(client, "close"):
                        await client.close()
                    elif hasattr(client, "cleanup"):
                        await client.cleanup()
                    logger.info(f"✅ {name} client closed")
                except Exception as exc:
                    logger.error(f"Error closing {name} client: {exc}")
        self.github_client = None
        self.google_workspace_client = None


mcp_pool = MCPClientPool()


def _cleanup_on_exit():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(mcp_pool.cleanup())
        else:
            loop.run_until_complete(mcp_pool.cleanup())
    except Exception as exc:
        logger.error(f"Error during atexit cleanup: {exc}")


atexit.register(_cleanup_on_exit)

# ============================================================================
# DIRECT RAG SERVICE — replaces the MCP subprocess approach
# ============================================================================

def _build_rag_retrieval_service():
    """
    Build HybridRetrieval directly from env vars.
    Returns None if Supabase credentials are missing.
    """
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_ANON_KEY", "")).strip()

    if not supabase_url or not supabase_key:
        logger.warning("⚠️  SUPABASE_URL / SUPABASE_SERVICE_KEY not set — user RAG disabled")
        return None

    try:
        from knowledge_engine.embedding_service import EmbeddingService
        from knowledge_engine.vector_store import SupabaseVectorStore
        from knowledge_engine.retrieval import HybridRetrieval

        embedding_service = EmbeddingService(
            embedding_dim=int(os.getenv("EMBEDDING_DIM", "384"))
        )
        vector_store = SupabaseVectorStore(
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            embedding_dim=int(os.getenv("EMBEDDING_DIM", "384")),
        )
        retrieval_service = HybridRetrieval(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )
        logger.info("✅ User RAG retrieval service ready (direct)")
        return retrieval_service
    except Exception as exc:
        logger.error(f"❌ Failed to build RAG retrieval service: {exc}")
        return None


_rag_retrieval_service = None


def get_rag_retrieval_service():
    """Lazy singleton for the user RAG retrieval service."""
    global _rag_retrieval_service
    if _rag_retrieval_service is None:
        _rag_retrieval_service = _build_rag_retrieval_service()
    return _rag_retrieval_service


# ============================================================================
# MODELS
# ============================================================================


class ContextItem(BaseModel):
    source: Literal["web_search", "rag", "conversation", "club_search"]
    content: str
    relevance_score: float = Field(ge=0, le=1)
    metadata: dict = Field(default_factory=dict)


class WorkerTask(BaseModel):
    id: int
    title: str
    worker_type: Literal["github", "conversational", "calendar", "gmail"] = "conversational"
    description: str
    parameters: dict = Field(default_factory=dict)
    requires_context: bool = False
    context_type: Optional[Literal["web", "rag", "club"]] = None
    google_service: Optional[str] = None


class ExecutionPlan(BaseModel):
    needs_context: bool = False
    context_type: Optional[Literal["web", "rag", "club", "mixed"]] = None
    reasoning: str
    tasks: List[WorkerTask] = Field(default_factory=list)
    search_queries: List[str] = Field(default_factory=list)
    rag_queries: List[str] = Field(default_factory=list)
    club_queries: List[str] = Field(default_factory=list)


class TaskResult(BaseModel):
    task_id: int
    worker_type: str
    success: bool
    output: str
    used_context: bool = False
    error: Optional[str] = None


class OrchestratorState(TypedDict):
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
# LLM
# ============================================================================

llm = ChatGroq(
    model="moonshotai/kimi-k2-instruct-0905",
    temperature=0.1,
    api_key=os.getenv("GROQ_API_KEY"),
)

_wiki_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
web_search_agent = create_react_agent(llm, tools=[_wiki_tool])

print("✅ LLM and Wikipedia search initialised")

# ============================================================================
# PLANNING
# ============================================================================

PLANNING_SYSTEM = """You are an intelligent planning agent that decides:
1. Does this query need context from web search, RAG, or club search?
2. Which workers are needed to execute the actual tasks?

Context Types:
- web   : General knowledge / Wikipedia-style information
- rag   : Internal documents, research papers, user-uploaded content
- club  : Club-specific information (events, announcements, coordinators)
- mixed : Multiple context sources needed
- null  : No additional context needed

Workers Available:
- conversational : General chat, explanations, analysis
- github         : GitHub operations (repos, PRs, files)
- calendar/gmail : Google Workspace operations

IMPORTANT: When context is needed, always set requires_context=true on
every task so the retrieved context is forwarded to the worker."""


def planning_agent_node(state: OrchestratorState) -> dict:
    print("\n" + "=" * 60)
    print("🤖 SMART PLANNING AGENT: Analysing query…")
    print("=" * 60)
    logger.info(f"Planning for query: {state['user_query']}")

    try:
        planner = llm.with_structured_output(ExecutionPlan)
        plan = planner.invoke([
            SystemMessage(content=PLANNING_SYSTEM),
            HumanMessage(content=(
                f"User Query: {state['user_query']}\n\n"
                "Analyse what context is needed (web, rag, club, mixed, or none).\n"
                "If context is needed, set needs_context=true and extract queries.\n"
                "Set requires_context=true on tasks that should use the retrieved context.\n"
                "Create tasks for the right workers."
            )),
        ])
        print(f"✅ Plan: context={plan.context_type}, reason={plan.reasoning}")
        logger.info(f"Plan created: {plan.reasoning}")
        return {"plan": plan, "tasks": plan.tasks}
    except Exception as exc:
        logger.error(f"Planning failed: {exc}", exc_info=True)
        raise


def route_after_planning(state: OrchestratorState) -> str:
    plan = state.get("plan")
    if not plan or not plan.needs_context:
        return "execute_tasks"
    return {
        "web": "web_search",
        "rag": "rag_search",
        "club": "club_search",
        "mixed": "gather_mixed_context",
    }.get(plan.context_type or "", "execute_tasks")


# ============================================================================
# CONTEXT PROVIDERS
# ============================================================================


class WebSearchProvider:
    async def search(self, query: str) -> List[ContextItem]:
        print(f"\n🌐 WEB SEARCH: '{query}'")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: web_search_agent.invoke(
                    {"messages": [{"role": "user", "content": query}]}
                ),
            )
            content = ""
            for msg in reversed(result.get("messages", [])):
                if hasattr(msg, "content") and msg.content:
                    content = msg.content
                    break
            content = content or str(result)
            print(f"   ✅ {len(content)} chars")
            return [ContextItem(
                source="web_search",
                content=content[:1000],
                relevance_score=0.9,
                metadata={"query": query},
            )]
        except Exception as exc:
            logger.error(f"Web search error: {exc}")
            return [ContextItem(
                source="web_search",
                content=f"Wikipedia search failed for: {query}",
                relevance_score=0.1,
                metadata={"error": str(exc), "query": query},
            )]


async def web_search_node(state: OrchestratorState) -> dict:
    plan = state["plan"]
    print("\n" + "=" * 60)
    print("🌐 GATHERING WEB CONTEXT")
    print("=" * 60)
    provider = WebSearchProvider()
    results = await asyncio.gather(
        *[provider.search(q) for q in plan.search_queries[:2]],
        return_exceptions=True,
    )
    all_context = []
    for r in results:
        if not isinstance(r, Exception):
            all_context.extend(r)
    combined = "\n\n".join(
        f"[Web: '{i.metadata.get('query')}']\n{i.content}"
        for i in sorted(all_context, key=lambda x: x.relevance_score, reverse=True)
    )
    return {"web_context": all_context, "combined_context": combined}


class RagSearchProvider:
    """
    Calls HybridRetrieval directly — no MCP subprocess needed.
    The MCP server (rag_server.py) is only for Claude Desktop / external clients.
    """

    async def search(self, query: str) -> List[ContextItem]:
        print(f"\n📚 RAG SEARCH (direct): '{query}'")

        retrieval_service = get_rag_retrieval_service()
        if retrieval_service is None:
            logger.warning("RAG retrieval service not available")
            return [ContextItem(
                source="rag",
                content="RAG service not available. Check SUPABASE_URL and SUPABASE_SERVICE_KEY.",
                relevance_score=0.0,
                metadata={"query": query},
            )]

        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: retrieval_service.retrieve(query=query, top_k=5),
            )

            chunks = results.get("chunks", [])
            if not chunks:
                return [ContextItem(
                    source="rag",
                    content="No relevant documents found in the knowledge base.",
                    relevance_score=0.0,
                    metadata={"query": query, "num_results": 0},
                )]

            # Format chunks into readable context
            formatted = "\n---\n".join(
                f"Result {i+1} (score: {c['score']:.3f})\n"
                f"Source: {c['metadata'].get('filename', 'unknown')}\n"
                f"{c['text']}"
                for i, c in enumerate(chunks)
            )
            print(f"   ✅ {len(chunks)} chunks retrieved")
            return [ContextItem(
                source="rag",
                content=formatted[:2000],
                relevance_score=chunks[0]["score"] if chunks else 0.0,
                metadata={"query": query, "num_results": len(chunks)},
            )]

        except Exception as exc:
            logger.error(f"RAG direct search error: {exc}")
            return [ContextItem(
                source="rag",
                content=f"RAG search failed: {exc}",
                relevance_score=0.0,
                metadata={"error": str(exc), "query": query},
            )]


async def rag_search_node(state: OrchestratorState) -> dict:
    plan = state["plan"]
    print("\n" + "=" * 60)
    print("📚 GATHERING RAG CONTEXT (direct)")
    print("=" * 60)
    provider = RagSearchProvider()
    results = await asyncio.gather(
        *[provider.search(q) for q in plan.rag_queries[:2]],
        return_exceptions=True,
    )
    all_context = []
    for r in results:
        if not isinstance(r, Exception):
            all_context.extend(r)
    combined = "\n\n".join(
        f"[RAG: '{i.metadata.get('query')}']\n{i.content}"
        for i in sorted(all_context, key=lambda x: x.relevance_score, reverse=True)
    )
    print(f"   Total RAG context: {len(combined)} chars")
    return {"rag_context": all_context, "combined_context": combined}


class ClubSearchProvider:
    async def search(self, query: str) -> List[ContextItem]:
        print(f"\n👥 CLUB SEARCH: '{query}'")
        try:
            loop = asyncio.get_event_loop()
            cat_resp = await loop.run_in_executor(
                None,
                lambda: llm.invoke([
                    SystemMessage(content="You are a category classifier. Respond with ONE word only."),
                    HumanMessage(content=(
                        f"Classify this query into one of: events, announcements, coordinators, general.\n"
                        f"Query: {query}\nRespond with the category name only."
                    )),
                ]),
            )
            category = cat_resp.content.strip().lower()
            if category not in {"events", "announcements", "coordinators", "general"}:
                category = "general"
            search_cat = None if category == "general" else category
            print(f"   🏷️ Category: {category}")

            from knowledge_engine.club.retrieval import get_club_retriever
            retriever = get_club_retriever()
            results = await loop.run_in_executor(
                None,
                lambda: retriever.retrieve(query=query, category=search_cat, top_k=3),
            )

            if not results:
                return [ContextItem(
                    source="club_search",
                    content="No club information found for this query.",
                    relevance_score=0.0,
                    metadata={"query": query, "category": category},
                )]

            combined_content = "\n\n".join(
                f"Result {i+1} (score: {r.get('score', 0):.2f}):\n{r.get('content', '')}"
                for i, r in enumerate(results)
            )
            avg_score = sum(r.get("score", 0.5) for r in results) / len(results)
            print(f"   ✅ {len(results)} club chunks retrieved")
            return [ContextItem(
                source="club_search",
                content=combined_content.strip(),
                relevance_score=avg_score,
                metadata={"query": query, "category": category, "results_count": len(results)},
            )]

        except Exception as exc:
            logger.error(f"Club search error: {exc}")
            return [ContextItem(
                source="club_search",
                content=f"Club search failed: {exc}",
                relevance_score=0.1,
                metadata={"error": str(exc), "query": query},
            )]


async def club_search_node(state: OrchestratorState) -> dict:
    plan = state["plan"]
    print("\n" + "=" * 60)
    print("👥 GATHERING CLUB CONTEXT")
    print("=" * 60)
    provider = ClubSearchProvider()
    results = await asyncio.gather(
        *[provider.search(q) for q in plan.club_queries[:2]],
        return_exceptions=True,
    )
    all_context = []
    for r in results:
        if not isinstance(r, Exception):
            all_context.extend(r)
    combined = "\n\n".join(
        f"[Club: '{i.metadata.get('query')}']\n{i.content}"
        for i in sorted(all_context, key=lambda x: x.relevance_score, reverse=True)
    )
    print(f"   Total club context: {len(combined)} chars")
    return {"club_context": all_context, "combined_context": combined}


async def gather_mixed_context_node(state: OrchestratorState) -> dict:
    plan = state["plan"]
    print("\n" + "=" * 60)
    print("🔀 GATHERING MIXED CONTEXT")
    print("=" * 60)

    coros = []
    if plan.search_queries:
        coros.append(("web", web_search_node(state)))
    if plan.rag_queries:
        coros.append(("rag", rag_search_node(state)))
    if plan.club_queries:
        coros.append(("club", club_search_node(state)))

    results = await asyncio.gather(*[c[1] for c in coros], return_exceptions=True)

    web_ctx, rag_ctx, club_ctx = [], [], []
    combined_parts = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Mixed context error: {result}")
            continue
        src = coros[i][0]
        if src == "web":
            web_ctx = result.get("web_context", [])
        elif src == "rag":
            rag_ctx = result.get("rag_context", [])
        elif src == "club":
            club_ctx = result.get("club_context", [])
        if result.get("combined_context"):
            combined_parts.append(result["combined_context"])

    combined = "\n\n".join(combined_parts)[:3000]
    print(f"\n   ✅ Mixed context: {len(combined)} chars")
    return {
        "web_context": web_ctx,
        "rag_context": rag_ctx,
        "club_context": club_ctx,
        "combined_context": combined,
    }


# ============================================================================
# WORKERS
# ============================================================================

GITHUB_TOOLS = [
    "create_repository", "get_file_contents", "create_or_update_file",
    "create_pull_request", "list_pull_requests", "update_pull_request",
    "search_repositories", "get_me",
]


async def github_worker_node(payload: dict) -> dict:
    task_data = payload["task"]
    context = payload.get("context", "")
    task_id = task_data["id"]
    print(f"\n  🛠️ GITHUB_WORKER: Task {task_id}")
    try:
        client = await mcp_pool.get_github_client()
        all_tools = await client.get_tools()
        filtered = [t for t in all_tools if t.name in GITHUB_TOOLS]
        if not filtered:
            return {"results": [TaskResult(task_id=task_id, worker_type="github",
                                           success=False, output="No GitHub tools available")]}
        agent = create_react_agent(llm, filtered)
        prompt = (
            f"GitHub Task: {task_data.get('description', '')}\n"
            + (f"\nContext:\n{context[:800]}\n" if context else "")
            + f"\nQuery: {payload.get('user_query', '')}"
        )
        response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
        output = next(
            (m.content for m in reversed(response.get("messages", [])) if getattr(m, "content", None)),
            str(response),
        )
        return {"results": [TaskResult(task_id=task_id, worker_type="github",
                                       success=True, output=output, used_context=bool(context))]}
    except Exception as exc:
        logger.error(f"GitHub task {task_id} failed: {exc}")
        return {"results": [TaskResult(task_id=task_id, worker_type="github",
                                       success=False, output=f"GitHub failed: {exc}", error=str(exc))]}


async def google_workspace_worker_node(payload: dict) -> dict:
    task_data = payload["task"]
    context = payload.get("context", "")
    task_id = task_data["id"]
    google_service = task_data.get("google_service", "")
    print(f"\n  🚀 GOOGLE_WORKER: Task {task_id} ({google_service})")
    try:
        client = await mcp_pool.get_google_workspace_client()
        all_tools = await client.get_tools()
        filtered = [
            t for t in all_tools
            if google_service.lower() in t.name.lower()
            or ("event" in t.name.lower() and google_service.lower() == "calendar")
        ] if google_service and google_service != "all_google" else all_tools
        if not filtered:
            return {"results": [TaskResult(task_id=task_id, worker_type=f"google_{google_service}",
                                           success=False, output=f"No tools for: {google_service}")]}
        agent = create_react_agent(llm, filtered)
        prompt = (
            f"Google Workspace Task ({google_service}): {task_data.get('description', '')}\n"
            + (f"\nContext:\n{context[:800]}\n" if context else "")
            + f"\nQuery: {payload.get('user_query', '')}"
        )
        response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
        output = next(
            (m.content for m in reversed(response.get("messages", [])) if getattr(m, "content", None)),
            str(response),
        )
        return {"results": [TaskResult(task_id=task_id, worker_type=f"google_{google_service}",
                                       success=True, output=output, used_context=bool(context))]}
    except Exception as exc:
        logger.error(f"Google Workspace task {task_id} failed: {exc}")
        return {"results": [TaskResult(task_id=task_id, worker_type=f"google_{google_service}",
                                       success=False, output=f"Google Workspace failed: {exc}", error=str(exc))]}


async def conversational_worker_node(payload: dict) -> dict:
    task_data = payload["task"]
    user_query = payload["user_query"]
    context = payload.get("context", "")
    task_id = task_data["id"]
    print(f"\n  💬 CONVERSATIONAL_WORKER: Task {task_id}"
          + (f" [with {len(context)} chars context]" if context else " [no context]"))
    try:
        prompt = (
            f"User Query: {user_query}\n"
            + (f"\nRelevant context retrieved from the knowledge base:\n{context}\n" if context else "")
            + f"\nTask: {task_data.get('description', 'Respond to the user query')}"
        )
        messages = [
            SystemMessage(content="You are a helpful assistant. When context is provided, base your answer on it. Be specific and cite details from the context."),
            HumanMessage(content=prompt),
        ]
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: llm.invoke(messages))
        return {"results": [TaskResult(task_id=task_id, worker_type="conversational",
                                       success=True, output=response.content, used_context=bool(context))]}
    except Exception as exc:
        logger.error(f"Conversational task {task_id} failed: {exc}")
        return {"results": [TaskResult(task_id=task_id, worker_type="conversational",
                                       success=False, output=f"Failed: {exc}", error=str(exc))]}


# ============================================================================
# TASK EXECUTOR — always pass context to workers when it exists
# ============================================================================


def fanout_to_workers(state: OrchestratorState):
    """
    Fan out tasks to workers.

    Context injection rule: always inject combined_context into the
    worker payload when it is non-empty — regardless of task.requires_context.
    The old flag-based approach silently dropped context because the planner
    didn't reliably set it. Workers ignore the context if it's empty, so
    always passing it is harmless and correct.
    """
    context = state.get("combined_context", "")
    sends = []
    for task in state["tasks"]:
        payload = {
            "task": task.model_dump(),
            "user_query": state["user_query"],
        }
        # Always inject context when available — this is the core fix
        if context:
            payload["context"] = context

        if task.worker_type == "github":
            sends.append(Send("github_worker", payload))
        elif task.worker_type.startswith("google_") or task.google_service:
            sends.append(Send("google_workspace_worker", payload))
        else:
            sends.append(Send("conversational_worker", payload))
    return sends


async def results_aggregator_node(state: OrchestratorState) -> dict:
    results = state.get("results", [])
    print("\n" + "=" * 60)
    print(f"📦 AGGREGATING {len(results)} RESULT(S)")
    print("=" * 60)

    if not results:
        return {"final_response": "No tasks were executed."}
    if len(results) == 1:
        return {"final_response": results[0].output}

    results_text = "\n\n".join(
        f"[{r.worker_type.upper()}] {r.output[:400]}…" for r in results
    )
    prompt = (
        f"Original Query: {state['user_query']}\n\n"
        f"Results from workers:\n{results_text}\n\n"
        "Provide a coherent final response."
    )
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: llm.invoke([
            SystemMessage(content="Integrate results from multiple sources helpfully."),
            HumanMessage(content=prompt),
        ]),
    )
    return {"final_response": response.content}


# ============================================================================
# BUILD GRAPH
# ============================================================================


def build_smart_orchestrator():
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
            "execute_tasks": "execute_tasks",
        },
    )
    for ctx_node in ("web_search", "rag_search", "club_search", "gather_mixed_context"):
        g.add_edge(ctx_node, "execute_tasks")

    g.add_conditional_edges(
        "execute_tasks",
        fanout_to_workers,
        {
            "github_worker": "github_worker",
            "google_workspace_worker": "google_workspace_worker",
            "conversational_worker": "conversational_worker",
        },
    )
    for worker in ("github_worker", "google_workspace_worker", "conversational_worker"):
        g.add_edge(worker, "aggregator")
    g.add_edge("aggregator", END)

    return g.compile()


# ============================================================================
# ORCHESTRATOR CLASS
# ============================================================================


class SmartOrchestrator:
    def __init__(self):
        self.graph = build_smart_orchestrator()
        print("\n" + "=" * 60)
        print("✅ SMART ORCHESTRATOR INITIALISED (ASYNC)")
        print("=" * 60)
        rag = get_rag_retrieval_service()
        print(f"   User RAG  : {'✅ ready' if rag else '❌ unavailable (check .env)'}")
        print("   Club RAG  : ✅ lazy (loads on first club query)")
        print("=" * 60)

    async def process(self, user_query: str, conversation_history: List[str] = None) -> dict:
        if not user_query or not user_query.strip():
            return {"success": False, "response": "Please provide a valid query.", "metadata": {}}

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
            "final_response": "",
        }

        try:
            final_state = await self.graph.ainvoke(initial_state)
            results = final_state.get("results", [])
            successful = [r for r in results if r.success]
            return {
                "success": True,
                "response": final_state["final_response"],
                "metadata": {
                    "total_tasks": len(results),
                    "successful_tasks": len(successful),
                    "web_search_used": bool(final_state.get("web_context")),
                    "rag_search_used": bool(final_state.get("rag_context")),
                    "club_search_used": bool(final_state.get("club_context")),
                    "workers_used": list({r.worker_type for r in results}),
                },
            }
        except Exception as exc:
            logger.error(f"Orchestrator error: {exc}", exc_info=True)
            return {"success": False, "response": f"Orchestrator error: {exc}", "metadata": {}}

    async def cleanup(self):
        await mcp_pool.cleanup()


# ============================================================================
# CLI
# ============================================================================


def interactive_mode():
    print("\n" + "=" * 60)
    print("🤖 SMART ORCHESTRATOR — CLI")
    print("=" * 60)

    orch = SmartOrchestrator()
    conversation: List[str] = []

    try:
        while True:
            try:
                query = input("\n💬 Query: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\n👋 Goodbye!")
                break
            if not query:
                continue
            if query.lower() in {"quit", "exit", "q"}:
                print("\n👋 Goodbye!")
                break

            result = asyncio.run(orch.process(query, conversation))
            conversation.append(f"User: {query}")
            if result["success"]:
                conversation.append(f"Assistant: {result['response'][:100]}…")

            print(f"\n{'='*60}\n🤖 RESPONSE:\n{'='*60}")
            print(result["response"])
            print("=" * 60)
            if result["success"]:
                m = result["metadata"]
                print(f"\n📊 workers={m['workers_used']}  "
                      f"rag={m['rag_search_used']}  club={m['club_search_used']}")
    finally:
        asyncio.run(orch.cleanup())


orchestrator = SmartOrchestrator()

if __name__ == "__main__":
    interactive_mode()
