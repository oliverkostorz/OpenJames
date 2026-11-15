from .. import vault

TOOL_SCHEMA = {"type": "function", "function": {"name": "store_secret",
    "description": "Store a credential in the local vault (private/accounts/<file>, 0600, gitignored). The value is never echoed back. action=list shows files and key names only.",
    "parameters": {"type": "object", "properties": {"action": {"enum": ["set", "list"]}, "file": {"type": "string"}, "key": {"type": "string"},
        "value": {"type": "string"}, "note": {"type": "string", "description": "non-secret note (site, username)"}}, "required": ["action"]}}}


def run(a):
    if a["action"] == "list":
        return {f.name: sorted(vault.pairs(f.read_text())) for f in sorted(vault.DIR.glob("*.txt"))} if vault.DIR.exists() else {}
    if not (a.get("file") and a.get("key") and a.get("value")): return {"error": "file, key and value are required"}
    vault.set_key(a["file"], a["key"], a["value"], a.get("note"))
    return {"stored": a["file"], "key": a["key"], "chars": len(a["value"])}
