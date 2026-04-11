"""
hitl/confirmation.py
IMPORTANT: confirmation_node receives a Send() PAYLOAD dict,
NOT the full OrchestratorState. Fix for 0 results bug.
"""
from __future__ import annotations
import logging
from langgraph.types import interrupt, Send

logger = logging.getLogger(__name__)

WRITE_SIGNALS = {
    "send", "create", "delete", "update", "modify",
    "draft", "schedule", "add event", "remove", "trash",
}
READ_SIGNALS = {
    "search", "list", "get", "read", "summarize", "summary",
    "fetch", "find", "show", "display", "retrieve",
}
GOOGLE_WORKER_TYPES = {"gmail", "calendar", "google_workspace", "google_gmail", "google_calendar"}


def _is_google_task(task: dict) -> bool:
    wt = (task.get("worker_type") or "").lower()
    gs = (task.get("google_service") or "").lower()
    return any(kw in wt or kw in gs for kw in GOOGLE_WORKER_TYPES)

def needs_confirmation(task: dict) -> bool:
    if not _is_google_task(task):
        return False
    combined = task.get("description", "").lower() + " " + task.get("title", "").lower()
    is_read  = any(sig in combined for sig in READ_SIGNALS)
    is_write = any(sig in combined for sig in WRITE_SIGNALS)
    if is_read and not is_write:
        return False
    return is_write


def build_confirmation_message(task: dict, user_query: str) -> str:
    worker_type = task.get("worker_type", "google").upper()
    description = task.get("description", "")
    params      = task.get("parameters", {})
    wt = (task.get("worker_type") or "").lower()
    gs = (task.get("google_service") or "").lower()

    lines = [
        "⚠️  **Action Requires Your Approval**", "",
        f"**Type:** {worker_type}",
        f"**Action:** {description}",
    ]
    if "gmail" in wt or gs == "gmail":
        if params.get("to"):      lines.append(f"**To:** {params['to']}")
        if params.get("subject"): lines.append(f"**Subject:** {params['subject']}")
        if params.get("body"):
            preview = params["body"][:150].replace("\n", " ")
            lines.append(f"**Body preview:** {preview}{'…' if len(params['body']) > 150 else ''}")
    elif "calendar" in wt or gs == "calendar":
        title = params.get("summary") or params.get("title") or ""
        if title:                  lines.append(f"**Event:** {title}")
        if params.get("start"):    lines.append(f"**Start:** {params['start']}")
        if params.get("end"):      lines.append(f"**End:** {params['end']}")
        if params.get("attendees"):lines.append(f"**Attendees:** {params['attendees']}")
    lines += ["", f"**Original request:** {user_query}", "",
              "Reply **approve** to proceed or **reject** to cancel."]
    return "\n".join(lines)


# ── The node — receives Send() payload, NOT OrchestratorState ────────────────

def confirmation_node(payload: dict):
    """
    Called via Send("confirmation_node", payload).
    payload = { task, user_query, user_id, context }

    Returns either:
      - Send("google_workspace_worker", payload)  — approved or read-only
      - { "results": [TaskResult(...)] }           — rejected
    """
    from orchestration.wow_orchestration import TaskResult

    task_dict  = payload.get("task", {})
    user_query = payload.get("user_query", "")

    # Read-only → skip HITL entirely
    if not needs_confirmation(task_dict):
        logger.info(f"HITL: task {task_dict.get('id')} read-only, skipping")
        return Send("google_workspace_worker", payload)

    # Write action → pause for human
    message = build_confirmation_message(task_dict, user_query)
    logger.info(f"HITL: pausing for task {task_dict.get('id')} — {task_dict.get('description')}")

    user_response: str = interrupt(message)   # ← GRAPH FREEZES HERE

    clean    = (user_response or "").strip().lower()
    approved = clean in {"approve", "yes", "y", "ok", "confirm", "proceed"}

    if approved:
        logger.info(f"HITL: task {task_dict.get('id')} APPROVED")
        return Send("google_workspace_worker", payload)

    logger.info(f"HITL: task {task_dict.get('id')} REJECTED ({clean!r})")
    return {
        "results": [TaskResult(
            task_id=task_dict.get("id", 0),
            worker_type=task_dict.get("worker_type", "google"),
            success=False,
            output="❌ Action cancelled by user.",
            error="user_rejected",
        )]
    }