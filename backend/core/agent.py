"""
backend/core/agent.py

Updated AgentManager that integrates with LangGraph orchestration.
Manages MCP tools and threads, delegates complex queries to orchestrator.
"""

import asyncio
import uuid
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Optional, Any
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
from pathlib import Path
import time
import logging
from langchain_core.messages import AIMessage

from core.config import settings
from api.models.response import ChatChunk, ToolInfo

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Manages MCP tools, LLM, and conversation threads.
    Works with LangGraph orchestrator for complex multi-agent workflows.
    """
    
    def __init__(self):
        # LLM and MCP attributes
        self.llm: Optional[ChatGroq] = None
        self.mcp_client: Optional[MultiServerMCPClient] = None
        self.tools: List = []
        self._initialized: bool = False
        self._server_config: Dict[str, Dict] = {}
        
        # Thread management
        self.threads: Dict[str, dict] = {}
        self.active_threads: set = set()
        
        # Orchestrator (will be set externally)
        self.orchestrator = None
        
        logger.info("AgentManager instance created")
    
    async def initialize(self):
        """Initialize LLM and MCP servers"""
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
        
        # Step 2: Configure MCP servers
        self._configure_servers()
        
        # Step 3: Initialize MCP client
        if self._server_config:
            try:
                self.mcp_client = MultiServerMCPClient(self._server_config)
                logger.info(f"✅ MCP Client created with {len(self._server_config)} servers")
                
                # Step 4: Load tools
                self.tools = await self.mcp_client.get_tools()
                logger.info(f"✅ Loaded {len(self.tools)} tools")
                
                for tool in self.tools:
                    logger.info(f"   📌 Tool: {tool.name}")
                
            except Exception as e:
                logger.warning(f"⚠️  Failed to initialize MCP tools: {e}")
                self.tools = []
        else:
            logger.warning("⚠️  No MCP servers enabled")
            self.tools = []
        
        self._initialized = True
        logger.info("🎉 Agent Manager initialization complete!\n")
    
    def _configure_servers(self):
        """Configure MCP servers based on settings"""
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
        
        if settings.enable_rag:
            self._server_config["rag"] = {
                "command": "python",
                "args": [str(servers_dir / "rag_server.py")],
                "transport": "stdio",
            }
            logger.info("  📚 RAG server enabled")
    
    async def shutdown(self):
        """Gracefully shutdown"""
        logger.info("🛑 Shutting down Agent Manager...")
        if self.mcp_client:
            try:
                await self.mcp_client.close()
            except:
                pass
        self._initialized = False
        logger.info("✅ Agent Manager shutdown complete")

        
    #  ============================================================================
    # TOOL EXECUTION - Base Method
    # ============================================================================

    async def call_tool(self, server_name: str, tool_name: str, parameters: Dict) -> Any:
        """
        Call a specific MCP tool with proper error handling.
        
        Args:
            server_name: "gmail", "google_drive", "google_calendar", "rag"
            tool_name: Exact name of the tool (e.g., "search_gmail", "get_latest_gmail_messages")
            parameters: Tool parameters dict
        
        Returns:
            Tool execution result
        """
        if not self._initialized:
            raise RuntimeError("Agent not initialized")
        
        # Find the tool by exact name
        tool = None
        for t in self.tools:
            if t.name == tool_name:
                tool = t
                break
        
        if not tool:
            available_tools = [t.name for t in self.tools]
            raise ValueError(
                f"Tool '{tool_name}' not found. Available tools: {available_tools}"
            )
        
        try:
            logger.info(f"🔧 Calling tool: {tool.name}")
            logger.debug(f"   Parameters: {parameters}")
            
            result = await tool.ainvoke(parameters)
            logger.info(f"✅ Tool executed: {tool.name}")
            return result
        
        except Exception as e:
            logger.error(f"❌ Tool execution failed: {tool.name} - {e}")
            raise


    # ============================================================================
    # GMAIL TOOL WRAPPERS
    # ============================================================================

    async def search_gmail(self, query: str, max_results: int = 10) -> Dict:
        """Search Gmail messages"""
        return await self.call_tool("gmail", "search_gmail", {
            "query": query,
            "max_results": max_results
        })

    async def get_gmail_message(self, message_id: str) -> Dict:
        """Get full content of a specific Gmail message"""
        return await self.call_tool("gmail", "get_gmail_message", {
            "message_id": message_id
        })

    async def send_gmail_message(self, to: str, subject: str, message: str, 
                                cc: str = None, bcc: str = None) -> Dict:
        """Send an email through Gmail"""
        params = {"to": to, "subject": subject, "message": message}
        if cc:
            params["cc"] = cc
        if bcc:
            params["bcc"] = bcc
        return await self.call_tool("gmail", "send_gmail_message", params)

    async def create_gmail_draft(self, to: str, subject: str, message: str) -> Dict:
        """Create a draft email in Gmail"""
        return await self.call_tool("gmail", "create_gmail_draft", {
            "to": to,
            "subject": subject,
            "message": message
        })

    async def get_gmail_thread(self, thread_id: str) -> Dict:
        """Get an entire Gmail conversation thread"""
        return await self.call_tool("gmail", "get_gmail_thread", {
            "thread_id": thread_id
        })

    async def get_latest_gmail_messages(self, count: int = 5) -> Dict:
        """Get the latest emails from inbox"""
        return await self.call_tool("gmail", "get_latest_gmail_messages", {
            "count": count
        })


    # ============================================================================
    # CALENDAR TOOL WRAPPERS
    # ============================================================================

    async def list_calendars(self) -> Dict:
        """List all calendars accessible to the user"""
        return await self.call_tool("google_calendar", "list_calendars", {})

    async def get_upcoming_events(self, calendar_id: str = "primary", 
                                max_results: int = 10, days_ahead: int = 7) -> Dict:
        """Get upcoming events from a calendar"""
        return await self.call_tool("google_calendar", "get_upcoming_events", {
            "calendar_id": calendar_id,
            "max_results": max_results,
            "days_ahead": days_ahead
        })

    async def create_calendar_event(self, summary: str, start_time: str, end_time: str,
                                    calendar_id: str = "primary", description: str = None,
                                    location: str = None, attendees: str = None,
                                    timezone: str = "UTC") -> Dict:
        """Create a new calendar event"""
        params = {
            "summary": summary,
            "start_time": start_time,
            "end_time": end_time,
            "calendar_id": calendar_id,
            "timezone": timezone
        }
        if description:
            params["description"] = description
        if location:
            params["location"] = location
        if attendees:
            params["attendees"] = attendees
        
        return await self.call_tool("google_calendar", "create_calendar_event", params)

    async def update_calendar_event(self, event_id: str, calendar_id: str = "primary",
                                    summary: str = None, start_time: str = None,
                                    end_time: str = None, description: str = None,
                                    location: str = None) -> Dict:
        """Update an existing calendar event"""
        params = {"event_id": event_id, "calendar_id": calendar_id}
        if summary:
            params["summary"] = summary
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        if description:
            params["description"] = description
        if location:
            params["location"] = location
        
        return await self.call_tool("google_calendar", "update_calendar_event", params)

    async def delete_calendar_event(self, event_id: str, calendar_id: str = "primary") -> Dict:
        """Delete a calendar event"""
        return await self.call_tool("google_calendar", "delete_calendar_event", {
            "event_id": event_id,
            "calendar_id": calendar_id
        })

    async def search_calendar_events(self, query: str, calendar_id: str = "primary",
                                    max_results: int = 10) -> Dict:
        """Search for calendar events by text query"""
        return await self.call_tool("google_calendar", "search_calendar_events", {
            "query": query,
            "calendar_id": calendar_id,
            "max_results": max_results
        })

    async def get_events_for_date(self, date: str, calendar_id: str = "primary") -> Dict:
        """Get all events for a specific date (YYYY-MM-DD format)"""
        return await self.call_tool("google_calendar", "get_events_for_date", {
            "date": date,
            "calendar_id": calendar_id
        })

    async def create_recurring_event(self, summary: str, start_time: str, end_time: str,
                                    recurrence_rule: str, calendar_id: str = "primary",
                                    description: str = None, location: str = None,
                                    timezone: str = "UTC") -> Dict:
        """Create a recurring calendar event"""
        params = {
            "summary": summary,
            "start_time": start_time,
            "end_time": end_time,
            "recurrence_rule": recurrence_rule,
            "calendar_id": calendar_id,
            "timezone": timezone
        }
        if description:
            params["description"] = description
        if location:
            params["location"] = location
        
        return await self.call_tool("google_calendar", "create_recurring_event", params)

    async def get_free_busy_times(self, time_min: str, time_max: str, 
                                calendars: str = None) -> Dict:
        """Check free/busy status for calendars"""
        params = {"time_min": time_min, "time_max": time_max}
        if calendars:
            params["calendars"] = calendars
        return await self.call_tool("google_calendar", "get_free_busy_times", params)


    # ============================================================================
    # GOOGLE DRIVE TOOL WRAPPERS
    # ============================================================================

    async def search_drive(self, query: str, max_results: int = 10) -> Dict:
        """Search for files in Google Drive"""
        return await self.call_tool("google_drive", "search_drive", {
            "query": query,
            "max_results": max_results
        })

    async def list_drive_files(self, folder_id: str = None, max_results: int = 20) -> Dict:
        """List files in Google Drive or a specific folder"""
        params = {"max_results": max_results}
        if folder_id:
            params["folder_id"] = folder_id
        return await self.call_tool("google_drive", "list_drive_files", params)

    async def get_drive_file_content(self, file_id: str) -> Dict:
        """Get the content of a Google Drive file"""
        return await self.call_tool("google_drive", "get_drive_file_content", {
            "file_id": file_id
        })

    async def download_drive_file(self, file_id: str, destination_path: str) -> Dict:
        """Download a file from Google Drive"""
        return await self.call_tool("google_drive", "download_drive_file", {
            "file_id": file_id,
            "destination_path": destination_path
        })

    async def upload_drive_file(self, file_path: str, folder_id: str = None,
                            file_name: str = None) -> Dict:
        """Upload a file to Google Drive"""
        params = {"file_path": file_path}
        if folder_id:
            params["folder_id"] = folder_id
        if file_name:
            params["file_name"] = file_name
        return await self.call_tool("google_drive", "upload_drive_file", params)

    async def create_drive_folder(self, folder_name: str, parent_folder_id: str = None) -> Dict:
        """Create a new folder in Google Drive"""
        params = {"folder_name": folder_name}
        if parent_folder_id:
            params["parent_folder_id"] = parent_folder_id
        return await self.call_tool("google_drive", "create_drive_folder", params)

    async def share_drive_file(self, file_id: str, email: str, role: str = "reader") -> Dict:
        """Share a Google Drive file with another user"""
        return await self.call_tool("google_drive", "share_drive_file", {
            "file_id": file_id,
            "email": email,
            "role": role
        })

    async def delete_drive_file(self, file_id: str) -> Dict:
        """Delete a file from Google Drive"""
        return await self.call_tool("google_drive", "delete_drive_file", {
            "file_id": file_id
        })

    async def get_drive_file_metadata(self, file_id: str) -> Dict:
        """Get detailed metadata for a Google Drive file"""
        return await self.call_tool("google_drive", "get_drive_file_metadata", {
            "file_id": file_id
        })


    # ============================================================================
    # RAG TOOL WRAPPER
    # ============================================================================

    async def rag_retrieve(self, query: str, top_k: int = 5, 
                        include_citations: bool = False) -> Dict:
        """Retrieve relevant context from indexed user resources"""
        return await self.call_tool("rag", "retrieve_context", {
            "query": query,
            "top_k": top_k,
            "include_citations": include_citations
        })


    # ============================================================================
    # HELPER: List All Available Tools
    # ============================================================================

    def list_available_tools(self) -> List[str]:
        """Get list of all available tool names"""
        return [tool.name for tool in self.tools]

    def get_tool_info(self, tool_name: str) -> Dict:
        """Get detailed information about a specific tool"""
        for tool in self.tools:
            if tool.name == tool_name:
                return {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": getattr(tool, 'args', {})
                }
        return None
    
    # ========== THREAD MANAGEMENT ==========
    
    def create_thread(self) -> str:
        """Create a new conversation thread"""
        thread_id = str(uuid.uuid4())
        
        self.threads[thread_id] = {
            "id": thread_id,
            "created_at": datetime.utcnow().isoformat(),
            "messages": [],
            "metadata": {},
            "status": "active"
        }
        
        self.active_threads.add(thread_id)
        logger.info(f"Created thread: {thread_id}")
        return thread_id
    
    def get_thread(self, thread_id: str) -> Optional[dict]:
        """Get thread by ID"""
        return self.threads.get(thread_id)
    
    def add_message(self, thread_id: str, role: str, content: str, metadata: Optional[dict] = None) -> bool:
        """Add message to thread"""
        thread = self.threads.get(thread_id)
        if not thread:
            return False
        
        message = {
            "id": str(uuid.uuid4()),
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        thread["messages"].append(message)
        return True
    
    def get_messages(self, thread_id: str) -> List[dict]:
        """Get all messages from thread"""
        thread = self.threads.get(thread_id)
        return thread["messages"] if thread else []
    
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
    
    # ========== CHAT METHODS (UPDATED) ==========
    
    async def chat(
        self, 
        message: str, 
        thread_id: Optional[str] = None,
        use_orchestrator: bool = True
    ) -> Dict[str, Any]:
        """
        Process a message through orchestrator or simple LLM.
        
        Args:
            message: User's message
            thread_id: Optional thread ID
            use_orchestrator: Whether to use LangGraph orchestrator (default: True)
        
        Returns:
            Response dict with message, metadata, etc.
        """
        if not self._initialized:
            raise RuntimeError("Agent not initialized")
        
        # Create thread if needed
        if not thread_id:
            thread_id = self.create_thread()
        
        # Verify thread exists
        if not self.get_thread(thread_id):
            raise ValueError(f"Thread not found: {thread_id}")
        
        start_time = time.time()
        
        # Add user message to thread
        self.add_message(thread_id, "user", message)
        
        try:
            # Get conversation history
            history = self.get_messages(thread_id)
            conversation_history = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in history[:-1]  # Exclude current message
            ]
            
            # ROUTE: Use orchestrator for complex queries
            if use_orchestrator and self.orchestrator:
                logger.info("🎯 Using LangGraph orchestrator")
                
                result = await self.orchestrator.process_message(
                    user_query=message,
                    thread_id=thread_id,
                    conversation_history=conversation_history
                )
                
                response_text = result["response"]
                tools_used = result.get("tools_used", [])
                metadata = result.get("metadata", {})
                
            else:
                # Fallback: Simple LLM call
                logger.info("💬 Using simple LLM")
                
                from langchain_core.messages import HumanMessage, SystemMessage
                
                messages = [
                    SystemMessage(content="You are a helpful assistant for a robotics club.")
                ]
                
                # Add history
                for msg in conversation_history[-5:]:  # Last 5 messages
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    else:
                        messages.append(AIMessage(content=msg["content"]))
                
                # Add current message
                messages.append(HumanMessage(content=message))
                
                llm_response = await self.llm.ainvoke(messages)
                response_text = llm_response.content
                tools_used = []
                metadata = {}
            
            execution_time = time.time() - start_time
            
            # Extract response content
            final_message = response["messages"][-1].content
            
            # Add assistant response to thread
            self.add_message(thread_id, "assistant", response_text)
            
            return {
                "message": response_text,
                "thread_id": thread_id,
                "message_id": f"msg_{uuid.uuid4().hex[:8]}",
                "tools_used": tools_used,
                "execution_time": execution_time,
                "metadata": {
                    "model": settings.llm_model,
                    **metadata
                }
            }
        
        except Exception as e:
            logger.error(f"❌ Error during chat: {e}")
            raise
    
    async def stream_chat(
        self, 
        message: str, 
        thread_id: Optional[str] = None,
        use_orchestrator: bool = True
    ) -> AsyncGenerator[ChatChunk, None]:
        """
        Stream response (simplified - orchestrator doesn't stream yet)
        """
        if not self._initialized:
            raise RuntimeError("Agent not initialized")
        
        # For now, get complete response and yield it
        # TODO: Implement streaming in orchestrator
        result = await self.chat(message, thread_id, use_orchestrator)
        
        # Simulate streaming by chunking
        response = result["message"]
        chunk_size = 50
        
        for i in range(0, len(response), chunk_size):
            chunk = response[i:i+chunk_size]
            yield ChatChunk(
                type="token",
                content=chunk,
                metadata={"thread_id": thread_id}
            )
            await asyncio.sleep(0.05)  # Simulate delay
        
        yield ChatChunk(
            type="done",
            metadata={
                "thread_id": thread_id,
                "tools_used": result.get("tools_used", [])
            }
        )
    
    # ========== UTILITY METHODS ==========
    
    def get_tools_info(self) -> List[ToolInfo]:
        """Get information about available tools"""
        tools_info = []
        for tool in self.tools:
            tools_info.append(ToolInfo(
                name=tool.name,
                description=tool.description,
                parameters=getattr(tool, 'args', {}),
                server=self._get_server_for_tool(tool.name)
            ))
        return tools_info
    
    def _get_server_for_tool(self, tool_name: str) -> str:
        """Determine server for a tool"""
        name_lower = tool_name.lower()
        if "gmail" in name_lower or "email" in name_lower:
            return "gmail"
        elif "drive" in name_lower:
            return "google_drive"
        elif "calendar" in name_lower or "event" in name_lower:
            return "google_calendar"
        elif "rag" in name_lower or "retrieve" in name_lower:
            return "rag"
        return "unknown"
    
    @property
    def is_initialized(self) -> bool:
        """Check if ready"""
        return self._initialized


# Global singleton
agent_manager = AgentManager()