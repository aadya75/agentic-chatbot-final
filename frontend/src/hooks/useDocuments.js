// frontend/src/hooks/useDocuments.js
import { useState, useCallback, useEffect } from 'react';
import { apiService } from '../api/services';

export function useDocuments() {
    const [documents, setDocuments] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState(null);
    const [uploadProgress, setUploadProgress] = useState(null);

    const loadDocuments = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        
        try {
            const result = await apiService.listResources();
            setDocuments(result.resources || []);
            return result;
        } catch (err) {
            console.error('Failed to load documents:', err);
            setError(err.message);
            throw err;
        } finally {
            setIsLoading(false);
        }
    }, []);

    const uploadDocument = useCallback(async (file) => {
        setIsUploading(true);
        setError(null);
        setUploadProgress({ status: 'uploading', progress: 0 });
        
        try {
            const uploadResult = await apiService.uploadDocument(file);
            
            setUploadProgress({ 
                status: 'processing', 
                progress: 20,
                taskId: uploadResult.task_id,
                message: 'Document uploaded, processing...'
            });
            
            if (uploadResult.task_id) {
                const pollInterval = setInterval(async () => {
                    try {
                        const status = await apiService.checkUploadStatus(uploadResult.task_id);
                        
                        setUploadProgress({
                            status: status.status,
                            progress: status.progress,
                            taskId: uploadResult.task_id,
                            message: status.message,
                            chunksCreated: status.chunks_created
                        });
                        
                        if (status.status === 'completed' || status.status === 'failed') {
                            clearInterval(pollInterval);
                            
                            if (status.status === 'completed') {
                                await loadDocuments();
                                setIsUploading(false);
                                setTimeout(() => setUploadProgress(null), 3000);
                            } else {
                                throw new Error(status.error || 'Processing failed');
                            }
                        }
                    } catch (pollError) {
                        clearInterval(pollInterval);
                        throw pollError;
                    }
                }, 2000);
                
                return () => clearInterval(pollInterval);
            }
            
            await loadDocuments();
            setIsUploading(false);
            setTimeout(() => setUploadProgress(null), 3000);
            
            return uploadResult;
            
        } catch (err) {
            console.error('Upload failed:', err);
            setError(err.message);
            setIsUploading(false);
            setUploadProgress(null);
            throw err;
        }
    }, [loadDocuments]);

    const deleteDocument = useCallback(async (paperId) => {
        setIsLoading(true);
        setError(null);
        
        try {
            await apiService.deleteResource(paperId);
            setDocuments(prev => prev.filter(doc => doc.paper_id !== paperId));
            return true;
        } catch (err) {
            console.error('Delete failed:', err);
            setError(err.message);
            throw err;
        } finally {
            setIsLoading(false);
        }
    }, []);

    const searchDocuments = useCallback(async (query, topK = 5) => {
        setIsLoading(true);
        setError(null);
        
        try {
            const result = await apiService.searchDocuments(query, topK, true);
            return result;
        } catch (err) {
            console.error('Search failed:', err);
            setError(err.message);
            throw err;
        } finally {
            setIsLoading(false);
        }
    }, []);

    const loadStats = useCallback(async () => {
        try {
            return await apiService.getKnowledgeStats();
        } catch (err) {
            console.error('Failed to load stats:', err);
            setError(err.message);
        }
    }, []);

    useEffect(() => {
        loadDocuments();
    }, [loadDocuments]);

    return {
        documents,
        isLoading,
        isUploading,
        error,
        uploadProgress,
        loadDocuments,
        uploadDocument,
        deleteDocument,
        searchDocuments,
        loadStats,
        hasDocuments: documents.length > 0,
        totalDocuments: documents.length
    };
}