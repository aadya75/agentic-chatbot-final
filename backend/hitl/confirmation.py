"""
hitl/confirmation.py

confirmation_node is called via Send("confirmation_node", payload) from fanout.

Key design: instead of relying on the planner to pre-fill email/calendar fields
(which fails when the body depends on retrieved context), we call the LLM
*inside confirmation_node* to draft the fields using:
  - task.parameters  (whatever the planner already filled in)
  - payload["context"] (already fetched by the context layer before this runs)
  - user_query

This means the modal is always pre-filled, even for queries like:
  "search my docs and email the summary to john@example.com"
  "check the club schedule and create a calendar event for the next meeting"

Flow:
  planning → context fetch → execute_tasks → fanout → confirmation_node
                                                            ↓
                                                 draft fields with LLM
                                                            ↓
                                                   interrupt(json_string)
                                                            ↓
                                                  [GRAPH FREEZES — modal shows]
                                                            ↓
                                                  user edits + approves/rejects
                                                            ↓
                                               inject edits → hitl_google_worker
"""
from __future__ import annotations
import json
import logging
import os

from langgraph.types import interrupt
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)

# Lightweight LLM just for field drafting — fast and cheap
_draft_llm = ChatGroq(
    model=os.getenv("WORKER_MODEL", "llama-3.1-8b-instant"),
    temperature=0.2,
    api_key=os.getenv("GROQ_API_KEY"),
)

WRITE_SIGNALS = {
    "send", "email", "mail", "reply", "forward", "draft",
    "delete", "trash", "remove", "mark as",
    "create", "schedule", "add event", "update", "modify",
    "cancel event", "reschedule", "write", "compose", "submit",
}
READ_SIGNALS = {
    "search", "list", "get", "read", "summarize", "summary",
    "fetch", "find", "show", "display", "retrieve", "check",
    "look up", "lookup", "view", "open", "count",
}
GOOGLE_WORKER_TYPES = {
    "gmail", "calendar", "google_workspace", "google_gmail", "google_calendar",
}


def _is_google_task(task: dict) -> bool:
    wt = (task.get("worker_type") or "").lower()
    gs = (task.get("google_service") or "").lower()
    return any(kw in wt or kw in gs for kw in GOOGLE_WORKER_TYPES)


def needs_confirmation(task: dict) -> bool:
    """Returns True if this task needs human approval before executing."""
    if not _is_google_task(task):
        return False
    combined = (
        (task.get("description") or "").lower() + " " +
        (task.get("title") or "").lower()
    )
    is_read  = any(sig in combined for sig in READ_SIGNALS)
    is_write = any(sig in combined for sig in WRITE_SIGNALS)
    if is_read and not is_write:
        return False
    return is_write


# ── Field drafting ─────────────────────────────────────────────────────────────

def _call_draft_llm(system: str, prompt: str) -> dict:
    """Shared LLM call + JSON parse for field drafting. Returns {} on failure."""
    try:
        response = _draft_llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=prompt),
        ])
        raw = (response.content or "").strip()
        # Strip markdown fences if model wraps the JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as exc:
        logger.warning(f"HITL: draft LLM call failed: {exc}")
        return {}


def _draft_gmail_fields(task: dict, user_query: str, context: str) -> dict:
    """
    Draft to/subject/body.
    - If planner already filled all three, skip the LLM call entirely.
    - Otherwise call the LLM with task params + fetched context.
    """
    params = task.get("parameters") or {}

    # Fast path: planner already did the work
    if params.get("to") and params.get("subject") and params.get("body"):
        return {
            "to":      params["to"],
            "subject": params["subject"],
            "body":    params["body"],
        }

    system = (
        "You are an email drafting assistant. "
        "Draft the email fields based on the user's request and any retrieved context. "
        "Return ONLY a raw JSON object with keys: to, subject, body. "
        "No markdown fences, no explanation."
    )
    prompt = "\n\n".join(filter(None, [
        f"User request: {user_query}",
        f"Planner params: {json.dumps(params)}" if params else "",
        f"Retrieved context:\n{context[:2000]}"  if context else "",
        "Draft the email. Return JSON only.",
    ]))

    drafted = _call_draft_llm(system, prompt)
    return {
        "to":      drafted.get("to",      params.get("to",      "")),
        "subject": drafted.get("subject", params.get("subject", "")),
        "body":    drafted.get("body",    params.get("body",    "")),
    }


