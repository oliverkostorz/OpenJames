"""Run dom_snapshot.js in the page over a raw CDP session and return candidates.

`cdp` is anything with `.send(method, params) -> dict` (Playwright's CDPSession).
Each candidate dict gets an `objectId` so later steps (listeners, AX names, P2 actions)
can address the exact DOM node without tagging the page.

After the ids are in place, `labels.fill_context` replaces placeholder-only names
(`div "Select…"`) with the question they belong to, so callers see "Country of residence".
"""

from __future__ import annotations

import json
from pathlib import Path

from . import labels

_JS = (Path(__file__).parent / "dom_snapshot.js").read_text()
OBJECT_GROUP = "td-observe"


def snapshot(cdp) -> dict:
    # Drop handles from the previous observation so the page doesn't accumulate them.
    try:
        cdp.send("Runtime.releaseObjectGroup", {"objectGroup": OBJECT_GROUP})
    except Exception:
        pass
    res = cdp.send("Runtime.evaluate", {
        "expression": _JS,
        "objectGroup": OBJECT_GROUP,
        "returnByValue": False,
        "awaitPromise": False,
    })
    if "exceptionDetails" in res:
        raise RuntimeError(f"dom_snapshot.js failed: {res['exceptionDetails'].get('text')}")
    root = res["result"]["objectId"]

    data = cdp.send("Runtime.callFunctionOn", {
        "objectId": root,
        "functionDeclaration": "function(){const {els, ...rest} = this; return JSON.stringify(rest);}",
        "returnByValue": True,
    })["result"]["value"]
    page = json.loads(data)

    els_obj = cdp.send("Runtime.callFunctionOn", {
        "objectId": root,
        "functionDeclaration": "function(){return this.els;}",
        "objectGroup": OBJECT_GROUP,
        "returnByValue": False,
    })["result"]["objectId"]
    props = cdp.send("Runtime.getProperties", {"objectId": els_obj, "ownProperties": True})["result"]
    ids: dict[int, str] = {}
    for p in props:
        if p["name"].isdigit() and "objectId" in p.get("value", {}):
            ids[int(p["name"])] = p["value"]["objectId"]
    for i, cand in enumerate(page["info"]):
        cand["objectId"] = ids.get(i)
    try:
        page["context_labels"] = labels.fill_context(cdp, page["info"])
    except Exception:
        page["context_labels"] = 0     # never let label enrichment break an observation
    return page
