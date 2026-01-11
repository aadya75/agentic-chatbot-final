// frontend/src/App.jsx
import React, { useState } from 'react';
import ChatContainer from './Components/ChatContainer';
import ThreadSidebar from './Components/ThreadSidebar';
import { useApiHealth } from './hooks/useApiHealth';
import { useThreads } from './hooks/useThreads';
import './App.css';

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  
  const health = useApiHealth({
    autoCheck: true,
    interval: 30000,
    onStatusChange: (status) => {
      console.log('Backend status:', status);
    },
  });

  const {
    threads,
    currentThreadId,
    isLoading: threadsLoading,
    createThread,
    deleteThread,
    selectThread,
    updateThreadPreview,
  } = useThreads();

  const [showConnectionStatus, setShowConnectionStatus] = useState(false);

  const handleNewThread = async () => {
    await createThread();
  };

  const handleSelectThread = (threadId) => {
    selectThread(threadId);
  };

  const handleDeleteThread = async (threadId) => {
    try {
      await deleteThread(threadId);
    } catch (error) {
      console.error('Failed to delete thread:', error);
      alert('Failed to delete chat. Please try again.');
    }
  };

  const handleMessageSent = (threadId, message) => {
    // Update thread preview with the new message
    updateThreadPreview(threadId, message);
  };

  if (health.loading && !health.lastChecked) {
    return (
      <div className="loading-screen">
        <div className="spinner"></div>
        <p>Connecting to backend...</p>
      </div>
    );
  }

  const ConnectionStatusBanner = () => {
    if (!showConnectionStatus && health.isHealthy) return null;

    return (
      <div className={`connection-banner ${health.isHealthy ? 'success' : 'error'}`}>
        <div className="connection-icon">
          {health.isHealthy ? '✅' : '❌'}
        </div>
        <div className="connection-details">
          <div className="connection-title">
            {health.isHealthy ? 'Backend Connected' : 'Backend Connection Error'}
          </div>
          <div className="connection-message">
            {health.isHealthy ? 'All systems operational' : health.error}
          </div>
        </div>
        {showConnectionStatus && (
          <button
            className="connection-close"
            onClick={() => setShowConnectionStatus(false)}
          >
            ×
          </button>
        )}
      </div>
    );
  };

  return (
    <div className="App">
      <ConnectionStatusBanner />
      
      <div className="app-layout">
        {/* Sidebar */}
        {sidebarOpen && (
          <ThreadSidebar
            threads={threads}
            currentThreadId={currentThreadId}
            onSelectThread={handleSelectThread}
            onNewThread={handleNewThread}
            onDeleteThread={handleDeleteThread}
            isLoading={threadsLoading}
          />
        )}

        {/* Main Content */}
        <div className="app-main-container">
          <header className="app-header">
            <div className="header-left">
              <button
                className="toggle-sidebar-btn"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                title={sidebarOpen ? 'Hide Sidebar' : 'Show Sidebar'}
              >
                {sidebarOpen ? '◀' : '▶'}
              </button>
              <div className="app-logo">🤖</div>
              <div className="app-title">
                <h1>Agentic Chatbot</h1>
                <div className="app-subtitle">
                  <span className={`status-dot ${health.isHealthy ? 'connected' : 'disconnected'}`}></span>
                  <span>
                    {health.isHealthy ? 'Connected' : 'Disconnected'} • 
                    Uptime: {Math.round(health.data?.uptime_seconds || 0)}s
                  </span>
                </div>
              </div>
            </div>
            
            <div className="header-actions">
              <button
                className="status-button"
                onClick={() => setShowConnectionStatus(!showConnectionStatus)}
                title="Connection Status"
              >
                <span className="button-icon">
                  {health.isHealthy ? '✅' : '❌'}
                </span>
                Status
              </button>
            </div>
          </header>

          <main className="app-main">
            {currentThreadId ? (
              <ChatContainer 
                threadId={currentThreadId}
                isBackendConnected={health.isHealthy}
                onMessageSent={handleMessageSent}
              />
            ) : (
              <div className="no-thread-selected">
                <div className="empty-state-large">
                  <div className="empty-icon-large">💬</div>
                  <h2>No chat selected</h2>
                  <p>Select a chat from the sidebar or create a new one</p>
                  <button className="create-thread-btn" onClick={handleNewThread}>
                    ✏️ New Chat
                  </button>
                </div>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}

export default App;