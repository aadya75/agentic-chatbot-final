// frontend/src/hooks/useChat.js
//
// Extended with Human-in-the-Loop (HITL) support.
// When the backend returns interrupted=true, the hook exposes
// `pendingConfirmation` state and a `confirmAction()` handler
// that the UI layer can use to render the ConfirmationModal.

import { useState, useCallback, useEffect } from 'react';
import { apiService } from '../api/services';

/**
 * Hook for managing chat conversations.
 *
 * New exports for HITL:
 *   pendingConfirmation  {object|null}  — { message, thread_id } when interrupted
 *   confirmAction        {fn}           — confirmAction("approve"|"reject")
 *   isConfirming         {boolean}      — true while confirm request is in-flight
 */
export function useChat(initialThreadId = null, onMessageSent = null) {
  const [threadId, setThreadId]       = useState(initialThreadId);
  const [messages, setMessages]       = useState([]);
  const [isLoading, setIsLoading]     = useState(false);
  const [isStreaming, setIsStreaming]  = useState(false);
  const [error, setError]             = useState(null);

  // ── HITL state ────────────────────────────────────────────────────
  const [pendingConfirmation, setPendingConfirmation] = useState(null);
  const [isConfirming, setIsConfirming] = useState(false);
  // ─────────────────────────────────────────────────────────────────

  // Update threadId when prop changes
  useEffect(() => {
    if (initialThreadId !== threadId) {
      setThreadId(initialThreadId);
      setMessages([]);
      setPendingConfirmation(null);
      if (initialThreadId) {
        loadMessages(initialThreadId);
      }
    }
  }, [initialThreadId]);

  const loadMessages = useCallback(async (tid) => {
    const id = tid || threadId;
    if (!id) return;
    try {
      const loadedMessages = await apiService.getMessages(id);
      setMessages(loadedMessages);
    } catch (err) {
      console.error('Failed to load messages:', err);
      if (!err.message.includes('404') && !err.message.includes('not found')) {
        setError(err.message);
      }
    }
  }, [threadId]);

  // ── Helper: handle any response (normal or interrupted) ───────────
  const _handleResponse = useCallback((result, userMessage) => {
    const data = result.data || result;

    if (data.interrupted && data.confirmation_required) {
      // Graph paused — show confirmation modal
      setPendingConfirmation(data.confirmation_required);
      return;
    }

    // Normal response — add assistant message
    setPendingConfirmation(null);
    const assistantMessage = {
      id: data.message_id || `assistant-${Date.now()}`,
      role: 'assistant',
      content: data.message,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, assistantMessage]);

    if (onMessageSent && threadId) {
      onMessageSent(threadId, userMessage);
    }
  }, [threadId, onMessageSent]);

  // ── Send message ──────────────────────────────────────────────────
  const sendMessage = useCallback(async (message, options = {}) => {
    if (!message.trim()) return;
    if (!threadId) {
      console.error('No thread ID available');
      return;
    }

    setIsLoading(true);
    setError(null);

    // Optimistic user bubble
    const tempId = `temp-${Date.now()}`;
    const userMessage = {
      id: tempId,
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMessage]);

    try {
      const result = await apiService.sendMessage(threadId, message, options);
      if (result.success) {
        // Replace temp with real user message
        setMessages(prev => prev.map(m =>
          m.id === tempId
            ? { ...m, id: `user-${Date.now()}` }
            : m
        ));
        _handleResponse(result, message);
      }
    } catch (err) {
      console.error('Failed to send message:', err);
      setError(err.message);
      setMessages(prev => prev.filter(m => m.id !== tempId));
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [threadId, onMessageSent, _handleResponse]);

  // ── Stream message (delegates to sendMessage) ─────────────────────
  const sendMessageStream = useCallback(async (message) => {
    if (!message.trim()) return;
    if (!threadId) {
      console.error('No thread ID available');
      return;
    }

    setIsStreaming(true);
    setError(null);

    const tempId = `temp-${Date.now()}`;
    const userMessage = {
      id: tempId,
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMessage]);

    try {
      const result = await apiService.sendMessage(threadId, message);
      if (result.success) {
        setMessages(prev => prev.map(m =>
          m.id === tempId ? { ...m, id: `user-${Date.now()}` } : m
        ));
        _handleResponse(result, message);
      }
      setIsStreaming(false);
    } catch (err) {
      console.error('Failed to stream message:', err);
      setError(err.message);
      setIsStreaming(false);
      setMessages(prev => prev.filter(m => m.id !== tempId));
      throw err;
    }
  }, [threadId, onMessageSent, _handleResponse]);

  // ── HITL: user approves or rejects ───────────────────────────────
  const confirmAction = useCallback(async (userResponse) => {
    if (!pendingConfirmation) return;
    const confThreadId = pendingConfirmation.thread_id;

    setIsConfirming(true);
    setError(null);

    try {
      const result = await apiService.confirmAction(confThreadId, userResponse);
      if (result.success) {
        _handleResponse(result, userResponse);
      }
    } catch (err) {
      console.error('Failed to confirm action:', err);
      setError(err.message);
      setPendingConfirmation(null);
    } finally {
      setIsConfirming(false);
    }
  }, [pendingConfirmation, _handleResponse]);

  // ── Dismiss a pending confirmation without resuming ───────────────
  const dismissConfirmation = useCallback(() => {
    setPendingConfirmation(null);
  }, []);

  const clearConversation = useCallback(() => {
    setMessages([]);
    setPendingConfirmation(null);
  }, []);

  return {
    // Core state
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

    // HITL
    pendingConfirmation,
    isConfirming,
    confirmAction,
    dismissConfirmation,
  };
}
