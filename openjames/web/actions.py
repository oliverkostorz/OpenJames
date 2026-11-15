"""High-level verbs by element id from the session's last Observation, built on humanize/.

    perform(session, "type", "e7", {"text": "the principal"})  -> "typed 6 chars into e7"

Verbs: click, type, select, check, uncheck, upload, hover, scroll, press, wait, back.
Each verb re-measures the element right before acting (pages move), wheel-scrolls it into
view, refuses to click through an overlay, and verifies its own effect where it can
(typed value, checked state, selected option). Errors are raised as ActionError with a
message meant for the model ("covered by div 'Cookie banner' — close it first").
"""

from __future__ import annotations

import os
from pathlib import Path

from .humanize import scroll, timing

ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIRS = [Path(p).expanduser().resolve() for p in os.environ.get(
    "OJ_WEB_UPLOAD_DIRS", f"~/.openjames/uploads{os.pathsep}{ROOT / 'tests' / 'web_fixtures'}").split(os.pathsep) if p]
VERBS = ("click", "type", "select", "check", "uncheck", "upload", "hover", "scroll", "press", "wait", "back")


class ActionError(Exception):
    pass


# --- element helpers ---------------------------------------------------------------------
def _el(session, target: str | None) -> dict:
    if not target:
        raise ActionError("this verb needs a target element id (e.g. e7)")
    if session.last is None:
        raise ActionError("no element map yet: call web_observe first")
    c = session.last.elements.get(target)
    if c is None or not c.get("objectId"):
        raise ActionError(f"unknown element {target!r} in the last observation; observe again")
    return c


def _call(session, c: dict, fn: str, args: list | None = None):
    try:
        r = session.cdp.send("Runtime.callFunctionOn", {
            "objectId": c["objectId"], "functionDeclaration": fn, "returnByValue": True,
            "arguments": [{"value": a} for a in (args or [])]})
    except Exception as e:
        raise ActionError(f"element {c['id']} is gone from the page ({e}); observe again") from e
    if "exceptionDetails" in r:
        raise ActionError(f"page script error: {r['exceptionDetails'].get('text')}")
    return r["result"].get("value")


def box(session, c: dict) -> list[float]:
    """Current [x, y, w, h] in main-viewport CSS px (works inside same-origin iframes)."""
    try:
        quads = session.cdp.send("DOM.getContentQuads", {"objectId": c["objectId"]})["quads"]
    except Exception as e:
        raise ActionError(f"element {c['id']} is gone or not rendered ({e}); observe again") from e
    if not quads:
        raise ActionError(f"element {c['id']} has no visible box (hidden or zero-size)")
    q = max(quads, key=lambda q: abs((q[2] - q[0]) * (q[5] - q[1])))
    xs, ys = q[0::2], q[1::2]
    return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]


HIT_JS = """function(x, y) {
  const root = this.getRootNode();
  const hit = (root && root.elementFromPoint ? root : document).elementFromPoint(x, y);
  if (!hit) return null;
  if (hit === this || this.contains(hit) || hit.contains(this)) return null;
  const lab = hit.closest && hit.closest('label');
  if (lab && (lab.control === this || lab.contains(this))) return null;
  if (this.labels && Array.from(this.labels).some(l => l.contains(hit))) return null;
  // Workday-style transparent click capture layer: sibling inside the same parent, same accessible name.
  if (hit.getAttribute('data-automation-id') === 'click_filter' && hit.parentElement && hit.parentElement.contains(this)) return null;
  return hit.tagName.toLowerCase() + ' ' + JSON.stringify((hit.innerText || hit.getAttribute('aria-label') || '').trim().slice(0, 60));
}"""


def _approach(session, c: dict) -> tuple[float, float, list[float]]:
    """Scroll into view, pick a human click point, check nothing covers it."""
    vh = session.last.viewport[1] if session.last else 800
    b = scroll.into_view(session.mouse, lambda: box(session, c), vh)
    x, y = session.mouse.target_point(b)
    if not c.get("frame"):
        blocker = _call(session, c, HIT_JS, [x, y])
        if blocker:
            raise ActionError(f"{c['id']} is covered by {blocker} — deal with that first (close/scroll)")
    return x, y, b


def _click(session, c: dict, count: int = 1) -> None:
    if c.get("disabled"):
        raise ActionError(f"{c['id']} is disabled")
    x, y, b = _approach(session, c)
    session.mouse.click(x, y, min(b[2], b[3]), count)


# --- verbs -------------------------------------------------------------------------------
def click(session, target, args) -> str:
    c = _el(session, target)
    _click(session, c, 2 if args.get("double") else 1)
    return f"clicked {target}"


