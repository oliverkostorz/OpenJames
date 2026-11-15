import ast, importlib, re
from pathlib import Path

TOOL_SCHEMA = {"type": "function", "function": {"name": "create_tool",
    "description": "Write a new tool module to openjames/tools/<name>.py. Must define TOOL_SCHEMA and run(arguments). Rolled back if invalid.",
    "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "code": {"type": "string"}}, "required": ["name", "code"]}}}


def run(arguments):
    name, code = arguments["name"], arguments["code"]
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", name): return "error: bad name"
    tree = ast.parse(code)
    if not any(isinstance(n, ast.FunctionDef) and n.name == "run" for n in tree.body): return "error: top-level run() missing"
    path = Path(__file__).parent / f"{name}.py"
    old = path.read_text() if path.exists() else None
    path.write_text(code)
    try:
        importlib.invalidate_caches()
        mod = importlib.import_module(f"openjames.tools.{name}"); importlib.reload(mod)
        assert "function" in mod.TOOL_SCHEMA
    except Exception as e:
        path.write_text(old) if old is not None else path.unlink()
        return f"error: rolled back ({e})"
    return f"ok: tool {name} registered"
