"""Find and launch the real Google Chrome with the assistant's own profile and a local CDP port.

Real Chrome + dedicated `--user-data-dir` (outside the repo, it holds live session cookies)
instead of Playwright's bundled Chromium: no `--enable-automation`, normal fingerprint, and
the principal logs in to sites once by hand. The debug port only listens on 127.0.0.1.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import httpx

CHROME_BIN = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
PROFILE_DIR = Path(os.environ.get("OJ_WEB_PROFILE", Path.home() / ".openjames" / "chrome-profile"))
PORT = int(os.environ.get("OJ_WEB_PORT", "9333"))
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "state" / "web"


def headless_default() -> bool:
    return os.environ.get("OJ_WEB_HEADLESS", "0").lower() in ("1", "true", "yes", "on")


def version(port: int = PORT) -> dict | None:
    """CDP /json/version, or None if nothing is listening."""
    try:
        r = httpx.get(f"http://127.0.0.1:{port}/json/version", timeout=1.0)
        return r.json() if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


def launch(port: int = PORT, profile: Path = PROFILE_DIR, headless: bool | None = None,
           wait: float = 15.0) -> dict:
    """Start Chrome (detached) unless it's already up on `port`; return /json/version."""
    v = version(port)
    if v:
        return v
    if not CHROME_BIN.exists():
        raise RuntimeError(f"Google Chrome not found at {CHROME_BIN}")
    profile.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    args = [
        str(CHROME_BIN),
        f"--user-data-dir={profile}",
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1280,900",
        # Keep input/rendering at full speed when the window is minimised, occluded or on
        # another Space (otherwise every CDP mouse event waits ~85 ms for a frame).
        "--disable-renderer-backgrounding",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
    ]
    if headless if headless is not None else headless_default():
        args.append("--headless=new")
    args.append("about:blank")
    # Launch through LaunchServices (`open -n`), like a user would: Chrome then runs at
    # normal app priority instead of inheriting our launchd ProcessType=Background clamp,
    # which slows every rendered frame (and so every input-event ack) ~3x. -g = don't steal focus.
    app = CHROME_BIN.parent.parent.parent
    log = str(LOG_DIR / "chrome.log")
    try:
        subprocess.run(["open", "-n", "-g", "-a", str(app), "--stdout", log, "--stderr", log,
                        "--args", *args[1:]], check=True, timeout=15, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        with open(log, "ab") as fh:
            subprocess.Popen(args, stdout=fh, stderr=fh, stdin=subprocess.DEVNULL,
                             start_new_session=True)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        v = version(port)
        if v:
            return v
        time.sleep(0.25)
    raise RuntimeError(f"Chrome did not open its debug port {port} within {wait}s (see state/web/chrome.log)")


def close(port: int = PORT) -> bool:
    """Ask Chrome to quit via CDP Browser.close. Returns False if it wasn't running."""
    v = version(port)
    if not v:
        return False
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        b.new_browser_cdp_session().send("Browser.close")
    return True


def our_pids(profile: Path = PROFILE_DIR) -> list[int]:
    """PIDs of Chrome processes started with our --user-data-dir (never anyone else's Chrome)."""
    try:
        out = subprocess.run(["pgrep", "-f", f"--user-data-dir={profile}"], capture_output=True,
                             text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [int(x) for x in out.split() if x.isdigit() and int(x) != os.getpid()]


def kill_ours(profile: Path = PROFILE_DIR, port: int = PORT, wait: float = 10.0) -> bool:
    """Terminate our Chrome: SIGTERM first (graceful, flushes profile), SIGKILL stragglers."""
    import signal
    pids = our_pids(profile)
    if not pids:
        return False
    for sig, grace in ((signal.SIGTERM, wait), (signal.SIGKILL, 3.0)):
        for pid in our_pids(profile):
            try:
                os.kill(pid, sig)
            except OSError:
                pass
        end = time.monotonic() + grace
        while time.monotonic() < end and (our_pids(profile) or version(port)):
            time.sleep(0.2)
        if not our_pids(profile) and not version(port):
            break
    return True


def restart(port: int = PORT, profile: Path = PROFILE_DIR, headless: bool | None = None) -> dict:
    """Replace a zombie Chrome (answers /json/version but rejects attach) with a fresh one."""
    kill_ours(profile, port)
    return launch(port, profile, headless=headless)