def hover(session, target, args) -> str:
    c = _el(session, target)
    x, y, b = _approach(session, c)
    session.mouse.move_to(x, y, min(b[2], b[3]))
    timing.sleep(session.persona.lognormal(0.4, 0.3))
    return f"hovering over {target}"


def type_(session, target, args) -> str:
    c = _el(session, target)
    text = str(args.get("text", ""))
    clear = args.get("clear", True)
    focused = _call(session, c, "function(){const r=this.getRootNode(); return (r.activeElement||document.activeElement)===this;}")
    if not focused:
        _click(session, c)
    timing.sleep(session.persona.lognormal(0.2, 0.3))
    cur = _call(session, c, "function(){return this.isContentEditable ? this.innerText : (this.value ?? '');}") or ""
    if clear and cur:
        session.kb.select_all_and_delete()
    session.kb.type(text)
    got = _call(session, c, "function(){return this.isContentEditable ? this.innerText : (this.value ?? '');}") or ""
    want = text if clear or not cur else cur + text
    note = ""
    if got.replace("\r", "") != want and got.strip() != want.strip():
        # Masked/formatted inputs legitimately reformat (phone, dates); report, don't fight.
        note = f" (field now shows {got[:80]!r}; it may reformat input — check it)"
    if args.get("enter"):
        session.kb.press("Enter")
    return f"typed {len(text)} chars into {target}{note}"


SELECT_JS = """function(opt) {
  if (this.tagName !== 'SELECT') return {custom: true};
  const o = Array.from(this.options);
  const norm = s => (s || '').trim().toLowerCase();
  let i = o.findIndex(x => norm(x.text) === norm(opt) || norm(x.value) === norm(opt));
  if (i < 0) i = o.findIndex(x => norm(x.text).includes(norm(opt)));
  if (i < 0) return {error: 'no option matching ' + JSON.stringify(opt) + '; options: ' + o.map(x => x.text.trim()).slice(0, 30).join(' | ')};
  this.focus();
  if (this.selectedIndex !== i) {
    this.selectedIndex = i;
    this.dispatchEvent(new Event('input', {bubbles: true}));
    this.dispatchEvent(new Event('change', {bubbles: true}));
  }
  return {chosen: o[i].text.trim()};
}"""

# Custom dropdowns (react-select, SuccessFactors/Workday div selects, ARIA comboboxes): the
# options only exist while the popup is open, often in a portal at the end of <body>.
# mode 'find' -> the matching option element (or null); mode 'list' -> visible option texts.
OPTIONS_JS = """function(opt, mode) {
  const norm = s => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
  const vis = el => { const r = el.getBoundingClientRect(), st = getComputedStyle(el);
                      return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none'; };
  const doc = this.ownerDocument, root = this.getRootNode();
  const owners = [this, ...this.querySelectorAll('[aria-controls],[aria-owns]')];
  const box = this.closest('[role=combobox],[aria-haspopup]');
  if (box) owners.push(box);
  const pools = [];
  for (const el of owners) for (const a of ['aria-controls', 'aria-owns']) {
    for (const id of (el.getAttribute(a) || '').split(/\\s+/).filter(Boolean)) {
      const lb = (root.getElementById && root.getElementById(id)) || doc.getElementById(id);
      if (lb && vis(lb) && !pools.includes(lb)) pools.push(lb);
    }
  }
  let opts = [];
  for (const p of pools) opts.push(...p.querySelectorAll('[role=option]'));
  if (!opts.length) for (const p of pools) opts.push(...p.querySelectorAll('li, [class*=option]'));
  if (!opts.length) opts = Array.from(doc.querySelectorAll('[role=option]'));
  if (!opts.length) opts = Array.from(doc.querySelectorAll(
    '[role=listbox] li, [role=menu] [role=menuitem], ul[class*=menu] li, ul[class*=dropdown] li, ' +
    'ul[class*=option] li, ul[class*=select] li, [class*=menu] [class*=option]'));
  opts = opts.filter(o => vis(o) && norm(o.innerText) && o.getAttribute('aria-disabled') !== 'true');
  if (mode === 'list') return opts.map(o => o.innerText.replace(/\\s+/g, ' ').trim().slice(0, 60)).slice(0, 40);
  const want = norm(opt);
  const hit = opts.find(o => norm(o.innerText) === want || norm(o.getAttribute('data-value')) === want)
           || opts.find(o => norm(o.innerText).startsWith(want))
           || opts.find(o => norm(o.innerText).includes(want));
  if (hit) hit.scrollIntoView({block: 'nearest'});
  return hit || null;
}"""

