from __future__ import annotations

import asyncio
import atexit
import logging
import operator
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, List, Literal, Optional, TypedDict
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, Command
from pydantic import BaseModel, Field, field_validator
try:
    from langgraph.prebuilt import create_react_agent
except ImportError:
    from langchain.agents import create_react_agent

load_dotenv()

servers_dir = Path(__file__).resolve().parent.parent / "mcp_servers"

# ============================================================================
# LOGGING — Windows-safe: never crashes on emoji / non-cp1252 bytes
# ============================================================================

class _SafeStreamHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            enc = getattr(self.stream, "encoding", "utf-8") or "utf-8"
            self.stream.write(
                msg.encode(enc, errors="replace").decode(enc, errors="replace")
                + self.terminator
            )
            self.flush()
        except Exception:
            self.handleError(record)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            f"orchestrator_{datetime.now():%Y%m%d}.log",
            encoding="utf-8",
        ),
        _SafeStreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================================
# MCP CLIENT POOL — GitHub + Google Workspace only; RAG is called directly
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
            pat = os.getenv("GITHUB_PAT")
            if not pat:
                raise ValueError("GITHUB_PAT environment variable not set")
            self.github_client = MultiServerMCPClient({
                "github": {
                    "transport": "http",
                    "url": "https://api.githubcopilot.com/mcp/",
                    "headers": {"Authorization": f"Bearer {pat}"},
                }
            })
            logger.info("GitHub MCP client initialised")
            return self.github_client

    # async def get_google_workspace_client(self):
    #     if self.google_workspace_client is not None:
    #         return self.google_workspace_client
    #     async with self._lock:
    #         if self.google_workspace_client is not None:
    #             return self.google_workspace_client
    #         from langchain_mcp_adapters.client import MultiServerMCPClient
    #         if not os.getenv("GOOGLE_OAUTH_CLIENT_ID"):
    #             raise ValueError("GOOGLE_OAUTH_CLIENT_ID must be set")
    #         self.google_workspace_client = MultiServerMCPClient({
    #             "google_workspace": {
    #                 "transport": "http",
    #                 "url": "http://localhost:8001/mcp/",
    #                 "headers": {},
    #             }
    #         })
    #         logger.info("Google Workspace MCP client initialised")
    #         return self.google_workspace_client

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
                    logger.info(f"{name} client closed")
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
        logger.error(f"atexit cleanup error: {exc}")


atexit.register(_cleanup_on_exit)

# ============================================================================
# DIRECT RAG SERVICE
# ============================================================================

def _build_rag_retrieval_service():
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_ANON_KEY", "")).strip()
    if not url or not key:
        logger.warning("SUPABASE_URL/KEY not set — user RAG disabled")
        return None
    try:
        from knowledge_engine.embedding_service import EmbeddingService
        from knowledge_engine.vector_store import SupabaseVectorStore
        from knowledge_engine.retrieval import HybridRetrieval
        dim = int(os.getenv("EMBEDDING_DIM", "384"))
        svc = HybridRetrieval(
            embedding_service=EmbeddingService(embedding_dim=dim),
            vector_store=SupabaseVectorStore(
                supabase_url=url, supabase_key=key, embedding_dim=dim
            ),
        )
        logger.info("User RAG retrieval service ready (direct)")
        return svc
    except Exception as exc:
        logger.error(f"Failed to build RAG retrieval service: {exc}")
        return None


_rag_retrieval_service = None


def get_rag_retrieval_service():
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
    worker_type: Literal["github", "conversational", "gmail", "calendar"] = "conversational"
    description: str
    parameters: dict = Field(default_factory=dict)
    requires_context: bool = False
    context_type: Optional[str] = None
    google_service: Optional[str] = None


