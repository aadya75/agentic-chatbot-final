// frontend/src/api/services.js
import { httpClient } from './httpClient';

/**
 * API service methods for interacting with the backend
 */
export const apiService = {
  /**
   * Test backend connection and health
   */
  async testConnection() {
    try {
      const response = await httpClient.get('/health');
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
    return await httpClient.get('/status');
  },

  /**
   * Create a new conversation thread
   */
  async createThread() {
    try {
      const response = await httpClient.post('/thread');
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
   * Get thread information
   */
  async getThread(threadId) {
    return await httpClient.get(`/thread/${threadId}`);
  },

  /**
   * Delete a thread
   */
  async deleteThread(threadId) {
    return await httpClient.delete(`/thread/${threadId}`);
  },

  /**
   * List all threads
   * Note: This endpoint may not exist in your backend yet
   */
  async listThreads() {
    try {
      return await httpClient.get('/threads');
    } catch (error) {
      console.warn('listThreads not implemented in backend');
      return [];
    }
  },

  /**
   * Send a message (uses /api/message endpoint)
   */
  async sendMessage(threadId, message, options = {}) {
    try {
      console.log('📨 Sending message:', { threadId, message });
      
      const response = await httpClient.post('/message', {
        message: message,
        thread_id: threadId,
        user_id: options.userId || null
      });
      
      console.log('📬 Received response:', response);
      
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
   * Stream a message response (Server-Sent Events)
   * Note: This requires backend streaming support
   */
  async streamMessage(threadId, message, onChunk, onComplete, onError) {
    // For now, fall back to regular message since streaming may not be implemented
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

  /**
   * Get all messages from a thread
   */
  async getMessages(threadId) {
    const response = await httpClient.get(`/threads/${threadId}/messages`);
    return response.messages || response;
  },

  /**
   * Clear all messages from a thread
   * Note: This endpoint may not exist in your backend yet
   */
  async clearMessages(threadId) {
    try {
      return await httpClient.delete(`/thread/${threadId}/messages`);
    } catch (error) {
      console.warn('clearMessages not implemented in backend');
      throw error;
    }
  },

  /**
   * Get available tools
   */
  async getTools() {
    return await httpClient.get('/tools');
  }
};

export default apiService;