SHOWN_JS = """function() {
  const box = this.closest('[role=combobox],[aria-haspopup]') || this;
  return [box.innerText, box.value, ...Array.from(box.querySelectorAll('input')).map(i => i.value)]
    .filter(Boolean).join(' ').replace(/\\s+/g, ' ').trim();
}"""


def _find_option(session, c: dict, opt: str) -> str | None:
    try:
        r = session.cdp.send("Runtime.callFunctionOn", {
            "objectId": c["objectId"], "functionDeclaration": OPTIONS_JS, "returnByValue": False,
            "arguments": [{"value": opt}, {"value": "find"}]})
    except Exception as e:
        raise ActionError(f"element {c['id']} is gone from the page ({e}); observe again") from e
    return (r.get("result") or {}).get("objectId")


def _select_custom(session, c: dict, target: str, opt: str) -> str:
    """Open a non-native dropdown, click the option whose text matches, verify what it shows."""
    if not opt.strip():
        raise ActionError("select needs an option text")
    oid = _find_option(session, c, opt)                # popup may already be open
    opened = False
    if not oid:
        _click(session, c)
        opened = True
        for _ in range(12):                            # options render/fetch asynchronously
            timing.sleep(0.25)
            oid = _find_option(session, c, opt)
            if oid:
                break
    if not oid:
        seen = _call(session, c, OPTIONS_JS, [opt, "list"]) or []
        if opened and seen:
            session.kb.press("Escape")                 # don't leave the popup covering the form
        if not seen:
            raise ActionError(f"{target} is not a <select> and opened no option list; click it and observe")
        raise ActionError(f"no option matching {opt!r} in {target}; options: {' | '.join(seen)}")
    o = {"id": f"option of {target}", "objectId": oid}
    timing.sleep(session.persona.lognormal(0.4, 0.3))  # read the list
    label = (_call(session, o, "function(){return this.innerText.replace(/\\s+/g, ' ').trim();}") or opt)[:80]
    b = box(session, o)
    x, y = session.mouse.target_point(b)
    blocker = None if c.get("frame") else _call(session, o, HIT_JS, [x, y])
    if blocker:
        raise ActionError(f"option {label!r} of {target} is covered by {blocker}")
    session.mouse.click(x, y, min(b[2], b[3]), 1)
    timing.sleep(0.3)
    shown = _call(session, c, SHOWN_JS) or ""
    if label.lower() in shown.lower():
        return f"selected {label!r} in {target}"
    return f"clicked option {label!r} of {target} (the field now shows {shown[:60]!r} — check it)"


def select(session, target, args) -> str:
    c = _el(session, target)
    if c.get("disabled"):
        raise ActionError(f"{target} is disabled")
    opt = str(args.get("option", ""))
    r = _call(session, c, "function(){return {custom: this.tagName !== 'SELECT'};}") or {}
    if r.get("custom"):
        return _select_custom(session, c, target, opt)
    # Move there and dwell like a person reading the options; the native popup itself is
    # not part of the DOM, so the choice is set directly (with input/change events).
    x, y, b = _approach(session, c)
    session.mouse.move_to(x, y, min(b[2], b[3]))
    timing.sleep(session.persona.lognormal(0.5, 0.4))
    r = _call(session, c, SELECT_JS, [opt]) or {}
    if r.get("error"):
        raise ActionError(r["error"])
    return f"selected {r['chosen']!r} in {target}"


def check(session, target, args, want: bool = True) -> str:
    c = _el(session, target)
    state = _call(session, c, "function(){return 'checked' in this && this.type ? this.checked : this.getAttribute('aria-checked') === 'true';}")
    if bool(state) == want:
        return f"{target} already {'checked' if want else 'unchecked'}"
    _click(session, c)
    timing.sleep(0.05)
    state = _call(session, c, "function(){return 'checked' in this && this.type ? this.checked : this.getAttribute('aria-checked') === 'true';}")
    if bool(state) != want:
        raise ActionError(f"clicked {target} but it is still {'checked' if state else 'unchecked'}")
    return f"{'checked' if want else 'unchecked'} {target}"


# A styled upload widget (SuccessFactors, Workday, …) hides the real <input type=file>
# behind a div/button, so the input never shows up in the element map. Look inside the
# widget, then in the nearest ancestors that contain exactly ONE such input (that is the
# slot belonging to this widget — never a different document slot on the same form).
SCRIPT_FIND_FILE = """function() {
  const own = this.querySelector && this.querySelector('input[type=file]');
  if (own) return own;
  if (this.tagName === 'INPUT' && this.type === 'file') return this;
  let n = this.parentElement;
  for (let i = 0; i < 4 && n && n.tagName !== 'FORM' && n.tagName !== 'BODY'; i++, n = n.parentElement) {
    const all = n.querySelectorAll ? Array.from(n.querySelectorAll('input[type=file]')) : [];
    if (all.length === 1) return all[0];
  }
  return null;
}"""

