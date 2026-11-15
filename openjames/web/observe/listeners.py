"""Which DOM nodes really react to input? (CDP DOMDebugger.getEventListeners)

Catches "buttons" that are plain <div>s with a JS handler. Limitation: handlers delegated to
document/window (most React apps) don't show up on the node itself; dom_snapshot.js covers
React separately via its __reactProps keys.
"""

from __future__ import annotations

ACTIVE_EVENTS = {
    "click", "dblclick", "mousedown", "mouseup", "pointerdown", "pointerup", "touchstart",
    "touchend", "keydown", "keyup", "keypress", "input", "change", "submit",
}


def active_events(cdp, object_id: str) -> list[str]:
    try:
        res = cdp.send("DOMDebugger.getEventListeners", {"objectId": object_id, "depth": 0})
    except Exception:
        return []
    return sorted({l["type"] for l in res.get("listeners", []) if l["type"] in ACTIVE_EVENTS})


def confirm(cdp, candidates: list[dict]) -> list[dict]:
    """Annotate every candidate with `events`; drop 'maybe' candidates nobody listens to."""
    kept = []
    for c in candidates:
        if c["kind"] in ("el", "maybe") and c.get("objectId"):
            c["events"] = active_events(cdp, c["objectId"])
        if c["kind"] == "maybe":
            if not c.get("events"):
                continue
            c["kind"], c["via"] = "el", "listener"
        kept.append(c)
    return kept
