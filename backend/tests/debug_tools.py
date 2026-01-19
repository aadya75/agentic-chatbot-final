"""
debug_tools.py

Run this to see the exact names and parameters of your MCP tools.
This will help you fix the tool wrapper methods.
"""

import os
import dotenv
dotenv.load_dotenv()
import asyncio
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BACKEND_DIR))

from core.agent import agent_manager


async def debug_tools():
    """Print all available tools with their exact names and parameters"""
    
    print("\n" + "="*70)
    print("🔍 MCP Tools Debug Information")
    print("="*70)
    
    # Initialize agent manager
    await agent_manager.initialize()
    
    print(f"\n✅ Found {len(agent_manager.tools)} tools\n")
    
    # Group tools by server
    tools_by_server = {
        "gmail": [],
        "calendar": [],
        "drive": [],
        "rag": [],
        "unknown": []
    }
    
    for tool in agent_manager.tools:
        name_lower = tool.name.lower()
        
        if "gmail" in name_lower or "email" in name_lower:
            tools_by_server["gmail"].append(tool)
        elif "calendar" in name_lower or "event" in name_lower:
            tools_by_server["calendar"].append(tool)
        elif "drive" in name_lower:
            tools_by_server["drive"].append(tool)
        elif "rag" in name_lower or "retrieve" in name_lower:
            tools_by_server["rag"].append(tool)
        else:
            tools_by_server["unknown"].append(tool)
    
    # Print tools by server
    for server, tools in tools_by_server.items():
        if not tools:
            continue
        
        print(f"\n{'='*70}")
        print(f"📧 {server.upper()} TOOLS ({len(tools)})")
        print('='*70)
        
        for tool in tools:
            print(f"\n🔧 Tool Name: '{tool.name}'")
            print(f"   Description: {tool.description}")
            
            # Try to get parameter information
            if hasattr(tool, 'args_schema'):
                print(f"   Parameters Schema: {tool.args_schema}")
            
            if hasattr(tool, 'args'):
                print(f"   Parameters: {tool.args}")
            
            # Try to get the function signature
            if hasattr(tool, 'func'):
                import inspect
                try:
                    sig = inspect.signature(tool.func)
                    print(f"   Function Signature: {sig}")
                except:
                    pass
    
    print("\n" + "="*70)
    print("📝 RECOMMENDED WRAPPER METHODS")
    print("="*70)
    
    # Generate wrapper recommendations
    print("\nBased on the tools found, update your agent.py with:")
    print("\n```python")
    
    # Gmail wrappers
    gmail_tools = tools_by_server["gmail"]
    if gmail_tools:
        print("\n# Gmail Wrappers")
        for tool in gmail_tools:
            method_name = tool.name.replace("-", "_").replace(" ", "_").lower()
            print(f"""
async def {method_name}(self, **kwargs) -> Dict:
    return await self.call_tool("gmail", "{tool.name}", kwargs)
""")
    
    # Calendar wrappers
    calendar_tools = tools_by_server["calendar"]
    if calendar_tools:
        print("\n# Calendar Wrappers")
        for tool in calendar_tools:
            method_name = tool.name.replace("-", "_").replace(" ", "_").lower()
            print(f"""
async def {method_name}(self, **kwargs) -> Dict:
    return await self.call_tool("google_calendar", "{tool.name}", kwargs)
""")
    
    print("\n```")
    
    print("\n" + "="*70)
    print("✅ Debug complete!")
    print("="*70)
    
    # Cleanup
    await agent_manager.shutdown()


if __name__ == "__main__":
    asyncio.run(debug_tools())