SCRIPT_ONLY_FILE = """function() {
  const r = this.getRootNode ? this.getRootNode() : document;
  const all = Array.from((r.querySelectorAll ? r : document).querySelectorAll('input[type=file]'));
  return all.length === 1 ? all[0] : null;
}"""


def _object_id(session, c: dict, fn: str) -> str | None:
    try:
        return session.cdp.send("Runtime.callFunctionOn", {
            "objectId": c["objectId"], "functionDeclaration": fn,
            "returnByValue": False}).get("result", {}).get("objectId")
    except Exception:            # noqa: BLE001 - a stale node is handled by the caller
        return None


def upload(session, target, args) -> str:
    c = _el(session, target)
    p = Path(str(args.get("path", ""))).expanduser().resolve()
    if not any(p.is_relative_to(d) for d in UPLOAD_DIRS):
        raise ActionError(f"uploads are only allowed from {', '.join(map(str, UPLOAD_DIRS))}")
    if not p.is_file():
        raise ActionError(f"no such file: {p}")

    if c.get("type") == "file":
        session.cdp.send("DOM.setFileInputFiles", {"files": [str(p)], "objectId": c["objectId"]})
        return f"attached {p.name} to {target}"

    # 1) a hidden input[type=file] inside or next to the widget (SuccessFactors keeps one
    #    per document slot; Workday replaces it after every upload)
    found = _object_id(session, c, SCRIPT_FIND_FILE)
    if found:
        session.cdp.send("DOM.setFileInputFiles", {"files": [str(p)], "objectId": found})
        return f"attached {p.name} to the file input behind {target}"

    # 2) the widget creates the input on click and opens the OS file picker — intercept it
    note = ""
    try:
        with session.page.expect_file_chooser(timeout=8000) as fc:
            _click(session, c)
        fc.value.set_files(str(p))
        return f"attached {p.name} via the file picker opened by {target}"
    except ActionError:
        raise
    except Exception as e:       # noqa: BLE001 - no picker opened, try the last resort
        note = str(e)

    # 3) last resort: the only file input on the page
    found = _object_id(session, c, SCRIPT_ONLY_FILE)
    if found:
        session.cdp.send("DOM.setFileInputFiles", {"files": [str(p)], "objectId": found})
        return f"attached {p.name} to the page's only file input (from {target})"
    raise ActionError(f"{target} is not a file input and no file input could be found near it ({note})")


def scroll_(session, target, args) -> str:
    if target:
        c = _el(session, target)
        vh = session.last.viewport[1]
        scroll.into_view(session.mouse, lambda: box(session, c), vh)
        return f"scrolled {target} into view"
    vh = session.last.viewport[1] if session.last else 800
    direction = args.get("direction", "down")
    amount = float(args.get("amount") or vh * session.persona.rng.uniform(0.7, 0.9))
    if session.mouse.y > vh or session.mouse.y < 0:
        session.mouse.move_to(session.last.viewport[0] / 2 if session.last else 400, vh / 2)
    scroll.scroll_by(session.mouse, amount if direction == "down" else -amount)
    return f"scrolled {direction} ~{int(amount)}px"


def press(session, target, args) -> str:
    key = str(args.get("key", ""))
    if target:
        c = _el(session, target)
        _call(session, c, "function(){this.focus();}")
    session.kb.press(key)
    return f"pressed {key}"


def wait(session, target, args) -> str:
    sec = min(float(args.get("seconds", 1.0)), 10.0)
    timing.sleep(sec)
    return f"waited {sec:.1f}s"


def back(session, target, args) -> str:
    session.page.go_back(wait_until="domcontentloaded", timeout=30000)
    return "went back"


_DISPATCH = {"click": click, "hover": hover, "type": type_, "select": select,
             "check": lambda s, t, a: check(s, t, a, True), "uncheck": lambda s, t, a: check(s, t, a, False),
             "upload": upload, "scroll": scroll_, "press": press, "wait": wait, "back": back}


def perform(session, verb: str, target: str | None, args: dict | None = None) -> str:
    if verb not in _DISPATCH:
        raise ActionError(f"unknown verb {verb!r}; use one of {', '.join(VERBS)}")
    timing.think(session.persona, 0.35)
    return _DISPATCH[verb](session, target, args or {})
