"""Question labels for widgets whose visible name is only a placeholder.

react-select (Greenhouse, Lever, …) renders a `div "Select…"` whose real question is not in
its text: it sits in `aria-labelledby` on an inner <input>, or in the `<label>`/`<legend>`
just before the widget. Without this, the element map (and the loop's decider) sees an
anonymous `div "Select…"` and cannot tell which question it belongs to.

Only placeholder-ish names trigger a query, one `Runtime.callFunctionOn` each, so the cost
stays at a handful of round-trips per page. Read-only: nothing is written to the page.
"""

from __future__ import annotations

import re
from pathlib import Path

_JS = (Path(__file__).parent / "label_context.js").read_text()

# Names that carry no information: the widget is still empty, or the text is a prompt.
PLACEHOLDER = re.compile(
    r"^(?:(?:select|choose|auswählen|bitte wählen)"
    r"(?:\s+(?:an?\s+)?(?:option|one|item|value))?"
    r"(?:\s*(?:\.\.\.|…))?"
    r"|-{2,}[^-]{0,40}-{2,}|\.{2,}|…)$",
    re.I,
)


def needs_context(name: str) -> bool:
    """True when `name` says nothing about which question this widget answers."""
    n = (name or "").strip()
    return not n or bool(PLACEHOLDER.match(n))


def resolve(cdp, object_id: str) -> str:
    """Ask the page for the context label of one element; '' if it has none."""
    try:
        res = cdp.send("Runtime.callFunctionOn", {
            "objectId": object_id,
            "functionDeclaration": _JS,
            "returnByValue": True,
            "silent": True,
        })
    except Exception:
        return ""
    val = (res.get("result") or {}).get("value")
    return str(val).strip()[:100] if isinstance(val, str) else ""


def fill_context(cdp, candidates: list[dict]) -> int:
    """Replace placeholder names with their question label, in place. Returns how many.

    Runs after the DOM snapshot (which knows the object ids) and before the AX fallback,
    so an unnamed element still gets a chance at a real accessible name later.
    """
    n = 0
    for c in candidates:
        if c.get("kind") != "el" or not c.get("objectId"):
            continue
        name = c.get("name") or ""
        if not needs_context(name):
            continue
        better = resolve(cdp, c["objectId"])
        if better and better.lower() != name.strip().lower():
            c["name"], c["name_src"] = better, "context"
            n += 1
    return n