class ExecutionPlan(BaseModel):
    """
    reasoning is required and must always be the first field populated.
    context_type is Optional[str] + @field_validator to handle LLM outputting
    the string "null" instead of JSON null (prevents Groq 400).
    """
    reasoning: str  # REQUIRED — always populate this first
    needs_context: bool = False
    context_type: Optional[str] = None
    tasks: List[WorkerTask] = Field(default_factory=list)
    search_queries: List[str] = Field(default_factory=list)
    rag_queries: List[str] = Field(default_factory=list)
    club_queries: List[str] = Field(default_factory=list)

    @field_validator("context_type", mode="before")
    @classmethod
    def normalise_context_type(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("null", "none", ""):
                return None
            if s in ("web", "rag", "club", "mixed"):
                return s
        return None


class TaskResult(BaseModel):
    task_id: int
    worker_type: str
    success: bool
    output: str
    used_context: bool = False
    error: Optional[str] = None


class OrchestratorState(TypedDict):
    user_id: str
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
# LLMs
#
# worker llm : llama-3.1-8b-instant (smaller, faster, 1M TPM) — used for all workers,
#
# planning_llm: llama-3.3-70b-versatile — reliable structured output,
#               temperature=0.0 for deterministic JSON generation.
#               Override via PLANNING_MODEL env var.
#
# llm:          llama-4-scout-17b (large context) — used for all other nodes
#               (web search agent, conversational worker, aggregator).
#               Override via ORCHESTRATOR_MODEL env var.
# ============================================================================

_model = os.getenv("ORCHESTRATOR_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
llm = ChatGroq(model=_model, temperature=0.7, api_key=os.getenv("GROQ_API_KEY"))

_planning_model = os.getenv("PLANNING_MODEL", "llama-3.3-70b-versatile")
planning_llm = ChatGroq(model=_planning_model, temperature=0.0, api_key=os.getenv("GROQ_API_KEY"))

_worker_model = os.getenv("WORKER_MODEL", "llama-3.1-8b-instant")
worker_llm = ChatGroq(model=_worker_model, temperature=0.1, api_key=os.getenv("GROQ_API_KEY"))


_wiki_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
web_search_agent = create_react_agent(llm, tools=[_wiki_tool])

print(f"Orchestrator LLM : {_model}")
print(f"Planning LLM     : {_planning_model}")
print(f"Worker LLM       : {_worker_model}")

# ============================================================================
# PLANNING
# ============================================================================

PLANNING_SYSTEM = """You are an intelligent planning agent. You MUST return a valid JSON object.

REQUIRED FIELDS (all must be present, reasoning must be non-empty):
  reasoning     : string  — ALWAYS fill this first. Briefly explain your routing decision.
  needs_context : boolean — true if external lookup is needed, false otherwise.
  context_type  : string or null — one of "web", "rag", "club", "mixed", or null.
  tasks         : list of task objects.
  search_queries: list of strings (empty list if not used).
  rag_queries   : list of strings (empty list if not used).
  club_queries  : list of strings (empty list if not used).

STEP 1 — Choose context_type (pick exactly one):
  "web"   - general / Wikipedia knowledge needed
  "rag"   - user-uploaded research papers or documents needed
  "club"  - robotics club events, announcements, coordinators needed
  "mixed" - multiple context sources needed
  null    - no external lookup needed (greetings, gmail/calendar tasks, simple chat)

STEP 2 — Populate the matching query list:
  If context_type = "club"  → add queries to club_queries
  If context_type = "rag"   → add queries to rag_queries
  If context_type = "web"   → add queries to search_queries
  If context_type = "mixed" → populate all relevant query lists
  If context_type = null    → leave all query lists as empty lists []

STEP 3 — Set needs_context:
  needs_context = true  when context_type is "web", "rag", "club", or "mixed"
  needs_context = false when context_type is null

STEP 4 — Choose worker_type per task:
  "conversational" - chat, explanation, analysis, answering from retrieved context
  "github"         - GitHub repos, PRs, files, code
  "gmail"          - read/search/send emails, summarize inbox
  "calendar"       - create/read/list events, summarize schedule

EXAMPLES:
  "What events is the robotics club running?"
    -> reasoning="User wants club event info, routing to club search.",
       context_type="club", needs_context=true, club_queries=["robotics club events"],
       worker_type="conversational"

  "What does my uploaded paper say about neural networks?"
    -> reasoning="User references an uploaded document, using RAG.",
       context_type="rag", needs_context=true, rag_queries=["neural networks"],
       worker_type="conversational"

  "Summarize my last 5 emails"
    -> reasoning="Direct Gmail task, no context lookup needed.",
       context_type=null, needs_context=false, worker_type="gmail"

  "What is machine learning?"
    -> reasoning="General knowledge question, using web search.",
       context_type="web", needs_context=true, search_queries=["machine learning"],
       worker_type="conversational"

  "Hi, how are you?"
    -> reasoning="Simple greeting, no lookup needed.",
       context_type=null, needs_context=false, worker_type="conversational"
"""


def planning_agent_node(state: OrchestratorState) -> dict:
    print("\n" + "=" * 60)
    print("PLANNING AGENT: Analysing query...")
    print("=" * 60)
    logger.info(f"Planning for query: {state['user_query'][:120]}")

    planner = planning_llm.with_structured_output(ExecutionPlan)
    messages = [
        SystemMessage(content=PLANNING_SYSTEM),
        HumanMessage(content=f"User Query: {state['user_query'][:500]}"),
    ]

    # Retry up to 3 times — planning_llm is reliable but network/rate errors happen
    plan: ExecutionPlan | None = None
    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            plan = planner.invoke(messages)
            break
        except Exception as exc:
            last_exc = exc
            logger.warning(f"Planning attempt {attempt}/3 failed: {exc}")

    if plan is None:
        logger.error(f"All planning attempts failed. Last error: {last_exc}")
        raise last_exc

    # ------------------------------------------------------------------
    # Post-processing: infer context_type from query lists.
    #
    # The LLM often outputs needs_context=True but context_type=None
    # simultaneously — an inconsistency we can't prevent in the schema.
    # Solution: if any query list is populated, derive context_type from
    # it instead of trusting the LLM's context_type field directly.
    # ------------------------------------------------------------------
    has_club = bool(plan.club_queries)
    has_rag  = bool(plan.rag_queries)
    has_web  = bool(plan.search_queries)

    if sum([has_club, has_rag, has_web]) >= 2:
        inferred_type = "mixed"
    elif has_club:
        inferred_type = "club"
    elif has_rag:
        inferred_type = "rag"
    elif has_web:
        inferred_type = "web"
    else:
        inferred_type = None

    final_context_type = inferred_type or plan.context_type
    final_needs_context = final_context_type is not None

    plan = plan.model_copy(update={
        "context_type": final_context_type,
        "needs_context": final_needs_context,
    })

    print(f"Plan: needs_context={plan.needs_context}  "
          f"context_type={plan.context_type}  "
          f"tasks={len(plan.tasks)}  "
          f"club_q={plan.club_queries}  "
          f"rag_q={plan.rag_queries}")
    logger.info(f"Plan reasoning: {plan.reasoning}")
    return {"plan": plan, "tasks": plan.tasks}


def route_after_planning(state: OrchestratorState) -> str:
    """
    Routes to the correct context node.
    Uses explicit `is None` check — `plan.context_type or ""` would turn
    None into "" which falls through to execute_tasks, skipping all context nodes.
    """
    plan = state.get("plan")
    if not plan or not plan.needs_context or plan.context_type is None:
        return "execute_tasks"
    return {
        "web":   "web_search",
        "rag":   "rag_search",
        "club":  "club_search",
        "mixed": "gather_mixed_context",
    }.get(plan.context_type, "execute_tasks")


# ============================================================================
# CONTEXT PROVIDERS
# ============================================================================

class WebSearchProvider:
    async def search(self, query: str) -> List[ContextItem]:
        print(f"  WEB: '{query}'")
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
            print(f"  Web done: {len(content)} chars")
            return [ContextItem(source="web_search", content=content[:1000],
                                relevance_score=0.9, metadata={"query": query})]
        except Exception as exc:
            logger.error(f"Web search error: {exc}")
            return [ContextItem(source="web_search",
                                content=f"Search failed: {query}",
                                relevance_score=0.1,
                                metadata={"error": str(exc), "query": query})]


async def web_search_node(state: OrchestratorState) -> dict:
    plan = state["plan"]
    print("\n== WEB CONTEXT ==")
    provider = WebSearchProvider()
    results = await asyncio.gather(
        *[provider.search(q) for q in plan.search_queries[:2]],
        return_exceptions=True,
    )
    all_ctx = [item for r in results if not isinstance(r, Exception) for item in r]
    combined = "\n\n".join(
        f"[Web: '{i.metadata.get('query')}']\n{i.content}"
        for i in sorted(all_ctx, key=lambda x: x.relevance_score, reverse=True)
    )
    return {"web_context": all_ctx, "combined_context": combined}


class RagSearchProvider:
    async def search(self, query: str) -> List[ContextItem]:
        print(f"  RAG: '{query}'")
        svc = get_rag_retrieval_service()
        if svc is None:
            return [ContextItem(source="rag",
                                content="RAG not available. Check SUPABASE_URL/KEY.",
                                relevance_score=0.0, metadata={"query": query})]
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, lambda: svc.retrieve(query=query, top_k=5)
            )
            chunks = results.get("chunks", [])
            if not chunks:
                return [ContextItem(source="rag",
                                    content="No documents found.",
                                    relevance_score=0.0,
                                    metadata={"query": query, "num_results": 0})]
            formatted = "\n---\n".join(
                f"Result {i+1} (score: {c['score']:.3f})\n"
                f"Source: {c['metadata'].get('filename', 'unknown')}\n{c['text']}"
                for i, c in enumerate(chunks)
            )
            print(f"  RAG done: {len(chunks)} chunks")
            return [ContextItem(source="rag", content=formatted[:2000],
                                relevance_score=chunks[0]["score"],
                                metadata={"query": query, "num_results": len(chunks)})]
        except Exception as exc:
            logger.error(f"RAG error: {exc}")
            return [ContextItem(source="rag", content=f"RAG failed: {exc}",
                                relevance_score=0.0,
                                metadata={"error": str(exc), "query": query})]


async def rag_search_node(state: OrchestratorState) -> dict:
    plan = state["plan"]
    print("\n== RAG CONTEXT ==")
    provider = RagSearchProvider()
    results = await asyncio.gather(
        *[provider.search(q) for q in plan.rag_queries[:2]],
        return_exceptions=True,
    )
    all_ctx = [item for r in results if not isinstance(r, Exception) for item in r]
    combined = "\n\n".join(
        f"[RAG: '{i.metadata.get('query')}']\n{i.content}"
        for i in sorted(all_ctx, key=lambda x: x.relevance_score, reverse=True)
    )
    print(f"  RAG total: {len(combined)} chars")
    return {"rag_context": all_ctx, "combined_context": combined}


class ClubSearchProvider:
    async def search(self, query: str) -> List[ContextItem]:
        print(f"  CLUB: '{query}'")
        try:
            loop = asyncio.get_event_loop()
            cat_resp = await loop.run_in_executor(
                None,
                lambda: llm.invoke([
                    SystemMessage(content=(
                        "Reply with exactly ONE word from: "
                        "events, announcements, coordinators, general"
                    )),
                    HumanMessage(content=query),
                ]),
            )
            category = cat_resp.content.strip().lower()
            if category not in {"events", "announcements", "coordinators", "general"}:
                category = "general"
            search_cat = None if category == "general" else category
            print(f"  Club category: {category}")

            from knowledge_engine.club.retrieval import get_club_retriever
            retriever = get_club_retriever()
            club_results = await loop.run_in_executor(
                None,
                lambda: retriever.retrieve(query=query, category=search_cat, top_k=3),
            )

            if not club_results:
                return [ContextItem(source="club_search",
                                    content="No club info found.",
                                    relevance_score=0.0,
                                    metadata={"query": query, "category": category})]

            combined = "\n\n".join(
                f"Result {i+1} (score: {r.get('score', 0):.2f}):\n{r.get('content', '')}"
                for i, r in enumerate(club_results)
            )
            avg = sum(r.get("score", 0.5) for r in club_results) / len(club_results)
            print(f"  Club done: {len(club_results)} chunks")
            return [ContextItem(source="club_search", content=combined.strip(),
                                relevance_score=avg,
                                metadata={"query": query, "category": category,
                                          "results_count": len(club_results)})]
        except Exception as exc:
            logger.error(f"Club search error: {exc}")
            return [ContextItem(source="club_search",
                                content=f"Club search failed: {exc}",
                                relevance_score=0.1,
                                metadata={"error": str(exc), "query": query})]


async def club_search_node(state: OrchestratorState) -> dict:
    plan = state["plan"]
    print("\n== CLUB CONTEXT ==")
    provider = ClubSearchProvider()
    results = await asyncio.gather(
        *[provider.search(q) for q in plan.club_queries[:2]],
        return_exceptions=True,
    )
    all_ctx = [item for r in results if not isinstance(r, Exception) for item in r]
    combined = "\n\n".join(
        f"[Club: '{i.metadata.get('query')}']\n{i.content}"
        for i in sorted(all_ctx, key=lambda x: x.relevance_score, reverse=True)
    )
    print(f"  Club total: {len(combined)} chars")
    return {"club_context": all_ctx, "combined_context": combined}


async def gather_mixed_context_node(state: OrchestratorState) -> dict:
    plan = state["plan"]
    print("\n== MIXED CONTEXT ==")
    coros = []
    if plan.search_queries:
        coros.append(("web", web_search_node(state)))
    if plan.rag_queries:
        coros.append(("rag", rag_search_node(state)))
    if plan.club_queries:
        coros.append(("club", club_search_node(state)))

    results = await asyncio.gather(*[c[1] for c in coros], return_exceptions=True)
    web_ctx, rag_ctx, club_ctx, parts = [], [], [], []
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
            parts.append(result["combined_context"])

    combined = "\n\n".join(parts)[:3000]
    print(f"  Mixed total: {len(combined)} chars")
    return {"web_context": web_ctx, "rag_context": rag_ctx,
            "club_context": club_ctx, "combined_context": combined}


# ============================================================================
# WORKERS
# ============================================================================

GITHUB_TOOLS = [
    "create_repository", "get_file_contents", "create_or_update_file",
    "create_pull_request", "list_pull_requests", "update_pull_request",
    "search_repositories", "get_me",
]

PARAM_TYPE_MAP = {
    "search_repositories": {"perPage": int, "page": int},
    "list_pull_requests": {"perPage": int, "page": int},
    "create_pull_request": {"draft": bool},
}

def fix_tool_parameters(tool_call: dict) -> dict:
    tool_name = tool_call.get("name")
    parameters = tool_call.get("parameters", {})
    if tool_name in PARAM_TYPE_MAP:
        for param_name, expected_type in PARAM_TYPE_MAP[tool_name].items():
            if param_name in parameters:
                value = parameters[param_name]
                if expected_type == int and isinstance(value, str):
                    try:
                        parameters[param_name] = int(value)
                    except ValueError:
                        pass
                elif expected_type == bool and isinstance(value, str):
                    parameters[param_name] = value.lower() == "true"
    return tool_call

def fix_tool_parameters(tool_call: dict) -> dict:
    tool_name = tool_call.get("name")
    parameters = tool_call.get("parameters", {})
    if tool_name in PARAM_TYPE_MAP:
        for param_name, expected_type in PARAM_TYPE_MAP[tool_name].items():
            if param_name in parameters:
                value = parameters[param_name]
                if expected_type == int and isinstance(value, str):
                    try:
                        parameters[param_name] = int(value)
                    except ValueError:
                        pass
                elif expected_type == bool and isinstance(value, str):
                    parameters[param_name] = value.lower() == "true"
    return tool_call

async def github_worker_node(payload: dict) -> dict:
    from auth.mcp_token_bridge import get_github_client_for_user
    from auth.github_oauth import clear_github_token
    from langchain.agents import create_agent

    task_data = payload["task"]
    context = payload.get("context", "")
    task_id = task_data["id"]
    user_id = payload.get("user_id")          # ← threaded through from the request

    print(f"\n  🛠️ GITHUB_WORKER: Task {task_id} for user {user_id}")

    # No user_id means we can't look up their token
    if not user_id:
        return {"results": [TaskResult(
            task_id=task_id, worker_type="github", success=False,
            output="No user_id in payload — cannot fetch GitHub token."
        )]}

    # Fetch per-user GitHub client
    client = await get_github_client_for_user(user_id)
    if client is None:
        return {"results": [TaskResult(
            task_id=task_id, worker_type="github", success=False,
            output=(
                "GitHub account not connected. "
                "Please connect your GitHub account in Settings → Integrations."
            )
        )]}

    try:
        all_tools = await client.get_tools()
        filtered = [t for t in all_tools if t.name in GITHUB_TOOLS]

        if not filtered:
            return {"results": [TaskResult(
                task_id=task_id, worker_type="github", success=False,
                output="No GitHub tools available."
            )]}

        agent = create_agent(worker_llm, filtered)

        prompt = (
            f"GitHub Task: {task_data.get('description', '')}\n"
            + (f"\nContext:\n{context[:800]}\n" if context else "")
            + f"\nQuery: {payload.get('user_query', '')}\n\n"
            "IMPORTANT:\n"
            "- Ensure numeric params like perPage/page are numbers, not strings\n"
        )

        response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})

        if "tool_calls" in response:
            response["tool_calls"] = [fix_tool_parameters(c) for c in response["tool_calls"]]

        output = next(
            (m.content for m in reversed(response.get("messages", []))
             if getattr(m, "content", None)),
            str(response),
        )

        return {"results": [TaskResult(
            task_id=task_id, worker_type="github", success=True,
            output=output, used_context=bool(context)
        )]}

    except Exception as exc:
        error_str = str(exc)

        # If GitHub returned 401, the token was revoked — clear it
        if "401" in error_str or "unauthorized" in error_str.lower():
            await clear_github_token(user_id)
            return {"results": [TaskResult(
                task_id=task_id, worker_type="github", success=False,
                output=(
                    "GitHub token has been revoked. "
                    "Please reconnect your GitHub account in Settings → Integrations."
                ),
                error=error_str,
            )]}

        logger.error(f"GitHub task {task_id} failed: {exc}")
        return {"results": [TaskResult(
            task_id=task_id, worker_type="github", success=False,
            output=f"GitHub failed: {exc}", error=error_str
        )]}
        



