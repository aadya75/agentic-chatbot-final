// frontend/src/Components/ThreadSidebar.jsx
import React, { useState, useEffect } from 'react';
import './ThreadSidebar.css';

function ThreadSidebar({ 
  threads, 
  currentThreadId, 
  onSelectThread, 
  onNewThread, 
  onDeleteThread,
  isLoading 
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [hoveredThread, setHoveredThread] = useState(null);

  // Filter threads based on search
  const filteredThreads = threads.filter(thread => {
    if (!searchQuery) return true;
    const preview = thread.preview?.toLowerCase() || '';
    return preview.includes(searchQuery.toLowerCase());
  });

  // Group threads by date
  const groupedThreads = groupThreadsByDate(filteredThreads);

  const handleDelete = (e, threadId) => {
    e.stopPropagation();
    if (window.confirm('Delete this conversation?')) {
      onDeleteThread(threadId);
    }
  };

  return (
    <div className="thread-sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <h2>💬 Chats</h2>
        <button 
          className="new-chat-btn"
          onClick={onNewThread}
          disabled={isLoading}
          title="New Chat"
        >
          <span className="icon">✏️</span>
          New Chat
        </button>
      </div>

      {/* Search */}
      <div className="sidebar-search">
        <input
          type="text"
          placeholder="Search conversations..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="search-input"
        />
        {searchQuery && (
          <button 
            className="clear-search"
            onClick={() => setSearchQuery('')}
          >
            ✕
          </button>
        )}
      </div>

      {/* Thread List */}
      <div className="thread-list">
        {isLoading ? (
          <div className="loading-threads">
            <div className="spinner-small"></div>
            <span>Loading chats...</span>
          </div>
        ) : filteredThreads.length === 0 ? (
          <div className="no-threads">
            <div className="empty-icon">📭</div>
            <p>{searchQuery ? 'No chats found' : 'No chats yet'}</p>
            <p className="empty-hint">Start a new conversation!</p>
          </div>
        ) : (
          Object.entries(groupedThreads).map(([dateGroup, groupThreads]) => (
            <div key={dateGroup} className="thread-group">
              <div className="thread-group-label">{dateGroup}</div>
              {groupThreads.map(thread => (
                <div
                  key={thread.id}
                  className={`thread-item ${currentThreadId === thread.id ? 'active' : ''}`}
                  onClick={() => onSelectThread(thread.id)}
                  onMouseEnter={() => setHoveredThread(thread.id)}
                  onMouseLeave={() => setHoveredThread(null)}
                >
                  <div className="thread-content">
                    <div className="thread-title">
                      {thread.title || thread.preview || 'New Chat'}
                    </div>
                    <div className="thread-preview">
                      {thread.preview || 'No messages yet'}
                    </div>
                    <div className="thread-meta">
                      <span className="thread-time">
                        {formatTime(thread.created_at || thread.timestamp)}
                      </span>
                      {thread.message_count > 0 && (
                        <span className="thread-count">
                          {thread.message_count} {thread.message_count === 1 ? 'message' : 'messages'}
                        </span>
                      )}
                    </div>
                  </div>
                  {hoveredThread === thread.id && (
                    <button
                      className="delete-thread-btn"
                      onClick={(e) => handleDelete(e, thread.id)}
                      title="Delete chat"
                    >
                      🗑️
                    </button>
                  )}
                </div>
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// Helper function to group threads by date
function groupThreadsByDate(threads) {
  const groups = {
    'Today': [],
    'Yesterday': [],
    'Last 7 Days': [],
    'Last 30 Days': [],
    'Older': []
  };

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const last7Days = new Date(today);
  last7Days.setDate(last7Days.getDate() - 7);
  const last30Days = new Date(today);
  last30Days.setDate(last30Days.getDate() - 30);

  threads.forEach(thread => {
    const threadDate = new Date(thread.created_at || thread.timestamp);
    
    if (threadDate >= today) {
      groups['Today'].push(thread);
    } else if (threadDate >= yesterday) {
      groups['Yesterday'].push(thread);
    } else if (threadDate >= last7Days) {
      groups['Last 7 Days'].push(thread);
    } else if (threadDate >= last30Days) {
      groups['Last 30 Days'].push(thread);
    } else {
      groups['Older'].push(thread);
    }
  });

  // Remove empty groups
  return Object.fromEntries(
    Object.entries(groups).filter(([_, threads]) => threads.length > 0)
  );
}

// Helper function to format time
function formatTime(timestamp) {
  if (!timestamp) return '';
  
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export default ThreadSidebar;