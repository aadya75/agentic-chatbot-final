// frontend/src/api/config.js - Vite version

// Vite uses import.meta.env
const isDevelopment = import.meta.env.DEV;
const isProduction = import.meta.env.PROD;

// API Configuration for Vite
const API_CONFIG = {
  // Base URL - can be set via .env file
  BASE_URL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  
  // API version
  API_VERSION: '1.0.0',
  
  // Request timeout in milliseconds
  TIMEOUT: 30000,
  
  // Maximum retry attempts for failed requests
  MAX_RETRIES: 3,
  
  // Retry delay in milliseconds
  RETRY_DELAY: 1000,
  
  // Debug mode - enabled in development
  DEBUG: isDevelopment,
};

// Log config in development
if (API_CONFIG.DEBUG) {
  console.log('🎯 Vite API Configuration:', {
    baseURL: API_CONFIG.BASE_URL,
    mode: isDevelopment ? 'development' : 'production',
    env: {
      VITE_API_URL: import.meta.env.VITE_API_URL,
      DEV: isDevelopment,
      PROD: isProduction,
    }
  });
}

// API Endpoints
export const ENDPOINTS = {
  // Health endpoints
  HEALTH: '/api/health',
  HEALTH_READY: '/api/health/ready',
  HEALTH_LIVE: '/api/health/live',
  
  // Chat endpoints
  CHAT: '/api/message',
  CREATE_THREAD: '/api/thread',
  GET_THREAD_MESSAGES: (threadId) => `/api/threads/${threadId}/messages`,
  
  // Tools endpoints
  TOOLS: '/api/tools',
  TOOL_SERVERS: '/api/tools/servers',
  EXECUTE_TOOL: '/api/tools/execute',
  TOOL_INFO: (toolName) => `/api/tools/${toolName}`,
  
  // Documentation
  DOCS: '/docs',
  REDOC: '/redoc',
  OPENAPI: '/openapi.json',
};

// For backward compatibility
export const API_STATUS = {
  SUCCESS: 'success',
  ERROR: 'error',
  PARTIAL: 'partial',
};

export const ERROR_MESSAGES = {
  NETWORK_ERROR: 'Network error. Please check your connection.',
  SERVER_ERROR: 'Server error. Please try again later.',
  TIMEOUT_ERROR: 'Request timeout. Please try again.',
  UNAUTHORIZED: 'Authentication required.',
  NOT_FOUND: 'Resource not found.',
  VALIDATION_ERROR: 'Validation failed.',
  DEFAULT: 'Something went wrong. Please try again.',
};

export default API_CONFIG;