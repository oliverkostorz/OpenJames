"""Self-extending tool registry. Drop a module with TOOL_SCHEMA (OpenAI-style) and run(arguments) here;
it is discovered at runtime. See docs/ADDING_A_TOOL.md."""
import importlib, pkgutil

def _modules():
    for m in pkgutil.iter_modules(__path__):
        if not m.name.startswith("_"):
            mod = importlib.import_module(f"{__name__}.{m.name}")
            if hasattr(mod, "TOOL_SCHEMA") and hasattr(mod, "run"): yield mod

def get_tool_schemas(): return [m.TOOL_SCHEMA for m in _modules()]

def call_tool(name, arguments):
    for m in _modules():
        if m.TOOL_SCHEMA["function"]["name"] == name: return m.run(arguments)
    raise KeyError(name)
