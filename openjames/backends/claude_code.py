from . import _cli

ENV_KEYS: list[str] = []  # uses the local `claude` CLI login


def run(system, prompt):
    return _cli(["claude", "-p", "--append-system-prompt", system, "--permission-mode", "acceptEdits"], prompt, "claude_code")
