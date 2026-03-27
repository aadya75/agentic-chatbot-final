// frontend/src/Components/UploadDocs.jsx
import React, { useState, useRef, useEffect } from 'react';
import { useDocuments } from '../hooks/useDocuments';
import './UploadDocs.css';

const UploadDocs = ({ onUploadSuccess }) => {
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [selectedFile, setSelectedFile] = useState(null);
    const [uploadError, setUploadError] = useState(null);
    const fileInputRef = useRef(null);
    
    const { uploadDocument, isUploading, uploadProgress } = useDocuments();

    // Reset everything when dialog closes
    useEffect(() => {
        if (!isDialogOpen) {
            resetFileSelection();
        }
    }, [isDialogOpen]);

    const resetFileSelection = () => {
        setSelectedFile(null);
        setUploadError(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    const handleFileSelect = (event) => {
        const file = event.target.files[0];
        setUploadError(null);
        
        if (file) {
            if (!file.name.toLowerCase().endsWith('.pdf')) {
                setUploadError('Only PDF files are supported');
                resetFileSelection();
                return;
            }
            
            const maxSize = 10 * 1024 * 1024;
            if (file.size > maxSize) {
                setUploadError('File size must be less than 10MB');
                resetFileSelection();
                return;
            }
            
            setSelectedFile(file);
        }
    };

    const handleUpload = async () => {
        if (!selectedFile) return;
        
        setUploadError(null);
        
        try {
            const result = await uploadDocument(selectedFile);
            
            // Success - close dialog after delay
            setTimeout(() => {
                resetFileSelection();
                setIsDialogOpen(false);
                if (onUploadSuccess) {
                    onUploadSuccess(result);
                }
            }, 1500);
            
        } catch (err) {
            console.error('Upload failed:', err);
            setUploadError(err.message || 'Upload failed. Please try again.');
            resetFileSelection();  // Reset so user can select new file
        }
    };

    const handleCancel = () => {
        resetFileSelection();
        setIsDialogOpen(false);
    };

    const formatFileSize = (bytes) => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    const getStatusMessage = () => {
        if (!uploadProgress) return '';
        if (uploadProgress.status === 'completed') return '✅ Complete!';
        if (uploadProgress.status === 'failed') return `❌ Failed: ${uploadProgress.message}`;
        if (uploadProgress.status === 'processing') return `🔄 ${uploadProgress.message || 'Processing...'}`;
        return '📤 Uploading...';
    };

    return (
        <>
            <button 
                className="upload-docs-btn"
                onClick={() => setIsDialogOpen(true)}
            >
                <span className="upload-icon">📚</span>
                Upload PDF
            </button>

            {isDialogOpen && (
                <div className="upload-docs-overlay" onClick={handleCancel}>
                    <div className="upload-docs-dialog" onClick={(e) => e.stopPropagation()}>
                        <div className="dialog-header">
                            <h3>Upload PDF to Knowledge Base</h3>
                            <button className="close-btn" onClick={handleCancel}>×</button>
                        </div>
                        
                        <div className="dialog-body">
                            {uploadError && (
                                <div className="error-message">
                                    ❌ {uploadError}
                                </div>
                            )}
                            
                            {!selectedFile ? (
                                <div className="file-select-area">
                                    <label htmlFor="file-upload" className="file-select-label">
                                        <div className="upload-icon-large">📄</div>
                                        <p>Click to select a PDF file</p>
                                        <p className="file-hint">PDF files only, max 10MB</p>
                                    </label>
                                    <input
                                        ref={fileInputRef}
                                        id="file-upload"
                                        type="file"
                                        accept=".pdf"
                                        onChange={handleFileSelect}
                                        style={{ display: 'none' }}
                                    />
                                </div>
                            ) : (
                                <div className="file-preview">
                                    <div className="file-info">
                                        <span className="file-icon">📑</span>
                                        <div className="file-details">
                                            <p className="file-name">{selectedFile.name}</p>
                                            <p className="file-size">{formatFileSize(selectedFile.size)}</p>
                                        </div>
                                        <button 
                                            className="remove-file-btn"
                                            onClick={() => resetFileSelection()}
                                            disabled={isUploading}
                                        >
                                            Remove
                                        </button>
                                    </div>
                                    
                                    {uploadProgress && (
                                        <div className="upload-progress">
                                            <div className="progress-bar">
                                                <div 
                                                    className="progress-fill" 
                                                    style={{ width: `${uploadProgress.progress}%` }}
                                                ></div>
                                            </div>
                                            <p className="progress-text">{getStatusMessage()}</p>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                        
                        <div className="dialog-footer">
                            <button 
                                className="cancel-btn" 
                                onClick={handleCancel}
                                disabled={isUploading}
                            >
                                Cancel
                            </button>
                            {selectedFile && (
                                <button 
                                    className="upload-btn" 
                                    onClick={handleUpload}
                                    disabled={isUploading}
                                >
                                    {isUploading ? 'Processing...' : 'Upload & Index'}
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};

export default UploadDocs;