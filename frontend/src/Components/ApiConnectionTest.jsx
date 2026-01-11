import React from 'react';
import { useApiHealth, useChat } from '../hooks';

const ApiConnectionTest = () => {
  const health = useApiHealth({
    autoCheck: true,
    interval: 10000,
    onStatusChange: (status) => {
      console.log('Health status changed:', status);
    },
  });

  const chat = useChat({
    autoCreateThread: true,
    onMessageSent: (msg) => console.log('Message sent:', msg),
    onMessageReceived: (msg) => console.log('Message received:', msg),
  });

  const [testMessage, setTestMessage] = React.useState('Hello, how are you?');
  const [isSending, setIsSending] = React.useState(false);

  const handleSendTest = async () => {
    if (!testMessage.trim() || isSending) return;
    
    setIsSending(true);
    try {
      await chat.sendMessage(testMessage);
      setTestMessage('');
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setIsSending(false);
    }
  };

  const handleQuickTest = async () => {
    await chat.sendMessage('Quick test message');
  };

  const handleClear = () => {
    chat.clearChat();
  };

  return (
    <div style={{
      maxWidth: '800px',
      margin: '0 auto',
      padding: '20px',
      fontFamily: 'Arial, sans-serif'
    }}>
      <h2>🔌 API Connection Test</h2>
      
      {/* Health Status */}
      <div style={{
        marginBottom: '20px',
        padding: '15px',
        borderRadius: '8px',
        backgroundColor: health.isHealthy ? '#e8f5e8' : '#f8d7da',
        border: `1px solid ${health.isHealthy ? '#d4edda' : '#f5c6cb'}`,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ margin: '0 0 5px 0', color: health.isHealthy ? '#155724' : '#721c24' }}>
              {health.isHealthy ? '✅ Backend Connected' : '❌ Backend Disconnected'}
            </h3>
            <p style={{ margin: '0', fontSize: '0.9em', color: '#666' }}>
              URL: {process.env.REACT_APP_API_URL || 'http://localhost:8000'}
              {health.lastCheckedTime && ` | Last checked: ${health.lastCheckedTime}`}
            </p>
          </div>
          <button
            onClick={health.checkHealth}
            disabled={health.loading}
            style={{
              padding: '8px 16px',
              backgroundColor: '#6c757d',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: health.loading ? 'not-allowed' : 'pointer'
            }}
          >
            {health.loading ? 'Checking...' : 'Re-check'}
          </button>
        </div>
        
        {health.data && (
          <div style={{ marginTop: '10px', fontSize: '0.9em' }}>
            <div><strong>Version:</strong> {health.getVersion()}</div>
            <div><strong>Uptime:</strong> {Math.round(health.getUptime())} seconds</div>
            <div><strong>Status:</strong> {health.data?.status || 'unknown'}</div>
          </div>
        )}
        
        {health.error && (
          <div style={{ marginTop: '10px', color: '#721c24' }}>
            <strong>Error:</strong> {health.error}
          </div>
        )}
      </div>

      {/* Chat Test */}
      <div style={{
        marginBottom: '20px',
        padding: '15px',
        backgroundColor: '#f8f9fa',
        borderRadius: '8px',
        border: '1px solid #e9ecef'
      }}>
        <h3>💬 Chat Test</h3>
        
        <div style={{ marginBottom: '15px' }}>
          <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
            <input
              type="text"
              value={testMessage}
              onChange={(e) => setTestMessage(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSendTest()}
              placeholder="Type a test message..."
              style={{ flex: 1, padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
              disabled={!health.isHealthy || isSending}
            />
            <button
              onClick={handleSendTest}
              disabled={!health.isHealthy || isSending || !testMessage.trim()}
              style={{
                padding: '8px 16px',
                backgroundColor: health.isHealthy ? '#007bff' : '#ccc',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: health.isHealthy && !isSending ? 'pointer' : 'not-allowed'
              }}
            >
              {isSending ? 'Sending...' : 'Send'}
            </button>
          </div>
          
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={handleQuickTest}
              disabled={!health.isHealthy || isSending}
              style={buttonStyle}
            >
              Quick Test
            </button>
            <button
              onClick={handleClear}
              disabled={chat.messages.length === 0}
              style={buttonStyle}
            >
              Clear Chat
            </button>
            <button
              onClick={chat.createThread}
              disabled={chat.loading}
              style={buttonStyle}
            >
              New Thread
            </button>
          </div>
        </div>

        {/* Chat Messages */}
        <div style={{
          maxHeight: '300px',
          overflowY: 'auto',
          marginTop: '15px',
          padding: '10px',
          backgroundColor: 'white',
          borderRadius: '4px',
          border: '1px solid #ddd'
        }}>
          {chat.messages.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#999', padding: '20px' }}>
              No messages yet. Send a test message!
            </div>
          ) : (
            chat.messages.map((msg) => (
              <div
                key={msg.id}
                style={{
                  marginBottom: '10px',
                  padding: '10px',
                  borderRadius: '8px',
                  backgroundColor: msg.isUser ? '#e3f2fd' : '#f5f5f5',
                  borderLeft: `4px solid ${msg.isUser ? '#2196f3' : '#4caf50'}`,
                  ...(msg.isError && {
                    backgroundColor: '#ffebee',
                    borderLeftColor: '#f44336'
                  })
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <strong>{msg.isUser ? 'You' : msg.isError ? 'Error' : 'Bot'}</strong>
                  <small style={{ color: '#666' }}>
                    {new Date(msg.timestamp).toLocaleTimeString()}
                  </small>
                </div>
                <div style={{ marginTop: '5px' }}>{msg.text}</div>
                {msg.metadata && (
                  <div style={{ marginTop: '5px', fontSize: '0.8em', color: '#666' }}>
                    {msg.metadata.toolsUsed?.length > 0 && (
                      <div>Tools used: {msg.metadata.toolsUsed.join(', ')}</div>
                    )}
                    {msg.metadata.executionTime && (
                      <div>Time: {msg.metadata.executionTime.toFixed(2)}s</div>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Stats */}
        {chat.messages.length > 0 && (
          <div style={{ marginTop: '15px', fontSize: '0.9em', color: '#666' }}>
            <strong>Stats:</strong> {chat.getStats().totalMessages} messages | 
            Thread: {chat.threadId?.substring(0, 8)}... | 
            Tools used: {chat.toolsUsed.length}
          </div>
        )}
      </div>

      {/* Connection Info */}
      <div style={{
        padding: '15px',
        backgroundColor: '#e7f3ff',
        borderRadius: '8px',
        fontSize: '0.9em'
      }}>
        <h4>📋 Connection Information</h4>
        <ul style={{ margin: '10px 0', paddingLeft: '20px' }}>
          <li><strong>Backend URL:</strong> {process.env.REACT_APP_API_URL || 'http://localhost:8000'}</li>
          <li><strong>Health Endpoint:</strong> GET /api/health</li>
          <li><strong>Chat Endpoint:</strong> POST /api/message</li>
          <li><strong>Status:</strong> {health.isHealthy ? 'Connected' : 'Disconnected'}</li>
          <li><strong>Retry Count:</strong> {health.retryCount}</li>
        </ul>
        
        {chat.error && (
          <div style={{ color: '#dc3545', marginTop: '10px' }}>
            <strong>Chat Error:</strong> {chat.error}
          </div>
        )}
        
        {health.error && (
          <div style={{ color: '#dc3545', marginTop: '10px' }}>
            <strong>Health Error:</strong> {health.error}
          </div>
        )}
      </div>
    </div>
  );
};

const buttonStyle = {
  padding: '8px 16px',
  backgroundColor: '#6c757d',
  color: 'white',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer',
  fontSize: '0.9em'
};

export default ApiConnectionTest;