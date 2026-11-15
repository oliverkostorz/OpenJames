"""What changed between two Observations: URL/title, new/removed elements, value and
checked changes, new visible text (validation errors, toasts, confirmations), JS dialogs.

`diff(before, after, dialogs)` returns a short text block for the model. Elements are
matched by a signature (tag, kind, type, name, frame) because ids are reassigned on every
observe; duplicates are paired in document order.
"""

from __future__ import annotations

from collections import defaultdict

from .element_map import Observation, _line

MAX_ADDED, MAX_REMOVED, MAX_TEXT = 15, 10, 10


def _sig(c: dict) -> tuple:
    return (c["tag"], c.get("type", ""), c.get("role", ""), c.get("name", ""), c.get("frame", 0))


def _group(obs: Observation) -> dict[tuple, list[dict]]:
    g: dict[tuple, list[dict]] = defaultdict(list)
    for c in obs.elements.values():
        g[_sig(c)].append(c)
    return g


def diff(before: Observation | None, after: Observation, dialogs: list[str] | None = None) -> str:
    out: list[str] = []
    for d in dialogs or []:
        out.append(f"! JS dialog (dismissed): {d[:200]}")
    if before is None:
        out.append("(no earlier observation to compare with)")
        return "\n".join(out)
    if after.url != before.url:
        out.append(f"URL changed → {after.url}")
    if after.title != before.title:
        out.append(f'title changed → "{after.title}"')
    if after.scroll[1] != before.scroll[1]:
        out.append(f"scrolled to y={after.scroll[1]} of {after.scroll[3]}")

    vh = after.viewport[1]
    b, a = _group(before), _group(after)
    added, removed, changed = [], [], []
    for sig, news in a.items():
        olds = b.get(sig, [])
        for i, c in enumerate(news):
            if i >= len(olds):
                added.append(c)
                continue
            o = olds[i]
            if o.get("value") != c.get("value") and "value" in c:
                changed.append(f'~ [{c["id"]}] {c.get("name", "")[:40]!r}: value "{o.get("value", "")}" → "{c["value"]}"')
            if o.get("checked") != c.get("checked") and "checked" in c:
                changed.append(f'~ [{c["id"]}] {c.get("name", "")[:40]!r}: {"checked" if c["checked"] else "unchecked"}')
            if o.get("expanded") != c.get("expanded") and "expanded" in c:
                changed.append(f'~ [{c["id"]}] {c.get("name", "")[:40]!r}: {"expanded" if c["expanded"] else "collapsed"}')
            if bool(o.get("disabled")) != bool(c.get("disabled")):
                changed.append(f'~ [{c["id"]}] {c.get("name", "")[:40]!r}: {"disabled" if c.get("disabled") else "enabled"}')
    for sig, olds in b.items():
        removed += olds[len(a.get(sig, [])):]

    if len(added) + len(removed) > 60 and after.url != before.url:
        out.append(f"(new page: {len(after.elements)} elements; see the element map)")
    else:
        out += ["+ " + _line(c, vh) for c in added[:MAX_ADDED]]
        if len(added) > MAX_ADDED:
            out.append(f"+ … {len(added) - MAX_ADDED} more new elements")
        out += ["- " + _line(c, vh).split("] ", 1)[-1] for c in removed[:MAX_REMOVED]]
        if len(removed) > MAX_REMOVED:
            out.append(f"- … {len(removed) - MAX_REMOVED} more removed")
    out += changed

    old_lines = set(before.page_text.splitlines())
    new_text = [ln.strip() for ln in after.page_text.splitlines()
                if ln.strip() and ln not in old_lines and len(ln.strip()) > 1]
    if new_text and not (after.url != before.url and len(new_text) > 30):
        out.append("new text:")
        out += [f"  | {ln[:200]}" for ln in new_text[:MAX_TEXT]]
        if len(new_text) > MAX_TEXT:
            out.append(f"  | … {len(new_text) - MAX_TEXT} more lines")
    if not out:
        out.append("no visible change")
    return "\n".join(out)
