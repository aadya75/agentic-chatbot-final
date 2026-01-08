# client.py

import os
import dotenv
dotenv.load_dotenv()
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio
from langchain.agents import create_agent
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
MCP_SERVERS_DIR = BACKEND_DIR / 'mcp_servers'

# Load API keys from environment variables
API_TOKEN = os.getenv("API_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

print(f"✅ API keys loaded")
print(f"   Bright Data (API_TOKEN): {'✓' if API_TOKEN else '✗ MISSING'}")
print(f"   Groq API Key: {'✓' if GROQ_API_KEY else '✗ MISSING'}")

async def run_agent():
    llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0.9, api_key=GROQ_API_KEY)
    print("✅ LLM created")

    # Configure all MCP serv/ers
    client = MultiServerMCPClient({
        # "math": {
        #     "command": "python",
        #     "args": [r"E:\X\projects\MCPs\two_tools\math_server.py"],
        #     "transport": "stdio",
        # },
        # "bright_data": {
        #     "command": "cmd",
        #     "args": ["/c", "npx", "@brightdata/mcp"],
        #     "transport": "stdio",
        #     "env": {
        #         "API_TOKEN": API_TOKEN,
        #     }
        # },
        "gmail": {
            "command": "python",
            "args": [str(MCP_SERVERS_DIR / "gmail_server.py")],
            "transport": "stdio",
        },
        "google_drive": {
            "command": "python",
            "args": [str(MCP_SERVERS_DIR / "drive_server.py")],
            "transport": "stdio",
        },
        "google_calendar": {
            "command": "python",
            "args": [str(MCP_SERVERS_DIR / "calendar_server.py")],
            "transport": "stdio",
        }
    })
    print("✅ Client created with all servers")
    
    tools = await client.get_tools()
    print(f"✅ Tools loaded ({len(tools)} total):")
    for tool in tools:
        print(f"   - {tool.name}")
    
    agent = create_agent(llm, tools)
    print("✅ Agent created")

    # Test 1: Math operations
    try:
        print("\n" + "="*60)
        print("🧮 Test 1: Math operations")
        print("="*60)
        math_response = await agent.ainvoke({
            "messages": [{
                "role": "user",
                "content": "First add 3 and 5. Then multiply the result by 12. Use tools step by step."
            }]
        })
        print("✅ Math Response:", math_response["messages"][-1].content)
    except Exception as e:
        print(f"❌ Math error: {e}")

    # Test 2: Bright Data search
    try:
        print("\n" + "="*60)
        print("🔍 Test 2: Bright Data search")
        print("="*60)
        bright_data_response = await agent.ainvoke({
            "messages": [{
                "role": "user",
                "content": "Search for 'Tesla stock price' using the search_engine tool"
            }]
        })
        print("✅ Bright Data Response:", bright_data_response["messages"][-1].content)
    except Exception as e:
        print(f"❌ Bright Data error: {e}")

    # Test 3: Gmail
    try:
        print("\n" + "="*60)
        print("📧 Test 3: Gmail - Get latest emails")
        print("="*60)
        gmail_response = await agent.ainvoke({
            "messages": [{
                "role": "user",
                "content": "Get my 3 latest emails from inbox"
            }]
        })
        print("✅ Gmail Response:", gmail_response["messages"][-1].content)
    except Exception as e:
        print(f"❌ Gmail error: {e}")

    # Test 4: Google Drive
    try:
        print("\n" + "="*60)
        print("📁 Test 4: Google Drive - List files")
        print("="*60)
        drive_response = await agent.ainvoke({
            "messages": [{
                "role": "user",
                "content": "List my recent files from Google Drive (up to 5 files)"
            }]
        })
        print("✅ Drive Response:", drive_response["messages"][-1].content)
    except Exception as e:
        print(f"❌ Drive error: {e}")

    # Test 5: Google Calendar
    try:
        print("\n" + "="*60)
        print("📅 Test 5: Google Calendar - Upcoming events")
        print("="*60)
        calendar_response = await agent.ainvoke({
            "messages": [{
                "role": "user",
                "content": "Show me my upcoming calendar events for the next 3 days"
            }]
        })
        print("✅ Calendar Response:", calendar_response["messages"][-1].content)
    except Exception as e:
        print(f"❌ Calendar error: {e}")

    # Test 6: Complex multi-tool task
    try:
        print("\n" + "="*60)
        print("🎯 Test 6: Complex task using multiple tools")
        print("="*60)
        complex_response = await agent.ainvoke({
            "messages": [{
                "role": "user",
                "content": """
                Please do the following:
                1. Search my Gmail for any unread emails
                2. Check my Google Calendar for today's events
                3. Tell me a summary of both
                """
            }]
        })
        print("✅ Complex Task Response:", complex_response["messages"][-1].content)
    except Exception as e:
        print(f"❌ Complex task error: {e}")

    print("\n" + "="*60)
    print("🎉 All tests completed!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_agent())