from auth.mcp_token_bridge import get_google_workspace_client_for_user

async def google_workspace_worker_node(payload: dict) -> dict:
    # Called either via Send(payload) from confirmation_node — payload has "task" key
    # or via fanout Send directly — same structure
    # Guard: if "task" key missing, payload IS the task dict itself
    if "task" in payload:
        task_data  = payload["task"]
        context    = payload.get("context", "")
        user_query = payload.get("user_query", "")
        user_id    = payload.get("user_id", "")
    else:
        # Fallback: treat entire payload as task_data
        task_data  = payload
        context    = ""
        user_query = ""
        user_id    = ""

    task_id = task_data.get("id", 0)
    google_service = (
        (task_data.get("google_service") or task_data.get("worker_type") or "")
    ).lower()
    print(f"  GOOGLE_WORKER: Task {task_id} ({google_service})")

    try:
        client = await get_google_workspace_client_for_user(user_id=user_id)
        if client is None:
            return {"results": [TaskResult(
                task_id=task_id, worker_type="google",
                success=False,
                output="Google account not connected. Please connect your Google account in Settings."
            )]}
        all_tools = await client.get_tools()

        gmail_kw = {"gmail", "email", "message", "inbox", "send", "draft", "thread", "label"}
        cal_kw   = {"calendar", "event", "schedule", "meeting", "attendee"}

        if google_service == "gmail":
            filtered = [t for t in all_tools
                        if any(kw in t.name.lower() for kw in gmail_kw)]
        elif google_service == "calendar":
            filtered = [t for t in all_tools
                        if any(kw in t.name.lower() for kw in cal_kw)]
        else:
            filtered = all_tools

        # Cap at 5 — each tool schema ~1800 tokens; prevents context explosion
        filtered = filtered[:5]

        if not filtered:
            return {"results": [TaskResult(
                task_id=task_id, worker_type=f"google_{google_service}",
                success=False, output=f"No tools found for: {google_service}")]}

        logger.info(f"Google {google_service}: {len(filtered)} tools: "
                    f"{[t.name for t in filtered]}")


        if google_service == "gmail":
            system_content = """You are a Gmail assistant. Use the available Gmail tools to fulfill requests.

Tool contracts:
- search_gmail_messages(query, max_results) -> list of objects, each with an "id" field.
  Call this first whenever you need to find or list emails.
  For "last N emails": query="", max_results=N.
  For emails from a sender: query="from:address@example.com".
  For emails with a keyword: query="the keyword".
- get_gmail_message_content(message_id) -> full email: subject, sender, date, body.
- get_gmail_messages_content_batch(message_ids) -> content of multiple emails.
  IMPORTANT: message_ids must be a non-empty list of IDs from search_gmail_messages.
  Never call this with an empty list.
- send_gmail_message(to, subject, body) -> sends an email. No prior search needed.
- get_gmail_attachment_content(message_id, attachment_id) -> retrieves an attachment.

Present email summaries as: Subject | From | Date | Key points (2 lines max each).
"""

        elif google_service == "calendar":
            system_content = """You are a Google Calendar assistant. Use the available Calendar tools.

Tool contracts:
- List/search tools -> return event objects: id, summary, start, end, attendees, description.
  Call a list tool first when reading or summarizing a schedule.
- Create tools -> require at minimum: summary (title), start datetime (ISO), end datetime (ISO).
  Extract these directly from the user request.
- Update tools -> require event id. Search/list first to get the id, then update.

Present schedules in chronological order: Date | Time | Event title 
"""

        else:
            system_content = (
                "You are a Google Workspace assistant. "
                "When a tool returns IDs or references, pass them as input to "
                "subsequent tools that need them. Be concise."
            )

        task_desc = task_data.get("description", "")[:500]
        prompt = f"User request: {user_query}\nTask: {task_desc}"
        if context:
            prompt += f"\n\nAdditional context:\n{context[:400]}"

        agent = create_react_agent(worker_llm, filtered)
        response = await agent.ainvoke({
            "messages": [
                SystemMessage(content=system_content),
                HumanMessage(content=prompt),
            ]
        })

        output = next(
            (m.content for m in reversed(response.get("messages", []))
             if getattr(m, "content", None)),
            str(response),
        )
        return {"results": [TaskResult(
            task_id=task_id, worker_type=f"google_{google_service}",
            success=True, output=output[:2000], used_context=bool(context))]}

    except Exception as exc:
        logger.error(f"Google Workspace task {task_id} failed: {exc}")
        return {"results": [TaskResult(
            task_id=task_id, worker_type=f"google_{google_service}",
            success=False, output=f"Google Workspace failed: {exc}",
            error=str(exc))]}


