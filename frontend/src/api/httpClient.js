// frontend/src/api/httpClient.js
class HttpClient {
  constructor(baseURL) {
    this.baseURL = baseURL;
    console.log('🔧 HttpClient initialized with baseURL:', baseURL);
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    
    console.log(`📤 Request: ${options.method || 'GET'} ${url}`);
    
    const config = {
      ...options,
      headers: {
        ...options.headers,
      },
    };

    if (options.body && options.body instanceof FormData) {
      delete config.headers['Content-Type'];
    } else if (!config.headers['Content-Type']) {
      config.headers['Content-Type'] = 'application/json';
    }

    try {
      const response = await fetch(url, config);
      const contentType = response.headers.get('content-type');
      
      if (contentType && !contentType.includes('application/json')) {
        return response;
      }

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || data.message || `HTTP ${response.status}`);
      }

      console.log(`✅ Response:`, data);
      return data;
      
    } catch (error) {
      console.error(`❌ Error:`, error.message);
      throw error;
    }
  }

  async get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  async post(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'POST',
      body: data instanceof FormData ? data : JSON.stringify(data),
    });
  }

  async put(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'DELETE' });
  }

  async patch(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }
}

const BASE_URL = 'http://localhost:8000/api';

console.log('🌐 Initializing httpClient with BASE_URL:', BASE_URL);

export const httpClient = new HttpClient(BASE_URL);
export default httpClient;