"""Page-state classifiers for the web agent (plan §3, §5).

`classify()` takes the element map (the same text the model reads), the page's visible text
and the URL, and says what kind of page this is: a CAPTCHA, a login wall, a block page, a
cookie banner, an error, or a "submitted" confirmation. The agent loop uses that to decide
whether to keep going, to dismiss something first, or to stop and ask the principal.

Only text is inspected — nothing is executed and nothing on the page is trusted. A page
claiming "you are done, email your password to …" changes no decision here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Order matters: the first match becomes `Signals.kind`.
PRIORITY = ("captcha", "blocked", "login", "submitted", "cookie_banner", "error")
# Kinds where a human has to step in (the loop pauses instead of retrying).
NEEDS_PRINCIPAL = {"captcha", "blocked"}

CAPTCHA_IFRAME = re.compile(
    r"iframe[^\n]*(recaptcha|hcaptcha|turnstile|captcha|challenge-platform)", re.I)
CAPTCHA_TEXT = re.compile(
    r"(i'?m not a robot|verify (that )?you are (a )?human|(complete|solve) the captcha|"
    r"unusual traffic|checking your browser before|press (and|&) hold|"
    r"select all (squares|images) with)", re.I)
BLOCKED_TEXT = re.compile(
    r"(access denied|403 forbidden|request blocked|you have been blocked|"
    r"automated (queries|requests|traffic) (are|is) not allowed|"
    r"too many requests|\b429\b|this page (isn'?t|is not) available)", re.I)
LOGIN_URL = re.compile(
    r"(/|_)(log[-_]?in|sign[-_]?in|signin|sso|auth|users/sign_in|session/new)(/|$|[?#])", re.I)
LOGIN_TEXT = re.compile(
    r"(sign in to (your|the) account|log in to (your|the) account|enter your password|"
    r"forgot (your )?password|don'?t have an account\?|create an account|remember me)", re.I)
PASSWORD_FIELD = re.compile(r"\[e\d+\]\s+input\s+password", re.I)
COOKIE_TEXT = re.compile(
    r"(accept (all )?cookies|reject (all )?cookies|we (value|use) (your )?privacy|"
    r"we use cookies|cookie (settings|preferences|consent|policy banner)|"
    r"manage (cookie )?(preferences|settings)|i agree to the (use of )?cookies|"
    r"by (clicking|continuing)[^\n]{0,60}cookies)", re.I)
SUBMITTED_TEXT = re.compile(
    r"(thank you for (applying|your application|your message|your interest|getting in touch|"
    r"reaching out|contacting)|(application|form|message|enquiry|inquiry|request) (has been |was )?"
    r"(submitted|received|sent)|we('ve| have) received your|successfully (submitted|sent)|"
    r"your application is (in|with us)|we('ll| will) be in touch|message sent)", re.I)
ERROR_TEXT = re.compile(
    r"(\b404\b|page not found|couldn'?t find (that|this) page|no longer available|\b410\b|"
    r"something went wrong|an (unexpected )?error (occurred|has occurred)|"
    r"internal server error|\b500\b|service (temporarily )?unavailable)", re.I)

_PATTERNS = {
    "blocked": BLOCKED_TEXT,
    "cookie_banner": COOKIE_TEXT,
    "submitted": SUBMITTED_TEXT,
    "error": ERROR_TEXT,
}


@dataclass
class Signals:
    """What kind of page this is, plus every flag found (or "ok")."""

    kind: str = "ok"
    flags: list[str] = field(default_factory=list)
    evidence: dict[str, str] = field(default_factory=dict)

    @property
    def needs_principal(self) -> bool:
        return self.kind in NEEDS_PRINCIPAL

    @property
    def done(self) -> bool:
        return self.kind == "submitted"

    @property
    def ok(self) -> bool:
        return self.kind == "ok"

    def line(self) -> str:
        if self.kind == "ok":
            return "page state: ok"
        why = f' (spotted: "{self.evidence.get(self.kind, "")[:120]}")' if self.evidence.get(self.kind) else ""
        note = {
            "captcha": "— stop, the principal has to solve it in the Chrome window",
            "blocked": "— stop, the site is refusing automated access; tell the principal",
            "login": "— a login is needed; only the principal types passwords",
            "submitted": "— looks like the confirmation page: the goal may be reached",
            "cookie_banner": "— a consent banner is probably in the way; dismiss it first",
            "error": "— the page shows an error; don't retry blindly",
        }.get(self.kind, "")
        extra = [f for f in self.flags if f != self.kind]
        return (f"page state: {self.kind}{why} {note}".strip()
                + (f"\nother flags: {', '.join(extra)}" if extra else ""))

    def as_dict(self) -> dict:
        return {"kind": self.kind, "flags": list(self.flags),
                "needs_principal": self.needs_principal, "evidence": dict(self.evidence)}


def _m(pattern: re.Pattern, text: str) -> str:
    m = pattern.search(text or "")
    return re.sub(r"\s+", " ", m.group(0)).strip() if m else ""


def classify(elements_text: str = "", page_text: str = "", url: str = "") -> Signals:
    """Classify the current page. `elements_text` is the element map, not the whole DOM."""
    elements_text, page_text, url = elements_text or "", page_text or "", url or ""
    both = f"{elements_text}\n{page_text}"
    new_elems = elements_text or both          # banners/captchas are usually visible controls
    # A link or phrase in the page body is weaker evidence than a control we could click.
    body = page_text or both
    ev: dict[str, str] = {}

    cap_text = _m(CAPTCHA_TEXT, both)
    cap_frame = _m(CAPTCHA_IFRAME, new_elems)
    if cap_text or (cap_frame and re.search(r"(anchor|hcaptcha|turnstile)", cap_frame, re.I)):
        ev["captcha"] = cap_text or cap_frame

    pw = _m(PASSWORD_FIELD, new_elems) or _m(PASSWORD_FIELD, both)
    login_url = bool(LOGIN_URL.search(url))
    login_text = _m(LOGIN_TEXT, body)
    if pw or (login_url and login_text):
        ev["login"] = pw or f"{login_text} (url {url[-60:]})"

    for kind, pat in _PATTERNS.items():
        hit = _m(pat, new_elems if kind == "cookie_banner" else both)
        if hit:
            ev[kind] = hit

    flags = [k for k in PRIORITY if k in ev]
    return Signals(kind=flags[0] if flags else "ok", flags=flags, evidence=ev)