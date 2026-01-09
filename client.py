import os
import sys
import dotenv
dotenv.load_dotenv()
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio
from langchain.agents import create_agent

# Load API keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

print(f"✅ API keys loaded")
print(f"   GROQ API Key: {'✓' if GROQ_API_KEY else '✗ MISSING'}")
print(f"   GitHub Token: {'✓' if GITHUB_TOKEN else '✗ MISSING'}")

async def run_agent():
    llm = ChatGroq(
    model_name="llama-3.1-70b-versatile",  # Better tool calling support
    temperature=0.7,
    api_key=GROQ_API_KEY
)
    print("✅ LLM created")

    

    client = MultiServerMCPClient({
        # "ddgs": {
        #     "command": sys.executable,  # Use current Python interpreter
        #     "args": ["backend/mcp_servers/web_search.py"],
        #     "transport": "stdio",
        # },
        "github": {
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-github",
                "--github-personal-access-token",
                GITHUB_TOKEN
            ],
            "transport": "stdio",
        }
    })
    print("✅ Client created")
    
    # Get and display all tools
    tools = await client.get_tools()
    print(f"\n📋 Tools loaded: {len(tools)} total")
    # for tool in tools:
    #     print(f"   - {tool.name}")
    #     print(f"     Description: {tool.description[:80]}...")
        # print()
    
    agent = create_agent(llm, tools)
    print("✅ Agent created")

    # Test web search
    # try:
    #     print("\n🔍 Testing web search...")
    #     web_search_response = await agent.ainvoke({
    #         "messages": [{
    #             "role": "user",
    #             "content": "search web for the top 3 hotels in bangalore"
    #         }]
    #     })
    #     print("✅ Web Search Response:", web_search_response["messages"][-1].content)
    # except Exception as e:
    #     print(f"❌ Web search error: {e}")
        # import traceback
        # traceback.print_exc()

    #Test GitHub
    try:
        print('\n🐙 Testing GitHub...')
        github_response = await agent.ainvoke({
            "messages": [
                {
                    "role": "system",
                    "content": "Be concise. Only list repository names briefly."
                },
                {
                    "role": "user",
                    "content": "find the top 3 most starred python repositories on github"
                }
            ]
        })
        print("✅ GitHub Response:", github_response["messages"][-1].content)
    except Exception as e:
        print(f"❌ GitHub error: {e}")

if __name__ == "__main__":
    asyncio.run(run_agent())