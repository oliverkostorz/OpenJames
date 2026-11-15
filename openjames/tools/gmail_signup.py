"""Tool: gmail_signup — create the assistant's Gmail account (the init wizard's signup step)."""
TOOL_SCHEMA = {"type": "function", "function": {"name": "gmail_signup",
    "description": "Create a Gmail account for the assistant in its own visible Chrome, human-paced, once per phone number. The password is generated and kept in the vault (never returned). The SMS code is relayed by the principal: pass sms_code when you have it (action=resume). Stops and hands over on ID/video checks or blocks. Only run on the principal's explicit request (the init wizard does).",
    "parameters": {"type": "object", "properties": {
        "action": {"enum": ["start", "resume"]}, "first": {"type": "string"}, "last": {"type": "string"},
        "username": {"type": "string"}, "birthday": {"type": "string", "description": "YYYY-MM-DD, the principal's own"},
        "phone": {"type": "string"}, "task_id": {"type": "string"}, "sms_code": {"type": "string"}}, "required": ["action"]}}}


def run(a):
    from .. import gmail_signup as g
    if a["action"] == "start":
        need = [k for k in ("first", "last", "username", "birthday", "phone") if not a.get(k)]
        if need: return {"error": f"missing: {need}"}
        return g.signup(a["first"], a["last"], a["username"], a["birthday"], a["phone"],
                        ask_code=lambda prompt, t: str(a.get("sms_code") or ""), say=lambda *_: None)
    if not (a.get("task_id") and a.get("sms_code")): return {"error": "task_id and sms_code required"}
    g._set_goal(a["task_id"], f"The SMS code is {''.join(c for c in a['sms_code'] if c.isdigit())}: type it and continue.")
    from . import web_task
    return web_task.run({"task_id": a["task_id"], "approved_labels": g.APPROVED, "max_steps": 40})
