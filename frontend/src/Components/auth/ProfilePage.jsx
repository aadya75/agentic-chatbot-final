// frontend/src/Components/auth/ProfilePage.jsx
//
// Full-page profile + settings view.
// Opened when user clicks the avatar button in the header.
// Contains: account info, Google connect, GitHub connect, logout.

import { useEffect } from "react";
import { useAuth } from "../../context/AuthContext";
import GoogleConnect from "./GoogleConnect";
import GitHubConnect from "./GithubConnect";
import "./ProfilePage.css";

export default function ProfilePage({ onBack }) {
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    // AppGate will automatically show LoginPage once isAuthenticated is false
  };

  // Handle OAuth redirects back to this page (?google=connected, ?github=connected)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("google") || params.get("github")) {
      // Clean URL without causing a reload
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  return (
    <div className="profile-page">
      {/* Header bar */}
      <div className="profile-header">
        <button className="profile-back-btn" onClick={onBack}>
          ← Back to chat
        </button>
        <h2 className="profile-header-title">Settings</h2>
      </div>

      <div className="profile-content">
        {/* Account section */}
        <section className="profile-section">
          <h3 className="profile-section-title">Account</h3>
          <div className="profile-account-card">
            <div className="profile-avatar-large">
              {user?.email?.[0]?.toUpperCase() || '?'}
            </div>
            <div className="profile-account-info">
              <p className="profile-email">{user?.email}</p>
              <p className="profile-user-id">ID: {user?.id}</p>
            </div>
          </div>
          <button className="logout-btn" onClick={handleLogout}>
            Sign out
          </button>
        </section>

        {/* Integrations section */}
        <section className="profile-section">
          <h3 className="profile-section-title">Integrations</h3>
          <p className="profile-section-desc">
            Connect external accounts so the AI assistant can act on your behalf.
          </p>
          <div className="integrations-grid">
            <GoogleConnect />
            <GitHubConnect />
          </div>
        </section>
      </div>
    </div>
  );
}
