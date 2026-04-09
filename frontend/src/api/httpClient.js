// frontend/src/api/httpClient.js
import API_CONFIG, { ENDPOINTS } from './config.js';

class HttpClient {
  constructor(baseURL, timeout = API_CONFIG.TIMEOUT) {
    this.baseURL = baseURL;
    this.timeout = timeout;
    this.maxRetries = API_CONFIG.MAX_RETRIES;
    this.retryDelay = API_CONFIG.RETRY_DELAY;
    this.authToken = null;
    
    // Try to load token from storage on initialization
    this.loadTokenFromStorage();
    
    if (API_CONFIG.DEBUG) {
      console.log('🔧 HttpClient initialized with baseURL:', baseURL);
    }
  }

  // Load token from storage on initialization
  loadTokenFromStorage() {
    const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
    if (token) {
      this.authToken = token;
      if (API_CONFIG.DEBUG) {
        console.log('🔑 Auth token loaded from storage');
      }
    }
  }

  async request(endpoint, options = {}, retryCount = 0) {
    // Handle both full URLs and relative paths
    const url = endpoint.startsWith('http') 
      ? endpoint 
      : `${this.baseURL}${endpoint}`;
    
    if (API_CONFIG.DEBUG) {
      console.log(`📤 Request: ${options.method || 'GET'} ${url}`);
    }

    // Prepare headers
    const headers = {
      ...options.headers,
    };

    // Auto-include auth token if available
    if (this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
      if (API_CONFIG.DEBUG) {
        console.log('🔑 Auth token included in request');
      }
    }

    // Handle FormData properly (don't set Content-Type, let browser set it with boundary)
    if (options.body && options.body instanceof FormData) {
      delete headers['Content-Type'];
    } 
    // Set default Content-Type for JSON bodies
    else if (!headers['Content-Type'] && 
             !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    const config = {
      ...options,
      headers,
    };

    // Add timeout handling
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);
    config.signal = controller.signal;

    try {
      const response = await fetch(url, config);
      clearTimeout(timeoutId);
      
      const contentType = response.headers.get('content-type');
      
      // Handle non-JSON responses (like file downloads)
      if (contentType && !contentType.includes('application/json')) {
        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(errorText || `HTTP ${response.status}`);
        }
        return response;
      }

      // Parse JSON response
      const data = await response.json();
      
      if (!response.ok) {
        // Handle specific HTTP status codes
        if (response.status === 401) {
          // Clear invalid token
          this.authToken = null;
          this.clearTokenFromStorage();
          
          // Emit auth error event for global handling
          window.dispatchEvent(new CustomEvent('auth:unauthorized', { 
            detail: { message: data.detail || data.message || 'Authentication required' }
          }));
        }
        
        throw new Error(data.detail || data.message || `HTTP ${response.status}`);
      }

      if (API_CONFIG.DEBUG) {
        console.log(`✅ Response:`, data);
      }
      return data;
      
    } catch (error) {
      clearTimeout(timeoutId);
      
      // Handle abort errors (timeout)
      if (error.name === 'AbortError') {
        const timeoutError = new Error(`Request timeout after ${this.timeout}ms`);
        if (API_CONFIG.DEBUG) {
          console.error(`⏰ Timeout:`, timeoutError.message);
        }
        throw timeoutError;
      }
      
      // Handle network errors with retry logic
      if (error.message.includes('Failed to fetch') || 
          error.message.includes('NetworkError') ||
          error.message === 'Network error') {
        
        if (retryCount < this.maxRetries) {
          if (API_CONFIG.DEBUG) {
            console.warn(`🔄 Retry ${retryCount + 1}/${this.maxRetries} for ${url}`);
          }
          await new Promise(resolve => setTimeout(resolve, this.retryDelay * (retryCount + 1)));
          return this.request(endpoint, options, retryCount + 1);
        }
        
        const networkError = new Error(API_CONFIG.ERROR_MESSAGES?.NETWORK_ERROR || 'Network error. Please check your connection.');
        if (API_CONFIG.DEBUG) {
          console.error(`🌐 Network Error:`, error.message);
        }
        throw networkError;
      }
      
      if (API_CONFIG.DEBUG) {
        console.error(`❌ Error:`, error.message);
      }
      throw error;
    }
  }

  async get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  async post(endpoint, data, options = {}) {
    const body = data instanceof FormData ? data : JSON.stringify(data);
    return this.request(endpoint, {
      ...options,
      method: 'POST',
      body,
    });
  }

  async put(endpoint, data, options = {}) {
    const body = data instanceof FormData ? data : JSON.stringify(data);
    return this.request(endpoint, {
      ...options,
      method: 'PUT',
      body,
    });
  }

  async delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'DELETE' });
  }

  async patch(endpoint, data, options = {}) {
    const body = data instanceof FormData ? data : JSON.stringify(data);
    return this.request(endpoint, {
      ...options,
      method: 'PATCH',
      body,
    });
  }

  // Helper method to set auth token
  setAuthToken(token) {
    if (token) {
      this.authToken = token;
      // Also store in memory for persistence
      if (API_CONFIG.DEBUG) {
        console.log('🔑 Auth token set');
      }
    } else {
      this.authToken = null;
      if (API_CONFIG.DEBUG) {
        console.log('🔑 Auth token cleared');
      }
    }
  }

  // Store token in localStorage/sessionStorage
  storeToken(token, remember = false) {
    if (token) {
      if (remember) {
        localStorage.setItem('access_token', token);
      } else {
        sessionStorage.setItem('access_token', token);
      }
      this.setAuthToken(token);
    }
  }

  // Clear token from storage
  clearTokenFromStorage() {
    localStorage.removeItem('access_token');
    sessionStorage.removeItem('access_token');
    this.setAuthToken(null);
  }

  // Get headers with auth token if present
  getAuthHeaders() {
    const headers = {};
    if (this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
    }
    return headers;
  }
}

// Construct the full base URL (without trailing slash)
const BASE_URL = API_CONFIG.BASE_URL.endsWith('/') 
  ? API_CONFIG.BASE_URL.slice(0, -1) 
  : API_CONFIG.BASE_URL;

if (API_CONFIG.DEBUG) {
  console.log('🌐 Initializing httpClient with BASE_URL:', BASE_URL);
}

export const httpClient = new HttpClient(BASE_URL);
export default httpClient;