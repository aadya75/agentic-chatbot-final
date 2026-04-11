// frontend/src/Components/ConfirmationModal.jsx
//
// Shown when the backend returns interrupted=true for a Google write action.
// Parses the structured confirmation message from the orchestrator and
// renders it cleanly with Approve / Reject buttons.

import React, { useMemo } from 'react';
import './ConfirmationModal.css';

/**
 * Parse the plain-text confirmation message produced by
 * hitl/confirmation.py::build_confirmation_message() into structured fields.
 *
 * The message uses "**Label:** Value" markdown-ish lines.
 */
function parseConfirmationMessage(raw = '') {
  const fields = {};
  const lines = raw.split('\n');

  for (const line of lines) {
    const match = line.match(/^\*\*(.+?):\*\*\s*(.+)$/);
    if (match) {
      fields[match[1].trim()] = match[2].trim();
    }
  }

  return fields;
}

/**
 * ConfirmationModal
 *
 * Props:
 *   message    {string}   — raw confirmation message from the backend
 *   threadId   {string}   — thread_id to send back on confirm
 *   onApprove  {fn}       — called with no args when user clicks Approve
 *   onReject   {fn}       — called with no args when user clicks Reject
 *   isLoading  {boolean}  — show spinner while request is in-flight
 */
export default function ConfirmationModal({
  message,
  threadId,
  onApprove,
  onReject,
  isLoading = false,
}) {
  const fields = useMemo(() => parseConfirmationMessage(message), [message]);

  // Decide icon based on action type
  const actionType = (fields['Type'] || '').toLowerCase();
  const icon = actionType.includes('gmail') ? '📧'
    : actionType.includes('calendar') ? '📅'
    : '⚠️';

  const actionLabel = fields['Action'] || 'Perform action';

  return (
    <div className="hitl-overlay" role="dialog" aria-modal="true" aria-labelledby="hitl-title">
      <div className="hitl-modal">

        {/* Header */}
        <div className="hitl-header">
          <span className="hitl-icon">{icon}</span>
          <h2 className="hitl-title" id="hitl-title">Action Requires Approval</h2>
        </div>

        {/* Detail card */}
        <div className="hitl-body">

          {fields['Type'] && (
            <div className="hitl-field">
              <span className="hitl-label">Service</span>
              <span className="hitl-value">{fields['Type']}</span>
            </div>
          )}

          {fields['Action'] && (
            <div className="hitl-field">
              <span className="hitl-label">Action</span>
              <span className="hitl-value">{actionLabel}</span>
            </div>
          )}

          {/* Gmail fields */}
          {fields['To'] && (
            <div className="hitl-field">
              <span className="hitl-label">To</span>
              <span className="hitl-value">{fields['To']}</span>
            </div>
          )}
          {fields['Subject'] && (
            <div className="hitl-field">
              <span className="hitl-label">Subject</span>
              <span className="hitl-value">{fields['Subject']}</span>
            </div>
          )}
          {fields['Body preview'] && (
            <div className="hitl-field">
              <span className="hitl-label">Preview</span>
              <span className="hitl-value preview">{fields['Body preview']}</span>
            </div>
          )}

          {/* Calendar fields */}
          {fields['Event'] && (
            <div className="hitl-field">
              <span className="hitl-label">Event</span>
              <span className="hitl-value">{fields['Event']}</span>
            </div>
          )}
          {fields['Start'] && (
            <div className="hitl-field">
              <span className="hitl-label">Start</span>
              <span className="hitl-value">{fields['Start']}</span>
            </div>
          )}
          {fields['End'] && (
            <div className="hitl-field">
              <span className="hitl-label">End</span>
              <span className="hitl-value">{fields['End']}</span>
            </div>
          )}
          {fields['Attendees'] && (
            <div className="hitl-field">
              <span className="hitl-label">Attendees</span>
              <span className="hitl-value">{fields['Attendees']}</span>
            </div>
          )}

          {fields['Original request'] && (
            <>
              <hr className="hitl-divider" />
              <p className="hitl-original-query">
                "{fields['Original request']}"
              </p>
            </>
          )}
        </div>

        {/* Action buttons */}
        <div className="hitl-actions">
          {isLoading ? (
            <div className="hitl-loading">
              <div className="hitl-spinner" />
              Processing…
            </div>
          ) : (
            <>
              <button
                className="hitl-btn hitl-btn-reject"
                onClick={onReject}
                disabled={isLoading}
              >
                ✕ Reject
              </button>
              <button
                className="hitl-btn hitl-btn-approve"
                onClick={onApprove}
                disabled={isLoading}
              >
                ✓ Approve
              </button>
            </>
          )}
        </div>

      </div>
    </div>
  );
}
