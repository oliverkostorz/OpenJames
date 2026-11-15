"""Per-task limits and the submit gate for the web agent (plan §5, §7, §8).

Everything that stops a web task *on purpose* lives here, so the loop in
`agent_loop.py` stays small:

- **domain allow-list** — a task may only visit the hosts it was given; anything else needs
  `allow_domain(host, reason)`, which is written to the audit log;
- **budgets** — steps, wall time, pages;
- **submit gate** — anything that looks like a final submit (apply, order, pay, send) stops
  the task for the principal's explicit approval;
- **submission cap** — a per-site daily counter, so a loop bug can't turn into a mass
  application run. It persists in `state/web/submits.json`.

Nothing here touches the browser; the loop calls it around each action.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from openjames.audit import log_event

ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMES = {"http", "https", "file", "about"}
SUBMIT_LOG = Path(os.environ.get("OJ_WEB_SUBMIT_LOG", ROOT / "state" / "web" / "submits.json"))

# Stop kinds that mean "a human has to do something before this can continue".
NEEDS_PRINCIPAL = {"approval", "domain", "rate"}


class GuardStop(Exception):
    """Raised to stop the loop. `kind` tells the caller how to report it.

    kind: "approval" (submit gate) | "domain" (outside the allow-list) |
          "rate" (submission cap) | "budget" (steps/time/pages used up).
    `needs` is "principal" when a human has to act, else None.
    """

    def __init__(self, kind: str, message: str, needs: str | None = "principal") -> None:
        super().__init__(message)
        self.kind, self.message = kind, message
        self.needs = needs

    def as_dict(self) -> dict:
        return {"kind": self.kind, "stop": self.message, "needs": self.needs}


def host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


@dataclass
class Guards:
    """Limits for one web task. Create with `Guards.for_task(start_url, ...)`."""

    goal: str = ""
    allowed_domains: set[str] = field(default_factory=set)
    max_steps: int = 25
    max_seconds: float = 600.0
    max_pages: int = 30
    min_seconds_between_actions: float = 0.0
    max_submits_per_day: int = 10
    allow_file: bool = False                     # file:// only for local fixtures/tests
    submit_log: Path = SUBMIT_LOG

    steps: int = 0
    pages: int = 0
    submits: int = 0
    started: float = field(default_factory=time.monotonic)
    last_action: float = 0.0

    @classmethod
    def for_task(cls, start_url: str = "", **kw) -> "Guards":
        g = cls(**kw)
        host = host_of(start_url)
        if host:
            g.allowed_domains.add(host)
        elif start_url.startswith("file:"):
            g.allow_file = True
        return g

    # --- domains ----------------------------------------------------------------------
    def check_url(self, url: str) -> str:
        """Allow `url` or raise GuardStop("domain", ...). Returns the url unchanged."""
        p = urlparse(url)
        if p.scheme not in SCHEMES:
            raise GuardStop("domain", f"refusing URL scheme {p.scheme!r}", needs=None)
        if p.scheme in ("file", "about"):
            if not self.allow_file:
                raise GuardStop("domain", "file:// URLs are only for local tests "
                                          "(Guards(allow_file=True))", needs=None)
            return url
        host = (p.hostname or "").lower()
        if not self._allowed(host):
            raise GuardStop(
                "domain",
                f"{host or url!r} is outside this task's allow-list "
                f"({', '.join(sorted(self.allowed_domains)) or 'empty'}) — "
                f"ask the principal before going there",
                needs="principal")
        return url

    def _allowed(self, host: str) -> bool:
        return any(host == d or host.endswith("." + d) for d in self.allowed_domains)

    def allow_domain(self, url_or_host: str, reason: str = "") -> str:
        """Add a host to the allow-list (logged). Use sparingly and say why."""
        host = host_of(url_or_host) if "//" in url_or_host else url_or_host.strip().lower()
        if not host:
            raise GuardStop("domain", f"cannot read a host from {url_or_host!r}", needs=None)
        if host not in self.allowed_domains:
            self.allowed_domains.add(host)
            log_event("web_domain_allow", host=host, reason=str(reason)[:200], goal=self.goal[:200])
        return host

    # --- budgets ----------------------------------------------------------------------
    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def note_page(self, url: str = "") -> int:
        self.pages += 1
        if self.pages > self.max_pages:
            raise GuardStop("budget", f"page budget of {self.max_pages} used up", needs=None)
        return self.pages

    def step(self, what: str = "action") -> int:
        """Count one action and enforce the step/time budget."""
        self.steps += 1
        if self.steps > self.max_steps:
            raise GuardStop("budget", f"step budget of {self.max_steps} used up", needs=None)
        left = self.max_seconds - self.elapsed
        if left <= 0:
            raise GuardStop("budget", f"time budget of {self.max_seconds:.0f}s used up "
                                      f"(at step {self.steps}: {what[:60]})", needs=None)
        return self.steps

    def pause_before_action(self) -> None:
        """Keep a human pace between actions when a minimum gap was configured."""
        if self.min_seconds_between_actions <= 0 or not self.last_action:
            self.last_action = time.monotonic()
            return
        gap = self.min_seconds_between_actions - (time.monotonic() - self.last_action)
        if gap > 0:
            time.sleep(min(gap, 60.0))
        self.last_action = time.monotonic()

    # --- submit gate ------------------------------------------------------------------
    def check_action(self, verb: str, label: str = "", is_submit: bool = False) -> None:
        """Refuse irreversible actions unless this run was explicitly approved."""
        if is_submit:
            raise GuardStop(
                "approval",
                f"'{label or verb}' is a final submit — it can't be undone, so the principal has to "
                f"approve it first (send him the answers + documents, then wait for his yes)",
                needs="principal")

    def note_submit(self, url: str = "") -> int:
        """Count one submission for today and enforce the per-site cap."""
        host = host_of(url) or "unknown"
        day = date.today().isoformat()
        data: dict = {}
        try:
            data = json.loads(self.submit_log.read_text())
            if not isinstance(data, dict):
                data = {}
        except (OSError, ValueError):
            pass
        today = data.get(day) if isinstance(data.get(day), dict) else {}
        n = int(today.get(host, 0))
        if n >= self.max_submits_per_day:
            raise GuardStop(
                "rate",
                f"{n} submissions to {host} today already (cap {self.max_submits_per_day}/day) — "
                f"stop and tell the principal",
                needs="principal")
        today[host] = n + 1
        data[day] = today
        data = {d: v for d, v in data.items() if d >= day}      # drop old days
        self.submit_log.parent.mkdir(parents=True, exist_ok=True)
        self.submit_log.write_text(json.dumps(data, indent=1, sort_keys=True))
        self.submits += 1
        log_event("web_submit_count", host=host, day=day, n=n + 1)
        return n + 1

    # --- reporting --------------------------------------------------------------------
    def summary(self) -> str:
        """One line about what this task has used so far."""
        return (f"{self.steps}/{self.max_steps} steps, {self.pages}/{self.max_pages} pages, "
                f"{self.elapsed:.0f}/{self.max_seconds:.0f}s"
                + (f", {self.submits} submit(s)" if self.submits else ""))

    def clock(self) -> str:
        return datetime.now().strftime("%H:%M:%S")