// frontend/src/Components/auth/ProfilePage.jsx

import { useEffect } from "react";
import { useAuth } from "../../context/AuthContext";
import GoogleConnect from "./GoogleConnect";
import GitHubConnect from "./GithubConnect";
import GlobalMemory from "./GlobalMemory";
import "./ProfilePage.css";

export default function ProfilePage({ onBack }) {
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("google") || params.get("github")) {
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
              {user?.email?.[0]?.toUpperCase() || "?"}
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

        {/* Personal context / global memory */}
        <section className="profile-section">
          <h3 className="profile-section-title">Assistant memory</h3>
          <p className="profile-section-desc">
            Anything you write here is sent with every message — your role,
            preferences, or anything the assistant should always know about you.
          </p>
          <GlobalMemory />
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