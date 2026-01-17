"""
Debug MCP Initialization Issues
Run this to identify which MCP server is failing
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv()


async def test_individual_server(server_name, server_config):
    """Test a single MCP server"""
    print(f"\n{'='*70}")
    print(f"Testing: {server_name}")
    print(f"{'='*70}")
    print(f"Command: {server_config['command']}")
    print(f"Args: {' '.join(server_config['args'])}")
    print()
    
    try:
        from mcp.client.stdio import stdio_client
        from mcp.client import ClientSession
        
        async with stdio_client(server_config) as (read, write):
            print(f"  ✓ Server process started")
            
            async with ClientSession(read, write) as session:
                print(f"  ✓ Client session created")
                
                await session.initialize()
                print(f"  ✓ Session initialized")
                
                # Try to list tools
                try:
                    tools = await session.list_tools()
                    print(f"  ✓ Tools listed: {len(tools)} tools found")
                    for tool in tools:
                        print(f"    - {tool.name}")
                except Exception as e:
                    print(f"  ⚠ Could not list tools: {e}")
                
                # Try to list resources
                try:
                    resources = await session.list_resources()
                    print(f"  ✓ Resources listed: {len(resources)} resources found")
                except Exception as e:
                    print(f"  ⚠ Could not list resources: {e}")
                
                print(f"\n✅ {server_name}: SUCCESS")
                return True
                
    except Exception as e:
        print(f"\n❌ {server_name}: FAILED")
        print(f"Error: {e}")
        print("\nFull traceback:")
        import traceback
        traceback.print_exc()
        return False


async def debug_all_servers():
    """Test all MCP servers individually"""
    
    print("\n" + "="*70)
    print("MCP SERVERS DEBUG TOOL")
    print("="*70)
    
    # Check if mcp_config.json exists
    config_path = Path("../mcp_config.json")
    if not config_path.exists():
        config_path = Path("mcp_config.json")
    
    if not config_path.exists():
        print("\n⚠️ mcp_config.json not found")
        print("Creating default configuration...")
        
        import json
        default_config = {
            "mcpServers": {
                "gmail": {
                    "command": "python",
                    "args": ["backend/mcp_servers/gmail_server.py"],
                    "env": {}
                },
                "google_drive": {
                    "command": "python",
                    "args": ["backend/mcp_servers/google_drive_server.py"],
                    "env": {}
                },
                "google_calendar": {
                    "command": "python",
                    "args": ["backend/mcp_servers/google_calendar_server.py"],
                    "env": {}
                },
                "rag": {
                    "command": "python",
                    "args": ["backend/mcp_servers/rag_server.py"],
                    "env": {}
                }
            }
        }
        
        with open("mcp_config.json", 'w') as f:
            json.dump(default_config, f, indent=2)
        
        print("✓ Created mcp_config.json")
        config_path = Path("mcp_config.json")
    
    # Define server configurations
    servers = {
        "gmail": {
            "command": "python",
            "args": ["mcp_servers/gmail_server.py"],
            "env": {}
        },
        "google_drive": {
            "command": "python",
            "args": ["mcp_servers/google_drive_server.py"],
            "env": {}
        },
        "google_calendar": {
            "command": "python",
            "args": ["mcp_servers/google_calendar_server.py"],
            "env": {}
        },
        "rag": {
            "command": "python",
            "args": ["mcp_servers/rag_server.py"],
            "env": {}
        }
    }
    
    # Check if server files exist
    print("\n" + "-"*70)
    print("FILE CHECK")
    print("-"*70)
    
    all_exist = True
    for name, config in servers.items():
        server_path = Path(config['args'][0])
        if server_path.exists():
            print(f"  ✓ {name}: {server_path}")
        else:
            print(f"  ✗ {name}: {server_path} (NOT FOUND)")
            all_exist = False
    
    if not all_exist:
        print("\n❌ Some server files are missing!")
        print("Make sure all MCP server files are in the correct location.")
        return
    
    # Test each server
    results = {}
    for name, config in servers.items():
        result = await test_individual_server(name, config)
        results[name] = result
        await asyncio.sleep(0.5)  # Small delay between tests
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    success_count = sum(1 for r in results.values() if r)
    total_count = len(results)
    
    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}  {name}")
    
    print(f"\nResults: {success_count}/{total_count} servers working")
    
    if success_count == total_count:
        print("\n🎉 All MCP servers are working correctly!")
        print("\nThe issue might be in how they're being initialized together.")
        print("Check your core/mcp_client.py or core/agent.py")
    else:
        print("\n⚠️ Some servers failed. Check the errors above.")
        print("\nCommon fixes:")
        print("  1. Make sure all dependencies are installed")
        print("  2. Check .env file has correct credentials")
        print("  3. Verify file paths in mcp_config.json")
        print("  4. For rag: ensure FAISS_INDEX_DIR exists")


async def test_rag_specifically():
    """Deep test of rag server"""
    
    print("\n" + "="*70)
    print("RAG DEEP TEST")
    print("="*70)
    
    # Check environment variables
    print("\nEnvironment Variables:")
    env_vars = [
        "FAISS_INDEX_DIR",
        "UPLOAD_DIR",
        "EMBEDDING_DIM",
        "NEO4J_URI",
        "NEO4J_USER",
        "NEO4J_PASSWORD"
    ]
    
    for var in env_vars:
        value = os.getenv(var, "(not set)")
        print(f"  {var}: {value}")
    
    # Check directories
    print("\nDirectory Check:")
    faiss_dir = os.getenv("FAISS_INDEX_DIR", "./data/indices")
    upload_dir = os.getenv("UPLOAD_DIR", "./data/uploads")
    
    for dir_path in [faiss_dir, upload_dir]:
        if Path(dir_path).exists():
            print(f"  ✓ {dir_path}")
        else:
            print(f"  ✗ {dir_path} (creating...)")
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            print(f"    ✓ Created {dir_path}")
    
    # Try to import and initialize
    print("\nImport Test:")
    try:
        from knowledge_engine.embedding_service import EmbeddingService
        print("  ✓ EmbeddingService")
        
        from knowledge_engine.vector_store import VectorStore
        print("  ✓ VectorStore")
        
        from knowledge_engine.retrieval import HybridRetrieval
        print("  ✓ HybridRetrieval")
        
        # Try to initialize
        print("\nInitialization Test:")
        embedding_service = EmbeddingService(embedding_dim=384)
        print("  ✓ EmbeddingService initialized")
        
        vector_store = VectorStore(
            index_dir=faiss_dir,
            embedding_dim=384,
            index_type="FlatL2"
        )
        print("  ✓ VectorStore initialized")
        
        stats = vector_store.get_stats()
        print(f"  ✓ Stats: {stats}")
        
        print("\n✅  RAG components working!")
        
    except Exception as e:
        print(f"\n❌ Import/initialization failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║              MCP SERVERS DEBUG TOOL                                ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    
    # Check we're in the right directory
    if not Path("mcp_servers").exists():
        print("\n❌ Error: mcp_servers directory not found")
        print("Please run this script from the backend directory")
        sys.exit(1)
    
    # Run tests
    asyncio.run(test_rag_specifically())
    print("\n")
    asyncio.run(debug_all_servers())