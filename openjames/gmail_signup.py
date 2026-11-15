"""Gmail signup for the init wizard: human-paced, one attempt, SMS code typed into the wizard.

Drives the existing web stack (web_task: humanize layer, guards, detect) in the assistant's own visible
Chrome profile. The password is made with `secrets`, lives only in the vault and is typed via a
{{vault:...}} reference, so the model never sees it. CAPTCHAs are solved with the captcha_solve tool
(standing permission); a block, ID/video check or suspicious-activity page stops and hands over.
"""
from __future__ import annotations
import json, re, secrets, string, time
from . import vault
from .paths import STATE

VAULT_FILE = "gmail.txt"
DOMAINS = ["accounts.google.com", "google.com", "gmail.com", "myaccount.google.com", "gstatic.com"]
APPROVED = ["Next", "Create account", "I agree", "Agree", "Send", "Verify", "Confirm", "Skip", "Done",
            "Yes, I'm in", "Turn on", "Create", "Continue", "Get code"]
SMS_WAIT_S = 600
MARK = STATE / "gmail_signup.json"          # one attempt per phone number: guard against retries
STOP_WORDS = re.compile(r"(verify your identity|video|upload.*(id|passport)|suspicious|unusual activity|"
                        r"can'?t create your google account|too many)", re.I)


def new_password(n: int = 20) -> str:
    alpha = string.ascii_letters + string.digits + "!@#$%^&*-_=+?"
    while True:
        pw = "".join(secrets.choice(alpha) for _ in range(n))
        if any(c.islower() for c in pw) and any(c.isupper() for c in pw) and any(c.isdigit() for c in pw) \
                and any(c in "!@#$%^&*-_=+?" for c in pw):
            return pw


def _attempted(phone: str) -> bool:
    try: return phone in json.loads(MARK.read_text())
    except Exception: return False


def _mark(phone: str) -> None:
    try: d = json.loads(MARK.read_text())
    except Exception: d = []
    MARK.parent.mkdir(parents=True, exist_ok=True)
    MARK.write_text(json.dumps(d + [phone])); MARK.chmod(0o600)


def goal(first, last, username, birthday, phone) -> str:
    return (
        "Create a Google account (Gmail) through the normal signup at https://accounts.google.com/signup. "
        f"First name: {first}. Last name: {last}. Birthday (YYYY-MM-DD): {birthday}. Phone number: {phone}. "
        f"Preferred username: {username} (if taken, take the closest free suggestion Google offers that keeps the name). "
        f"Type the password with the literal text {{{{vault:{VAULT_FILE}:password}}}} in both password fields. "
        "Work like a person: fill the fields in page order, one at a time, never paste. "
        "When Google asks for the SMS verification code, use action ask with the question 'SMS code needed' and "
        "wait; after you are given the code, type it. Accept the terms. Skip optional steps (recovery email) when possible. "
        "Stop with ask on any ID/video check, 'suspicious activity' or 'can't create account' page: do not try to defeat it. "
        "Finish when the account exists and the Gmail inbox or myaccount page is shown. "
        "Never retry from scratch after a failure."
    )


def _loop(): 
    from .web import agent_loop
    return agent_loop


def _set_goal(task_id: str, extra: str) -> None:
    al = _loop(); st = al.load_state(task_id)
    st.goal = st.goal + "\n" + extra
    from pathlib import Path
    (al.TASK_DIR / f"{task_id}.json").write_text(json.dumps(st.as_dict(), indent=1))


