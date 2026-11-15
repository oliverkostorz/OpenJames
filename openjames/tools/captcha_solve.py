"""Tool: captcha_solve — help the assistant get past a CAPTCHA in his own Chrome (standing permission).

the principal allowed solving captchas without asking him each time. This tool covers what can be
done reliably without a paid third-party solver:
  inspect         find the captcha on the open tab: kind (recaptcha/hcaptcha/turnstile/text/math),
                  question text (e.g. "7 + 3 = ?"), the answer input's label, a screenshot path
  click_checkbox  click the "I'm not a robot" / Turnstile / hCaptcha checkbox like a human
                  (mouse glides to it, short pause) and report whether a token/checked state appeared
  screenshot      PNG of the captcha area (image/audio-free: read it yourself, you can see images)
  click_at        click page coordinates (image-grid challenges), humanized
Text and arithmetic captchas: use `inspect`, read the question (or the screenshot), type the
answer with web_act. Image grids: `screenshot`, decide the tiles, `click_at`, then press
Verify with web_act. If it still fails after 3 tries, give up and ask the principal (ask_principal).
"""
import os
import random
import time
from pathlib import Path

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "captcha_solve",
        "description": (
            "Solve a CAPTCHA on a page open in the assistant's Chrome (always allowed, no permission needed). "
            "action=inspect: detect kind + question text + screenshot path; click_checkbox: human-like "
            "click on the reCAPTCHA/hCaptcha/Turnstile checkbox and report the result; screenshot: PNG "
            "of the captcha area to read; click_at: click page x,y (image grids). Type text/math "
            "answers with web_act. After 3 failed tries stop and ask_principal."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["inspect", "click_checkbox", "screenshot", "click_at"]},
                "url_fragment": {"type": "string", "description": "part of the open tab's URL (default: the active/last tab)"},
                "x": {"type": "number", "description": "click_at: page x (CSS px)"},
                "y": {"type": "number", "description": "click_at: page y (CSS px)"},
            },
            "required": ["action"],
        },
    },
}

FRAME_KINDS = (("recaptcha", "recaptcha"), ("hcaptcha", "hcaptcha"),
               ("turnstile", "challenges.cloudflare.com"), ("turnstile", "turnstile"))

PAGE_JS = """() => {
  const out = {text: null, label: null, input: null, img: null};
  const nodes = Array.from(document.querySelectorAll('label, div, span, p, td, legend'));
  for (const n of nodes) {
    const t = (n.innerText || '').trim();
    if (!t || t.length > 200 || n.children.length > 4) continue;
    if (/captcha|rechen|sicherheitsfrage|security question|human verification|what is \\d|wie viel/i.test(t)
        || /^\\s*\\d+\\s*[-+*x×\\/÷]\\s*\\d+\\s*(=|\\?)/.test(t)) {
      out.text = t.replace(/\\s+/g, ' ');
      const inp = n.querySelector('input[type=text],input:not([type])')
        || (n.htmlFor && document.getElementById(n.htmlFor))
        || (n.closest('div,fieldset,form') || document).querySelector('input[type=text],input:not([type])');
      if (inp) out.input = (inp.id || inp.name || inp.placeholder || 'input');
      break;
    }
  }
  const img = document.querySelector('img[src*=captcha i], img[alt*=captcha i], img[id*=captcha i]');
  if (img) out.img = img.src.slice(0, 120);
  return out;
}"""


def _page(browser, frag: str):
    pages = [pg for ctx in browser.contexts for pg in ctx.pages]
    if frag:
        pages = [p for p in pages if frag.lower() in (p.url or "").lower()]
    return pages[-1] if pages else None


def _kind_of_frames(page):
    found = []
    for fr in page.frames:
        u = (fr.url or "").lower()
        for kind, needle in FRAME_KINDS:
            if needle in u:
                found.append((kind, fr))
                break
    return found


def _glide(page, x: float, y: float) -> None:
    sx, sy = random.uniform(80, 400), random.uniform(80, 400)
    page.mouse.move(sx, sy)
    steps = random.randint(18, 30)
    for i in range(1, steps + 1):
        t = i / steps
        e = t * t * (3 - 2 * t)
        page.mouse.move(sx + (x - sx) * e + random.uniform(-1.5, 1.5),
                        sy + (y - sy) * e + random.uniform(-1.5, 1.5))
        time.sleep(random.uniform(0.008, 0.02))
    time.sleep(random.uniform(0.15, 0.4))


