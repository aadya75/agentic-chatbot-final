import React, { useState, useEffect, useRef, useCallback } from 'react';
import MessageItem from './MessageItem';
import './ChatBox.css';

const ChatBox = React.forwardRef(({ messages, loading = false }, ref) => {
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [lastMessageId, setLastMessageId] = useState(null);
  const chatContainerRef = useRef(null);
  const messagesEndRef = useRef(null);
  const isScrollingRef = useRef(false);

  // Format date for separators
  const formatDate = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleDateString([], {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  // Group messages by date
  const groupMessagesByDate = useCallback(() => {
    const groups = [];
    let currentDate = null;
    let currentGroup = [];

    messages.forEach((message, index) => {
      const messageDate = formatDate(message.timestamp || message.id);
      
      if (messageDate !== currentDate) {
        if (currentGroup.length > 0) {
          groups.push({ date: currentDate, messages: currentGroup });
        }
        currentDate = messageDate;
        currentGroup = [message];
      } else {
        currentGroup.push(message);
      }

      // Last message in array
      if (index === messages.length - 1) {
        groups.push({ date: currentDate, messages: currentGroup });
      }
    });

    return groups;
  }, [messages]);

  // Scroll to bottom function
  const scrollToBottom = useCallback((smooth = true) => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({
        behavior: smooth ? 'smooth' : 'auto',
        block: 'end'
      });
      setUnreadCount(0);
    }
  }, []);

  // Handle scroll events
  const handleScroll = useCallback(() => {
    if (!chatContainerRef.current || isScrollingRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    
    setShowScrollBottom(!isNearBottom);
    
    // Count unread messages when not at bottom
    if (!isNearBottom) {
      const lastReadIndex = messages.findIndex(msg => msg.id === lastMessageId);
      if (lastReadIndex !== -1) {
        const newUnread = messages.length - lastReadIndex - 1;
        setUnreadCount(Math.max(0, newUnread));
      }
    } else {
      setUnreadCount(0);
      if (messages.length > 0) {
        setLastMessageId(messages[messages.length - 1].id);
      }
    }
  }, [messages, lastMessageId]);

  // Handle new message indicator click
  const handleNewMessageClick = () => {
    scrollToBottom();
    setUnreadCount(0);
  };

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (messages.length === 0) return;

    const lastMessage = messages[messages.length - 1];
    const isUserMessage = lastMessage.isUser;
    
    if (chatContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
      
      // Auto-scroll if near bottom or it's a bot message
      if (isNearBottom || !isUserMessage) {
        isScrollingRef.current = true;
        scrollToBottom();
        setTimeout(() => {
          isScrollingRef.current = false;
        }, 300);
      } else if (isUserMessage) {
        // User sent message but not at bottom - show unread indicator
        setUnreadCount(prev => prev + 1);
      }
    }
  }, [messages, scrollToBottom]);

  // Initialize last message ID
  useEffect(() => {
    if (messages.length > 0 && !lastMessageId) {
      setLastMessageId(messages[messages.length - 1].id);
    }
  }, [messages, lastMessageId]);

  // Handle loading state
  if (loading) {
    return (
      <div className="chat-box" ref={ref}>
        <div className="chat-loading">
          <div className="loading-spinner"></div>
          <p>Loading messages...</p>
        </div>
      </div>
    );
  }

  // Handle empty state
  if (messages.length === 0) {
    return (
      <div className="chat-box" ref={ref}>
        <div className="welcome-message">
          <h2>Welcome to Chat</h2>
          <p>Start a conversation by sending a message. I'm here to help with any questions you might have.</p>
          
          <div className="welcome-features">
            <div className="feature">
              <div className="feature-icon">
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
              </div>
              <h4>Instant Responses</h4>
              <p>Get quick answers to your questions</p>
            </div>
            
            <div className="feature">
              <div className="feature-icon">
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M21 6h-2v9H6v2c0 .55.45 1 1 1h11l4 4V7c0-.55-.45-1-1-1zm-4 6V3c0-.55-.45-1-1-1H3c-.55 0-1 .45-1 1v14l4-4h10c.55 0 1-.45 1-1z"/>
                </svg>
              </div>
              <h4>Smart Assistant</h4>
              <p>AI-powered intelligent conversations</p>
            </div>
            
            <div className="feature">
              <div className="feature-icon">
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/>
                </svg>
              </div>
              <h4>Secure & Private</h4>
              <p>Your conversations are protected</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const messageGroups = groupMessagesByDate();

  return (
    <div className="chat-box" ref={chatContainerRef} onScroll={handleScroll}>
      {unreadCount > 0 && (
        <div className="unread-indicator">
          <span className="unread-count">
            {unreadCount} new message{unreadCount > 1 ? 's' : ''}
          </span>
        </div>
      )}
      
      <div className="messages-container">
        {messageGroups.map((group, groupIndex) => (
          <React.Fragment key={group.date}>
            <div className="date-separator">
              <span>{group.date}</span>
            </div>
            
            {group.messages.map((message) => (
              <MessageItem
                key={message.id}
                message={message}
                isUser={message.isUser}
                timestamp={message.timestamp || message.id}
                status={message.status}
                showAvatar={true}
                showTime={true}
              />
            ))}
          </React.Fragment>
        ))}
        
        {/* Invisible element for auto-scrolling */}
        <div ref={messagesEndRef} style={{ height: '1px' }} />
      </div>

      {/* Scroll to bottom button */}
      {showScrollBottom && (
        <button
          className="scroll-bottom-btn visible"
          onClick={() => scrollToBottom()}
          aria-label="Scroll to bottom"
        >
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M16.59 8.59L12 13.17 7.41 8.59 6 10l6 6 6-6z"/>
          </svg>
        </button>
      )}

      {/* New message indicator */}
      {unreadCount > 0 && (
        <div className="new-message-indicator" onClick={handleNewMessageClick}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M16.59 8.59L12 13.17 7.41 8.59 6 10l6 6 6-6z"/>
          </svg>
          {unreadCount} new
        </div>
      )}
    </div>
  );
});

ChatBox.displayName = 'ChatBox';

export default ChatBox;