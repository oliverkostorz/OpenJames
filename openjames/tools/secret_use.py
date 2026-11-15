import json
from .. import vault
from ..audit import log_event

TOOL_SCHEMA = {"type": "function", "function": {"name": "secret_use",
    "description": "Use a stored credential WITHOUT ever printing it. info: key names of a file. type: type the value into a web element (id from the latest web map) via the browser. reveal: return the value (only if the principal asked to see it; it then enters the chat).",
    "parameters": {"type": "object", "properties": {"action": {"enum": ["info", "type", "reveal"]}, "file": {"type": "string"}, "key": {"type": "string"},
        "target": {"type": "string", "description": "type: element id"}, "tab": {"type": "string"}, "enter": {"type": "boolean"}}, "required": ["action", "file"]}}}


def _value(a):
    pairs = vault.pairs(vault.read(a["file"]))
    if not pairs: raise KeyError("file empty or missing")
    if a.get("key"): return pairs[a["key"]]
    if len(pairs) == 1: return next(iter(pairs.values()))
    raise KeyError(f"several keys, pass key: {sorted(pairs)}")


def run(a):
    act = a["action"]
    if act == "info": return {"keys": sorted(vault.pairs(vault.read(a["file"])))}
    try: v = _value(a)
    except KeyError as e: return {"error": str(e)}
    if act == "reveal":
        log_event("secret_reveal", file=a["file"], key=a.get("key")); return {"value": v}
    if not a.get("target"): return {"error": "target element id required"}
    from ..web import client
    params = {"verb": "type", "target": a["target"], "args": {"text": v, "clear": True, "enter": bool(a.get("enter"))}, "include_text": False}
    if a.get("tab"): params["tab"] = a["tab"]
    r = client.call("act", params, timeout=180)
    log_event("secret_use", file=a["file"], key=a.get("key"), ok=r.get("ok"))
    return {"ok": r.get("ok"), "typed_chars": len(v), "result": r.get("result"), "diff": r.get("diff")}