def _shot(page, name: str, clip=None) -> str:
    d = Path(__file__).resolve().parent.parent.parent / "state" / "web"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"captcha-{name}-{int(time.time())}.png"
    page.screenshot(path=str(p), clip=clip) if clip else page.screenshot(path=str(p))
    return str(p)


def _solved(page) -> bool:
    try:
        for fr in page.frames:
            u = (fr.url or "").lower()
            if "recaptcha/api2/anchor" in u:
                if fr.locator("#recaptcha-anchor[aria-checked=true]").count():
                    return True
        return bool(page.evaluate(
            "() => Array.from(document.querySelectorAll('textarea[name=g-recaptcha-response],"
            "textarea[name=h-captcha-response],input[name=cf-turnstile-response]')).some(e => e.value && e.value.length > 20)"))
    except Exception:
        return False


def run(arguments: dict):
    from playwright.sync_api import sync_playwright

    action = arguments.get("action")
    if action not in ("inspect", "click_checkbox", "screenshot", "click_at"):
        return {"status": "error", "error": "action must be inspect|click_checkbox|screenshot|click_at"}
    port = int(os.environ.get("OJ_WEB_PORT", "9333"))
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        except Exception as e:
            return {"status": "error", "error": f"cannot attach to Chrome on port {port}: {e}"}
        page = _page(browser, str(arguments.get("url_fragment") or ""))
        if page is None:
            return {"status": "error", "error": "no matching open tab"}
        frames = _kind_of_frames(page)

        if action == "inspect":
            info = page.evaluate(PAGE_JS)
            kinds = sorted({k for k, _ in frames})
            kind = kinds[0] if kinds else ("text" if info.get("text") else None)
            if kind == "text" and info.get("text") and any(c in info["text"] for c in "+-*×x/÷"):
                kind = "math"
            return {"status": "ok", "kind": kind, "frames": kinds, "question": info.get("text"),
                    "answer_input": info.get("input"), "image": info.get("img"),
                    "solved": _solved(page), "url": page.url, "screenshot": _shot(page, "page"),
                    "hint": "text/math: type the answer with web_act; checkbox: click_checkbox; grid: screenshot + click_at"}

        if action == "screenshot":
            return {"status": "ok", "screenshot": _shot(page, "page"), "url": page.url}

        if action == "click_at":
            x, y = arguments.get("x"), arguments.get("y")
            if x is None or y is None:
                return {"status": "error", "error": "x and y required"}
            _glide(page, float(x), float(y))
            page.mouse.down(); time.sleep(random.uniform(0.05, 0.12)); page.mouse.up()
            time.sleep(0.6)
            return {"status": "ok", "clicked": [x, y], "screenshot": _shot(page, "after")}

        # click_checkbox
        if not frames:
            return {"status": "error", "error": "no reCAPTCHA/hCaptcha/Turnstile frame on the page; try inspect"}
        if _solved(page):
            return {"status": "ok", "solved": True, "note": "already solved"}
        for kind, fr in frames:
            if kind == "recaptcha" and "anchor" not in fr.url:
                continue
            try:
                el = fr.frame_element()
                box = el.bounding_box()
                if not box:
                    continue
                el.scroll_into_view_if_needed()
                box = el.bounding_box()
                # checkbox sits at the left of the widget; Turnstile too
                x = box["x"] + min(30, box["width"] * 0.12)
                y = box["y"] + box["height"] / 2
                _glide(page, x, y)
                page.mouse.down(); time.sleep(random.uniform(0.05, 0.12)); page.mouse.up()
                for _ in range(10):
                    time.sleep(0.7)
                    if _solved(page):
                        return {"status": "ok", "solved": True, "kind": kind}
                return {"status": "ok", "solved": False, "kind": kind,
                        "note": "clicked; no token yet — probably an image challenge opened: use screenshot + click_at, then Verify",
                        "screenshot": _shot(page, "after")}
            except Exception as e:
                return {"status": "error", "error": f"{type(e).__name__}: {e}"}
        return {"status": "error", "error": "no clickable captcha frame"}
