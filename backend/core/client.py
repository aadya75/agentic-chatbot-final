"""
test.py

Updated test script for orchestration system.
Now tests both direct MCP and orchestrator.
"""

import os
import dotenv
dotenv.load_dotenv()
import asyncio
from pathlib import Path
import sys

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BACKEND_DIR))

from core.agent import agent_manager
from orchestration.orchestrator import create_orchestrator

# Load API keys
API_TOKEN = os.getenv("API_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

print(f"✅ API keys loaded")
print(f"   Groq API Key: {'✓' if GROQ_API_KEY else '✗ MISSING'}")


async def test_direct_mcp():
    """Test direct MCP tool access"""
    print("\n" + "="*70)
    print("📋 TEST 1: Direct MCP Tool Access")
    print("="*70)
    
    try:
        # Initialize
        await agent_manager.initialize()
        
        # # Test Gmail
        print("\n📧 Testing Gmail...")
        result = await agent_manager.get_latest_gmail_messages(count=3)
        print(f"✅ Got {len(result.get('messages', []))} emails")
        
        # Test Calendar
        print("\n📅 Testing Calendar...")
        result = await agent_manager.get_upcoming_events(days=5)
        print(f"✅ Got {len(result.get('events', []))} events")
        
        # Test RAG
        print("\n📚 Testing RAG...")
        result = await agent_manager.rag_retrieve("What is PID control?", top_k=3)
        print(f"✅ Got {len(result.get('documents', []))} documents")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    try:
        await agent_manager.initialize()
        # # Test Gmail
        print("\n📧 Testing Gmail...")
        result = await agent_manager.get_latest_gmail_messages(count=3)
        print(f"✅ Got {len(result.get('messages', []))} emails")
    except Exception as e:
        print(f"❌ Error: {e}")
        
    try: 
        # Test Calendar
        print("\n📅 Testing Calendar...")
        result = await agent_manager.get_upcoming_events(days=5)
        print(f"✅ Got {len(result.get('events', []))} events")
    except Exception as e:
        print(f"❌ Error: {e}")
        
    try:
        # Test RAG
        print("\n📚 Testing RAG...")
        result = await agent_manager.rag_retrieve("What is PID control?", top_k=3)
        print(f"✅ Got {len(result.get('documents', []))} documents")
    except Exception as e:
        print(f"❌ Error: {e}")
        


async def test_orchestrator():
    """Test LangGraph orchestrator"""
    print("\n" + "="*70)
    print("🎯 TEST 2: LangGraph Orchestrator")
    print("="*70)
    
    try:
        # Initialize
        await agent_manager.initialize()
        
        # Create orchestrator
        orchestrator = create_orchestrator(agent_manager)
        agent_manager.orchestrator = orchestrator
        
        print("\n✅ Orchestrator ready")
        
        # Test 1: Simple knowledge query
        # print("\n📚 Test 1: Knowledge query")
        # result = await agent_manager.chat(
        #     message="What is PID control?",
        #     use_orchestrator=True
        # )
        # print(f"Response: {result['message']}...")
        # print(f"Intents: {result['metadata'].get('intents', [])}")
        # print(f"Tools used: {result.get('tools_used', [])}")
        
        # Test 2: Email query
        print("\n📧 Test 2: Email query")
        result = await agent_manager.chat(
            message="Send an email to nainaamodii@gmail.com informing that orhestration of agentic chatbot is successfull.",
            use_orchestrator=True
        )
        print(f"Response: {result['message']}...")
        print(f"Intents: {result['metadata'].get('intents', [])}")
        print(f"Tools used: {result.get('tools_used', [])}")
        
        # Test 3: Multi-intent query
        print("\n🎯 Test 3: Multi-intent query")
        result = await agent_manager.chat(
            message="Create an event with following details : name PID controllers on 22 january 2026 for 3:00 pm to 4:00pm",
            use_orchestrator=True
        )
        print(f"Response: {result['message']}...")
        print(f"Intents: {result['metadata'].get('intents', [])}")
        print(f"Tools used: {result.get('tools_used', [])}")
        
    #     # Test 4: Red flag
    #     print("\n🚨 Test 4: Red flag detection")
    #     result = await agent_manager.chat(
    #         message="Delete all my emails",
    #         use_orchestrator=True
    #     )
    #     print(f"Response: {result['message']}...")
    #     print(f"Red flag: {result['metadata'].get('red_flag', False)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def test_thread_management():
    """Test conversation threads"""
    print("\n" + "="*70)
    print("💬 TEST 3: Thread Management")
    print("="*70)
    
    try:
        await agent_manager.initialize()
        orchestrator = create_orchestrator(agent_manager)
        agent_manager.orchestrator = orchestrator
        
        # Create thread
        thread_id = agent_manager.create_thread()
        print(f"✅ Created thread: {thread_id}")
        
        # Message 1
        result1 = await agent_manager.chat(
            message="I'm working on a drone project",
            thread_id=thread_id,
            use_orchestrator=True
        )
        print(f"\nMessage 1: {result1['message'][:100]}...")
        
        # Message 2 (with context)
        result2 = await agent_manager.chat(
            message="What sensors do I need?",
            thread_id=thread_id,
            use_orchestrator=True
        )
        print(f"\nMessage 2: {result2['message'][:100]}...")
        
        # Check thread
        messages = agent_manager.get_messages(thread_id)
        print(f"\n✅ Thread has {len(messages)} messages")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("🤖 Robotics Club Assistant - Test Suite")
    print("="*70)
    
    # Choose which tests to run
    # await test_direct_mcp()
    await test_orchestrator()
    # await test_thread_management()
    
    # Cleanup
    await agent_manager.shutdown()
    
    print("\n" + "="*70)
    print("✅ All tests completed!")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())


