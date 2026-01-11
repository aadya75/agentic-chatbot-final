// frontend/src/DebugTest.jsx
// Add this component temporarily to test API calls directly

import React, { useState } from 'react';

function DebugTest() {
  const [results, setResults] = useState([]);

  const addResult = (test, success, data) => {
    setResults(prev => [...prev, { test, success, data, time: new Date().toLocaleTimeString() }]);
  };

  const testDirect = async () => {
    // Test 1: Direct fetch to health endpoint
    try {
      console.log('Testing: http://localhost:8000/api/health');
      const response = await fetch('http://localhost:8000/api/health');
      const data = await response.json();
      addResult('Direct /api/health', response.ok, data);
    } catch (error) {
      addResult('Direct /api/health', false, error.message);
    }

    // Test 2: Direct fetch to create thread
    try {
      console.log('Testing: http://localhost:8000/api/thread');
      const response = await fetch('http://localhost:8000/api/thread', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await response.json();
      addResult('Direct POST /api/thread', response.ok, data);
    } catch (error) {
      addResult('Direct POST /api/thread', false, error.message);
    }
  };

  const testWithHttpClient = async () => {
    // Test 3: Using httpClient
    try {
      const { httpClient } = await import('./api/httpClient');
      console.log('httpClient.baseURL:', httpClient.baseURL);
      
      const health = await httpClient.get('/health');
      addResult('httpClient /health', true, health);
    } catch (error) {
      addResult('httpClient /health', false, error.message);
    }

    // Test 4: Create thread with httpClient
    try {
      const { httpClient } = await import('./api/httpClient');
      const thread = await httpClient.post('/thread');
      addResult('httpClient POST /thread', true, thread);
    } catch (error) {
      addResult('httpClient POST /thread', false, error.message);
    }
  };

  const testWithApiService = async () => {
    // Test 5: Using apiService
    try {
      const { apiService } = await import('./api/services');
      const health = await apiService.testConnection();
      addResult('apiService.testConnection()', true, health);
    } catch (error) {
      addResult('apiService.testConnection()', false, error.message);
    }

    // Test 6: Create thread with apiService
    try {
      const { apiService } = await import('./api/services');
      const thread = await apiService.createThread();
      addResult('apiService.createThread()', true, thread);
    } catch (error) {
      addResult('apiService.createThread()', false, error.message);
    }
  };

  return (
    <div style={{ padding: '20px', maxWidth: '800px', margin: '0 auto' }}>
      <h1>🔍 API Debug Test</h1>
      
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
        <button onClick={testDirect} style={buttonStyle}>
          Test Direct Fetch
        </button>
        <button onClick={testWithHttpClient} style={buttonStyle}>
          Test HttpClient
        </button>
        <button onClick={testWithApiService} style={buttonStyle}>
          Test ApiService
        </button>
        <button onClick={() => setResults([])} style={buttonStyle}>
          Clear
        </button>
      </div>

      <div>
        <h2>Results:</h2>
        {results.length === 0 && <p>No tests run yet</p>}
        {results.map((result, index) => (
          <div
            key={index}
            style={{
              padding: '10px',
              margin: '10px 0',
              border: `2px solid ${result.success ? 'green' : 'red'}`,
              borderRadius: '5px',
              background: result.success ? '#e8f5e9' : '#ffebee'
            }}
          >
            <div style={{ fontWeight: 'bold' }}>
              {result.success ? '✅' : '❌'} {result.test}
            </div>
            <div style={{ fontSize: '12px', color: '#666' }}>{result.time}</div>
            <pre style={{ fontSize: '12px', overflow: 'auto' }}>
              {JSON.stringify(result.data, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}

const buttonStyle = {
  padding: '10px 20px',
  fontSize: '14px',
  cursor: 'pointer',
  borderRadius: '5px',
  border: '1px solid #ccc',
  background: '#f0f0f0'
};

export default DebugTest;