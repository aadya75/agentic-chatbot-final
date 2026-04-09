// frontend/src/pages/OAuthCallback.jsx
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiService from '../api/services';

export default function OAuthCallback() {
  const navigate = useNavigate();

  useEffect(() => {
    const handleCallback = async () => {
      const result = await apiService.handleOAuthCallback();
      
      if (result.success) {
        // Redirect to dashboard or settings page
        navigate('/settings?connected=true');
      } else {
        navigate('/settings?error=oauth_failed');
      }
    };

    handleCallback();
  }, [navigate]);

  return (
    <div style={{ textAlign: 'center', padding: '50px' }}>
      <h2>Completing authentication...</h2>
      <p>Please wait while we connect your account.</p>
    </div>
  );
}