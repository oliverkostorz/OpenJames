# AGENTS.md: conventions for humans and for OpenJames when it edits itself
- Channels: `openjames/channels/<name>.py`, subclass `Channel`, export `CHANNEL`, list in `config.CHANNELS`. See docs/CONVENTIONS.md.
- Backends: `openjames/backends/<name>.py` with `run(system, prompt)` and `ENV_KEYS`; raise `Unavailable`/`Exhausted`.
- Tools: `openjames/tools/<name>.py` with `TOOL_SCHEMA` + `run(arguments)`; auto-discovered.
- Privacy: no secrets, ids, addresses or phone numbers in tracked files. Secrets only in `.env`; choices in `config.toml`. Run `uv run python tests/test_guards.py` before committing.
- Changes ship with an assert-script test in `tests/`. Unapproved external actions are forbidden.
- **Tool-first rule:** every feature/capability must be a registry tool callable by the API backends' tool loop (`openjames/toolloop.py`), never CLI-only. CLIs use the same tools via `python -m openjames.toolcli`. Backends with a loop set `TOOL_LOOP = True` and `run(system, prompt, allowed=None)`.
