import os
import dotenv
dotenv.load_dotenv()
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio
from langchain.agents import create_agent

# Load API keys from environment variables
API_TOKEN = os.getenv("API_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

print(f"✅ API keys loaded")
print(f"   Bright Data (API_TOKEN): {'✓' if API_TOKEN else '✗ MISSING'}")

async def run_agent():
    llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0.9, api_key=GROQ_API_KEY)
    print("✅ LLM created")

    client = MultiServerMCPClient({
        "math": {
            "command": "python",
            "args": [r"E:\X\projects\MCPs\two_tools\math_server.py"],
            "transport": "stdio",
        },
        "bright_data": {
            "command": "cmd",  # Use cmd instead of npx
            "args": ["/c", "npx", "@brightdata/mcp"],  # cmd /c to run npx
            "transport": "stdio",
            "env": {
                "API_TOKEN": API_TOKEN,
            }
        }
    })
    print("✅ Client created")
    
    tools = await client.get_tools()
    print(f"✅ Tools loaded: {[t.name for t in tools]}")
    
    agent = create_agent(llm, tools)
    print("✅ Agent created")

    # Test 1: Math operations
    try:
        print("\n🧮 Testing math operations...")
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
        print("\n🔍 Testing Bright Data search...")
        bright_data_response = await agent.ainvoke({
            "messages": [{
                "role": "user",
                "content": "Search for 'Tesla stock price' using the search_engine tool"
            }]
        })
        print("✅ Bright Data Response:", bright_data_response["messages"][-1].content)
    except Exception as e:
        print(f"❌ Bright Data error: {e}")

if __name__ == "__main__":
    asyncio.run(run_agent())