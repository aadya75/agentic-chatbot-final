import React, { useState, useEffect, useRef } from 'react';
import './MessageInput.css';

export default function MessageInput({ onSend, isBotTyping = false }) {
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const inputRef = useRef(null);
  const MAX_LENGTH = 1000;

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isSending || input.length > MAX_LENGTH) return;
    
    setIsSending(true);
    try {
      await onSend(trimmed);
      setInput('');
    } catch (error) {
      console.error('Error sending message:', error);
      // Keep the message if sending failed
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handlePaste = (e) => {
    const pastedText = e.clipboardData.getData('text');
    if (pastedText.length > MAX_LENGTH) {
      e.preventDefault();
      setInput(pastedText.substring(0, MAX_LENGTH));
    }
  };

  // Focus input on component mount
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  // Auto-resize textarea (optional - if you change to textarea)
  const isOverLimit = input.length > MAX_LENGTH;
  const charCountPercentage = (input.length / MAX_LENGTH) * 100;

  const getCharCounterClass = () => {
    if (isOverLimit) return 'error';
    if (input.length > MAX_LENGTH * 0.9) return 'warning';
    return '';
  };

  return (
    <>
      {isBotTyping && (
        <div className="typing-indicator">
          Bot is typing
          <div className="typing-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      )}
      
      <form className="message-input-form" onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          type="text"
          className="message-input-field"
          value={input}
          onChange={(e) => {
            if (e.target.value.length <= MAX_LENGTH) {
              setInput(e.target.value);
            }
          }}
          onKeyPress={handleKeyPress}
          onPaste={handlePaste}
          placeholder="Type a message..."
          disabled={isSending || isBotTyping}
          maxLength={MAX_LENGTH}
          autoFocus
        />
        
        {input.length > 0 && (
          <div className={`char-counter ${getCharCounterClass()}`}>
            {input.length}/{MAX_LENGTH}
          </div>
        )}
        
        <button 
          type="submit" 
          className="send-button"
          disabled={!input.trim() || isSending || isOverLimit || isBotTyping}
          title={isOverLimit ? 'Message too long' : 'Send message'}
        >
          {isSending ? (
            'Sending...'
          ) : (
            <>
              <svg className="send-icon" viewBox="0 0 24 24" fill="currentColor">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
              Send
            </>
          )}
        </button>
      </form>
    </>
  );
}