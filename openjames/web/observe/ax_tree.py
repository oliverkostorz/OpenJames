"""Accessible names/roles from Chrome's accessibility tree (CDP Accessibility domain).

Only queried for elements the DOM heuristics couldn't name (icon-only buttons, <svg>s),
one getPartialAXTree call each, so the cost stays small.
"""

from __future__ import annotations


def ax_info(cdp, object_id: str) -> tuple[str, str]:
    try:
        nodes = cdp.send("Accessibility.getPartialAXTree",
                         {"objectId": object_id, "fetchRelatives": False}).get("nodes", [])
    except Exception:
        return "", ""
    for n in nodes:
        if n.get("ignored"):
            continue
        name = (n.get("name") or {}).get("value") or ""
        role = (n.get("role") or {}).get("value") or ""
        return str(name).strip()[:100], str(role)
    return "", ""


def fill_names(cdp, candidates: list[dict]) -> None:
    for c in candidates:
        if c["kind"] == "el" and not c.get("name") and c.get("objectId"):
            name, role = ax_info(cdp, c["objectId"])
            if name:
                c["name"], c["name_src"] = name, "ax"
            if role and not c.get("role") and role not in ("generic", "none"):
                c["role"] = role