def _draft_calendar_fields(task: dict, user_query: str, context: str) -> dict:
    """
    Draft title/start/end/attendees/description.
    - If planner filled the essentials (title + start + end), skip LLM.
    - Otherwise call the LLM with task params + fetched context.
    """
    params = task.get("parameters") or {}
    title  = params.get("summary") or params.get("title", "")

    # Fast path
    if title and params.get("start") and params.get("end"):
        return {
            "title":       title,
            "start":       params.get("start",       ""),
            "end":         params.get("end",         ""),
            "attendees":   params.get("attendees",   ""),
            "description": params.get("description", ""),
        }

    system = (
        "You are a calendar event drafting assistant. "
        "Draft the event fields based on the user's request and any retrieved context. "
        "Return ONLY a raw JSON object with keys: title, start, end, attendees, description. "
        "Use ISO 8601 for start/end (e.g. 2024-01-15T10:00:00). "
        "Use empty string for fields you cannot determine. "
        "No markdown fences, no explanation."
    )
    prompt = "\n\n".join(filter(None, [
        f"User request: {user_query}",
        f"Planner params: {json.dumps(params)}" if params else "",
        f"Retrieved context:\n{context[:2000]}"  if context else "",
        "Draft the calendar event. Return JSON only.",
    ]))

    drafted = _call_draft_llm(system, prompt)
    return {
        "title":       drafted.get("title",       title),
        "start":       drafted.get("start",       params.get("start",       "")),
        "end":         drafted.get("end",         params.get("end",         "")),
        "attendees":   drafted.get("attendees",   params.get("attendees",   "")),
        "description": drafted.get("description", params.get("description", "")),
    }


def _build_interrupt_payload(task: dict, user_query: str, context: str) -> dict:
    """
    Build the structured dict passed to interrupt().
    Frontend reads this directly — no regex parsing needed.
    """
    wt = (task.get("worker_type") or "").lower()
    gs = (task.get("google_service") or "").lower()

    if "gmail" in wt or gs == "gmail":
        fields = _draft_gmail_fields(task, user_query, context)
        return {"type": "gmail", "action": task.get("description", "Send email"),
                "user_query": user_query, **fields}

    elif "calendar" in wt or gs == "calendar":
        fields = _draft_calendar_fields(task, user_query, context)
        return {"type": "calendar", "action": task.get("description", "Create calendar event"),
                "user_query": user_query, **fields}

    else:
        return {"type": "google", "action": task.get("description", "Google action"),
                "user_query": user_query}


# ── LangGraph node ────────────────────────────────────────────────────────────

