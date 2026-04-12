// frontend/src/Components/ConfirmationModal.jsx
//
// Reads the structured JSON payload sent by confirmation_node via interrupt().
// Fields are pre-filled by the agent (using fetched context) — user just
// reviews and edits before approving or cancelling.

import React, { useState, useMemo } from 'react';
import './ConfirmationModal.css';

/**
 * Parse the interrupt payload.
 * Backend sends JSON.stringify({type, action, to, subject, body, user_query, ...})
 * Falls back gracefully if the string isn't valid JSON.
 */
function parseInterruptPayload(raw = '') {
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object') return parsed;
  } catch (_) {
    // Not JSON — return empty object, fields will just be blank
  }
  return {};
}

export default function ConfirmationModal({
  message,        // raw string from confirmation_required.message (JSON)
  threadId,
  onApprove,      // onApprove(jsonString)
  onReject,
  isLoading = false,
}) {
  const data = useMemo(() => parseInterruptPayload(message), [message]);
  const isCalendar = (data.type || '').toLowerCase() === 'calendar';

  // ── Gmail fields — pre-filled from LLM draft ──────────────────────
  const [to,      setTo]      = useState(data.to      || '');
  const [subject, setSubject] = useState(data.subject || '');
  const [body,    setBody]    = useState(data.body    || '');

  // ── Calendar fields — pre-filled from LLM draft ───────────────────
  const [eventTitle,   setEventTitle]   = useState(data.title       || '');
  const [startTime,    setStartTime]    = useState(data.start       || '');
  const [endTime,      setEndTime]      = useState(data.end         || '');
  const [attendees,    setAttendees]    = useState(data.attendees   || '');
  const [description,  setDescription]  = useState(data.description || '');

  const handleApprove = () => {
    const payload = isCalendar
      ? JSON.stringify({ approved: true, title: eventTitle, start: startTime,
                         end: endTime, attendees, description })
      : JSON.stringify({ approved: true, to, subject, body });
    onApprove(payload);
  };

  const icon        = isCalendar ? '📅' : '📧';
  const title       = isCalendar ? 'Confirm Calendar Event' : 'Confirm Email';
  const actionLabel = data.action || (isCalendar ? 'Create calendar event' : 'Send email');

  return (
    <div className="hitl-overlay" role="dialog" aria-modal="true">
      <div className="hitl-modal hitl-modal-compose">

        {/* Header */}
        <div className="hitl-header">
          <span className="hitl-icon">{icon}</span>
          <h2 className="hitl-title">{title}</h2>
        </div>

        <p className="hitl-subtitle">
          {actionLabel}. Review and edit before confirming.
        </p>

        {/* ── Gmail compose form ─────────────────────────────────── */}
        {!isCalendar && (
          <div className="hitl-compose">
            <div className="hitl-field-row">
              <label className="hitl-label">To</label>
              <input
                className="hitl-input"
                type="email"
                value={to}
                onChange={e => setTo(e.target.value)}
                placeholder="recipient@example.com"
                disabled={isLoading}
              />
            </div>
            <div className="hitl-field-row">
              <label className="hitl-label">Subject</label>
              <input
                className="hitl-input"
                type="text"
                value={subject}
                onChange={e => setSubject(e.target.value)}
                placeholder="Email subject"
                disabled={isLoading}
              />
            </div>
            <div className="hitl-field-row hitl-field-row--body">
              <label className="hitl-label">Body</label>
              <textarea
                className="hitl-textarea"
                value={body}
                onChange={e => setBody(e.target.value)}
                placeholder="Email body…"
                rows={8}
                disabled={isLoading}
              />
            </div>
          </div>
        )}

        {/* ── Calendar compose form ──────────────────────────────── */}
        {isCalendar && (
          <div className="hitl-compose">
            <div className="hitl-field-row">
              <label className="hitl-label">Event Title</label>
              <input
                className="hitl-input"
                type="text"
                value={eventTitle}
                onChange={e => setEventTitle(e.target.value)}
                placeholder="Meeting title"
                disabled={isLoading}
              />
            </div>
            <div className="hitl-field-row">
              <label className="hitl-label">Start</label>
              <input
                className="hitl-input"
                type="text"
                value={startTime}
                onChange={e => setStartTime(e.target.value)}
                placeholder="2024-01-15T10:00:00"
                disabled={isLoading}
              />
            </div>
            <div className="hitl-field-row">
              <label className="hitl-label">End</label>
              <input
                className="hitl-input"
                type="text"
                value={endTime}
                onChange={e => setEndTime(e.target.value)}
                placeholder="2024-01-15T11:00:00"
                disabled={isLoading}
              />
            </div>
            <div className="hitl-field-row">
              <label className="hitl-label">Attendees</label>
              <input
                className="hitl-input"
                type="text"
                value={attendees}
                onChange={e => setAttendees(e.target.value)}
                placeholder="email1@example.com, email2@example.com"
                disabled={isLoading}
              />
            </div>
            <div className="hitl-field-row hitl-field-row--body">
              <label className="hitl-label">Description</label>
              <textarea
                className="hitl-textarea"
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="Event description (optional)"
                rows={4}
                disabled={isLoading}
              />
            </div>
          </div>
        )}

        {/* Original request */}
        {data.user_query && (
          <p className="hitl-original-query">
            Original: "{data.user_query}"
          </p>
        )}

        {/* Actions */}
        <div className="hitl-actions">
          {isLoading ? (
            <div className="hitl-loading">
              <div className="hitl-spinner" />
              {isCalendar ? 'Creating event…' : 'Sending…'}
            </div>
          ) : (
            <>
              <button className="hitl-btn hitl-btn-reject" onClick={onReject}>
                ✕ Cancel
              </button>
              <button
                className="hitl-btn hitl-btn-approve"
                onClick={handleApprove}
                disabled={isCalendar ? !eventTitle : !to}
              >
                {isCalendar ? '📅 Create Event' : '📧 Send Email'}
              </button>
            </>
          )}
        </div>

      </div>
    </div>
  );
}
