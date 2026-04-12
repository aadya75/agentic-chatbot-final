// frontend/src/api/config.js

const isDevelopment = import.meta.env.DEV;
const isProduction = import.meta.env.PROD;

const API_CONFIG = {
  BASE_URL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  API_VERSION: '1.0.0',
  TIMEOUT: 300000,
  MAX_RETRIES: 3,
  RETRY_DELAY: 1000,
  DEBUG: isDevelopment,
};

if (API_CONFIG.DEBUG) {
  console.log('🎯 API Config:', {
    baseURL: API_CONFIG.BASE_URL,
    mode: isDevelopment ? 'development' : 'production',
  });
}

export const ENDPOINTS = {
  // Health
  HEALTH:        '/api/health',
  STATUS:        '/api/status',

  // Auth  (no /api prefix — matches backend)
  SIGNUP:        '/auth/signup',
  LOGIN:         '/auth/login',
  LOGOUT:        '/auth/logout',
  REFRESH:       '/auth/refresh',
  ME:            '/auth/me',

  GOOGLE_CONNECT:    '/auth/google/connect',
  GOOGLE_CALLBACK:   '/auth/google/callback',
  GOOGLE_DISCONNECT: '/auth/google/disconnect',

  GITHUB_CONNECT:    '/auth/github/connect',
  GITHUB_CALLBACK:   '/auth/github/callback',
  GITHUB_DISCONNECT: '/auth/github/disconnect',

  // Chat  (/api prefix — matches backend)
  SEND_MESSAGE:        '/api/message',
  CREATE_THREAD:       '/api/thread',
  GET_THREAD_MESSAGES: (threadId) => `/api/threads/${threadId}/messages`,
  DELETE_THREAD:       (threadId) => `/api/thread/${threadId}`,

  // Knowledge  (/api/knowledge prefix — matches backend)
  KNOWLEDGE_UPLOAD:  '/api/knowledge/upload',
  KNOWLEDGE_STATUS:  (taskId) => `/api/knowledge/status/${taskId}`,
  KNOWLEDGE_LIST:    '/api/knowledge/resources',
  KNOWLEDGE_DELETE:  (paperId) => `/api/knowledge/resources/${paperId}`,
  KNOWLEDGE_STATS:   '/api/knowledge/stats',
  KNOWLEDGE_SEARCH:  '/api/knowledge/search',
  KNOWLEDGE_INFO:    '/api/knowledge/system/info',
};

export const API_STATUS = {
  SUCCESS: 'success',
  ERROR: 'error',
  PARTIAL: 'partial',
};

export const ERROR_MESSAGES = {
  NETWORK_ERROR:    'Network error. Please check your connection.',
  SERVER_ERROR:     'Server error. Please try again later.',
  TIMEOUT_ERROR:    'Request timeout. Please try again.',
  UNAUTHORIZED:     'Authentication required.',
  NOT_FOUND:        'Resource not found.',
  VALIDATION_ERROR: 'Validation failed.',
  DEFAULT:          'Something went wrong. Please try again.',
};

export default API_CONFIG;