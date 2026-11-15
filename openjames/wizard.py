"""First-run setup wizard: choose channels, backends + fallback priority, allowed principals, secrets.

Secrets go to .env (chmod 600), choices to config.toml. Both are gitignored. Re-run any time.
"""
from __future__ import annotations
import getpass, importlib, os, platform, shutil
from . import channels
from .config import BACKENDS, CHANNELS, Config, dump
from .paths import CONFIG, ENV


def pick(title: str, options: list[tuple[str, str]], ordered=False) -> list[str]:
    print(f"\n{title}")
    for i, (k, note) in enumerate(options, 1): print(f"  {i}. {k:14} {note}")
    hint = "numbers in priority order, e.g. 2 1" if ordered else "numbers, e.g. 1 2"
    while True:
        raw = input(f"> {hint}: ").replace(",", " ").split()
        if raw and all(r.isdigit() and 1 <= int(r) <= len(options) for r in raw) and len(set(raw)) == len(raw):
            return [options[int(r) - 1][0] for r in raw]
        print("  please enter valid, distinct numbers")


def write_env(values: dict[str, str]):
    lines = ENV.read_text().splitlines() if ENV.exists() else []
    lines = [l for l in lines if l.split("=", 1)[0] not in values] + [f"{k}={v}" for k, v in values.items()]
    ENV.write_text("\n".join(lines) + "\n"); ENV.chmod(0o600)


def gmail_step():
    """Optional: create the assistant's Gmail account (human-paced, real Chrome, SMS code typed here)."""
    from . import gmail_signup as g
    print("\n3) Gmail account for the assistant (optional). It opens Chrome on this machine and signs up like a person;")
    print("   one attempt per phone number. If Google asks for an ID/video check it stops and tells you.")
    if input("   Create it now? [y/N] ").strip().lower() != "y": return
    first, last = input("   First name: ").strip(), input("   Last name: ").strip()
    user = input("   Preferred username (before @gmail.com): ").strip()
    bday = input("   Your birthday YYYY-MM-DD: ").strip()
    phone = input("   Phone number you control (+country code): ").strip()
    if not all((first, last, user, bday, phone)): print("   incomplete, skipped."); return

    def ask_code(prompt, timeout_s):
        import select, sys
        print(f"   {prompt} (waiting up to {timeout_s // 60} min, Enter on empty = give up)")
        r, _, _ = select.select([sys.stdin], [], [], timeout_s)
        return sys.stdin.readline().strip() if r else ""
    r = g.signup(first, last, user, bday, phone, ask_code, say=lambda m: print("  ", m))
    print(f"   -> {r['status']}" + (f": {r.get('why')}" if r.get("why") else f" ({r.get('username')}; password is in private/accounts/gmail.txt)"))
    if r["status"] != "done": return
    print("   Next: 2-step verification (same phone, a second SMS) and an app password so the email channel can log in.")
    s = g.secure_account(phone, ask_code, say=lambda m: print("  ", m))
    print(f"   -> {s['status']}" + (f" at {s.get('step')}: {s.get('why')}" if s.get("why") else " (EMAIL_ADDRESS + EMAIL_APP_PASSWORD saved to .env; nothing printed)"))


def main():
    print("OpenJames setup. Nothing leaves this machine; secrets are stored in .env (mode 600, gitignored).")
    opts = []
    for c in CHANNELS:
        ch = channels.get(c)
        note = "needs macOS" if "darwin" in ch.platforms and platform.system() != "Darwin" else ("no credentials" if not ch.env_keys else "")
        opts.append((c, note))
    chosen = pick("1) How should OpenJames talk to you? (pick one or more)", opts)
    cfg = Config(channels=chosen)
    env: dict[str, str] = {}
    for c in chosen:
        ch = channels.get(c)
        if ch.help: print(f"\n[{c}] {ch.help}")
        for k in ch.env_keys:
            if k not in os.environ and not (ENV.exists() and k + "=" in ENV.read_text()):
                v = getpass.getpass(f"[{c}] {k} (hidden): ").strip()
                if v: env[k] = v
        who = ""
        if type(ch).discover_sender is not channels.Channel.discover_sender:
            os.environ.update(env)
            print(f"[{c}] Waiting up to 2 min: send any message to your bot now to auto-detect your id (Enter to type it instead)...")
            try: who = ch.discover_sender() or ""
            except Exception as e: print(f"  auto-detect failed ({type(e).__name__})")
            if who: print(f"  detected {who}")
        if not who: who = input(f"[{c}] {ch.id_hint} (only this principal is accepted): ").strip()
        cfg.allowed_senders[c] = [who.lower()] if who else []
    bopts = []
    for b in BACKENDS:
        m = importlib.import_module(f"openjames.backends.{b}")
        cli = {"claude_code": "claude", "codex": "codex", "gemini": "gemini"}.get(b)
        note = (f"CLI {'found' if shutil.which(cli) else 'NOT found'}, uses your subscription" if cli else "paid API key")
        bopts.append((b, note))
    cfg.backends = pick("2) Which model backends should be active? Order = fallback priority (first is tried first)", bopts, ordered=True)
    for b in cfg.backends:
        for k in importlib.import_module(f"openjames.backends.{b}").ENV_KEYS:
            v = getpass.getpass(f"[{b}] {k} (hidden): ").strip()
            if v: env[k] = v
    if env: write_env(env)
    CONFIG.write_text(dump(cfg))
    gmail_step()
    print(f"\nWrote {CONFIG.name} and .env. Next: `uv run openjames doctor`, then `uv run openjames deploy`.")
