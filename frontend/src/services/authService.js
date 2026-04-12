// frontend/src/services/authService.js

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const tokenStorage = {
  getAccessToken: () => localStorage.getItem("access_token"),
  getRefreshToken: () => localStorage.getItem("refresh_token"),
  set: (accessToken, refreshToken) => {
    localStorage.setItem("access_token", accessToken);
    if (refreshToken) localStorage.setItem("refresh_token", refreshToken);
  },
  clear: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  },
};

async function authFetch(path, options = {}) {
  const token = tokenStorage.getAccessToken();

  // If no token at all, redirect immediately — don't bother hitting the server
  if (!token) {
    tokenStorage.clear();
    window.location.href = "/login";
    throw new Error("No access token");
  }

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    ...options.headers,
  };

  let resp = await fetch(`${API_BASE}${path}`, { ...options, headers });

  // Token expired — try to refresh once, then retry the original request
  if (resp.status === 401) {
    const refreshed = await authService.refreshSession();
    if (refreshed) {
      headers.Authorization = `Bearer ${tokenStorage.getAccessToken()}`;
      resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
    } else {
      // Refresh failed — session is dead, send to login
      tokenStorage.clear();
      window.location.href = "/login";
      throw new Error("Session expired");
    }
  }

  return resp;
}

export const authService = {
  async signup(email, password) {
    const resp = await fetch(`${API_BASE}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "Signup failed");
    return data;
  },

  async login(email, password) {
    const resp = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "Login failed");
    tokenStorage.set(data.access_token, data.refresh_token);
    return data;
  },

  async logout() {
    try {
      await authFetch("/auth/logout", { method: "POST" });
    } catch {
      // ignore — we're logging out anyway
    } finally {
      tokenStorage.clear();
    }
  },

  async refreshSession() {
    const refreshToken = tokenStorage.getRefreshToken();
    if (!refreshToken) return false;
    try {
      const resp = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!resp.ok) return false;
      const data = await resp.json();
      tokenStorage.set(data.access_token, data.refresh_token);
      return true;
    } catch {
      return false;
    }
  },

  async getMe() {
    const resp = await authFetch("/auth/me");
    if (!resp.ok) throw new Error("Failed to fetch user");
    return resp.json();
  },

  isLoggedIn() {
    return !!tokenStorage.getAccessToken();
  },

  // ── Google OAuth ────────────────────────────────────────────────────────

  async getGoogleConnectUrl() {
    const resp = await authFetch("/auth/google/connect");
    if (!resp.ok) throw new Error("Failed to get Google connect URL");
    return (await resp.json()).url;
  },

  async connectGoogle() {
    const url = await this.getGoogleConnectUrl();
    window.location.href = url;
  },

  async disconnectGoogle() {
    const resp = await authFetch("/auth/google/disconnect", { method: "DELETE" });
    if (!resp.ok) throw new Error("Failed to disconnect Google");
    return resp.json();
  },

  // ── GitHub OAuth ────────────────────────────────────────────────────────

  async getGitHubConnectUrl() {
    const resp = await authFetch("/auth/github/connect");
    if (!resp.ok) throw new Error("Failed to get GitHub connect URL");
    return (await resp.json()).url;
  },

  async connectGitHub() {
    const url = await this.getGitHubConnectUrl();
    window.location.href = url;
  },

  async disconnectGitHub() {
    const resp = await authFetch("/auth/github/disconnect", { method: "DELETE" });
    if (!resp.ok) throw new Error("Failed to disconnect GitHub");
    return resp.json();
  },
};

export default authService;