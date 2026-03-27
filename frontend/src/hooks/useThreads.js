// frontend/src/hooks/useThreads.js
import { useState, useCallback, useEffect } from 'react';
import { apiService } from '../api/services';

export function useThreads() {
  const [threads, setThreads] = useState([]);
  const [currentThreadId, setCurrentThreadId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadThreads = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const threadList = await apiService.listThreads();
      
      const enhancedThreads = await Promise.all(
        threadList.map(async (thread) => {
          try {
            const messages = await apiService.getMessages(thread.id);
            const lastUserMessage = messages
              .filter(m => m.role === 'user')
              .pop();
            
            return {
              ...thread,
              preview: lastUserMessage?.content || 'New chat',
              title: lastUserMessage?.content?.slice(0, 50) || 'New chat',
              timestamp: thread.created_at
            };
          } catch (err) {
            console.warn(`Failed to load messages for thread ${thread.id}:`, err);
            return {
              ...thread,
              preview: 'New chat',
              title: 'New chat',
              timestamp: thread.created_at
            };
          }
        })
      );

      enhancedThreads.sort((a, b) => 
        new Date(b.timestamp) - new Date(a.timestamp)
      );

      setThreads(enhancedThreads);
    } catch (err) {
      console.error('Failed to load threads:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createThread = useCallback(async () => {
    try {
      const result = await apiService.createThread();
      
      if (result.success) {
        const newThread = {
          id: result.threadId,
          created_at: new Date().toISOString(),
          message_count: 0,
          status: 'active',
          preview: 'New chat',
          title: 'New chat',
          timestamp: new Date().toISOString()
        };

        setThreads(prev => [newThread, ...prev]);
        setCurrentThreadId(result.threadId);
        
        return result.threadId;
      }
    } catch (err) {
      console.error('Failed to create thread:', err);
      setError(err.message);
      throw err;
    }
  }, []);

  const deleteThread = useCallback(async (threadId) => {
    try {
      await apiService.deleteThread(threadId);
      
      setThreads(prev => prev.filter(t => t.id !== threadId));
      
      if (currentThreadId === threadId) {
        const remainingThreads = threads.filter(t => t.id !== threadId);
        
        if (remainingThreads.length > 0) {
          setCurrentThreadId(remainingThreads[0].id);
        } else {
          const newThreadId = await createThread();
          setCurrentThreadId(newThreadId);
        }
      }
      
      return true;
    } catch (err) {
      console.error('Failed to delete thread:', err);
      setError(err.message);
      throw err;
    }
  }, [currentThreadId, threads, createThread]);

  const selectThread = useCallback((threadId) => {
    setCurrentThreadId(threadId);
  }, []);

  const updateThreadPreview = useCallback((threadId, message) => {
    setThreads(prev => prev.map(thread => {
      if (thread.id === threadId) {
        return {
          ...thread,
          preview: message.slice(0, 100),
          title: message.slice(0, 50),
          message_count: (thread.message_count || 0) + 1,
          timestamp: new Date().toISOString()
        };
      }
      return thread;
    }));

    setThreads(prev => [...prev].sort((a, b) => 
      new Date(b.timestamp) - new Date(a.timestamp)
    ));
  }, []);

  const getCurrentThread = useCallback(() => {
    return threads.find(t => t.id === currentThreadId);
  }, [threads, currentThreadId]);

  useEffect(() => {
    loadThreads();
  }, [loadThreads]);

  useEffect(() => {
    if (!isLoading && threads.length === 0 && !currentThreadId) {
      createThread();
    }
  }, [isLoading, threads.length, currentThreadId, createThread]);

  return {
    threads,
    currentThreadId,
    isLoading,
    error,
    loadThreads,
    createThread,
    deleteThread,
    selectThread,
    updateThreadPreview,
    getCurrentThread,
  };
}