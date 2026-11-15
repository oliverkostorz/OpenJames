import datetime as dt
from .. import guards
from ..paths import MEMORY
from . import notify_principal

TOOL_SCHEMA = {"type": "function", "function": {"name": "ask_principal",
    "description": "Ask the principal a question only they can answer (consent, choice, missing detail): pushes a short ACTION NEEDED message and records it in memory/open-questions.md so it is never buried. Use before any external/irreversible action that was not explicitly approved.",
    "parameters": {"type": "object", "properties": {"question": {"type": "string"}, "options": {"type": "string", "description": "answer format, e.g. 'yes / no'"}}, "required": ["question"]}}}


def run(a):
    qid = "Q-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    line = f"{qid}: {a['question']}" + (f" (answer: {a['options']})" if a.get("options") else "")
    r = notify_principal.run({"text": "ACTION NEEDED\n" + line + "\nReply starting with the id."})
    if r.get("status") != "queued": return r
    f = MEMORY / "open-questions.md"; f.parent.mkdir(exist_ok=True)
    with f.open("a") as o: o.write(f"- OPEN {line}\n")
    return {"id": qid, **r}
