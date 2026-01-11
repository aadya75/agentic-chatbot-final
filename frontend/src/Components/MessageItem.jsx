import React from 'react';
import './MessageItem.css';

const MessageItem = ({ message, isUser, timestamp, status = 'sent', showAvatar = true, showTime = true }) => {
  const formatTime = (ts) => {
    if (!ts) return '';
    const date = new Date(ts);
    return date.toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const getInitials = () => {
    return isUser ? 'You' : 'AI';
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'sending':
        return (
          <div className="status-icon sending">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2A10 10 0 1 0 12 22A10 10 0 0 0 12 2Z" opacity="0.5"/>
              <path d="M20 12A8 8 0 1 1 4 12A8 8 0 0 1 20 12Z"/>
            </svg>
          </div>
        );
      case 'sent':
        return (
          <div className="status-icon sent">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
            </svg>
          </div>
        );
      case 'read':
        return (
          <div className="status-icon read">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
            </svg>
          </div>
        );
      default:
        return null;
    }
  };

  // Render code blocks if message contains code
  const renderContent = (text) => {
    if (text.includes('```')) {
      const parts = text.split('```');
      return parts.map((part, index) => {
        if (index % 2 === 1) {
          return (
            <pre key={index} className="code-block">
              <code>{part}</code>
            </pre>
          );
        }
        return <span key={index}>{part}</span>;
      });
    }
    return text;
  };

  // Check if message is a typing indicator
  if (message.text === '_TYPING_') {
    return (
      <div className="message-container bot">
        {showAvatar && (
          <div className="message-avatar bot">{getInitials()}</div>
        )}
        <div className="typing-indicator-bubble">
          <div className="typing-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`message-container ${isUser ? 'user' : 'bot'}`}>
      {!isUser && showAvatar && (
        <div className="message-avatar bot">{getInitials()}</div>
      )}
      
      <div className={`message-bubble ${isUser ? 'user' : 'bot'} ${message.error ? 'error' : ''}`}>
        <div className="message-content">
          {renderContent(message.text)}
        </div>
        
        <div className="message-meta">
          {showTime && timestamp && (
            <span className="message-time">{formatTime(timestamp)}</span>
          )}
          
          {isUser && status !== 'sent' && (
            <div className="message-status">
              {getStatusIcon()}
            </div>
          )}
        </div>
      </div>
      
      {isUser && showAvatar && (
        <div className="message-avatar user">{getInitials()}</div>
      )}
    </div>
  );
};

export default MessageItem;