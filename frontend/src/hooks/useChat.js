// frontend/src/hooks/useChat.js
import { useState, useCallback, useEffect, useRef } from 'react';
import { apiService } from '../api/services';

/**
 * Hook for managing chat conversations
 * Works with external thread management
 */
export function useChat(initialThreadId = null, onMessageSent = null) {
  const [threadId, setThreadId] = useState(initialThreadId);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);

  // Update threadId when prop changes
  useEffect(() => {
    if (initialThreadId !== threadId) {
      setThreadId(initialThreadId);
      setMessages([]); // Clear messages when switching threads
      
      // Load messages for the new thread
      if (initialThreadId) {
        loadMessages(initialThreadId);
      }
    }
  }, [initialThreadId]);

  /**
   * Load existing messages from thread
   */
  const loadMessages = useCallback(async (tid) => {
    const id = tid || threadId;
    if (!id) return;

    try {
      const loadedMessages = await apiService.getMessages(id);
      setMessages(loadedMessages);
    } catch (err) {
      console.error('Failed to load messages:', err);
      // Don't set error for 404 on empty threads
      if (!err.message.includes('404') && !err.message.includes('not found')) {
        setError(err.message);
      }
    }
  }, [threadId]);

  /**
   * Send a message (non-streaming)
   */
  const sendMessage = useCallback(async (message, options = {}) => {
    if (!message.trim()) return;
    if (!threadId) {
      console.error('No thread ID available');
      return;
    }

    setIsLoading(true);
    setError(null);

    // Add user message optimistically
    const userMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMessage]);

    try {
      console.log('Sending message to thread:', threadId);
      const result = await apiService.sendMessage(threadId, message, options);
      console.log('Got response:', result);
      
      if (result.success) {
        // Replace optimistic message and add assistant response
        setMessages(prev => {
          // Remove temporary message
          const filtered = prev.filter(m => m.id !== userMessage.id);
          
          // Add real user message
          const realUserMessage = {
            id: `user-${Date.now()}`,
            role: 'user',
            content: message,
            timestamp: result.data.timestamp
          };
          
          // Add assistant message
          const assistantMessage = {
            id: result.data.message_id || `assistant-${Date.now()}`,
            role: 'assistant',
            content: result.data.message,
            timestamp: result.data.timestamp
          };
          
          console.log('Adding messages:', { realUserMessage, assistantMessage });
          
          return [...filtered, realUserMessage, assistantMessage];
        });

        // Notify parent about message sent
        if (onMessageSent) {
          onMessageSent(threadId, message);
        }
      }
    } catch (err) {
      console.error('Failed to send message:', err);
      setError(err.message);
      
      // Remove optimistic message on error
      setMessages(prev => prev.filter(m => m.id !== userMessage.id));
      
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [threadId, onMessageSent]);

  /**
   * Send a message with streaming response
   */
  const sendMessageStream = useCallback(async (message) => {
    if (!message.trim()) return;
    if (!threadId) {
      console.error('No thread ID available');
      return;
    }

    setIsStreaming(true);
    setError(null);

    // Add user message
    const userMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMessage]);

    // Prepare assistant message placeholder
    const assistantMessageId = `assistant-${Date.now()}`;

    try {
      // For now, just use regular send since streaming may not be implemented
      const result = await apiService.sendMessage(threadId, message);
      
      if (result.success) {
        const assistantMessage = {
          id: result.data.message_id || assistantMessageId,
          role: 'assistant',
          content: result.data.message,
          timestamp: new Date().toISOString()
        };
        
        setMessages(prev => [...prev, assistantMessage]);

        // Notify parent
        if (onMessageSent) {
          onMessageSent(threadId, message);
        }
      }
      
      setIsStreaming(false);
    } catch (err) {
      console.error('Failed to stream message:', err);
      setError(err.message);
      setIsStreaming(false);
      throw err;
    }
  }, [threadId, onMessageSent]);

  /**
   * Clear the conversation
   */
  const clearConversation = useCallback(async () => {
    setMessages([]);
  }, []);

  return {
    // State
    threadId,
    messages,
    isLoading,
    isStreaming,
    error,
    
    // Actions
    sendMessage,
    sendMessageStream,
    clearConversation,
    loadMessages,
  };
}