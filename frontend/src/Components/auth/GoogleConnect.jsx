// frontend/src/components/Auth/GoogleConnect.jsx
//
// Drop this on a /settings page or anywhere in the UI.
// Shows Google connection status and connect/disconnect button.
// Also handles the redirect back from Google (?google=connected)

import { useEffect } from "react";
import { useAuth } from "../../context/AuthContext";

export default function GoogleConnect() {
  const { isGoogleConnected, googleEmail, connectGoogle, disconnectGoogle, refreshUser } = useAuth();

  // After Google OAuth callback, the URL has ?google=connected or ?google=error
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const googleParam = params.get("google");
    if (googleParam === "connected") {
      refreshUser();
      // Clean up URL
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [refreshUser]);

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <GoogleIcon />
        <span style={styles.title}>Google Workspace</span>
      </div>

      {isGoogleConnected ? (
        <>
          <p style={styles.status}>
            <span style={styles.dot} /> Connected as <strong>{googleEmail}</strong>
          </p>
          <p style={styles.hint}>
            Gmail and Calendar are available in your AI assistant.
          </p>
          <button onClick={disconnectGoogle} style={styles.disconnectBtn}>
            Disconnect
          </button>
        </>
      ) : (
        <>
          <p style={styles.hint}>
            Connect your Google account to let the assistant access Gmail and Calendar.
          </p>
          <button onClick={connectGoogle} style={styles.connectBtn}>
            Connect Google account
          </button>
        </>
      )}
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  );
}

const styles = {
  card: {
    border: "1px solid #d3d1c7",
    borderRadius: 12,
    padding: "20px 24px",
    maxWidth: 420,
  },
  header: { display: "flex", alignItems: "center", gap: 10, marginBottom: 12 },
  title: { fontSize: 15, fontWeight: 500, color: "#1a1a18" },
  status: { fontSize: 14, color: "#1a1a18", marginBottom: 6 },
  dot: {
    display: "inline-block",
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: "#639922",
    marginRight: 6,
  },
  hint: { fontSize: 13, color: "#5f5e5a", marginBottom: 16, lineHeight: 1.5 },
  connectBtn: {
    padding: "9px 16px",
    fontSize: 14,
    fontWeight: 500,
    background: "#fff",
    border: "1px solid #d3d1c7",
    borderRadius: 8,
    cursor: "pointer",
    color: "#1a1a18",
  },
  disconnectBtn: {
    padding: "9px 16px",
    fontSize: 14,
    background: "none",
    border: "1px solid #d3d1c7",
    borderRadius: 8,
    cursor: "pointer",
    color: "#A32D2D",
  },
};
