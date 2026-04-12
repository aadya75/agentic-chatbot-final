// frontend/src/App.jsx
import React, { useState } from 'react';
import ChatContainer from './Components/ChatContainer';
import ThreadSidebar from './Components/ThreadSidebar';
import UploadDocs from './Components/UploadDocs';
import { useApiHealth } from './hooks/useApiHealth';
import { useThreads } from './hooks/useThreads';
import './App.css';
import { AuthProvider } from "./context/AuthContext";
import { useAuth } from "./context/AuthContext";
import LoginPage from "./Components/auth/LoginPage";
import ProfilePage from "./Components/auth/ProfilePage";

// ── Inner app — only rendered when authenticated ───────────────────────────
function AuthenticatedApp() {
  const { user, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showProfile, setShowProfile] = useState(false);

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

  const handleNewThread = async () => { await createThread(); };
  const handleSelectThread = (threadId) => { selectThread(threadId); };
  const handleDeleteThread = async (threadId) => {
    try {
      await deleteThread(threadId);
    } catch (error) {
      console.error('Failed to delete thread:', error);
      alert('Failed to delete chat. Please try again.');
    }
  };
  const handleMessageSent = (threadId, message) => {
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

  // Show profile page as a full overlay when toggled
  if (showProfile) {
    return (
      <div className="App">
        <ProfilePage onBack={() => setShowProfile(false)} />
      </div>
    );
  }

  return (
    <div className="App">
      <ConnectionStatusBanner />

      <div className="app-layout">
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
                    {health.isHealthy ? 'Connected' : 'Disconnected'} •&nbsp;
                    Uptime: {Math.round(health.data?.uptime_seconds || 0)}s
                  </span>
                </div>
              </div>
            </div>

            <div className="header-actions">
              <UploadDocs
                onUploadSuccess={(result) => {
                  console.log('PDF uploaded:', result);
                  alert(`PDF "${result.filename}" uploaded and indexed successfully!`);
                }}
              />

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

              {/* Profile / Settings button */}
              <button
                className="profile-button"
                onClick={() => setShowProfile(true)}
                title={`Signed in as ${user?.email}`}
              >
                <span className="profile-avatar">
                  {user?.email?.[0]?.toUpperCase() || '?'}
                </span>
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

// ── Auth gate — shown while loading or when logged out ─────────────────────
function AppGate() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="spinner"></div>
        <p>Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return <AuthenticatedApp />;
}

// ── Root — AuthProvider wraps everything ───────────────────────────────────
function App() {
  return (
    <AuthProvider>
      <AppGate />
    </AuthProvider>
  );
}

export default App;
