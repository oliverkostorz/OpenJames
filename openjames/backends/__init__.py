"""Model backends and the fallback chain.

A backend is `run(system: str, prompt: str) -> str`. It raises `Unavailable` when it cannot run
(CLI missing, no key) and `Exhausted` when its quota/budget is used up; the chain then moves to the
next backend in the user's configured priority order.
"""
from __future__ import annotations
import importlib, os, shutil, subprocess


class Unavailable(RuntimeError): ...
class Exhausted(RuntimeError): ...


def _cli(cmd: list[str], stdin: str, name: str) -> str:
    if not shutil.which(cmd[0]): raise Unavailable(f"{cmd[0]} not on PATH")
    env = {k: v for k, v in os.environ.items() if not k.endswith("API_KEY")}  # subscription CLIs must not bill API keys
    p = subprocess.run(cmd, input=stdin, capture_output=True, text=True, env=env, timeout=3600)
    if p.returncode:
        err = (p.stderr or p.stdout).lower()
        if any(s in err for s in ("rate limit", "quota", "429", "usage limit")): raise Exhausted(name)
        raise RuntimeError(f"{name} failed: {p.stderr[-500:]}")
    return p.stdout.strip()


def run_chain(order: list[str], system: str, prompt: str) -> tuple[str, str]:
    """Try backends in order; return (backend_name, reply)."""
    errors = []
    for name in order:
        try:
            return name, importlib.import_module(f"openjames.backends.{name}").run(system, prompt)
        except (Unavailable, Exhausted) as e:
            errors.append(f"{name}: {e!r}")
    raise RuntimeError("all backends unavailable: " + "; ".join(errors))
