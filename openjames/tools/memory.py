from pathlib import Path
from ..paths import MEMORY

TOOL_SCHEMA = {"type": "function", "function": {"name": "memory",
    "description": "Read or append a markdown file under memory/ (persistent notes between runs).",
    "parameters": {"type": "object", "properties": {"action": {"enum": ["read", "append"]}, "path": {"type": "string"}, "text": {"type": "string"}}, "required": ["action", "path"]}}}


def run(a):
    p = (MEMORY / a["path"]).resolve()
    if MEMORY.resolve() not in p.parents or p.suffix != ".md": return "error: path must be a .md under memory/"
    if a["action"] == "read": return p.read_text() if p.exists() else ""
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f: f.write(a.get("text", "") + "\n")
    return "ok"
