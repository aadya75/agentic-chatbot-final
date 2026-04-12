// frontend/src/api/services.js
import { httpClient } from './httpClient';
import API_CONFIG, { ENDPOINTS } from './config.js';

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
    } else {
      localStorage.removeItem('access_token');
      sessionStorage.removeItem('access_token');
      httpClient.setAuthToken(null);
    }
  },

  // =========================================================================
  // Health & Status
  // =========================================================================

  async testConnection() {
    try {
      const response = await httpClient.get(ENDPOINTS.HEALTH);
      return { connected: true, data: response, error: null };
    } catch (error) {
      return { connected: false, data: null, error: error.message || 'Failed to connect' };
    }
  },

  async getStatus() {
    return await httpClient.get(ENDPOINTS.STATUS);
  },

  // =========================================================================
  // Authentication Methods
  // =========================================================================

  async signup(userData) {
    const response = await httpClient.post(ENDPOINTS.SIGNUP, {
      email: userData.email,
      password: userData.password,
      full_name: userData.full_name,
    });
    if (response.access_token) {
      this.setAuthToken(response.access_token, userData.remember || false);
    }
    return { success: true, data: response };
  },

  async login(credentials) {
    const response = await httpClient.post(ENDPOINTS.LOGIN, {
      email: credentials.email,
      password: credentials.password,
    });
    if (response.access_token) {
      this.setAuthToken(response.access_token, credentials.remember || false);
    }
    return { success: true, data: response };
  },

  async logout() {
    try {
      await httpClient.post(ENDPOINTS.LOGOUT);
    } finally {
      this.setAuthToken(null);
    }
    return { success: true };
  },

  async refreshToken() {
    const response = await httpClient.post(ENDPOINTS.REFRESH);
    if (response.access_token) {
      this.setAuthToken(response.access_token, true);
    }
    return response;
  },

  async getCurrentUser() {
    const token = this.getAuthToken();
    if (!token) throw new Error('No auth token');
    httpClient.setAuthToken(token);
    return await httpClient.get(ENDPOINTS.ME);
  },

  async isAuthenticated() {
    try {
      await this.getCurrentUser();
      return true;
    } catch {
      return false;
    }
  },

  async initializeAuth() {
    const token = this.getAuthToken();
    if (token) {
      httpClient.setAuthToken(token);
      try {
        const user = await this.getCurrentUser();
        return { authenticated: true, user };
      } catch {
        this.setAuthToken(null);
        return { authenticated: false, user: null };
      }
    }
    return { authenticated: false, user: null };
  },

  // =========================================================================
  // OAuth Methods — FIXED
  // Step 1: fetch the OAuth URL from backend (with Bearer token)
  // Step 2: redirect browser to the OAuth provider (GitHub/Google)
  // =========================================================================

  async initiateGoogleLogin() {
    const token = this.getAuthToken();
    if (!token) throw new Error('Not authenticated');

    // Fetch the Google OAuth URL from our backend (requires auth)
    const response = await fetch(
      `${API_CONFIG.BASE_URL}${ENDPOINTS.GOOGLE_CONNECT}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to get Google connect URL');
    }

    const { url } = await response.json();
    // Now redirect browser to Google (no auth header needed — it's Google's page)
    window.location.href = url;
  },

  async initiateGithubLogin() {
    const token = this.getAuthToken();
    if (!token) throw new Error('Not authenticated');

    // Fetch the GitHub OAuth URL from our backend (requires auth)
    const response = await fetch(
      `${API_CONFIG.BASE_URL}${ENDPOINTS.GITHUB_CONNECT}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to get GitHub connect URL');
    }

    const { url } = await response.json();
    // Now redirect browser to GitHub (no auth header needed — it's GitHub's page)
    window.location.href = url;
  },

  async disconnectGithub() {
    const token = this.getAuthToken();
    if (!token) throw new Error('Not authenticated');

    const response = await fetch(
      `${API_CONFIG.BASE_URL}${ENDPOINTS.GITHUB_DISCONNECT}`,
      {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      }
    );

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to disconnect GitHub');
    }

    return response.json();
  },

  async disconnectGoogle() {
    const token = this.getAuthToken();
    if (!token) throw new Error('Not authenticated');

    const response = await fetch(
      `${API_CONFIG.BASE_URL}${ENDPOINTS.GOOGLE_DISCONNECT}`,
      {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      }
    );

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to disconnect Google');
    }

    return response.json();
  },

  async handleOAuthCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    const error = urlParams.get('error');

    if (error) return { success: false, error };

    if (token) {
      this.setAuthToken(token, true);
      window.history.replaceState({}, document.title, window.location.pathname);
      return { success: true, token };
    }

    return { success: false, error: 'No token received' };
  },

  // =========================================================================
  // Thread / Chat
  // =========================================================================

  async createThread() {
    const token = this.getAuthToken();
    if (!token) throw new Error('Not authenticated');
    httpClient.setAuthToken(token);
    const response = await httpClient.post(ENDPOINTS.CREATE_THREAD);
    return { success: true, threadId: response.thread_id, data: response };
  },

  async deleteThread(threadId) {
    const token = this.getAuthToken();
    if (!token) throw new Error('Not authenticated');
    httpClient.setAuthToken(token);
    return await httpClient.delete(ENDPOINTS.DELETE_THREAD(threadId));
  },

  async listThreads() {
    console.warn('listThreads endpoint not implemented in backend');
    return [];
  },

  async sendMessage(threadId, message, options = {}) {
    const token = this.getAuthToken();
    if (!token) throw new Error('Not authenticated');
    httpClient.setAuthToken(token);
    const response = await httpClient.post(ENDPOINTS.SEND_MESSAGE, {
      message,
      thread_id: threadId,
      user_id: options.userId || null,
    });
    return { success: true, data: response };
  },

  async streamMessage(threadId, message, onChunk, onComplete, onError) {
    try {
      const result = await this.sendMessage(threadId, message);
      if (result.success) {
        onChunk?.({ type: 'token', content: result.data.message });
        onComplete?.();
      }
    } catch (error) {
      onError?.(error);
    }
  },

  async getMessages(threadId) {
    const token = this.getAuthToken();
    if (!token) throw new Error('Not authenticated');
    httpClient.setAuthToken(token);
    const response = await httpClient.get(ENDPOINTS.GET_THREAD_MESSAGES(threadId));
    return response.messages || response;
  },

  // =========================================================================
  // Knowledge Base
  // =========================================================================

  async uploadDocument(file) {
    const token = this.getAuthToken();
    if (!token) throw new Error('Not authenticated');
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${httpClient.baseURL}${ENDPOINTS.KNOWLEDGE_UPLOAD}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Upload failed');
    }
    return response.json();
  },

  async uploadMultipleDocuments(files) {
    const results = { success: [], failed: [] };
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

  async checkUploadStatus(taskId) {
    const token = this.getAuthToken();
    if (!token) throw new Error('Not authenticated');
    httpClient.setAuthToken(token);
    return await httpClient.get(ENDPOINTS.KNOWLEDGE_STATUS(taskId));
  },

  async pollUploadStatus(taskId, interval = 2000, maxAttempts = 60) {
    let attempts = 0;
    while (attempts < maxAttempts) {
      try {
        const status = await this.checkUploadStatus(taskId);
        if (status.status === 'completed') return { success: true, data: status };
        if (status.status === 'failed') return { success: false, error: status.error || 'Processing failed' };
        await new Promise(resolve => setTimeout(resolve, interval));
        attempts++;
      } catch {
        await new Promise(resolve => setTimeout(resolve, interval));
        attempts++;
      }
    }
    return { success: false, error: 'Processing timeout' };
  },

  async listResources() {
    const token = this.getAuthToken();
    if (!token) throw new Error('Not authenticated');
    httpClient.setAuthToken(token);
    return await httpClient.get(ENDPOINTS.KNOWLEDGE_LIST);
  },

  async deleteResource(paperId) {
    const token = this.getAuthToken();
    if (!token) throw new Error('Not authenticated');
    httpClient.setAuthToken(token);
    return await httpClient.delete(ENDPOINTS.KNOWLEDGE_DELETE(paperId));
  },

  async searchDocuments(query, topK = 5, includeCitations = false) {
    const token = this.getAuthToken();
    if (!token) throw new Error('Not authenticated');
    httpClient.setAuthToken(token);
    return await httpClient.post(ENDPOINTS.KNOWLEDGE_SEARCH, {
      query,
      top_k: topK,
      include_citations: includeCitations,
    });
  },

  async getKnowledgeStats() {
    const token = this.getAuthToken();
    if (!token) throw new Error('Not authenticated');
    httpClient.setAuthToken(token);
    return await httpClient.get(ENDPOINTS.KNOWLEDGE_STATS);
  },

  async getKnowledgeSystemInfo() {
    return await httpClient.get(ENDPOINTS.KNOWLEDGE_INFO);
  },

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
        ...resource,
      }));
    } catch {
      return [];
    }
  },

  async bulkDeleteResources(paperIds) {
    const results = { success: [], failed: [] };
    const settled = await Promise.allSettled(
      paperIds.map(async (paperId) => {
        await this.deleteResource(paperId);
        return paperId;
      })
    );
    for (const result of settled) {
      if (result.status === 'fulfilled') {
        results.success.push(result.value);
      } else {
        results.failed.push({ paperId: result.reason?.paperId, error: result.reason?.message });
      }
    }
    return results;
  },

  validateFile(file) {
    const maxSize = 10 * 1024 * 1024;
    if (file.type !== 'application/pdf') return { valid: false, error: 'Only PDF files are allowed' };
    if (file.size > maxSize) return { valid: false, error: 'File size must be less than 10MB' };
    return { valid: true, error: null };
  },
};

if (typeof window !== 'undefined') {
  window.addEventListener('auth:unauthorized', () => {
    apiService.setAuthToken(null);
    window.dispatchEvent(new CustomEvent('app:logout', { detail: { reason: 'unauthorized' } }));
  });
}

export default apiService;