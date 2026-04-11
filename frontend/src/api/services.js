// frontend/src/api/services.js
import { httpClient } from './httpClient';
import API_CONFIG, { ENDPOINTS } from './config.js';

/**
 * API service methods for interacting with the backend
 */
export const apiService = {
  // =========================================================================
  // Helper to get auth token from storage
  // =========================================================================
  
  getAuthToken() {
    return localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
  },

  setAuthToken(token, remember = false) {
    if (token) {
      if (remember) {
        localStorage.setItem('access_token', token);
      } else {
        sessionStorage.setItem('access_token', token);
      }
      httpClient.setAuthToken(token);
      
      if (API_CONFIG.DEBUG) {
        console.log('🔑 Auth token saved to storage');
      }
    } else {
      localStorage.removeItem('access_token');
      sessionStorage.removeItem('access_token');
      httpClient.setAuthToken(null);
      
      if (API_CONFIG.DEBUG) {
        console.log('🔑 Auth token cleared from storage');
      }
    }
  },

  // =========================================================================
  // Health & Status
  // =========================================================================

  /**
   * Test backend connection and health
   */
  async testConnection() {
    try {
      const response = await httpClient.get(ENDPOINTS.HEALTH);
      return {
        connected: true,
        data: response,
        error: null
      };
    } catch (error) {
      return {
        connected: false,
        data: null,
        error: error.message || 'Failed to connect to backend'
      };
    }
  },

  /**
   * Get detailed backend status
   */
  async getStatus() {
    return await httpClient.get(ENDPOINTS.STATUS);
  },

  // =========================================================================
  // Authentication Methods
  // =========================================================================

  /**
   * User signup
   */
  async signup(userData) {
    try {
      const response = await httpClient.post(ENDPOINTS.SIGNUP, {
        email: userData.email,
        password: userData.password,
        full_name: userData.full_name
      });
      
      if (response.access_token) {
        this.setAuthToken(response.access_token, userData.remember || false);
      }
      
      return {
        success: true,
        data: response
      };
    } catch (error) {
      console.error('Signup failed:', error);
      throw error;
    }
  },

  /**
   * User login
   */
  async login(credentials) {
    try {
      const response = await httpClient.post(ENDPOINTS.LOGIN, {
        email: credentials.email,
        password: credentials.password
      });
      
      if (response.access_token) {
        this.setAuthToken(response.access_token, credentials.remember || false);
      }
      
      if (API_CONFIG.DEBUG) {
        console.log('✅ Login successful');
      }
      
      return {
        success: true,
        data: response
      };
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  },

  /**
   * User logout
   */
  async logout() {
    try {
      await httpClient.post(ENDPOINTS.LOGOUT);
      this.setAuthToken(null);
      return { success: true };
    } catch (error) {
      console.error('Logout failed:', error);
      // Still clear local token even if server logout fails
      this.setAuthToken(null);
      throw error;
    }
  },

  /**
   * Refresh authentication token
   */
  async refreshToken() {
    try {
      const response = await httpClient.post(ENDPOINTS.REFRESH);
      if (response.access_token) {
        this.setAuthToken(response.access_token, true);
      }
      return response;
    } catch (error) {
      console.error('Token refresh failed:', error);
      this.setAuthToken(null);
      throw error;
    }
  },

  /**
   * Get current user info
   */
  async getCurrentUser() {
    try {
      const token = this.getAuthToken();
      if (!token) {
        throw new Error('No auth token');
      }
      
      // Make sure token is set in httpClient
      httpClient.setAuthToken(token);
      
      const response = await httpClient.get(ENDPOINTS.ME);
      return response;
    } catch (error) {
      console.error('Get current user failed:', error);
      throw error;
    }
  },

  /**
   * Check if user is authenticated
   */
  async isAuthenticated() {
    try {
      await this.getCurrentUser();
      return true;
    } catch {
      return false;
    }
  },

  /**
   * Initialize auth on app start
   */
  async initializeAuth() {
    const token = this.getAuthToken();
    if (token) {
      if (API_CONFIG.DEBUG) {
        console.log('🔑 Found existing token, initializing auth...');
      }
      
      httpClient.setAuthToken(token);
      
      try {
        const user = await this.getCurrentUser();
        if (API_CONFIG.DEBUG) {
          console.log('✅ Auth initialized successfully for user:', user.email);
        }
        return { authenticated: true, user };
      } catch (error) {
        if (API_CONFIG.DEBUG) {
          console.warn('⚠️ Token validation failed, clearing auth:', error.message);
        }
        // Token is invalid or expired
        this.setAuthToken(null);
        return { authenticated: false, user: null };
      }
    }
    
    if (API_CONFIG.DEBUG) {
      console.log('ℹ️ No existing token found');
    }
    return { authenticated: false, user: null };
  },

  // frontend/src/api/services.js
// Add/replace these OAuth methods

  // =========================================================================
  // OAuth Methods - FIXED VERSION
  // =========================================================================

  /**
   * Initiate Google OAuth flow
   * This should redirect to your backend, which then redirects to Google
   */
  async initiateGoogleLogin() {
    try {
      // Redirect to backend's Google connect endpoint
      // The backend will handle creating the proper Google OAuth URL
      const googleAuthUrl = `${API_CONFIG.BASE_URL}${ENDPOINTS.GOOGLE_CONNECT}`;
      
      if (API_CONFIG.DEBUG) {
        console.log('🔐 Redirecting to Google OAuth:', googleAuthUrl);
      }
      
      // Redirect the browser to the backend endpoint
      window.location.href = googleAuthUrl;
    } catch (error) {
      console.error('Failed to initiate Google login:', error);
      throw error;
    }
  },

  /**
   * Initiate GitHub OAuth flow
   * This should redirect to your backend, which then redirects to GitHub
   */
  async initiateGithubLogin() {
    try {
      // Redirect to backend's GitHub connect endpoint
      // The backend will handle creating the proper GitHub OAuth URL
      const githubAuthUrl = `${API_CONFIG.BASE_URL}${ENDPOINTS.GITHUB_CONNECT}`;
      
      if (API_CONFIG.DEBUG) {
        console.log('🔐 Redirecting to GitHub OAuth:', githubAuthUrl);
      }
      
      // Redirect the browser to the backend endpoint
      window.location.href = githubAuthUrl;
    } catch (error) {
      console.error('Failed to initiate GitHub login:', error);
      throw error;
    }
  },

  /**
   * Handle OAuth callback (to be called on your callback page)
   * This is called after Google/GitHub redirect back to your frontend
   */
  async handleOAuthCallback() {
    // Get token from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    const error = urlParams.get('error');
    
    if (error) {
      console.error('OAuth error:', error);
      return { success: false, error };
    }
    
    if (token) {
      // Store the token
      this.setAuthToken(token, true);
      
      if (API_CONFIG.DEBUG) {
        console.log('✅ OAuth login successful');
      }
      
      // Clean up URL (remove token from query string)
      window.history.replaceState({}, document.title, window.location.pathname);
      
      return { success: true, token };
    }
    
    return { success: false, error: 'No token received' };
  },

  /**
   * Get Google OAuth URL (DEPRECATED - use initiateGoogleLogin instead)
   * This was causing the direct GitHub issue
   */
  getGoogleAuthUrl() {
    console.warn('getGoogleAuthUrl is deprecated. Use initiateGoogleLogin() instead');
    return `${API_CONFIG.BASE_URL}${ENDPOINTS.GOOGLE_CONNECT}`;
  },

  /**
   * Get GitHub OAuth URL (DEPRECATED - use initiateGithubLogin instead)
   * This was causing the direct GitHub issue
   */
  getGithubAuthUrl() {
    console.warn('getGithubAuthUrl is deprecated. Use initiateGithubLogin() instead');
    return `${API_CONFIG.BASE_URL}${ENDPOINTS.GITHUB_CONNECT}`;
  },

  // =========================================================================
  // Thread/Chat Management
  // =========================================================================

  /**
   * Create a new conversation thread
   */
  async createThread() {
    try {
      const token = this.getAuthToken();
      if (!token) {
        throw new Error('Not authenticated');
      }
      
      httpClient.setAuthToken(token);
      
      const response = await httpClient.post(ENDPOINTS.CREATE_THREAD);
      return {
        success: true,
        threadId: response.thread_id,
        data: response
      };
    } catch (error) {
      console.error('Failed to create thread:', error);
      throw error;
    }
  },

  /**
   * Delete a thread
   */
  async deleteThread(threadId) {
    try {
      const token = this.getAuthToken();
      if (!token) {
        throw new Error('Not authenticated');
      }
      
      httpClient.setAuthToken(token);
      
      return await httpClient.delete(ENDPOINTS.DELETE_THREAD(threadId));
    } catch (error) {
      console.error('Failed to delete thread:', error);
      throw error;
    }
  },

  /**
   * List all threads
   * NOTE: This endpoint doesn't exist in your backend
   */
  async listThreads() {
    console.warn('listThreads endpoint not implemented in backend');
    return [];
  },

  /**
   * Send a message
   */
  async sendMessage(threadId, message, options = {}) {
    try {
      const token = this.getAuthToken();
      if (!token) {
        throw new Error('Not authenticated');
      }
      
      httpClient.setAuthToken(token);
      
      if (API_CONFIG.DEBUG) {
        console.log('📨 Sending message:', { threadId, message });
      }
      
      const response = await httpClient.post(ENDPOINTS.SEND_MESSAGE, {
        message: message,
        thread_id: threadId,
        user_id: options.userId || null
      });
      
      if (API_CONFIG.DEBUG) {
        console.log('📬 Received response:', response);
      }
      
      return {
        success: true,
        data: response
      };
    } catch (error) {
      console.error('❌ Failed to send message:', error);
      throw error;
    }
  },

  /**
   * Confirm (approve or reject) a pending HITL action.
   * Called after sendMessage returns interrupted=true.
   *
   * @param {string} threadId   - From confirmation_required.thread_id
   * @param {string} userResp   - "approve" or "reject"
   * @returns {object}          - Same shape as sendMessage()
   */
  async confirmAction(threadId, userResp) {
    const token = this.getAuthToken();
    if (!token) throw new Error('Not authenticated');
    httpClient.setAuthToken(token);

    if (API_CONFIG.DEBUG) {
      console.log('🔐 HITL confirm:', { threadId, userResp });
    }

    const response = await httpClient.post('/api/message/confirm', {
      thread_id: threadId,
      response: userResp,
    });

    return { success: true, data: response };
  },

  /**
   * Stream a message response (Server-Sent Events)
   */
  async streamMessage(threadId, message, onChunk, onComplete, onError) {
    try {
      const token = this.getAuthToken();
      if (!token) {
        throw new Error('Not authenticated');
      }
      
      // For now, fall back to regular message
      const result = await this.sendMessage(threadId, message);
      if (result.success) {
        // Simulate streaming by sending the complete response as one chunk
        onChunk?.({ type: 'token', content: result.data.message });
        onComplete?.();
      }
    } catch (error) {
      onError?.(error);
    }
  },

  /**
   * Get all messages from a thread
   */
  async getMessages(threadId) {
    try {
      const token = this.getAuthToken();
      if (!token) {
        throw new Error('Not authenticated');
      }
      
      httpClient.setAuthToken(token);
      
      const response = await httpClient.get(ENDPOINTS.GET_THREAD_MESSAGES(threadId));
      return response.messages || response;
    } catch (error) {
      console.error('Failed to get messages:', error);
      throw error;
    }
  },

  /**
   * Clear all messages from a thread
   * NOTE: This endpoint doesn't exist in your backend
   */
  async clearMessages(threadId) {
    console.warn('clearMessages endpoint not implemented in backend');
    throw new Error('Not implemented');
  },

  /**
   * Get available tools
   */
  async getTools() {
    try {
      return await httpClient.get('/api/tools');
    } catch (error) {
      console.warn('getTools endpoint not available');
      return { tools: [] };
    }
  },

  // =========================================================================
  // Knowledge Base / Document Management
  // =========================================================================

  /**
   * Upload a PDF document to the knowledge base
   */
  async uploadDocument(file) {
    const token = this.getAuthToken();
    if (!token) {
      throw new Error('Not authenticated');
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    const url = `${httpClient.baseURL}${ENDPOINTS.KNOWLEDGE_UPLOAD}`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData,
      // Don't set Content-Type header - let browser set it with boundary
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || error.message || 'Upload failed');
    }
    
    return response.json();
  },

  /**
   * Upload multiple documents
   */
  async uploadMultipleDocuments(files) {
    const results = {
      success: [],
      failed: []
    };
    
    for (const file of files) {
      try {
        const result = await this.uploadDocument(file);
        results.success.push({ file: file.name, ...result });
      } catch (error) {
        results.failed.push({ file: file.name, error: error.message });
      }
    }
    
    return results;
  },

  /**
   * Check the processing status of an uploaded document
   */
  async checkUploadStatus(taskId) {
    const token = this.getAuthToken();
    if (!token) {
      throw new Error('Not authenticated');
    }
    
    httpClient.setAuthToken(token);
    return await httpClient.get(ENDPOINTS.KNOWLEDGE_STATUS(taskId));
  },

  /**
   * Poll for upload status until complete
   */
  async pollUploadStatus(taskId, interval = 2000, maxAttempts = 60) {
    let attempts = 0;
    
    while (attempts < maxAttempts) {
      try {
        const status = await this.checkUploadStatus(taskId);
        
        if (status.status === 'completed') {
          return { success: true, data: status };
        } else if (status.status === 'failed') {
          return { success: false, error: status.error || 'Processing failed' };
        }
        
        if (API_CONFIG.DEBUG) {
          console.log(`Polling status for ${taskId}: ${status.status} (${status.progress}%)`);
        }
        
        await new Promise(resolve => setTimeout(resolve, interval));
        attempts++;
      } catch (error) {
        console.error('Error polling status:', error);
        await new Promise(resolve => setTimeout(resolve, interval));
        attempts++;
      }
    }
    
    return { success: false, error: 'Processing timeout' };
  },

  /**
   * List all resources/documents in the knowledge base
   */
  async listResources() {
    const token = this.getAuthToken();
    if (!token) {
      throw new Error('Not authenticated');
    }
    
    httpClient.setAuthToken(token);
    return await httpClient.get(ENDPOINTS.KNOWLEDGE_LIST);
  },

  /**
   * Delete a resource/document from the knowledge base
   */
  async deleteResource(paperId) {
    const token = this.getAuthToken();
    if (!token) {
      throw new Error('Not authenticated');
    }
    
    httpClient.setAuthToken(token);
    return await httpClient.delete(ENDPOINTS.KNOWLEDGE_DELETE(paperId));
  },

  /**
   * Search the knowledge base for relevant documents
   */
  async searchDocuments(query, topK = 5, includeCitations = false) {
    const token = this.getAuthToken();
    if (!token) {
      throw new Error('Not authenticated');
    }
    
    httpClient.setAuthToken(token);
    return await httpClient.post(ENDPOINTS.KNOWLEDGE_SEARCH, {
      query: query,
      top_k: topK,
      include_citations: includeCitations
    });
  },

  /**
   * Get knowledge base statistics
   */
  async getKnowledgeStats() {
    const token = this.getAuthToken();
    if (!token) {
      throw new Error('Not authenticated');
    }
    
    httpClient.setAuthToken(token);
    return await httpClient.get(ENDPOINTS.KNOWLEDGE_STATS);
  },

  /**
   * Get system information about the knowledge base
   */
  async getKnowledgeSystemInfo() {
    return await httpClient.get(ENDPOINTS.KNOWLEDGE_INFO);
  },

  // =========================================================================
  // Helper methods
  // =========================================================================

  /**
   * Get a formatted list of resources with metadata
   */
  async getFormattedResources() {
    try {
      const result = await this.listResources();
      return result.resources.map(resource => ({
        id: resource.paper_id,
        name: resource.filename,
        uploadDate: resource.upload_date,
        userId: resource.user_id,
        type: 'pdf',
        status: resource.status || 'completed',
        ...resource
      }));
    } catch (error) {
      console.error('Failed to get formatted resources:', error);
      return [];
    }
  },

  /**
   * Bulk delete multiple resources
   */
  async bulkDeleteResources(paperIds) {
    const results = {
      success: [],
      failed: []
    };
    
    const deletePromises = paperIds.map(async (paperId) => {
      try {
        await this.deleteResource(paperId);
        return { paperId, success: true };
      } catch (error) {
        return { paperId, success: false, error: error.message };
      }
    });
    
    const settledResults = await Promise.allSettled(deletePromises);
    
    for (const result of settledResults) {
      if (result.status === 'fulfilled') {
        if (result.value.success) {
          results.success.push(result.value.paperId);
        } else {
          results.failed.push({ 
            paperId: result.value.paperId, 
            error: result.value.error 
          });
        }
      }
    }
    
    return results;
  },

  /**
   * Enhanced search with additional metadata
   */
  async enhancedSearch(query, options = {}) {
    const { topK = 5, includeCitations = true, minRelevanceScore = 0 } = options;
    
    const result = await this.searchDocuments(query, topK, includeCitations);
    
    if (minRelevanceScore > 0 && result.chunks) {
      result.chunks = result.chunks.filter(
        chunk => (chunk.relevance_score || 0) >= minRelevanceScore
      );
      result.num_results = result.chunks.length;
    }
    
    return result;
  },

  /**
   * Get document by ID with additional metadata
   */
  async getDocumentById(paperId) {
    try {
      const resources = await this.listResources();
      const resource = resources.resources.find(r => r.paper_id === paperId);
      
      if (!resource) {
        throw new Error('Document not found');
      }
      
      return {
        found: true,
        document: resource
      };
    } catch (error) {
      console.error('Failed to get document:', error);
      return {
        found: false,
        error: error.message
      };
    }
  },

  /**
   * Validate file before upload
   */
  validateFile(file) {
    const maxSize = 10 * 1024 * 1024; // 10MB
    const allowedTypes = ['application/pdf'];
    
    if (!allowedTypes.includes(file.type)) {
      return {
        valid: false,
        error: 'Only PDF files are allowed'
      };
    }
    
    if (file.size > maxSize) {
      return {
        valid: false,
        error: 'File size must be less than 10MB'
      };
    }
    
    return {
      valid: true,
      error: null
    };
  }
};

// Setup global auth error handler
if (typeof window !== 'undefined') {
  window.addEventListener('auth:unauthorized', (event) => {
    if (API_CONFIG.DEBUG) {
      console.warn('🔒 Authentication error detected:', event.detail);
    }
    // Clear token and dispatch logout event
    apiService.setAuthToken(null);
    window.dispatchEvent(new CustomEvent('app:logout', { 
      detail: { reason: 'unauthorized', message: event.detail?.message }
    }));
  });
}

export default apiService;