def confirmation_node(payload: dict) -> dict:
    """
    Called via Send("confirmation_node", payload).
    payload keys: task, user_query, user_id, context (already fetched)

    Steps:
      1. Read-only task → pass straight through (no interrupt).
      2. Write task → draft fields with LLM → interrupt(json) → FREEZE.
      3. On resume → inject user-edited values → return approved payload.

    State updates returned:
      Approved:  {"hitl_approved_payload": updated_payload}
      Rejected:  {"results": [TaskResult(...)], "hitl_approved_payload": None}
      Read-only: {"hitl_approved_payload": payload}
    """
    from orchestration.wow_orchestration import TaskResult

    task_dict  = payload.get("task") or {}
    user_query = payload.get("user_query") or ""
    context    = payload.get("context") or ""   # already fetched by context layer

    # ── 1. Read-only: pass straight to worker ────────────────────────
    if not needs_confirmation(task_dict):
        logger.info(f"HITL: task {task_dict.get('id')} is read-only, bypassing")
        return {"hitl_approved_payload": payload}

    # ── 2. Draft fields using LLM (context already available here) ────
    logger.info(f"HITL: drafting fields for task {task_dict.get('id')} "
                f"— {task_dict.get('description')} "
                f"[context: {len(context)} chars]")

    interrupt_data = _build_interrupt_payload(task_dict, user_query, context)

    logger.info(f"HITL: pausing — type={interrupt_data.get('type')} "
                f"to={interrupt_data.get('to', 'N/A')} "
                f"title={interrupt_data.get('title', 'N/A')}")

    # Frontend receives this JSON string, parses it, pre-fills the modal
    user_response: str = interrupt(json.dumps(interrupt_data))  # ← GRAPH FREEZES

    clean = (user_response or "").strip()

    # ── Reject: plain string ──────────────────────────────────────────
    if clean.lower() in {"reject", "cancel", "no", "n"}:
        logger.info(f"HITL: task {task_dict.get('id')} REJECTED (plain string)")
        return {
            "hitl_approved_payload": None,
            "results": [TaskResult(
                task_id=task_dict.get("id", 0),
                worker_type=task_dict.get("worker_type", "google"),
                success=False, output="❌ Action cancelled by user.", error="user_rejected",
            )],
        }

    # ── Parse JSON from modal ─────────────────────────────────────────
    try:
        data = json.loads(clean)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"HITL: unparseable resume response {clean!r} → reject")
        return {
            "hitl_approved_payload": None,
            "results": [TaskResult(
                task_id=task_dict.get("id", 0),
                worker_type=task_dict.get("worker_type", "google"),
                success=False, output="❌ Action cancelled (invalid response).", error="user_rejected",
            )],
        }

    if not data.get("approved"):
        logger.info(f"HITL: task {task_dict.get('id')} REJECTED via JSON")
        return {
            "hitl_approved_payload": None,
            "results": [TaskResult(
                task_id=task_dict.get("id", 0),
                worker_type=task_dict.get("worker_type", "google"),
                success=False, output="❌ Action cancelled by user.", error="user_rejected",
            )],
        }

    # ── 3. Approved — merge user edits over drafted values ────────────
    logger.info(f"HITL: task {task_dict.get('id')} APPROVED")

    params = dict(task_dict.get("parameters") or {})
    wt = (task_dict.get("worker_type") or "").lower()
    gs = (task_dict.get("google_service") or "").lower()

    if "gmail" in wt or gs == "gmail":
        # User-edited values win; fall back to what LLM drafted
        params["to"]      = data.get("to",      interrupt_data.get("to",      ""))
        params["subject"] = data.get("subject", interrupt_data.get("subject", ""))
        params["body"]    = data.get("body",    interrupt_data.get("body",    ""))

        final_context = (
            f"CONFIRMED EMAIL TO SEND:\n"
            f"To: {params['to']}\n"
            f"Subject: {params['subject']}\n"
            f"Body:\n{params['body']}\n\n"
            f"Send this email exactly as specified using send_gmail_message tool."
        )
        updated_task = {**task_dict, "parameters": params,
                        "description": f"Send email to {params['to']} with subject '{params['subject']}'"}

    elif "calendar" in wt or gs == "calendar":
        params["summary"]     = data.get("title",       interrupt_data.get("title",       ""))
        params["start"]       = data.get("start",       interrupt_data.get("start",       ""))
        params["end"]         = data.get("end",         interrupt_data.get("end",         ""))
        params["attendees"]   = data.get("attendees",   interrupt_data.get("attendees",   ""))
        params["description"] = data.get("description", interrupt_data.get("description", ""))

        final_context = (
            f"CONFIRMED CALENDAR EVENT TO CREATE:\n"
            f"Title: {params['summary']}\n"
            f"Start: {params['start']}\n"
            f"End: {params['end']}\n"
            f"Attendees: {params['attendees']}\n"
            f"Description: {params['description']}\n\n"
            f"Create this event exactly as specified using the calendar create tool."
        )
        updated_task = {**task_dict, "parameters": params}

    else:
        final_context = context
        updated_task  = task_dict

    updated_payload = {**payload, "task": updated_task, "context": final_context}
    return {"hitl_approved_payload": updated_payload}