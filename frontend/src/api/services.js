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
  },

  // =========================================================================
  // Knowledge Base / Document Management (Supabase-powered)
  // =========================================================================

  /**
   * Upload a PDF document to the knowledge base
   * @param {File} file - The PDF file to upload
   * @returns {Promise<Object>} - Returns { task_id, paper_id, filename, message }
   */
  async uploadDocument(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    const url = `${httpClient.baseURL}/knowledge/upload`;
    
    const response = await fetch(url, {
      method: 'POST',
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
   * Check the processing status of an uploaded document
   * @param {string} taskId - The task ID returned from uploadDocument
   * @returns {Promise<Object>} - Returns status info including progress, status, etc.
   */
  async checkUploadStatus(taskId) {
    return await httpClient.get(`/knowledge/status/${taskId}`);
  },

  /**
   * List all resources/documents in the knowledge base for the current user
   * @returns {Promise<Object>} - Returns { resources: [], total: number, user_id: string }
   */
  async listResources() {
    return await httpClient.get('/knowledge/resources');
  },

  /**
   * Delete a resource/document from the knowledge base
   * @param {string} paperId - The paper ID to delete
   * @returns {Promise<Object>} - Returns { success: true, paper_id: string, message: string }
   */
  async deleteResource(paperId) {
    return await httpClient.delete(`/knowledge/resources/${paperId}`);
  },

  /**
   * Search the knowledge base for relevant documents
   * @param {string} query - The search query
   * @param {number} topK - Number of results to return (default: 5)
   * @param {boolean} includeCitations - Whether to include citation information (default: false)
   * @returns {Promise<Object>} - Returns search results with chunks and citations
   */
  async searchDocuments(query, topK = 5, includeCitations = false) {
    return await httpClient.post('/knowledge/search', {
      query: query,
      top_k: topK,
      include_citations: includeCitations
    });
  },

  /**
   * Get knowledge base statistics for the current user
   * @returns {Promise<Object>} - Returns stats about documents, chunks, embeddings, etc.
   */
  async getKnowledgeStats() {
    return await httpClient.get('/knowledge/stats');
  },

  /**
   * Get system information about the knowledge base configuration
   * @returns {Promise<Object>} - Returns system config like supabase status, embedding dim, etc.
   */
  async getKnowledgeSystemInfo() {
    return await httpClient.get('/knowledge/system/info');
  },

  // =========================================================================
  // Optional: Helper methods for document management
  // =========================================================================

  /**
   * Get a formatted list of resources with metadata
   * @returns {Promise<Array>} - Returns formatted resources array
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
        ...resource
      }));
    } catch (error) {
      console.error('Failed to get formatted resources:', error);
      return [];
    }
  },

  /**
   * Bulk delete multiple resources
   * @param {Array<string>} paperIds - Array of paper IDs to delete
   * @returns {Promise<Object>} - Returns results of bulk delete operation
   */
  async bulkDeleteResources(paperIds) {
    const results = {
      success: [],
      failed: []
    };
    
    for (const paperId of paperIds) {
      try {
        await this.deleteResource(paperId);
        results.success.push(paperId);
      } catch (error) {
        results.failed.push({ paperId, error: error.message });
      }
    }
    
    return results;
  },

  /**
   * Enhanced search with additional metadata
   * @param {string} query - The search query
   * @param {Object} options - Search options
   * @returns {Promise<Object>} - Returns enhanced search results
   */
  async enhancedSearch(query, options = {}) {
    const { topK = 5, includeCitations = true, minRelevanceScore = 0 } = options;
    
    const result = await this.searchDocuments(query, topK, includeCitations);
    
    // Filter by relevance score if specified
    if (minRelevanceScore > 0 && result.chunks) {
      result.chunks = result.chunks.filter(
        chunk => (chunk.relevance_score || 0) >= minRelevanceScore
      );
      result.num_results = result.chunks.length;
    }
    
    return result;
  }
};

export default apiService;