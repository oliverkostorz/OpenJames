from __future__ import annotations
import email as _email, imaplib, os, smtplib
from email.message import EmailMessage
from . import Channel, Message


class Email(Channel):
    name = "email"
    env_keys = ["EMAIL_ADDRESS", "EMAIL_APP_PASSWORD", "EMAIL_IMAP_HOST", "EMAIL_SMTP_HOST"]

    def poll(self):
        box = imaplib.IMAP4_SSL(os.environ["EMAIL_IMAP_HOST"])
        box.login(os.environ["EMAIL_ADDRESS"], os.environ["EMAIL_APP_PASSWORD"])
        box.select("INBOX")
        out = []
        for num in box.search(None, "UNSEEN")[1][0].split():
            msg = _email.message_from_bytes(box.fetch(num, "(RFC822)")[1][0][1])
            # TODO(contributors): verify DMARC / aligned DKIM from Authentication-Results before trusting From.
            body = msg.get_payload(decode=True) if not msg.is_multipart() else msg.get_payload()[0].get_payload(decode=True)
            out.append(Message("email", _email.utils.parseaddr(msg["From"])[1].lower(), (body or b"").decode(errors="replace")))
        box.logout()
        return out

    def send(self, to, text):
        m = EmailMessage(); m["From"] = os.environ["EMAIL_ADDRESS"]; m["To"] = to; m["Subject"] = "OpenJames"; m.set_content(text)
        with smtplib.SMTP_SSL(os.environ["EMAIL_SMTP_HOST"]) as s:
            s.login(os.environ["EMAIL_ADDRESS"], os.environ["EMAIL_APP_PASSWORD"]); s.send_message(m)


CHANNEL = Email