async def conversational_worker_node(payload: dict) -> dict:
    task_data = payload["task"]
    user_query = payload["user_query"]
    context = payload.get("context", "")
    task_id = task_data["id"]
    ctx_info = f" [{len(context)} chars context]" if context else " [no context]"
    print(f"  CONVERSATIONAL: task {task_id}{ctx_info}")
    try:
        prompt = (
            f"User Query: {user_query}\n"
            + (f"\nContext from knowledge base:\n{context}\n" if context else "")
            + f"\nTask: {task_data.get('description', 'Respond to the user query')}"
        )
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: llm.invoke([
                SystemMessage(content=(
                    ''''You are a helpful Robotic club assistant. You can retrieve context from user docs, web,and robotic club resources.
                    You have capability to execute gmail, google calendar and github operations for user.
                    You are here to assist the robotic club member and improve their productivity.
                    When context is provided, '''
                    "base your answer on it and cite specific details."
                )),
                HumanMessage(content=prompt),
            ]),
        )
        return {"results": [TaskResult(task_id=task_id, worker_type="conversational",
                                       success=True, output=response.content,
                                       used_context=bool(context))]}
    except Exception as exc:
        logger.error(f"Conversational task {task_id} failed: {exc}")
        return {"results": [TaskResult(task_id=task_id, worker_type="conversational",
                                       success=False, output=f"Failed: {exc}",
                                       error=str(exc))]}


