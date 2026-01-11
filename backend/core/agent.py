async def initialize(self):
        """
        Initialize the agent and MCP servers.
        
        This is async because MCP server connections can take time.
        """
        if self._initialized:
            logger.warning("Agent already initialized")
            return
        
        logger.info("🚀 Initializing Agent Manager...")
        
        # Step 1: Initialize LLM with tool choice disabled by default
        self.llm = ChatGroq(
            model_name=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.groq_api_key,
            model_kwargs={
                "tool_choice": "auto"  # Let model choose, but only from provided tools
            }
        )
        logger.info(f"✅ LLM initialized: {settings.llm_model}")
        
        # Step 2: Configure MCP servers based on settings
        self._configure_servers()
        
        # Step 3: Initialize MCP client with configured servers
        if self._server_config:
            try:
                self.mcp_client = MultiServerMCPClient(self._server_config)
                logger.info(f"✅ MCP Client created with {len(self._server_config)} servers")
            except Exception as e:
                logger.warning(f"⚠️  Warning: Failed to initialize MCP client: {e}")
                logger.info("   Continuing without MCP tools...")
                
                # Step 4: Load tools# backend/core/agent.py

import asyncio
import uuid
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Optional, Any
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from pathlib import Path
import time
import logging

from core.config import settings
from api.models.response import ChatChunk, ToolInfo

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Manages the LangChain agent lifecycle AND conversation threads.
    
    Combines agent functionality with thread/conversation management.
    """
    
    def __init__(self):
        # Agent-related attributes
        self.llm: Optional[ChatGroq] = None
        self.mcp_client: Optional[MultiServerMCPClient] = None
        self.agent = None
        self.tools: List = []
        self._initialized: bool = False
        self._server_config: Dict[str, Dict] = {}
        
        # Thread management attributes
        self.threads: Dict[str, dict] = {}
        self.active_threads: set = set()
        
        logger.info("AgentManager instance created")
    
    async def initialize(self):
        """
        Initialize the agent and MCP servers.
        
        This is async because MCP server connections can take time.
        """
        if self._initialized:
            logger.warning("Agent already initialized")
            return
        
        logger.info("🚀 Initializing Agent Manager...")
        
        # Step 1: Initialize LLM
        self.llm = ChatGroq(
            model_name=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.groq_api_key
        )
        logger.info(f"✅ LLM initialized: {settings.llm_model}")
        
        # Step 2: Configure MCP servers based on settings
        self._configure_servers()
        
        # Step 3: Initialize MCP client with configured servers
        if self._server_config:
            try:
                self.mcp_client = MultiServerMCPClient(self._server_config)
                logger.info(f"✅ MCP Client created with {len(self._server_config)} servers")
                
                # Step 4: Load tools from all servers
                self.tools = await self.mcp_client.get_tools()
                logger.info(f"✅ Loaded {len(self.tools)} tools")
                
                # Log tool names for debugging
                for tool in self.tools:
                    logger.info(f"   📌 Tool: {tool.name}")
                
            except Exception as e:
                logger.warning(f"⚠️  Warning: Failed to initialize MCP tools: {e}")
                logger.info("   Continuing without MCP tools...")
                self.tools = []
        else:
            logger.warning("⚠️  No MCP servers enabled")
            self.tools = []
        
        # Step 5: Create agent with tools
        # Important: Only create agent with tools if we have them
        if self.tools:
            try:
                self.agent = create_agent(self.llm, self.tools)
                logger.info("✅ Agent created successfully with tools")
            except Exception as e:
                logger.error(f"❌ Failed to create agent with tools: {e}")
                logger.info("   Creating agent without tools...")
                self.agent = create_agent(self.llm, [])
        else:
            self.agent = create_agent(self.llm, [])
            logger.info("✅ Agent created without tools")
        
        self._initialized = True
        logger.info("🎉 Agent Manager initialization complete!\n")
    
    def _configure_servers(self):
        """
        Configure which MCP servers to enable based on settings.
        
        This allows easy enable/disable of servers via environment variables.
        """
        servers_dir = Path(__file__).resolve().parent.parent / 'mcp_servers'
        
        if settings.enable_gmail:
            self._server_config["gmail"] = {
                "command": "python",
                "args": [str(servers_dir / "gmail_server.py")],
                "transport": "stdio",
            }
            logger.info("  📧 Gmail server enabled")
        
        if settings.enable_google_drive:
            self._server_config["google_drive"] = {
                "command": "python",
                "args": [str(servers_dir / "google_drive_server.py")],
                "transport": "stdio",
            }
            logger.info("  📁 Google Drive server enabled")
        
        if settings.enable_google_calendar:
            self._server_config["google_calendar"] = {
                "command": "python",
                "args": [str(servers_dir / "google_calendar_server.py")],
                "transport": "stdio",
            }
            logger.info("  📅 Google Calendar server enabled")
    
    async def shutdown(self):
        """Gracefully shutdown agent and close connections"""
        logger.info("🛑 Shutting down Agent Manager...")
        if self.mcp_client:
            try:
                await self.mcp_client.close()
            except AttributeError:
                pass
        self._initialized = False
        logger.info("✅ Agent Manager shutdown complete")
    
    # ========== THREAD MANAGEMENT METHODS ==========
    
    def create_thread(self) -> str:
        """
        Create a new conversation thread
        
        Returns:
            str: The new thread ID
        """
        thread_id = str(uuid.uuid4())
        
        self.threads[thread_id] = {
            "id": thread_id,
            "created_at": datetime.utcnow().isoformat(),
            "messages": [],
            "metadata": {},
            "status": "active"
        }
        
        self.active_threads.add(thread_id)
        
        logger.info(f"Created new thread: {thread_id}")
        return thread_id
    
    def get_thread(self, thread_id: str) -> Optional[dict]:
        """Get a thread by ID"""
        return self.threads.get(thread_id)
    
    def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread"""
        if thread_id in self.threads:
            del self.threads[thread_id]
            self.active_threads.discard(thread_id)
            logger.info(f"Deleted thread: {thread_id}")
            return True
        return False
    
    def list_threads(self) -> List[dict]:
        """List all threads"""
        return [
            {
                "id": thread_id,
                "created_at": thread_data["created_at"],
                "message_count": len(thread_data["messages"]),
                "status": thread_data["status"]
            }
            for thread_id, thread_data in self.threads.items()
        ]
    
    def add_message(self, thread_id: str, role: str, content: str, metadata: Optional[dict] = None) -> bool:
        """Add a message to a thread"""
        thread = self.threads.get(thread_id)
        if not thread:
            logger.warning(f"Thread not found: {thread_id}")
            return False
        
        message = {
            "id": str(uuid.uuid4()),
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        thread["messages"].append(message)
        logger.debug(f"Added message to thread {thread_id}")
        return True
    
    def get_messages(self, thread_id: str) -> List[dict]:
        """Get all messages from a thread"""
        thread = self.threads.get(thread_id)
        if not thread:
            return []
        return thread["messages"]
    
    def clear_thread(self, thread_id: str) -> bool:
        """Clear all messages from a thread"""
        thread = self.threads.get(thread_id)
        if not thread:
            return False
        
        thread["messages"] = []
        logger.info(f"Cleared messages from thread: {thread_id}")
        return True
    
    def get_thread_count(self) -> int:
        """Get total number of threads"""
        return len(self.threads)
    
    def get_active_thread_count(self) -> int:
        """Get number of active threads"""
        return len(self.active_threads)
    
    # ========== CHAT METHODS WITH THREAD SUPPORT ==========
    
    async def chat(
        self, 
        message: str, 
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a message to the agent and get complete response.
        
        Args:
            message: User's message
            thread_id: Optional thread ID for conversation context
        
        Returns:
            Dict with response message, tools used, and metadata
        """
        if not self._initialized:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        # Create thread if not provided
        if not thread_id:
            thread_id = self.create_thread()
        
        # Verify thread exists
        thread = self.get_thread(thread_id)
        if not thread:
            raise ValueError(f"Thread not found: {thread_id}")
        
        start_time = time.time()
        
        # Add user message to thread
        self.add_message(thread_id, "user", message)
        
        try:
            # Get conversation history
            history = self.get_messages(thread_id)
            
            # Build messages for agent (all messages in thread)
            agent_messages = []
            for msg in history:
                agent_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            logger.info(f"Processing message with {len(self.tools)} available tools")
            
            # Invoke agent with conversation history
            # The agent will automatically use tools if needed
            try:
                response = await self.agent.ainvoke({
                    "messages": agent_messages
                })
            except Exception as e:
                logger.error(f"Agent invocation error: {e}")
                # If tool-related error, try without agent (direct LLM)
                if "tool" in str(e).lower() or "function" in str(e).lower():
                    logger.warning("Tool error detected, falling back to direct LLM call")
                    from langchain.schema import HumanMessage
                    llm_response = await self.llm.ainvoke([HumanMessage(content=message)])
                    response = {
                        "messages": [llm_response]
                    }
                else:
                    raise
            
            execution_time = time.time() - start_time
            
            # Extract response content
            final_message = response["messages"][-1].content
            
            # Add assistant response to thread
            self.add_message(thread_id, "assistant", final_message)
            
            # Track which tools were used
            tools_used = []
            if "intermediate_steps" in response:
                for step in response["intermediate_steps"]:
                    if hasattr(step, 'tool'):
                        tools_used.append(step.tool)
            
            return {
                "message": final_message,
                "thread_id": thread_id,
                "message_id": f"msg_{uuid.uuid4().hex[:8]}",
                "tools_used": tools_used,
                "execution_time": execution_time,
                "metadata": {
                    "model": settings.llm_model,
                }
            }
        
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ Error during chat: {e}")
            raise
    
    async def stream_chat(
        self, 
        message: str, 
        thread_id: Optional[str] = None
    ) -> AsyncGenerator[ChatChunk, None]:
        """
        Stream agent response token by token with thread support.
        
        Yields:
            ChatChunk objects with incremental response data
        """
        if not self._initialized:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        # Create thread if not provided
        if not thread_id:
            thread_id = self.create_thread()
        
        # Verify thread exists
        thread = self.get_thread(thread_id)
        if not thread:
            raise ValueError(f"Thread not found: {thread_id}")
        
        # Add user message to thread
        self.add_message(thread_id, "user", message)
        
        try:
            # Get conversation history
            history = self.get_messages(thread_id)
            
            # Build messages for agent
            agent_messages = []
            for msg in history[:-1]:  # Exclude last message
                agent_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            agent_messages.append({
                "role": "user",
                "content": message
            })
            
            # Accumulate response for storing in thread
            full_response = ""
            
            # Stream from agent
            async for chunk in self.agent.astream({
                "messages": agent_messages
            }):
                if "messages" in chunk:
                    content = chunk["messages"][-1].content
                    if content:
                        full_response += content
                        yield ChatChunk(
                            type="token",
                            content=content,
                            metadata={"thread_id": thread_id}
                        )
                
                elif "tools" in chunk:
                    tool_call = chunk["tools"]
                    yield ChatChunk(
                        type="tool_call",
                        tool_name=tool_call.get("name"),
                        tool_input=tool_call.get("args"),
                        metadata={"thread_id": thread_id}
                    )
                
                elif "tool_result" in chunk:
                    yield ChatChunk(
                        type="tool_result",
                        tool_output=chunk["tool_result"],
                        metadata={"thread_id": thread_id}
                    )
            
            # Add complete assistant response to thread
            if full_response:
                self.add_message(thread_id, "assistant", full_response)
            
            # Send completion signal
            yield ChatChunk(
                type="done",
                metadata={"thread_id": thread_id}
            )
        
        except Exception as e:
            logger.error(f"❌ Error during streaming: {e}")
            yield ChatChunk(
                type="error",
                content=str(e),
                metadata={"thread_id": thread_id}
            )
    
    # ========== TOOL INFORMATION METHODS ==========
    
    def get_tools_info(self) -> List[ToolInfo]:
        """Get information about all available tools"""
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