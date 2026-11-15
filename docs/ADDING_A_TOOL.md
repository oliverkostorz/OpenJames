# Adding a tool
Create `openjames/tools/<name>.py` with an OpenAI-style `TOOL_SCHEMA` and `run(arguments)`. It is registered on next import. The assistant can do this itself with the `create_tool` tool; review generated tools before trusting them, there is no sandbox.
