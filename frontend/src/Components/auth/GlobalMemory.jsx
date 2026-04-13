// frontend/src/Components/settings/GlobalMemory.jsx
//
// Lets the user write 1-2 lines of personal preferences that get
// prepended to every orchestrator request as "global memory".
// Fits inside the ProfilePage settings layout.

import { useState, useEffect, useRef } from "react";
import apiService from "../../api/services";
import "./GlobalMemory.css";

const MAX_CHARS = 300;

export default function GlobalMemory() {
  const [value, setValue]       = useState("");
  const [saved, setSaved]       = useState("");   // last successfully saved value
  const [status, setStatus]     = useState("idle"); // idle | loading | saving | saved | error
  const [error, setError]       = useState("");
  const textareaRef             = useRef(null);
  const saveTimerRef            = useRef(null);

  // Load on mount
  useEffect(() => {
    setStatus("loading");
    apiService
      .getPreferences()
      .then((prefs) => {
        setValue(prefs);
        setSaved(prefs);
        setStatus("idle");
      })
      .catch(() => {
        setStatus("error");
        setError("Couldn't load preferences.");
      });
    return () => clearTimeout(saveTimerRef.current);
  }, []);

  const isDirty = value !== saved;
  const remaining = MAX_CHARS - value.length;

  const handleChange = (e) => {
    const next = e.target.value;
    if (next.length > MAX_CHARS) return;
    setValue(next);
    setStatus("idle");
    setError("");
  };

  const handleSave = async () => {
    if (!isDirty || status === "saving") return;
    setStatus("saving");
    setError("");
    try {
      const saved = await apiService.setPreferences(value.trim());
      setSaved(saved);
      setStatus("saved");
      // Reset to idle after 2s
      saveTimerRef.current = setTimeout(() => setStatus("idle"), 2000);
    } catch {
      setStatus("error");
      setError("Failed to save. Please try again.");
    }
  };

  const handleClear = () => {
    setValue("");
    setError("");
    setStatus("idle");
  };

  // Allow Ctrl/Cmd+Enter to save
  const handleKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      handleSave();
    }
  };

  return (
    <div className="gm-card">
      <div className="gm-header">
        <div className="gm-title-row">
          <span className="gm-icon">🧠</span>
          <span className="gm-title">Personal context</span>
          {status === "saved" && (
            <span className="gm-badge gm-badge--saved">Saved</span>
          )}
          {status === "error" && (
            <span className="gm-badge gm-badge--error">Error</span>
          )}
        </div>
        <p className="gm-desc">
          Tell the assistant about yourself — preferred style, role, or
          anything useful. This is included in every conversation.
        </p>
      </div>

      <div className={`gm-field ${status === "error" ? "gm-field--error" : ""}`}>
        {status === "loading" ? (
          <div className="gm-skeleton" />
        ) : (
          <textarea
            ref={textareaRef}
            className="gm-textarea"
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="e.g. I'm a robotics club member focused on ROS2. Prefer concise technical answers in metric units."
            rows={3}
            spellCheck={false}
          />
        )}

        <div className="gm-footer">
          <span className={`gm-counter ${remaining <= 30 ? "gm-counter--warn" : ""}`}>
            {remaining} left
          </span>
          <div className="gm-actions">
            {value && (
              <button
                className="gm-btn gm-btn--ghost"
                onClick={handleClear}
                disabled={status === "saving"}
                type="button"
              >
                Clear
              </button>
            )}
            <button
              className={`gm-btn gm-btn--primary ${!isDirty ? "gm-btn--disabled" : ""}`}
              onClick={handleSave}
              disabled={!isDirty || status === "saving" || status === "loading"}
              type="button"
            >
              {status === "saving" ? (
                <span className="gm-spinner" />
              ) : (
                "Save"
              )}
            </button>
          </div>
        </div>
      </div>

      {error && <p className="gm-error">{error}</p>}

      <p className="gm-hint">
        <kbd>Ctrl</kbd>+<kbd>Enter</kbd> to save quickly
      </p>
    </div>
  );
}