# ============================================================================
# FANOUT — always inject context; route gmail/calendar to google_workspace_worker
# ============================================================================

def fanout_to_workers(state: OrchestratorState):
    """
    Updated version — includes user_id in every worker payload so workers
    can fetch per-user tokens from Supabase.
    """
    context = state.get("combined_context", "")
    user_id = state.get("user_id", "")          # ← comes from initial_state

    sends = []
    for task in state["tasks"]:
        payload = {
            "task": task.model_dump(),
            "user_query": state["user_query"],
            "user_id": user_id,                  # ← injected here
        }
        if context:
            payload["context"] = context

        if task.worker_type == "github":
            sends.append(Send("github_worker", payload))
        elif task.worker_type.startswith("google_") or task.google_service:
            sends.append(Send("google_workspace_worker", payload))
        else:
            sends.append(Send("conversational_worker", payload))
    return sends


# ============================================================================
# AGGREGATOR
# ============================================================================

async def results_aggregator_node(state: OrchestratorState) -> dict:
    results = state.get("results", [])
    print(f"\n== AGGREGATING {len(results)} result(s) ==")
    if not results:
        return {"final_response": "No tasks executed."}
    if len(results) == 1:
        return {"final_response": results[0].output}
    results_text = "\n\n".join(
        f"[{r.worker_type.upper()}] {r.output[:400]}..." for r in results
    )
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: llm.invoke([
            SystemMessage(content="Integrate results from multiple sources helpfully."),
            HumanMessage(content=(
                f"Query: {state['user_query']}\n\n"
                f"Results:\n{results_text}\n\nProvide a coherent final response."
            )),
        ]),
    )
    return {"final_response": response.content}


