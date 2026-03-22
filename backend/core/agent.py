import asyncio
import uuid
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Optional, Any
from pathlib import Path
import time
import logging
from core.config import settings
from api.models.response import ChatChunk, ToolInfo

# Import the smart orchestrator - THIS IS REQUIRED
from orchestration.wow_orchestration import SmartOrchestrator
logger = logging.getLogger(__name__)


class AgentManager:
    """
    Manages conversation threads and routes all queries to SmartOrchestrator.
    
    The orchestrator handles ALL processing including:
    - LLM interactions
    - MCP server connections
    - Tool usage
    - Context gathering (web, RAG, club)
    - Multi-worker execution (GitHub, Google Workspace)
    """
    
    def __init__(self):
        # Smart Orchestrator (handles everything)
        self.orchestrator: Optional[SmartOrchestrator] = None
        
        # Thread management attributes
        self.threads: Dict[str, dict] = {}
        self.active_threads: set = set()
        
        # Initialization flag
        self._initialized: bool = False
        
        logger.info("AgentManager instance created")
    
    async def initialize(self):
        """
        Initialize the Smart Orchestrator.
        
        The orchestrator handles all MCP servers, tools, and LLM connections internally.
        """
        if self._initialized:
            logger.warning("Agent already initialized")
            return
        
        logger.info("🚀 Initializing Agent Manager with Smart Orchestrator...")
        
        try:
            # Initialize Smart Orchestrator (it handles everything internally)
            self.orchestrator = SmartOrchestrator()
            logger.info("✅ Smart Orchestrator initialized successfully")
            logger.info("   The orchestrator will handle:")
            logger.info("   • LLM (Groq)")
            logger.info("   • Context providers (Web, RAG, Club)")
            logger.info("   • Workers (GitHub, Google Workspace, Conversational)")
            logger.info("   • MCP servers (as configured in orchestrator)")
            
            self._initialized = True
            logger.info("🎉 Agent Manager initialization complete!\n")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Smart Orchestrator: {e}")
            logger.error("   Please ensure:")
            logger.error("   1. smart_orchestrator.py is in the correct location")
            logger.error("   2. All dependencies are installed")
            logger.error("   3. Required environment variables are set (GROQ_API_KEY, etc.)")
            raise RuntimeError(f"Cannot start without Smart Orchestrator: {e}")
    
    async def shutdown(self):
        """Gracefully shutdown agent"""
        logger.info("🛑 Shutting down Agent Manager...")
        # Orchestrator handles its own cleanup
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
    
    # ========== ORCHESTRATOR-BASED CHAT METHODS ==========
    
    async def chat(
        self, 
        message: str, 
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a message to the Smart Orchestrator and get complete response.
        
        All processing is handled by the orchestrator including:
        - Planning (what context/workers are needed)
        - Context gathering (web search, RAG, club search)
        - Worker execution (GitHub, Google Workspace, conversational)
        - Response aggregation
        
        Args:
            message: User's message
            thread_id: Optional thread ID for conversation context
        
        Returns:
            Dict with response message, execution time, and metadata
        """
        if not self._initialized:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        
        if not self.orchestrator:
            raise RuntimeError("Smart Orchestrator not available. Cannot process messages.")
        
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
            # Get conversation history for context (exclude current message)
            history = self.get_messages(thread_id)[:-1]
            conversation_history = [
                f"{msg['role']}: {msg['content']}" 
                for msg in history
            ]
            
            logger.info(f"🎯 Processing with Smart Orchestrator")
            logger.info(f"   Query: {message[:100]}{'...' if len(message) > 100 else ''}")
            logger.info(f"   History: {len(conversation_history)} previous messages")
            
            # result= await self.orchestrator.process(message, conversation_history)
            # Run orchestrator processing (synchronous, so run in executor)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.orchestrator.process(message, conversation_history)
            )


            
            execution_time = time.time() - start_time
            
            # Check if orchestrator processing was successful
            if not result.get("success", False):
                error_msg = result.get("response", "Unknown orchestrator error")
                logger.error(f"❌ Orchestrator processing failed: {error_msg}")
                raise RuntimeError(f"Orchestrator failed: {error_msg}")
            
            # Extract response and metadata
            response_text = result["response"]
            metadata = result.get("metadata", {})
            
            logger.info(f"✅ Orchestrator processing complete")
            logger.info(f"   Execution time: {execution_time:.2f}s")
            logger.info(f"   Workers used: {metadata.get('workers_used', [])}")
            logger.info(f"   Web search: {metadata.get('web_search_used', False)}")
            logger.info(f"   RAG search: {metadata.get('rag_search_used', False)}")
            logger.info(f"   Club search: {metadata.get('club_search_used', False)}")
            
            # Add assistant response to thread
            self.add_message(thread_id, "assistant", response_text, metadata={
                "orchestrator_metadata": metadata
            })
            
            # Determine which tools/workers were used
            tools_used = []
            workers_used = metadata.get("workers_used", [])
            
            for worker in workers_used:
                if worker == "github":
                    tools_used.append("github_tools")
                elif "google" in worker.lower():
                    tools_used.append(f"google_{worker}")
                elif worker == "conversational":
                    tools_used.append("llm")
            
            return {
                "message": response_text,
                "thread_id": thread_id,
                "message_id": f"msg_{uuid.uuid4().hex[:8]}",
                "execution_time": execution_time,
                "tools_used": tools_used,
                "metadata": {
                    "orchestrator_used": True,
                    "web_search_used": metadata.get("web_search_used", False),
                    "rag_search_used": metadata.get("rag_search_used", False),
                    "club_search_used": metadata.get("club_search_used", False),
                    "total_tasks": metadata.get("total_tasks", 0),
                    "successful_tasks": metadata.get("successful_tasks", 0),
                    "workers_used": workers_used
                }
            }
        
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ Error during orchestrator processing: {e}")
            logger.error(f"   Query was: {message[:100]}...")
            logger.error(f"   Thread: {thread_id}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def stream_chat(
        self, 
        message: str, 
        thread_id: Optional[str] = None
    ) -> AsyncGenerator[ChatChunk, None]:
        """
        Stream orchestrator response.
        
        Note: Streaming is not yet implemented in the orchestrator.
        This method will process the full response and yield it as chunks.
        
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
        
        logger.warning("⚠️  Orchestrator streaming not yet implemented")
        logger.info("   Processing full response then streaming output...")
        
        try:
            # Get full response from orchestrator
            result = await self.chat(message, thread_id)
            
            # Stream the response token by token
            response_text = result["message"]
            words = response_text.split()
            
            # Yield words as tokens
            for i, word in enumerate(words):
                chunk_text = word + (" " if i < len(words) - 1 else "")
                yield ChatChunk(
                    type="token",
                    content=chunk_text,
                    metadata={"thread_id": thread_id}
                )
                # Small delay to simulate streaming
                await asyncio.sleep(0.01)
            
            # Send completion signal with metadata
            yield ChatChunk(
                type="done",
                metadata={
                    "thread_id": thread_id,
                    **result["metadata"]
                }
            )
        
        except Exception as e:
            logger.error(f"❌ Error during streaming: {e}")
            yield ChatChunk(
                type="error",
                content=str(e),
                metadata={"thread_id": thread_id}
            )
    
    # ========== STATUS AND INFO METHODS ==========
    
    def get_orchestrator_status(self) -> Dict[str, Any]:
        """Get status of Smart Orchestrator"""
        if not self.orchestrator:
            return {
                "enabled": False,
                "status": "not_initialized",
                "message": "Orchestrator not initialized"
            }
        
        return {
            "enabled": True,
            "status": "ready",
            "features": {
                "web_search": True,
                "rag_search": True,
                "club_search": True,
                "github_worker": True,
                "google_workspace_worker": True,
                "conversational_worker": True,
                "mixed_context": True,
                "intelligent_planning": True
            },
            "description": "All queries are processed through Smart Orchestrator"
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get overall agent manager status"""
        return {
            "initialized": self._initialized,
            "orchestrator": self.get_orchestrator_status(),
            "threads": {
                "total": self.get_thread_count(),
                "active": self.get_active_thread_count()
            }
        }
    
    @property
    def is_initialized(self) -> bool:
        """Check if agent is ready to use"""
        return self._initialized and self.orchestrator is not None


# Global instance (singleton pattern)
agent_manager = AgentManager()
