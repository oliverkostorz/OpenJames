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
