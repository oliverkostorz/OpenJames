TOOL_SCHEMA = {"type": "function", "function": {"name": "subagent",
    "description": "Fresh, isolated, tool-less model call: second opinion, review, summary or draft of the text you pass in. It sees nothing else.",
    "parameters": {"type": "object", "properties": {"task": {"type": "string"}, "context": {"type": "string"}}, "required": ["task"]}}}


def run(a):
    from .. import backends
    from ..config import load
    _, r = backends.run_chain(load().backends, "You are a careful assistant. Answer only from the given text.", a["task"] + "\n\n" + a.get("context", ""), allowed=[], api_only=True)
    return r