# ============================================================================
# GRAPH
# ============================================================================

def build_smart_orchestrator():
    """Original graph — no HITL. Used as fallback / CLI."""
    g = StateGraph(OrchestratorState)

    g.add_node("planning",               planning_agent_node)
    g.add_node("web_search",             web_search_node)
    g.add_node("rag_search",             rag_search_node)
    g.add_node("club_search",            club_search_node)
    g.add_node("gather_mixed_context",   gather_mixed_context_node)
    g.add_node("execute_tasks",          lambda s: s)
    g.add_node("github_worker",          github_worker_node)
    g.add_node("google_workspace_worker",google_workspace_worker_node)
    g.add_node("conversational_worker",  conversational_worker_node)
    g.add_node("aggregator",             results_aggregator_node)

    g.add_edge(START, "planning")
    g.add_conditional_edges(
        "planning",
        route_after_planning,
        {
            "web_search":           "web_search",
            "rag_search":           "rag_search",
            "club_search":          "club_search",
            "gather_mixed_context": "gather_mixed_context",
            "execute_tasks":        "execute_tasks",
        },
    )
    for ctx in ("web_search", "rag_search", "club_search", "gather_mixed_context"):
        g.add_edge(ctx, "execute_tasks")

    g.add_conditional_edges(
        "execute_tasks",
        fanout_to_workers,
        {
            "github_worker":           "github_worker",
            "google_workspace_worker": "google_workspace_worker",
            "conversational_worker":   "conversational_worker",
        },
    )
    for w in ("github_worker", "google_workspace_worker", "conversational_worker"):
        g.add_edge(w, "aggregator")
    g.add_edge("aggregator", END)

    return g.compile()


# ============================================================================
# FANOUT WITH HITL — Google tasks routed through confirmation_node first
# ============================================================================

