import React, { useState, useRef, useEffect } from 'react';
import ChatBox from './ChatBox';
import MessageInput from './MessageInput';
import './ChatContainer.css';

export default function ChatContainer() {
  const [messages, setMessages] = useState([]);
  const [isBotTyping, setIsBotTyping] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('online');
  const scrollRef = useRef(null);

  // Add a new message to the list
  const addMessage = (text, isUser = true) => {
    const newMessage = { 
      id: Date.now(), 
      text, 
      isUser,
      timestamp: Date.now(),
      status: 'sent'
    };
    setMessages(prev => [...prev, newMessage]);
  };

  // Handle user message
  const handleUserMessage = (userText) => {
    addMessage(userText, true);
    setIsBotTyping(true);
    
    // Simulate bot response
    setTimeout(() => {
      const responses = [
        `I understand you said: "${userText}"`,
        `Thanks for sharing: "${userText}"`,
        `Got it! You mentioned: "${userText}"`,
        `Interesting point about "${userText}"`
      ];
      const botReply = responses[Math.floor(Math.random() * responses.length)];
      addMessage(botReply, false);
      setIsBotTyping(false);
    }, 1000 + Math.random() * 1000);
  };

  // Clear chat history
  const clearChat = () => {
    if (window.confirm('Are you sure you want to clear all messages?')) {
      setMessages([]);
    }
  };

  // Export chat
  const exportChat = () => {
    const chatData = messages.map(msg => ({
      time: new Date(msg.timestamp).toLocaleString(),
      sender: msg.isUser ? 'You' : 'Bot',
      message: msg.text
    }));
    
    const blob = new Blob([JSON.stringify(chatData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-history-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Simulate connection status changes
  useEffect(() => {
    const statuses = ['online', 'connecting', 'offline'];
    const interval = setInterval(() => {
      if (Math.random() > 0.9) { // 10% chance to change status
        setConnectionStatus(statuses[Math.floor(Math.random() * statuses.length)]);
      }
    }, 5000);
    
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="chat-container">
      {/* Header */}
      <header className="chat-header">
        <div className="chat-header-info">
          <button 
            className="header-btn mobile-only"
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            aria-label="Toggle sidebar"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/>
            </svg>
          </button>
          
          <div className="chat-avatar">
            AI
          </div>
          
          <div className="chat-title">
            <h2>AI Assistant</h2>
            <p>Online • Ready to help</p>
          </div>
        </div>
        
        <div className="chat-header-actions">
          <button 
            className="header-btn"
            onClick={clearChat}
            aria-label="Clear chat"
            title="Clear chat"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
          
          <button 
            className="header-btn"
            onClick={exportChat}
            aria-label="Export chat"
            title="Export chat"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
            </svg>
          </button>
          
          <button 
            className="header-btn"
            onClick={() => window.print()}
            aria-label="Print chat"
            title="Print chat"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 8H5c-1.66 0-3 1.34-3 3v6h4v4h12v-4h4v-6c0-1.66-1.34-3-3-3zm-3 11H8v-5h8v5zm3-7c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1zm-1-9H6v4h12V3z"/>
            </svg>
          </button>
        </div>
      </header>
      
      {/* Main content */}
      <main className="chat-main">
        {/* Sidebar (optional - can be hidden) */}
        <aside className={`chat-sidebar ${isSidebarOpen ? 'open' : ''}`}>
          <div className="sidebar-header">
            <h3>Conversations</h3>
          </div>
          <div className="conversation-list">
            {/* Add conversation history here if needed */}
            <p style={{ padding: '1rem', color: '#8E8E93', textAlign: 'center' }}>
              Conversation history will appear here
            </p>
          </div>
        </aside>
        
        {/* Chat area */}
        <section className="chat-area">
          <ChatBox 
            messages={messages} 
            ref={scrollRef} 
            loading={false}
          />
          <MessageInput 
            onSend={handleUserMessage} 
            isBotTyping={isBotTyping}
          />
        </section>
      </main>
      
      {/* Footer */}
      <footer className="chat-footer">
        <div className="connection-status">
          <div className={`status-indicator ${connectionStatus}`}></div>
          <span>Status: {connectionStatus}</span>
        </div>
        
        <div className="message-count">
          Messages: {messages.length}
        </div>
      </footer>
    </div>
  );
}