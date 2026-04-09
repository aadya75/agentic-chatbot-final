// frontend/src/Components/auth/GitHubConnect.jsx

import { useEffect } from "react";
import { useAuth } from "../../context/AuthContext";

export default function GitHubConnect() {
  const {
    isGitHubConnected,
    githubUsername,
    connectGitHub,
    disconnectGitHub,
    refreshUser,
  } = useAuth();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("github") === "connected") {
      refreshUser();
    }
  }, [refreshUser]);

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <GitHubIcon />
        <span style={styles.title}>GitHub</span>
        <span style={isGitHubConnected ? styles.badgeOn : styles.badgeOff}>
          {isGitHubConnected ? "Connected" : "Not connected"}
        </span>
      </div>

      <p style={styles.hint}>
        {isGitHubConnected
          ? `Repos, PRs and files are available. Connected as @${githubUsername}.`
          : "Connect your GitHub account to let the assistant manage repositories and pull requests."}
      </p>

      {isGitHubConnected ? (
        <button onClick={disconnectGitHub} style={styles.disconnectBtn}>
          Disconnect
        </button>
      ) : (
        <button onClick={connectGitHub} style={styles.connectBtn}>
          Connect GitHub account
        </button>
      )}
    </div>
  );
}

function GitHubIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" color="#1a1a18">
      <path d="M12 2C6.477 2 2 6.477 2 12c0 4.418 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.342-3.369-1.342-.454-1.155-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.202 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z"/>
    </svg>
  );
}

const styles = {
  card: {
    background: "#fff",
    border: "1px solid #e8e6de",
    borderRadius: 12,
    padding: "18px 20px",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginBottom: 10,
  },
  title: { fontSize: 15, fontWeight: 500, color: "#1a1a18", flex: 1 },
  badgeOn: {
    fontSize: 12,
    background: "#EAF3DE",
    color: "#3B6D11",
    borderRadius: 20,
    padding: "2px 10px",
  },
  badgeOff: {
    fontSize: 12,
    background: "#f1efe8",
    color: "#888780",
    borderRadius: 20,
    padding: "2px 10px",
  },
  hint: { fontSize: 13, color: "#5f5e5a", marginBottom: 14, lineHeight: 1.5 },
  connectBtn: {
    padding: "8px 16px",
    fontSize: 14,
    fontWeight: 500,
    background: "#1a1a18",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    cursor: "pointer",
  },
  disconnectBtn: {
    padding: "8px 16px",
    fontSize: 14,
    background: "none",
    border: "1px solid #d3d1c7",
    borderRadius: 8,
    cursor: "pointer",
    color: "#A32D2D",
  },
};
