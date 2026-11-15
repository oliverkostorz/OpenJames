TOOL_SCHEMA = {"type": "function", "function": {"name": "list_tools", "description": "List all registered tools.", "parameters": {"type": "object", "properties": {}}}}

def run(arguments):
    from . import get_tool_schemas
    return [f"{s['function']['name']}: {s['function']['description']}" for s in get_tool_schemas()]