def signup(first, last, username, birthday, phone, ask_code, say=print, max_rounds: int = 12) -> dict:
    """Run the whole signup. `ask_code(prompt, timeout_s)` returns the SMS code or '' on timeout."""
    from . import tools
    if _attempted(phone):
        return {"status": "refused", "why": "one attempt per phone number was already made; wait or use another number"}
    if not vault.pairs(vault.read(VAULT_FILE)).get("password"):
        vault.set_key(VAULT_FILE, "password", new_password(), f"google account {username}")
    vault.set_key(VAULT_FILE, "username", f"{username}@gmail.com")
    _mark(phone)
    say("Warming up Chrome (google.com, a search) ...")
    out = tools.call_tool("web_task", {"goal": "Open https://www.google.com, wait a moment, scroll a little, and search for 'gmail' like a person would, then finish.",
                                       "start_url": "https://www.google.com", "allowed_domains": DOMAINS, "max_steps": 6})
    task_id, captcha_tries = None, 0
    args = {"goal": goal(first, last, username, birthday, phone), "start_url": "https://accounts.google.com/signup",
            "allowed_domains": DOMAINS, "approved_labels": APPROVED, "max_steps": 40, "max_seconds": 900}
    for _ in range(max_rounds):
        out = tools.call_tool("web_task", args)
        text = out if isinstance(out, str) else json.dumps(out)
        m = re.search(r"Web task (\S+)", text)
        task_id = m.group(1) if m else task_id
        args = {"task_id": task_id, "approved_labels": APPROVED, "max_steps": 40, "max_seconds": 900}
        if "finished" in text.split("\n", 1)[0]:
            return {"status": "done", "task": task_id, "username": f"{username}@gmail.com"}
        if "captcha" in text.lower() and "stopped by: captcha" in text:
            captcha_tries += 1
            if captcha_tries > 3:
                return {"status": "needs-human", "task": task_id, "why": "captcha failed 3 times"}
            say("CAPTCHA seen, trying to solve it ...")
            r = tools.call_tool("captcha_solve", {"action": "click_checkbox"})
            if isinstance(r, dict) and not r.get("solved"):
                tools.call_tool("captcha_solve", {"action": "inspect"})
            time.sleep(2); continue
        if STOP_WORDS.search(text):
            return {"status": "needs-human", "task": task_id, "why": "Google asked for an extra check; stopped without trying to defeat it"}
        if re.search(r"sms code|verification code|6-digit", text, re.I):
            code = ask_code("Enter the 6-digit code sent to your phone", SMS_WAIT_S)
            if not code:
                return {"status": "timeout", "task": task_id, "why": "no code entered within 10 minutes (resume later with web_task task_id)"}
            _set_goal(task_id, f"The SMS code is {re.sub(chr(92)+'D', '', code)}: type it into the code field and continue.")
            continue
        return {"status": "needs-human", "task": task_id, "why": text[:400]}
    return {"status": "stopped", "task": task_id, "why": "round budget used"}


# ---- after signup: 2-step verification + app password (for IMAP/SMTP of the email channel) -------------

SECURE_APPROVED = APPROVED + ["Turn on 2-Step Verification", "Turn on", "Get started", "Use your phone number",
                              "Send code", "Try another way"]
SPACED = re.compile(r"\b([A-Za-z]{4}\s[A-Za-z]{4}\s[A-Za-z]{4}\s[A-Za-z]{4})\b")
PLAIN = re.compile(r"(?<![A-Za-z])([A-Za-z]{16})(?![A-Za-z])")
APP_NAME = "OpenJames"


def twosv_goal(phone: str) -> str:
    return (
        "Turn on 2-Step Verification for the signed-in Google account: open https://myaccount.google.com/signinoptions/twosv "
        f"and follow 'Turn on 2-Step Verification' using the phone number {phone} (text message, not an app). "
        f"If Google asks for the account password, type the literal text {{{{vault:{VAULT_FILE}:password}}}}. "
        "When Google asks for the SMS verification code, use action ask with the question 'SMS code needed' and wait; "
        "after you are given the code, type it. Do not add other verification steps, skip backup/recovery offers. "
        "Stop with ask on any ID/video check or 'suspicious activity' page: do not try to defeat it. "
        "Finish when the page says 2-Step Verification is on."
    )


def app_password_goal() -> str:
    return (
        "Open https://myaccount.google.com/apppasswords (if Google asks for the password, type the literal text "
        f"{{{{vault:{VAULT_FILE}:password}}}}). Type the app name '{APP_NAME}' into the app-name field and STOP right there: "
        "do NOT click Create. The Create click and the one-time password are handled outside this task. "
        "Finish as soon as the name is typed and the Create button is visible."
    )


def _candidates(text: str) -> list[str]:
    seen, out = set(), []
    for rx in (SPACED, PLAIN):
        for m in rx.finditer(text or ""):
            c = m.group(1).replace(" ", "")
            if c.lower() not in seen:
                seen.add(c.lower()); out.append(c)
    return out


def _imap_ok(addr: str, pw: str) -> bool:
    import imaplib
    try:
        box = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
        try: box.login(addr, pw); return True
        finally:
            try: box.logout()
            except Exception: pass
    except Exception:
        return False


