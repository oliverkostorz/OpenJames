import os, httpx
from . import Unavailable, Exhausted
from .. import toolloop

ENV_KEYS = ["OPENROUTER_KEY"]
TOOL_LOOP = True


def run(system, prompt, allowed=None):
    key = os.environ.get("OPENROUTER_KEY")
    if not key: raise Unavailable("OPENROUTER_KEY not set")

    def post(msgs, sch):
        body = {"model": os.environ.get("OPENJAMES_OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5"), "messages": msgs}
        if sch: body["tools"] = sch
        r = httpx.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, timeout=300, json=body)
        if r.status_code in (402, 429): raise Exhausted("openrouter")
        r.raise_for_status()
        return r.json()["choices"][0]["message"]
    return toolloop.openai_loop(post, system, prompt, allowed)
