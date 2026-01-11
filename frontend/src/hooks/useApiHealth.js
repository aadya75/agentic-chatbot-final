// frontend/src/hooks/useApiHealth.js

import { useState, useEffect, useCallback, useRef } from 'react';
import { apiService } from '../api/services';

/**
 * Hook for monitoring API health status
 * @param {Object} options - Hook options
 * @param {boolean} options.autoCheck - Whether to auto-check on mount
 * @param {number} options.interval - Auto-check interval in ms (0 to disable)
 * @param {Function} options.onStatusChange - Callback when status changes
 * @param {Function} options.onError - Callback on error
 * @returns {Object} Health status and controls
 */
export function useApiHealth(options = {}) {
  const {
    autoCheck = true,
    interval = 30000, // 30 seconds
    onStatusChange = null,
    onError = null,
  } = options;

  const [status, setStatus] = useState({
    loading: false,
    connected: false,
    data: null,
    error: null,
    lastChecked: null,
    retryCount: 0,
  });

  // Use refs to avoid recreating the checkHealth function
  const isCheckingRef = useRef(false);
  const onStatusChangeRef = useRef(onStatusChange);
  const onErrorRef = useRef(onError);

  // Keep refs updated
  useEffect(() => {
    onStatusChangeRef.current = onStatusChange;
    onErrorRef.current = onError;
  }, [onStatusChange, onError]);

  const checkHealth = useCallback(async (isAutoCheck = false) => {
    // Prevent concurrent checks
    if (isCheckingRef.current) {
      console.log('Health check already in progress, skipping...');
      return;
    }

    isCheckingRef.current = true;

    setStatus(prev => ({ 
      ...prev, 
      loading: true,
      // Only reset error on manual check
      ...(isAutoCheck ? {} : { error: null })
    }));
    
    try {
      const result = await apiService.testConnection();
      
      const newStatus = {
        loading: false,
        connected: result.connected,
        data: result.data || result,
        error: result.error || null,
        lastChecked: new Date().toISOString(),
        retryCount: result.connected ? 0 : status.retryCount + 1,
      };
      
      setStatus(newStatus);
      
      if (onStatusChangeRef.current) {
        onStatusChangeRef.current(newStatus);
      }
      
      isCheckingRef.current = false;
      return newStatus;
      
    } catch (error) {
      const errorStatus = {
        loading: false,
        connected: false,
        data: null,
        error: error.message,
        lastChecked: new Date().toISOString(),
        retryCount: status.retryCount + 1,
      };
      
      setStatus(errorStatus);
      
      if (onErrorRef.current) {
        onErrorRef.current(error, errorStatus);
      }
      
      isCheckingRef.current = false;
      return errorStatus;
    }
  }, [status.retryCount]);

  // Auto-check on mount and interval
  useEffect(() => {
    if (!autoCheck) return;

    let mounted = true;
    let intervalId = null;

    const initialCheck = async () => {
      if (mounted) {
        await checkHealth(true);
      }
    };

    // Run initial check
    initialCheck();

    // Set up interval if specified
    if (interval > 0) {
      intervalId = setInterval(() => {
        if (mounted) {
          checkHealth(true);
        }
      }, interval);
    }

    return () => {
      mounted = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
      isCheckingRef.current = false;
    };
  }, [autoCheck, interval]); // Removed checkHealth from dependencies

  return {
    // State
    ...status,
    
    // Derived state
    isHealthy: status.connected && !status.error,
    isError: !!status.error,
    isLoading: status.loading,
    
    // Format last checked time
    lastCheckedTime: status.lastChecked ? new Date(status.lastChecked).toLocaleTimeString() : null,
    lastCheckedDate: status.lastChecked ? new Date(status.lastChecked).toLocaleDateString() : null,
    
    // Actions
    checkHealth: () => checkHealth(false),
    retry: () => checkHealth(false),
    
    reset: () => setStatus({
      loading: false,
      connected: false,
      data: null,
      error: null,
      lastChecked: null,
      retryCount: 0,
    }),
    
    // Health data helpers
    getUptime: () => status.data?.uptime_seconds || 0,
    getVersion: () => status.data?.version || 'unknown',
    getServerStatus: () => status.data?.mcp_servers || {},
  };
}