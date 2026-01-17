"""
MCP Server for Research RAG
Provides retrieval-only access to the knowledge base
"""

import os
import sys
import json
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from mcp.server import Server
from mcp.types import Resource, Tool, TextContent
from dotenv import load_dotenv

from knowledge_engine.embedding_service import EmbeddingService
from knowledge_engine.vector_store import VectorStore
from knowledge_engine.graph_store import GraphStore
from knowledge_engine.retrieval import HybridRetrieval

# Load environment variables
load_dotenv()

# Initialize MCP server
server = Server("research-rag")

# Initialize knowledge engine components
FAISS_INDEX_DIR = os.getenv("FAISS_INDEX_DIR", "./data/indices")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Initialize services
embedding_service = EmbeddingService(embedding_dim=EMBEDDING_DIM)
vector_store = VectorStore(
    index_dir=FAISS_INDEX_DIR,
    embedding_dim=EMBEDDING_DIM,
    index_type=os.getenv("FAISS_INDEX_TYPE", "FlatL2")
)

# Initialize graph store (optional)
graph_store = None
if NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD:
    graph_store = GraphStore(
        uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
        database=NEO4J_DATABASE
    )

# Initialize retrieval service
retrieval_service = HybridRetrieval(
    embedding_service=embedding_service,
    vector_store=vector_store,
    graph_store=graph_store
)


@server.list_resources()
async def list_resources() -> list[Resource]:
    """
    List all indexed research papers as resources
    """
    resources = retrieval_service.get_all_resources()
    
    return [
        Resource(
            uri=f"paper://{r['paper_id']}",
            name=r['filename'],
            mimeType="application/pdf",
            description=f"Research paper: {r['filename']}"
        )
        for r in resources
    ]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """
    List available RAG tools
    """
    return [
        Tool(
            name="retrieve_context",
            description="Retrieve relevant context from indexed user resources. "
                       "Returns top-k text chunks that are most relevant to the query. "
                       "Use this when you need to find information from the knowledge base.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query or question"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5
                    },
                    "include_citations": {
                        "type": "boolean",
                        "description": "Include citation graph information (requires Neo4j)",
                        "default": False
                    }
                },
                "required": ["query"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    Handle tool calls
    """
    if name == "retrieve_context":
        query = arguments.get("query", "")
        top_k = arguments.get("top_k", 5)
        include_citations = arguments.get("include_citations", False)
        
        if not query:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": "Query cannot be empty"
                }, indent=2)
            )]
        
        # Perform retrieval
        results = retrieval_service.retrieve(
            query=query,
            top_k=top_k,
            include_citations=include_citations
        )
        
        # Format response
        response = {
            "query": query,
            "num_results": len(results["chunks"]),
            "chunks": [
                {
                    "text": chunk["text"],
                    "score": chunk["score"],
                    "source": chunk["metadata"].get("filename", "unknown"),
                    "paper_id": chunk["paper_id"]
                }
                for chunk in results["chunks"]
            ]
        }
        
        # Add citations if requested and available
        if include_citations and results.get("citations"):
            response["citations"] = results["citations"]
        
        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]
    
    else:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": f"Unknown tool: {name}"
            }, indent=2)
        )]


async def main():
    """Run the MCP server"""
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())