# backend/core/agent.py

import asyncio
from typing import AsyncGenerator, Dict, List, Optional, Any
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from pathlib import Path
import time
import uuid

from core.config import settings
from api.models.response import ChatChunk, ToolInfo


class AgentManager:
    """
    Manages the LangChain agent lifecycle.
    
    Why a class? Encapsulates state management and provides
    clean interface for starting, stopping, and using the agent.
    """
    
    def __init__(self):
        self.llm: Optional[ChatGroq] = None
        self.mcp_client: Optional[MultiServerMCPClient] = None
        self.agent = None
        self.tools: List = []
        self._initialized: bool = False
        self._server_config: Dict[str, Dict] = {}
    
    async def initialize(self):
        """
        Initialize the agent and MCP servers.
        
        This is async because MCP server connections can take time.
        """
        if self._initialized:
            print("⚠️  Agent already initialized")
            return
        
        print("🚀 Initializing Agent Manager...")
        
        # Step 1: Initialize LLM
        self.llm = ChatGroq(
            model_name=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.groq_api_key
        )
        print(f"✅ LLM initialized: {settings.llm_model}")
        
        # Step 2: Configure MCP servers based on settings
        self._configure_servers()
        
        # Step 3: Initialize MCP client with configured servers
        if self._server_config:
            self.mcp_client = MultiServerMCPClient(self._server_config)
            print(f"✅ MCP Client created with {len(self._server_config)} servers")
            
            # Step 4: Load tools from all servers
            self.tools = await self.mcp_client.get_tools()
            print(f"✅ Loaded {len(self.tools)} tools")
            
            # Step 5: Create agent with tools
            self.agent = create_agent(self.llm, self.tools)
            print("✅ Agent created successfully")
        else:
            print("⚠️  No MCP servers enabled")
            self.agent = create_agent(self.llm, [])
        
        self._initialized = True
        print("🎉 Agent Manager initialization complete!\n")
    
    def _configure_servers(self):
        """
        Configure which MCP servers to enable based on settings.
        
        This allows easy enable/disable of servers via environment variables.
        """
        servers_dir = settings.mcp_servers_dir
        
        if settings.enable_gmail:
            self._server_config["gmail"] = {
                "command": "python",
                "args": [str(servers_dir / "gmail_server.py")],
                "transport": "stdio",
            }
            print("  📧 Gmail server enabled")
        
        if settings.enable_google_drive:
            self._server_config["google_drive"] = {
                "command": "python",
                "args": [str(servers_dir / "google_drive_server.py")],
                "transport": "stdio",
            }
            print("  📁 Google Drive server enabled")
        
        if settings.enable_google_calendar:
            self._server_config["google_calendar"] = {
                "command": "python",
                "args": [str(servers_dir / "google_calendar_server.py")],
                "transport": "stdio",
            }
            print("  📅 Google Calendar server enabled")
    
    async def shutdown(self):
        """Gracefully shutdown agent and close connections"""
        print("🛑 Shutting down Agent Manager...")
        if self.mcp_client:
            # MCP client cleanup (if it has a close method)
            try:
                await self.mcp_client.close()
            except AttributeError:
                pass  # Client might not have close method
        self._initialized = False
        print("✅ Agent Manager shutdown complete")
    
    async def chat(
        self, 
        message: str, 
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a message to the agent and get complete response.
        
        Args:
            message: User's message
            conversation_id: Optional conversation ID for context
        
        Returns:
            Dict with response message, tools used, and metadata
        """
        if not self._initialized:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        start_time = time.time()
        conversation_id = conversation_id or f"conv_{uuid.uuid4().hex[:8]}"
        
        try:
            # Invoke agent with user message
            response = await self.agent.ainvoke({
                "messages": [{
                    "role": "user",
                    "content": message
                }]
            })
            
            execution_time = time.time() - start_time
            
            # Extract response content
            final_message = response["messages"][-1].content
            
            # Track which tools were used (if available in response)
            tools_used = []
            # LangGraph might include tool calls in intermediate steps
            if "intermediate_steps" in response:
                for step in response["intermediate_steps"]:
                    if hasattr(step, 'tool'):
                        tools_used.append(step.tool)
            
            return {
                "message": final_message,
                "conversation_id": conversation_id,
                "message_id": f"msg_{uuid.uuid4().hex[:8]}",
                "tools_used": tools_used,
                "execution_time": execution_time,
                "metadata": {
                    "model": settings.llm_model,
                }
            }
        
        except Exception as e:
            execution_time = time.time() - start_time
            print(f"❌ Error during chat: {e}")
            raise
    
    async def stream_chat(
        self, 
        message: str, 
        conversation_id: Optional[str] = None
    ) -> AsyncGenerator[ChatChunk, None]:
        """
        Stream agent response token by token.
        
        This is more complex but provides better UX - user sees
        response appearing in real-time like ChatGPT.
        
        Yields:
            ChatChunk objects with incremental response data
        """
        if not self._initialized:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        conversation_id = conversation_id or f"conv_{uuid.uuid4().hex[:8]}"
        
        try:
            # LangChain streaming
            async for chunk in self.agent.astream({
                "messages": [{
                    "role": "user",
                    "content": message
                }]
            }):
                # Different chunk types based on agent state
                if "messages" in chunk:
                    # Final message
                    content = chunk["messages"][-1].content
                    if content:
                        yield ChatChunk(
                            type="token",
                            content=content,
                            metadata={"conversation_id": conversation_id}
                        )
                
                elif "tools" in chunk:
                    # Tool being called
                    tool_call = chunk["tools"]
                    yield ChatChunk(
                        type="tool_call",
                        tool_name=tool_call.get("name"),
                        tool_input=tool_call.get("args"),
                        metadata={"conversation_id": conversation_id}
                    )
                
                elif "tool_result" in chunk:
                    # Tool result received
                    yield ChatChunk(
                        type="tool_result",
                        tool_output=chunk["tool_result"],
                        metadata={"conversation_id": conversation_id}
                    )
            
            # Send completion signal
            yield ChatChunk(
                type="done",
                metadata={"conversation_id": conversation_id}
            )
        
        except Exception as e:
            print(f"❌ Error during streaming: {e}")
            yield ChatChunk(
                type="error",
                content=str(e),
                metadata={"conversation_id": conversation_id}
            )
    
    def get_tools_info(self) -> List[ToolInfo]:
        """
        Get information about all available tools.
        
        Useful for frontend to display capabilities.
        """
        tools_info = []
        for tool in self.tools:
            tools_info.append(ToolInfo(
                name=tool.name,
                description=tool.description,
                parameters=tool.args if hasattr(tool, 'args') else {},
                server=self._get_server_for_tool(tool.name)
            ))
        return tools_info
    
    def _get_server_for_tool(self, tool_name: str) -> str:
        """Determine which server provides a given tool"""
        if "gmail" in tool_name.lower():
            return "gmail"
        elif "drive" in tool_name.lower():
            return "google_drive"
        elif "calendar" in tool_name.lower():
            return "google_calendar"
        return "unknown"
    
    @property
    def is_initialized(self) -> bool:
        """Check if agent is ready to use"""
        return self._initialized


# Global instance (singleton pattern)
agent_manager = AgentManager()