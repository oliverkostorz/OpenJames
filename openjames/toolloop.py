"""Tool-calling loop for API backends (OpenAI-style and Anthropic) plus the CLI bridge.

Every capability is a registry tool (openjames/tools/); API backends call it through this loop,
CLI backends through `python -m openjames.toolcli <name> '<json>'`. Same tools, same behaviour.
"""
from __future__ import annotations
import json
from . import tools

MAX_ROUNDS = 20


def schemas(allowed=None) -> list[dict]:
    return [s for s in tools.get_tool_schemas() if allowed is None or s["function"]["name"] in allowed]


def execute(name: str, arguments, allowed=None) -> str:
    if allowed is not None and name not in allowed: return f"error: tool {name} not allowed here"
    try:
        out = tools.call_tool(name, arguments if isinstance(arguments, dict) else json.loads(arguments or "{}"))
    except Exception as e:
        return f"error: {type(e).__name__}: {e}"
    return out if isinstance(out, str) else json.dumps(out, default=str)


def openai_loop(post, system, prompt, allowed=None) -> str:
    """post(payload_extra: dict, messages) -> assistant message dict (OpenAI chat format)."""
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    sch = schemas(allowed)
    for _ in range(MAX_ROUNDS):
        m = post(msgs, sch)
        calls = m.get("tool_calls") or []
        if not calls: return m.get("content") or ""
        msgs.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": calls})
        for c in calls:
            msgs.append({"role": "tool", "tool_call_id": c["id"],
                         "content": execute(c["function"]["name"], c["function"].get("arguments"), allowed)})
    return "error: tool loop hit MAX_ROUNDS"


def anthropic_loop(post, system, prompt, allowed=None) -> str:
    """post(messages, anthropic_tools) -> response dict with `content` blocks."""
    msgs = [{"role": "user", "content": prompt}]
    sch = [{"name": s["function"]["name"], "description": s["function"]["description"],
            "input_schema": s["function"]["parameters"]} for s in schemas(allowed)]
    for _ in range(MAX_ROUNDS):
        r = post(msgs, sch)
        blocks = r["content"]
        uses = [b for b in blocks if b["type"] == "tool_use"]
        if not uses: return "".join(b.get("text", "") for b in blocks if b["type"] == "text")
        msgs.append({"role": "assistant", "content": blocks})
        msgs.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": b["id"],
                                                  "content": execute(b["name"], b["input"], allowed)} for b in uses]})
    return "error: tool loop hit MAX_ROUNDS"