def fanout_to_workers_hitl(state: OrchestratorState):
    """
    Like fanout_to_workers but Google tasks go through confirmation_node first.
    GitHub and conversational tasks bypass HITL entirely.
    """
    context = state.get("combined_context", "")
    user_id = state.get("user_id", "")

    sends = []
    for task in state["tasks"]:
        payload = {
            "task": task.model_dump(),
            "user_query": state["user_query"],
            "user_id": user_id,
        }
        if context:
            payload["context"] = context

        if task.worker_type == "github":
            sends.append(Send("github_worker", payload))
        elif task.worker_type in ("gmail", "calendar") or (
            task.worker_type.startswith("google_") or task.google_service
        ):
            # Google tasks → confirmation gate
            sends.append(Send("confirmation_node", payload))
        else:
            sends.append(Send("conversational_worker", payload))
    return sends


def route_after_confirmation(state: OrchestratorState) -> str:
    """After confirmation_node: remaining approved tasks → worker; empty → aggregator."""
    return "google_workspace_worker" if state.get("tasks") else "aggregator"


def build_smart_orchestrator_with_hitl(checkpointer=None):
    """
    Full orchestrator graph with Human-in-the-Loop confirmation for
    Google write actions (Gmail send, Calendar create/update/delete).

    Args:
        checkpointer: LangGraph checkpointer (SqliteSaver / AsyncPostgresSaver).
                      Required for HITL to persist state across HTTP requests.
    """
    from hitl.confirmation import confirmation_node

    g = StateGraph(OrchestratorState)

    # ── Existing nodes (unchanged) ──
    g.add_node("planning",                planning_agent_node)
    g.add_node("web_search",              web_search_node)
    g.add_node("rag_search",              rag_search_node)
    g.add_node("club_search",             club_search_node)
    g.add_node("gather_mixed_context",    gather_mixed_context_node)
    g.add_node("execute_tasks",           lambda s: s)
    g.add_node("github_worker",           github_worker_node)
    g.add_node("google_workspace_worker", google_workspace_worker_node)
    g.add_node("conversational_worker",   conversational_worker_node)
    g.add_node("aggregator",              results_aggregator_node)

    # ── New HITL confirmation node ──
    g.add_node("confirmation_node",       confirmation_node)

    # ── Same edges as before up to execute_tasks ──
    g.add_edge(START, "planning")
    g.add_conditional_edges(
        "planning",
        route_after_planning,
        {
            "web_search":           "web_search",
            "rag_search":           "rag_search",
            "club_search":          "club_search",
            "gather_mixed_context": "gather_mixed_context",
            "execute_tasks":        "execute_tasks",
        },
    )
    for ctx in ("web_search", "rag_search", "club_search", "gather_mixed_context"):
        g.add_edge(ctx, "execute_tasks")

    # ── Updated fanout: Google → confirmation first ──
    g.add_conditional_edges(
        "execute_tasks",
        fanout_to_workers_hitl,
        {
            "github_worker":        "github_worker",
            "confirmation_node":    "confirmation_node",
            "conversational_worker":"conversational_worker",
        },
    )

    # ── After confirmation: approved → worker, all rejected → aggregator ──
    g.add_conditional_edges(
        "confirmation_node",
        route_after_confirmation,
        {
            "google_workspace_worker": "google_workspace_worker",
            "aggregator":              "aggregator",
        },
    )

    for w in ("github_worker", "google_workspace_worker", "conversational_worker"):
        g.add_edge(w, "aggregator")
    g.add_edge("aggregator", END)

    return g.compile(checkpointer=checkpointer)


# ============================================================================
# ORCHESTRATOR
# ============================================================================

