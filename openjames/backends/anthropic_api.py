import os, httpx
from . import Unavailable, Exhausted

ENV_KEYS = ["ANTHROPIC_API_KEY"]


def run(system, prompt):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key: raise Unavailable("ANTHROPIC_API_KEY not set")
    r = httpx.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": key, "anthropic-version": "2023-06-01"}, timeout=300,
                   json={"model": os.environ.get("OPENJAMES_ANTHROPIC_MODEL", "claude-sonnet-4-5"), "max_tokens": 8192,
                         "system": system, "messages": [{"role": "user", "content": prompt}]})
    if r.status_code in (402, 429): raise Exhausted("anthropic_api")
    r.raise_for_status()
    return r.json()["content"][0]["text"]
