import json
from ..experts import EXPERTS

TOOL_SCHEMA = {"type": "function", "function": {"name": "delegate",
    "description": "Hand ONE bounded objective to an expert agent (fresh isolated model call, own prompt, restricted tools). Experts: " + ", ".join(EXPERTS) + ".",
    "parameters": {"type": "object", "properties": {"expert": {"type": "string", "enum": list(EXPERTS)}, "objective": {"type": "string"}}, "required": ["expert", "objective"]}}}


def run(a):
    from .. import backends
    from ..config import load
    if a["expert"] not in EXPERTS: return f"error: unknown expert {a['expert']}"
    system, allowed = EXPERTS[a["expert"]]
    try:
        _, reply = backends.run_chain(load().backends, system, a["objective"], allowed=allowed, api_only=True)
    except RuntimeError as e:
        return f"error: {e}"
    return reply
