// frontend/src/Components/ConfirmationModal.jsx
//
// Reads the structured JSON payload sent by confirmation_node via interrupt().
// Fields are pre-filled by the agent (using fetched context) — user just
// reviews and edits before approving or cancelling.

import React, { useState, useMemo, useEffect } from 'react';  // ← added useEffect
import './ConfirmationModal.css';

function parseInterruptPayload(raw = '') {
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object') return parsed;
  } catch (_) {}
  return {};
}

export default function ConfirmationModal({
  message,
  threadId,
  onApprove,
  onReject,
  isLoading = false,
}) {
  const data = useMemo(() => parseInterruptPayload(message), [message]);
  const isCalendar = (data.type || '').toLowerCase() === 'calendar';

  const [to,          setTo]          = useState(data.to          || '');
  const [subject,     setSubject]     = useState(data.subject     || '');
  const [body,        setBody]        = useState(data.body        || '');
  const [eventTitle,  setEventTitle]  = useState(data.title       || '');
  const [startTime,   setStartTime]   = useState(data.start       || '');
  const [endTime,     setEndTime]     = useState(data.end         || '');
  const [attendees,   setAttendees]   = useState(data.attendees   || '');
  const [description, setDescription] = useState(data.description || '');

  // ── Reset all fields when a new interrupt message arrives ─────────
  // useState only initialises once — useEffect handles subsequent modals
  // (e.g. calendar modal → gmail modal in the same HITL session)
  useEffect(() => {
    const d = parseInterruptPayload(message);
    setTo(d.to          || '');
    setSubject(d.subject     || '');
    setBody(d.body        || '');
    setEventTitle(d.title       || '');
    setStartTime(d.start       || '');
    setEndTime(d.end         || '');
    setAttendees(d.attendees   || '');
    setDescription(d.description || '');
  }, [message]);  // ← fires whenever the backend sends a new interrupt payload

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

        <div className="hitl-header">
          <span className="hitl-icon">{icon}</span>
          <h2 className="hitl-title">{title}</h2>
        </div>

        <p className="hitl-subtitle">
          {actionLabel}. Review and edit before confirming.
        </p>

        {!isCalendar && (
          <div className="hitl-compose">
            <div className="hitl-field-row">
              <label className="hitl-label">To</label>
              <input className="hitl-input" type="email" value={to}
                onChange={e => setTo(e.target.value)}
                placeholder="recipient@example.com" disabled={isLoading} />
            </div>
            <div className="hitl-field-row">
              <label className="hitl-label">Subject</label>
              <input className="hitl-input" type="text" value={subject}
                onChange={e => setSubject(e.target.value)}
                placeholder="Email subject" disabled={isLoading} />
            </div>
            <div className="hitl-field-row hitl-field-row--body">
              <label className="hitl-label">Body</label>
              <textarea className="hitl-textarea" value={body}
                onChange={e => setBody(e.target.value)}
                placeholder="Email body…" rows={8} disabled={isLoading} />
            </div>
          </div>
        )}

        {isCalendar && (
          <div className="hitl-compose">
            <div className="hitl-field-row">
              <label className="hitl-label">Event Title</label>
              <input className="hitl-input" type="text" value={eventTitle}
                onChange={e => setEventTitle(e.target.value)}
                placeholder="Meeting title" disabled={isLoading} />
            </div>
            <div className="hitl-field-row">
              <label className="hitl-label">Start</label>
              <input className="hitl-input" type="text" value={startTime}
                onChange={e => setStartTime(e.target.value)}
                placeholder="2026-04-15T10:00:00+05:30" disabled={isLoading} />
            </div>
            <div className="hitl-field-row">
              <label className="hitl-label">End</label>
              <input className="hitl-input" type="text" value={endTime}
                onChange={e => setEndTime(e.target.value)}
                placeholder="2026-04-15T10:00:00+05:30" disabled={isLoading} />
            </div>
            <div className="hitl-field-row">
              <label className="hitl-label">Attendees</label>
              <input className="hitl-input" type="text" value={attendees}
                onChange={e => setAttendees(e.target.value)}
                placeholder="email1@example.com, email2@example.com" disabled={isLoading} />
            </div>
            <div className="hitl-field-row hitl-field-row--body">
              <label className="hitl-label">Description</label>
              <textarea className="hitl-textarea" value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="Event description (optional)" rows={4} disabled={isLoading} />
            </div>
          </div>
        )}

        {data.user_query && (
          <p className="hitl-original-query">
            Original: "{data.user_query}"
          </p>
        )}

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
              <button className="hitl-btn hitl-btn-approve" onClick={handleApprove}
                disabled={isCalendar ? !eventTitle : !to}>
                {isCalendar ? '📅 Create Event' : '📧 Send Email'}
              </button>
            </>
          )}
        </div>

      </div>
    </div>
  );
}