class SmartOrchestrator:
    """
    Smart Orchestrator with Human-in-the-Loop support for Google write actions.

    Normal flow  : process() → returns final response.
    HITL flow    : process() → returns {interrupted: True, confirmation_required: {...}}
                   resume()  → returns final response after user approves/rejects.
    """

    def __init__(self):
        from hitl.checkpointer import get_checkpointer
        self._checkpointer = get_checkpointer()
        self.graph = build_smart_orchestrator_with_hitl(checkpointer=self._checkpointer)

        # Track which thread IDs are currently paused waiting for confirmation.
        # Maps thread_id → confirmation message string.
        self._pending_confirmations: dict[str, str] = {}

        rag_ok = get_rag_retrieval_service() is not None
        print(f"\n{'='*60}")
        print(f"SMART ORCHESTRATOR READY  (model: {_model})")
        print(f"  Planning LLM : {_planning_model}")
        print(f"  User RAG     : {'ready' if rag_ok else 'UNAVAILABLE -- check .env'}")
        print(f"  Club RAG     : lazy (initialises on first club query)")
        print(f"  Workers      : conversational | github | gmail | calendar")
        print(f"  Worker LLM   : {os.getenv('WORKER_MODEL', 'llama-3.1-8b-instant')}")
        print(f"  HITL         : ENABLED (gmail send / calendar create/update/delete)")
        print(f"{'='*60}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_config(self, thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    def _extract_interrupt(self, state_or_exc, thread_id: str) -> dict | None:
        """
        LangGraph surfaces interrupts in two ways depending on version:
          1. As __interrupt__ key in the returned state dict.
          2. As a GraphInterrupt / NodeInterrupt exception.
        Handle both here.
        """
        # Pattern 1: interrupt in state
        if isinstance(state_or_exc, dict):
            interrupt_data = state_or_exc.get("__interrupt__")
            if interrupt_data:
                msg = interrupt_data[0].value if hasattr(interrupt_data[0], "value") else str(interrupt_data[0])
                self._pending_confirmations[thread_id] = msg
                return {
                    "success": True,
                    "interrupted": True,
                    "confirmation_required": {"message": msg, "thread_id": thread_id},
                }
            return None

        # Pattern 2: exception
        exc = state_or_exc
        exc_type = type(exc).__name__
        if "interrupt" not in exc_type.lower() and "Interrupt" not in exc_type:
            return None

        try:
            val = exc.value if hasattr(exc, "value") else str(exc)
            if isinstance(val, (list, tuple)) and val:
                val = val[0].value if hasattr(val[0], "value") else str(val[0])
            msg = str(val)
        except Exception:
            msg = str(exc)

        self._pending_confirmations[thread_id] = msg
        return {
            "success": True,
            "interrupted": True,
            "confirmation_required": {"message": msg, "thread_id": thread_id},
        }

    def _build_success_response(self, final: dict) -> dict:
        results = final.get("results", [])
        return {
            "success": True,
            "interrupted": False,
            "response": final.get("final_response", ""),
            "metadata": {
                "total_tasks":      len(results),
                "successful_tasks": sum(1 for r in results if r.success),
                "web_search_used":  bool(final.get("web_context")),
                "rag_search_used":  bool(final.get("rag_context")),
                "club_search_used": bool(final.get("club_context")),
                "workers_used":     list({r.worker_type for r in results}),
            },
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process(self, user_query: str,
                      conversation_history: List[str] = None,
                      user_id: str = "") -> dict:
        """
        Process a user query.

        Returns either:
          - Normal:      {success, interrupted=False, response, metadata}
          - Interrupted: {success, interrupted=True,  confirmation_required: {message, thread_id}}
        """
        if not user_query or not user_query.strip():
            return {"success": False, "interrupted": False, "response": "Empty query.", "metadata": {}}

        thread_id = user_id or "default"
        config    = self._make_config(thread_id)

        state: OrchestratorState = {
            "user_id":               user_id,
            "user_query":            user_query.strip(),
            "conversation_history":  conversation_history or [],
            "plan":                  None,
            "web_context":           [],
            "rag_context":           [],
            "club_context":          [],
            "combined_context":      "",
            "tasks":                 [],
            "results":               [],
            "final_response":        "",
        }

        try:
            final = await self.graph.ainvoke(state, config=config)

            # Check if graph paused mid-run (interrupt embedded in state)
            interrupt_resp = self._extract_interrupt(final, thread_id)
            if interrupt_resp:
                return interrupt_resp

            return self._build_success_response(final)

        except Exception as exc:
            # Check if this is a LangGraph interrupt exception
            interrupt_resp = self._extract_interrupt(exc, thread_id)
            if interrupt_resp:
                return interrupt_resp

            logger.error(f"Orchestrator error: {exc}", exc_info=True)
            return {"success": False, "interrupted": False,
                    "response": f"Orchestrator error: {exc}", "metadata": {}}

    async def resume(self, thread_id: str, user_response: str) -> dict:
        """
        Resume a paused graph after the user approves or rejects.

        Args:
            thread_id:     The user_id used in the original process() call.
            user_response: "approve" | "reject" (or yes/no/ok/cancel).

        Returns the final response dict, same shape as process().
        """
        config = self._make_config(thread_id)
        self._pending_confirmations.pop(thread_id, None)

        try:
            final = await self.graph.ainvoke(
                Command(resume=user_response),
                config=config,
            )

            # Could be another interrupt (multiple write tasks in one query)
            interrupt_resp = self._extract_interrupt(final, thread_id)
            if interrupt_resp:
                return interrupt_resp

            return self._build_success_response(final)

        except Exception as exc:
            interrupt_resp = self._extract_interrupt(exc, thread_id)
            if interrupt_resp:
                return interrupt_resp

            logger.error(f"Resume error: {exc}", exc_info=True)
            return {"success": False, "interrupted": False,
                    "response": f"Resume error: {exc}", "metadata": {}}

    def is_pending_confirmation(self, thread_id: str) -> bool:
        """Returns True if this thread is currently paused waiting for user confirmation."""
        return thread_id in self._pending_confirmations

    def get_pending_message(self, thread_id: str) -> str | None:
        """Returns the pending confirmation message for a thread, or None."""
        return self._pending_confirmations.get(thread_id)

    async def cleanup(self):
        await mcp_pool.cleanup()


# ============================================================================
# CLI
# ============================================================================

def interactive_mode():
    print(f"\n{'='*60}\nSMART ORCHESTRATOR -- CLI\n{'='*60}")
    orch = SmartOrchestrator()
    history: List[str] = []
    try:
        while True:
            try:
                query = input("\nQuery: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break
            if not query:
                continue
            if query.lower() in {"quit", "exit", "q"}:
                print("\nGoodbye!")
                break

            result = asyncio.run(orch.process(query, history))
            history.append(f"User: {query}")
            if result["success"]:
                history.append(f"Assistant: {result['response'][:100]}...")

            print(f"\n{'='*60}\nRESPONSE\n{'='*60}")
            print(result["response"])
            if result["success"]:
                m = result["metadata"]
                print(f"\nworkers={m['workers_used']}  "
                      f"rag={m['rag_search_used']}  "
                      f"club={m['club_search_used']}")
    finally:
        asyncio.run(orch.cleanup())


orchestrator = SmartOrchestrator()

if __name__ == "__main__":
    interactive_mode()