from . import _cli

ENV_KEYS: list[str] = []


def run(system, prompt):
    return _cli(["codex", "exec", "-"], f"{system}\n\n{prompt}", "codex")
