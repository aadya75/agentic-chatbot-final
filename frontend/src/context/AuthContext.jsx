// frontend/src/context/AuthContext.jsx  (updated — adds GitHub)
//
// Added: isGitHubConnected, githubUsername, connectGitHub, disconnectGitHub

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import authService, { tokenStorage } from "../services/authService";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    if (!tokenStorage.getAccessToken()) {
      setLoading(false);
      return;
    }
    try {
      const me = await authService.getMe();
      setUser(me);
    } catch {
      tokenStorage.clear();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadUser(); }, [loadUser]);

  const login = async (email, password) => {
    const data = await authService.login(email, password);
    const me = await authService.getMe();
    setUser(me);
    return data;
  };

  const signup = async (email, password) => authService.signup(email, password);

  const logout = async () => {
    await authService.logout();
    setUser(null);
  };

  const refreshUser = useCallback(async () => {
    try {
      const me = await authService.getMe();
      setUser(me);
    } catch { /* ignore */ }
  }, []);

  // ── Google ─────────────────────────────────────────────────────────────
  const connectGoogle = async () => authService.connectGoogle();

  const disconnectGoogle = async () => {
    await authService.disconnectGoogle();
    await refreshUser();
  };

  // ── GitHub ─────────────────────────────────────────────────────────────
  const connectGitHub = async () => authService.connectGitHub();

  const disconnectGitHub = async () => {
    await authService.disconnectGitHub();
    await refreshUser();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: !!user,

        // Google
        isGoogleConnected: user?.google?.connected ?? false,
        googleEmail: user?.google?.email ?? null,
        connectGoogle,
        disconnectGoogle,

        // GitHub
        isGitHubConnected: user?.github?.connected ?? false,
        githubUsername: user?.github?.username ?? null,
        connectGitHub,
        disconnectGitHub,

        login,
        signup,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
