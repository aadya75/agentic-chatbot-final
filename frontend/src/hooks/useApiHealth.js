// frontend/src/hooks/useApiHealth.js
import { useState, useEffect, useCallback, useRef } from 'react';
import { apiService } from '../api/services';

export function useApiHealth(options = {}) {
  const {
    autoCheck = true,
    interval = 30000,
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

  const isCheckingRef = useRef(false);
  const onStatusChangeRef = useRef(onStatusChange);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onStatusChangeRef.current = onStatusChange;
    onErrorRef.current = onError;
  }, [onStatusChange, onError]);

  const checkHealth = useCallback(async (isAutoCheck = false) => {
    if (isCheckingRef.current) {
      console.log('Health check already in progress, skipping...');
      return;
    }

    isCheckingRef.current = true;

    setStatus(prev => ({ 
      ...prev, 
      loading: true,
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

  useEffect(() => {
    if (!autoCheck) return;

    let mounted = true;
    let intervalId = null;

    const initialCheck = async () => {
      if (mounted) {
        await checkHealth(true);
      }
    };

    initialCheck();

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
  }, [autoCheck, interval, checkHealth]);

  return {
    ...status,
    isHealthy: status.connected && !status.error,
    isError: !!status.error,
    isLoading: status.loading,
    lastCheckedTime: status.lastChecked ? new Date(status.lastChecked).toLocaleTimeString() : null,
    lastCheckedDate: status.lastChecked ? new Date(status.lastChecked).toLocaleDateString() : null,
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
    getUptime: () => status.data?.uptime_seconds || 0,
    getVersion: () => status.data?.version || 'unknown',
    getServerStatus: () => status.data?.mcp_servers || {},
  };
}