import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from openjames import toolloop, backends, tools

# openai-format loop: model calls list_tools, then answers
seen = []
def post(msgs, sch):
    seen.append(len(msgs))
    if msgs[-1]["role"] == "user":
        return {"content": "", "tool_calls": [{"id": "1", "type": "function", "function": {"name": "list_tools", "arguments": "{}"}}]}
    assert "delegate" in msgs[-1]["content"]
    return {"content": "done"}
assert toolloop.openai_loop(post, "s", "p") == "done"

# anthropic-format loop
def apost(msgs, sch):
    assert any(t["name"] == "delegate" for t in sch)
    if len(msgs) == 1: return {"content": [{"type": "tool_use", "id": "a", "name": "list_tools", "input": {}}]}
    assert msgs[-1]["content"][0]["type"] == "tool_result"
    return {"content": [{"type": "text", "text": "ok"}]}
assert toolloop.anthropic_loop(apost, "s", "p") == "ok"

# allow-list is enforced and errors are returned, not raised
assert "not allowed" in toolloop.execute("create_tool", {}, allowed=["memory"])
assert toolloop.execute("nope", {}).startswith("error")
assert "delegate" in [s["function"]["name"] for s in tools.get_tool_schemas()]

# delegate: experts get restricted tools, API only; CLIs skipped
import types
m = types.ModuleType("fakeapi"); m.TOOL_LOOP = True
m.run = lambda s, p, allowed=None: f"{allowed}"
sys.modules["openjames.backends.fakeapi"] = m
c = types.ModuleType("fakecli"); c.run = lambda s, p: "cli"
sys.modules["openjames.backends.fakecli"] = c
assert backends.run_chain(["fakecli", "fakeapi"], "", "", ["memory"], api_only=True) == ("fakeapi", "['memory']")
assert backends.run_chain(["fakecli"], "", "")[1] == "cli"
assert "delegate" not in str(__import__("openjames.experts", fromlist=["x"]).EXPERTS)
print("ok")
