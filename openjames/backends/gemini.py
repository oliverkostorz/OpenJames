from . import _cli

ENV_KEYS: list[str] = []


def run(system, prompt):
    return _cli(["gemini", "-p", f"{system}\n\n{prompt}"], "", "gemini")
