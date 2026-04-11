// frontend/src/Components/ChatContainer.jsx
import React, { useState, useRef, useEffect } from 'react';
import { useChat } from '../hooks/useChat';
import ConfirmationModal from './ConfirmationModal';
import './ChatContainer.css';

function ChatContainer({ threadId, isBackendConnected, onMessageSent }) {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef(null);

  const {
    messages,
    isLoading,
    isStreaming,
    error,
    sendMessage,
    sendMessageStream,
    // HITL
    pendingConfirmation,
    isConfirming,
    confirmAction,
  } = useChat(threadId, onMessageSent);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!inputValue.trim() || isLoading || isStreaming) return;
    if (!isBackendConnected) {
      alert('Backend is not connected. Please wait...');
      return;
    }
    if (!threadId) {
      alert('No thread selected. Please select or create a chat.');
      return;
    }

    const message = inputValue.trim();
    setInputValue('');

    try {
      await sendMessageStream(message);
    } catch (err) {
      console.error('Failed to send message:', err);
    }
  };

  return (
    <div className="chat-container">

      {/* ── HITL Confirmation Modal ─────────────────────────────────── */}
      {pendingConfirmation && (
        <ConfirmationModal
          message={pendingConfirmation.message}
          threadId={pendingConfirmation.thread_id}
          isLoading={isConfirming}
          onApprove={() => confirmAction('approve')}
          onReject={() => confirmAction('reject')}
        />
      )}

      {/* ── Messages ────────────────────────────────────────────────── */}
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">💬</div>
            <h3>Start a conversation</h3>
            <p>Send a message to begin chatting with the AI assistant</p>
          </div>
        )}

        {messages.map((message) => (
          <div key={message.id} className={`message ${message.role}`}>
            <div className="message-header">
              <span className="message-role">
                {message.role === 'user' ? '👤 You' : '🤖 Assistant'}
              </span>
              <span className="message-time">
                {new Date(message.timestamp).toLocaleTimeString()}
              </span>
            </div>
            <div className="message-content">{message.content}</div>
          </div>
        ))}

        {/* Waiting-for-confirmation indicator (replaces generic typing dots) */}
        {pendingConfirmation && !isConfirming && (
          <div className="message assistant">
            <div className="message-header">
              <span className="message-role">🤖 Assistant</span>
            </div>
            <div className="message-content" style={{ color: '#f0a500', fontStyle: 'italic' }}>
              ⏳ Waiting for your approval before proceeding…
            </div>
          </div>
        )}

        {(isStreaming || isLoading) && !pendingConfirmation && (
          <div className="typing-indicator">
            <span></span><span></span><span></span>
          </div>
        )}

        {error && (
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Input ───────────────────────────────────────────────────── */}
      <form className="chat-input-form" onSubmit={handleSubmit}>
        <div className="input-wrapper">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={
              pendingConfirmation
                ? 'Waiting for your approval above…'
                : isBackendConnected
                ? 'Type your message…'
                : 'Waiting for backend connection…'
            }
            disabled={
              !isBackendConnected ||
              isLoading ||
              isStreaming ||
              !threadId ||
              !!pendingConfirmation   // lock input while modal is open
            }
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            rows={1}
            className="chat-input"
          />
          <button
            type="submit"
            disabled={
              !inputValue.trim() ||
              !isBackendConnected ||
              isLoading ||
              isStreaming ||
              !threadId ||
              !!pendingConfirmation
            }
            className="send-button"
          >
            {isLoading || isStreaming ? '⏳' : '📤'}
          </button>
        </div>
        <div className="input-hint">
          Press Enter to send, Shift+Enter for new line
        </div>
      </form>
    </div>
  );
}

export default ChatContainer;
