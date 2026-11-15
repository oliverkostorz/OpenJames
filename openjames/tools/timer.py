from .. import timers

TOOL_SCHEMA = {"type": "function", "function": {"name": "timer",
    "description": "Set, list or cancel timers. When a timer is due the prompt is run later as a new task and its answer goes to the principal. Use for reminders, follow-ups, recurring checks.",
    "parameters": {"type": "object", "properties": {"action": {"enum": ["set", "list", "cancel"]},
        "prompt": {"type": "string", "description": "set: what to do/say when it fires (self-contained)"},
        "at": {"type": "string", "description": "set: ISO time in UTC, e.g. 2026-12-01T09:00"}, "in_minutes": {"type": "number", "description": "set: relative alternative to at"},
        "every_minutes": {"type": "number", "description": "set: repeat interval"}, "id": {"type": "string", "description": "cancel: timer id"}}, "required": ["action"]}}}


def run(a):
    if a["action"] == "list": return timers.load()
    if a["action"] == "cancel":
        ts = timers.load(); keep = [t for t in ts if t["id"] != a.get("id")]; timers.save(keep)
        return "cancelled" if len(keep) < len(ts) else "no such timer"
    if not a.get("prompt") or not (a.get("at") or a.get("in_minutes")): return "error: prompt and at/in_minutes required"
    return timers.add(a["prompt"], a.get("at"), a.get("in_minutes"), a.get("every_minutes"))
