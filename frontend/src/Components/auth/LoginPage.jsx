// frontend/src/components/Auth/LoginPage.jsx
//
// Login + Signup form. Drop this on your /login route.
// After login, redirects to "/" (or wherever you configure).

import { useState } from "react";
import { useAuth } from "../../context/AuthContext";

export default function LoginPage() {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState("login");       // "login" | "signup"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setMessage("");
    setLoading(true);

    try {
      if (mode === "login") {
        await login(email, password);
        window.location.href = "/";
      } else {
        await signup(email, password);
        setMessage("Account created! Check your email to confirm, then log in.");
        setMode("login");
      }
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.title}>
          {mode === "login" ? "Welcome back" : "Create account"}
        </h1>

        {error && <div style={styles.error}>{error}</div>}
        {message && <div style={styles.success}>{message}</div>}

        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            style={styles.input}
            placeholder="you@example.com"
          />

          <label style={styles.label}>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={styles.input}
            placeholder="••••••••"
            minLength={6}
          />

          <button type="submit" disabled={loading} style={styles.button}>
            {loading ? "Please wait…" : mode === "login" ? "Log in" : "Sign up"}
          </button>
        </form>

        <p style={styles.toggle}>
          {mode === "login" ? "Don't have an account? " : "Already have an account? "}
          <button
            onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(""); }}
            style={styles.link}
          >
            {mode === "login" ? "Sign up" : "Log in"}
          </button>
        </p>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#f9f9f7",
  },
  card: {
    background: "#fff",
    borderRadius: 12,
    padding: "40px 36px",
    width: "100%",
    maxWidth: 400,
    boxShadow: "0 2px 16px rgba(0,0,0,0.08)",
  },
  title: {
    fontSize: 22,
    fontWeight: 500,
    marginBottom: 24,
    color: "#1a1a18",
  },
  form: { display: "flex", flexDirection: "column", gap: 4 },
  label: { fontSize: 13, color: "#5f5e5a", marginBottom: 4, marginTop: 12 },
  input: {
    padding: "10px 12px",
    fontSize: 15,
    border: "1px solid #d3d1c7",
    borderRadius: 8,
    outline: "none",
    color: "#1a1a18",
  },
  button: {
    marginTop: 20,
    padding: "11px 0",
    fontSize: 15,
    fontWeight: 500,
    background: "#534AB7",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    cursor: "pointer",
  },
  toggle: { marginTop: 20, fontSize: 14, color: "#5f5e5a", textAlign: "center" },
  link: {
    background: "none",
    border: "none",
    color: "#534AB7",
    cursor: "pointer",
    fontSize: 14,
    padding: 0,
  },
  error: {
    background: "#FCEBEB",
    color: "#A32D2D",
    borderRadius: 8,
    padding: "10px 14px",
    fontSize: 14,
    marginBottom: 12,
  },
  success: {
    background: "#EAF3DE",
    color: "#3B6D11",
    borderRadius: 8,
    padding: "10px 14px",
    fontSize: 14,
    marginBottom: 12,
  },
};