def capture_app_password(addr: str) -> dict:
    """Click Create on the app-passwords page, read the one-time password straight from the page, prove it by an
    IMAP login and only then store it (.env EMAIL_APP_PASSWORD, vault). Nothing secret is returned or printed."""
    from .web import client
    obs = client.call("observe", {"max_elements": 80}) or {}
    els = obs.get("elements") or {}
    target = next((k for k, v in els.items() if isinstance(v, dict) and str(v.get("name", "")).strip().lower() == "create"), None)
    if not target: return {"status": "error", "why": "Create button not found"}
    client.call("act", {"verb": "click", "target": target, "max_elements": 5})
    time.sleep(2)
    page = client.call("observe", {"include_text": True, "max_text": 6000, "view": "text"}) or {}
    for pw in _candidates(page.get("page_text") or ""):
        if _imap_ok(addr, pw):
            from .paths import ENV
            vault.set_key(VAULT_FILE, "app_password", pw, f"app password {APP_NAME}")
            from .wizard import write_env
            write_env({"EMAIL_ADDRESS": addr, "EMAIL_APP_PASSWORD": pw})
            return {"status": "ok", "stored": ["EMAIL_ADDRESS", "EMAIL_APP_PASSWORD in .env", f"private/accounts/{VAULT_FILE}"]}
    return {"status": "error", "why": "no candidate on the page logged in over IMAP; nothing written (IMAP may need enabling or the page differed)"}


def _drive(args: dict, ask_code, say, max_rounds: int = 8) -> dict:
    """Run web_task rounds, relaying SMS code prompts and stopping on checks; returns status dict."""
    from . import tools
    task_id = None
    for _ in range(max_rounds):
        out = tools.call_tool("web_task", args)
        text = out if isinstance(out, str) else json.dumps(out)
        m = re.search(r"Web task (\S+)", text)
        task_id = m.group(1) if m else task_id
        args = {"task_id": task_id, "approved_labels": SECURE_APPROVED, "max_steps": 40, "max_seconds": 900}
        if "finished" in text.split("\n", 1)[0]:
            return {"status": "done", "task": task_id}
        if "stopped by: captcha" in text:
            say("CAPTCHA seen, trying to solve it ...")
            r = tools.call_tool("captcha_solve", {"action": "click_checkbox"})
            if isinstance(r, dict) and not r.get("solved"): tools.call_tool("captcha_solve", {"action": "inspect"})
            time.sleep(2); continue
        if STOP_WORDS.search(text):
            return {"status": "needs-human", "task": task_id, "why": "Google asked for an extra check; stopped without trying to defeat it"}
        if re.search(r"sms code|verification code|6-digit", text, re.I):
            code = ask_code("Enter the 6-digit code sent to your phone", SMS_WAIT_S)
            if not code: return {"status": "timeout", "task": task_id, "why": "no code entered within 10 minutes"}
            _set_goal(task_id, f"The SMS code is {re.sub(chr(92)+'D', '', code)}: type it into the code field and continue.")
            continue
        return {"status": "needs-human", "task": task_id, "why": text[:400]}
    return {"status": "stopped", "task": task_id, "why": "round budget used"}


def secure_account(phone: str, ask_code, say=print) -> dict:
    """After signup: turn on 2-step verification (SMS to `phone`), create the app password, store it for the email channel."""
    addr = vault.pairs(vault.read(VAULT_FILE)).get("username")
    if not addr or not vault.pairs(vault.read(VAULT_FILE)).get("password"):
        return {"status": "refused", "why": "no gmail account in the vault; run the signup first"}
    say("Turning on 2-step verification ...")
    r = _drive({"goal": twosv_goal(phone), "start_url": "https://myaccount.google.com/signinoptions/twosv",
                "allowed_domains": DOMAINS, "approved_labels": SECURE_APPROVED, "max_steps": 40, "max_seconds": 900}, ask_code, say)
    if r["status"] != "done": return {**r, "step": "2sv"}
    say("Creating the app password ...")
    r = _drive({"goal": app_password_goal(), "start_url": "https://myaccount.google.com/apppasswords",
                "allowed_domains": DOMAINS, "approved_labels": SECURE_APPROVED, "max_steps": 25, "max_seconds": 600}, ask_code, say)
    if r["status"] != "done": return {**r, "step": "app-password"}
    c = capture_app_password(addr)
    return {**c, "username": addr} if c["status"] == "ok" else {"status": "needs-human", "step": "capture", **c}
