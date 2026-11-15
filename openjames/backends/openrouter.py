import os, httpx
from . import Unavailable, Exhausted

ENV_KEYS = ["OPENROUTER_KEY"]


def run(system, prompt):
    key = os.environ.get("OPENROUTER_KEY")
    if not key: raise Unavailable("OPENROUTER_KEY not set")
    r = httpx.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, timeout=300,
                   json={"model": os.environ.get("OPENJAMES_OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5"),
                         "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]})
    if r.status_code in (402, 429): raise Exhausted("openrouter")
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
