from __future__ import annotations
import email as _email, email.utils, imaplib, os, smtplib
from email.message import EmailMessage
from . import Channel, Message

# Zero-config hosts for common providers, derived from the address. Override with EMAIL_IMAP_HOST / EMAIL_SMTP_HOST.
PRESETS = {
    "gmail.com": ("imap.gmail.com", "smtp.gmail.com"), "googlemail.com": ("imap.gmail.com", "smtp.gmail.com"),
    "outlook.com": ("outlook.office365.com", "smtp.office365.com"), "hotmail.com": ("outlook.office365.com", "smtp.office365.com"),
    "live.com": ("outlook.office365.com", "smtp.office365.com"),
    "icloud.com": ("imap.mail.me.com", "smtp.mail.me.com"), "me.com": ("imap.mail.me.com", "smtp.mail.me.com"),
    "yahoo.com": ("imap.mail.yahoo.com", "smtp.mail.yahoo.com"), "fastmail.com": ("imap.fastmail.com", "smtp.fastmail.com"),
    "gmx.net": ("imap.gmx.net", "mail.gmx.net"), "gmx.de": ("imap.gmx.net", "mail.gmx.net"),
    "web.de": ("imap.web.de", "smtp.web.de"), "proton.me": ("127.0.0.1", "127.0.0.1"),
}


def hosts(address: str, env=os.environ) -> tuple[str, str]:
    dom = address.rsplit("@", 1)[-1].lower()
    imap, smtp = PRESETS.get(dom, (f"imap.{dom}", f"smtp.{dom}"))
    return env.get("EMAIL_IMAP_HOST") or imap, env.get("EMAIL_SMTP_HOST") or smtp


def authenticated(msg) -> bool:
    """True only if the receiving server reports a DMARC pass (aligned SPF/DKIM); otherwise From is spoofable."""
    return any("dmarc=pass" in h.lower() for h in msg.get_all("Authentication-Results", []))


def text_of(msg) -> str:
    parts = msg.walk() if msg.is_multipart() else [msg]
    for p in parts:
        if p.get_content_type() == "text/plain":
            return (p.get_payload(decode=True) or b"").decode(p.get_content_charset() or "utf-8", errors="replace")
    return ""


class Email(Channel):
    name = "email"
    env_keys = ["EMAIL_ADDRESS", "EMAIL_APP_PASSWORD"]
    help = "Use an app password (Gmail: myaccount.google.com/apppasswords). IMAP/SMTP hosts are detected from the address."
    id_hint = "your own email address (the only sender accepted)"

    def _login(self):
        imap, _ = hosts(os.environ["EMAIL_ADDRESS"])
        box = imaplib.IMAP4_SSL(imap)
        box.login(os.environ["EMAIL_ADDRESS"], os.environ["EMAIL_APP_PASSWORD"])
        return box

    def check(self):
        try: self._login().logout(); return None
        except Exception as e: return f"IMAP login failed ({type(e).__name__})"

    def poll(self):
        box = self._login(); box.select("INBOX")
        out = []
        for num in box.search(None, "UNSEEN")[1][0].split():
            msg = _email.message_from_bytes(box.fetch(num, "(RFC822)")[1][0][1])
            if not authenticated(msg): continue          # spoofed or unverifiable: drop
            out.append(Message("email", _email.utils.parseaddr(msg["From"])[1].lower(), text_of(msg)))
        box.logout()
        return out

    def send(self, to, text):
        _, smtp = hosts(os.environ["EMAIL_ADDRESS"])
        m = EmailMessage(); m["From"] = os.environ["EMAIL_ADDRESS"]; m["To"] = to; m["Subject"] = "OpenJames"; m.set_content(text)
        with smtplib.SMTP_SSL(smtp) as s:
            s.login(os.environ["EMAIL_ADDRESS"], os.environ["EMAIL_APP_PASSWORD"]); s.send_message(m)


CHANNEL = Email
