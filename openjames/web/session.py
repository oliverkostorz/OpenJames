"""Browser session owned by the daemon: Playwright attached to real Chrome over CDP.

Holds the current page, its raw CDP session and the last Observation (id -> node map), so
consecutive tool calls see the same tabs and can refer to ids from the last observe.

`observe()` also returns a compact, picklable view of the page (`url`, `title`, `page_text`,
`elements` = id -> {name, tag, type, submit, disabled}) so callers in *other* processes — the
web-agent loop — can gate on the submit flag without holding CDP handles.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from . import chrome
from .humanize.keyboard import Keyboard
from .humanize.mouse import Mouse
from .humanize.rng import Persona
from .observe.diff import diff
from .observe.element_map import Observation, compact, observe

ALLOWED_SCHEMES = {"http", "https", "file", "about"}
TABS_FILE = chrome.LOG_DIR / "tabs.json"   # tab name -> last URL, survives daemon restarts


ZOMBIE_MARKERS = ("browser context management is not supported", "targetclosed",
                  "target closed", "browser has been closed")


def is_zombie_error(e: BaseException) -> bool:
    m = str(e).lower()
    return any(k in m for k in ZOMBIE_MARKERS) or type(e).__name__ == "TargetClosedError"


class Session:
    def __init__(self, port: int = chrome.PORT, headless: bool | None = None,
                 profile: Path = chrome.PROFILE_DIR):
        self.port, self.headless, self.profile = port, headless, profile
        if getattr(self, "_stream", None) is not None:
            self._stream.close()
        self._pw = self._browser = self.page = self.cdp = self._stream = None
        self.mouse = self.kb = None
        self._proxy = None
        self.last: Observation | None = None
        self.persona = Persona.new()
        self.mouse: Mouse | None = None
        self.kb: Keyboard | None = None
        self.dialogs: list[str] = []
        self._cookies: list[dict] = []
        self._tabs: dict[str, object] = {}     # task/tab name -> Page (one tab per task)
        self._lasts: dict[int, Observation | None] = {}

    # --- connection -------------------------------------------------------------------
    def ensure(self) -> None:
        if self._browser is not None and self._browser.is_connected() and self.page and not self.page.is_closed():
            return
        from playwright.sync_api import sync_playwright
        chrome.launch(self.port, self.profile, headless=self.headless)
        if self._pw is None:
            self._pw = sync_playwright().start()
        try:
            ctx = self._attach()
        except Exception as e:
            if not is_zombie_error(e):
                raise
            # Chrome answers /json/version but won't take a Playwright attach: replace it,
            # then put back the session cookies we last saw (they die with the process).
            self._browser = None
            chrome.restart(self.port, self.profile, headless=self.headless)
            ctx = self._attach()
            if self._cookies:
                try:
                    ctx.add_cookies(self._cookies)
                except Exception:
                    pass
        pages = [p for p in ctx.pages if not p.is_closed()]
        self._use(pages[-1] if pages else ctx.new_page())

    def _attach(self):
        if self._browser is None or not self._browser.is_connected():
            if self._proxy is None:
                from .cdp_proxy import CdpProxy
                self._proxy = CdpProxy(self.port)
                self._proxy.start()
            self._browser = self._pw.chromium.connect_over_cdp(self._proxy.url)
        return self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()

    def _snapshot_cookies(self) -> None:
        try:
            self._cookies = self.page.context.cookies()
        except Exception:
            pass

    def _use(self, page) -> None:
        self.page = page
        self.cdp = page.context.new_cdp_session(page)
        self.last = None
        start = (self.mouse.x, self.mouse.y) if self.mouse else (
            self.persona.rng.uniform(300, 900), self.persona.rng.uniform(200, 600))
        if getattr(self, "_stream", None) is not None:
            self._stream.close()
        try:
            from .cdp_ws import for_page
            self._stream = for_page(self.cdp, self.port)
        except Exception:
            self._stream = None     # falls back to acked events via Playwright
        self.mouse = Mouse(self.cdp, self.persona, start, self._stream)
        self.kb = Keyboard(self.cdp, self.persona)
        page.on("dialog", self._on_dialog)

    def _on_dialog(self, dialog) -> None:
        # alert/confirm/prompt block the page; record for the diff and dismiss (never "OK"
        # a confirm the model didn't see).
        self.dialogs.append(f"{dialog.type}: {dialog.message}")
        try:
            dialog.dismiss()
        except Exception:
            pass

    def close(self, quit_chrome: bool = False) -> None:
        try:
            if quit_chrome and self._browser is not None and self._browser.is_connected():
                self._browser.new_browser_cdp_session().send("Browser.close")
        except Exception:
            pass
        for obj in (self._browser,):
            try:
                obj and obj.close()   # disconnects; Chrome itself keeps running
            except Exception:
                pass
        if self._pw is not None:
            self._pw.stop()
        if getattr(self, "_stream", None) is not None:
            self._stream.close()
        self._pw = self._browser = self.page = self.cdp = self._stream = None
        self.mouse = self.kb = None

    # --- verbs ------------------------------------------------------------------------
    def tabs(self) -> list[dict]:
        self.ensure()
        return [{"index": i, "url": p.url, "current": p == self.page}
                for i, p in enumerate(self.page.context.pages)]

    def select_tab(self, name: str) -> bool:
        """Work in the tab owned by `name`, opening a fresh one on first use (returns True if new).
        Tasks that wait for the principal keep their tab, so a second task never navigates over it."""
        self.ensure()
        page = self._tabs.get(name)
        if page is None or page.is_closed():
            page = self._readopt(name)
        new = page is None or page.is_closed()
        if new:
            page = self.page.context.new_page()
            self._tabs[name] = page
        if page is not self.page:
            if self.page is not None:
                self._lasts[id(self.page)] = self.last
            self._use(page)
            self.last = self._lasts.get(id(page))
            try:
                page.bring_to_front()
            except Exception:
                pass
        self._current_tab = name
        self._save_tabs()
        return new

    def _readopt(self, name: str):
        """After a daemon restart: find an open page whose URL equals the one saved for `name`."""
        try:
            url = json.loads(TABS_FILE.read_text()).get(name)
        except Exception:
            return None
        if not url or url == "about:blank":
            return None
        taken = {id(p) for p in self._tabs.values()}
        for p in self.page.context.pages:
            if not p.is_closed() and p.url == url and id(p) not in taken:
                self._tabs[name] = p
                return p
        return None

    def _save_tabs(self) -> None:
        try:
            data = {n: p.url for n, p in self._tabs.items() if not p.is_closed()}
            TABS_FILE.parent.mkdir(parents=True, exist_ok=True)
            TABS_FILE.write_text(json.dumps(data))
        except Exception:
            pass

    def close_tab(self, name: str) -> bool:
        """Close the tab of a finished task (never the last tab: Chrome would quit)."""
        page = self._tabs.pop(name, None)
        self._save_tabs()
        if page is None or page.is_closed():
            return False
        self.ensure()
        pages = [p for p in page.context.pages if not p.is_closed()]
        if len(pages) <= 1:
            return False
        was_current = page is self.page
        self._lasts.pop(id(page), None)
        page.close()
        if was_current:
            rest = [p for p in page.context.pages if not p.is_closed()]
            self._use(rest[-1])
        return True

    def navigate(self, url: str, timeout_ms: int = 30000) -> dict:
        scheme = urlparse(url).scheme
        if scheme not in ALLOWED_SCHEMES:
            raise ValueError(f"refusing URL scheme {scheme!r}")
        self.ensure()
        resp = self.page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            self.page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass   # long-polling sites never go idle; the DOM is there
        self.last = None
        self._save_tabs()
        return {"url": self.page.url, "status": resp.status if resp else None}

    def observe(self, max_elements: int = 150, include_text: bool = False,
                max_text: int = 3000, screenshot: bool = False,
                view: str = "map", find: str = "") -> dict:
        self.ensure()
        t0 = time.monotonic()
        obs = observe(self.cdp)
        self.last = obs
        self._snapshot_cookies()
        self._save_tabs()
        if view == "auto":  # V6: small page -> full map, big page -> cheap outline
            view = "map" if len(obs.elements) <= 25 else "outline"
        text = obs.find(find) if find else obs.reader(max_text) if view == "text" else obs.outline() if view == "outline" else obs.rows(max_elements) if view == "rows" else obs.text(max_elements, include_text, max_text)
        if find and include_text:
            text += "\n# Visible text\n" + obs.page_text[:max_text]
        out = {"text": text,
               "n_elements": len(obs.elements), "ms": int((time.monotonic() - t0) * 1000),
               "url": obs.url, "title": obs.title, "page_text": obs.page_text[:6000],
               "elements": compact(obs.elements)}
        if screenshot:
            chrome.LOG_DIR.mkdir(parents=True, exist_ok=True)
            path = chrome.LOG_DIR / f"shot-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.png"
            self.page.screenshot(path=str(path))
            out["screenshot"] = str(path)
        return out

    def act(self, verb: str, target: str | None = None, args: dict | None = None,
            max_elements: int = 150, include_text: bool = False, settle_ms: int = 600) -> dict:
        """Do one humanised action, then re-observe and report what changed + the new map."""
        from .actions import ActionError, perform

        self.ensure()
        before = self.last
        self.dialogs = []
        n_tabs = len(self.page.context.pages)
        t0 = time.monotonic()
        try:
            result, ok = perform(self, verb, target, args or {}), True
        except ActionError as e:
            result, ok = f"FAILED: {e}", False
        if ok:
            try:   # let navigation / XHR / animations settle
                self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                self.page.wait_for_load_state("networkidle", timeout=settle_ms + 1500)
            except Exception:
                pass
            time.sleep(settle_ms / 1000 * self.persona.speed)
            self._wait_dom_quiet()
        new_tab = self._switch_to_new_tab(n_tabs)
        obs = observe(self.cdp)
        self.last = obs
        if new_tab:
            result += " (it opened a new tab; now working in it)"
        return {"ok": ok, "result": result, "diff": diff(before, obs, self.dialogs),
                "text": obs.text(max_elements, include_text), "ms": int((time.monotonic() - t0) * 1000),
                "url": obs.url}

    def _wait_dom_quiet(self, quiet_ms: int = 600, max_ms: int = 3000) -> None:
        """Conditional reveals often arrive after a timer/fetch: wait until the DOM has been
        mutation-free for quiet_ms (cap max_ms) so the diff sees the revealed fields."""
        js = ("([q, m]) => new Promise(res => { let t = setTimeout(done, q); const hard = setTimeout(done, m);"
              " const mo = new MutationObserver(() => { clearTimeout(t); t = setTimeout(done, q); });"
              " mo.observe(document, {subtree: true, childList: true, attributes: true, characterData: true});"
              " function done() { mo.disconnect(); clearTimeout(t); clearTimeout(hard); res(true); } })")
        try:
            self.page.evaluate(js, [quiet_ms, max_ms])
        except Exception:
            pass

    def _switch_to_new_tab(self, n_before: int) -> bool:
        pages = [p for p in self.page.context.pages if not p.is_closed()]
        if len(pages) > n_before and pages[-1] != self.page:
            try:
                pages[-1].wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
            self._use(pages[-1])
            cur = getattr(self, "_current_tab", None)
            if cur:
                self._tabs[cur] = pages[-1]     # the task follows its popup
            return True
        return False

    def trace(self) -> list[tuple[float, float, float]]:
        return list(self.mouse.trace) if self.mouse else []
