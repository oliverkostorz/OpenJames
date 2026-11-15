"""Long-lived web daemon: owns one Chrome session, serves JSON-RPC on a unix socket.

Protocol: one JSON line `{"method": ..., "params": {...}}` in, one JSON line
`{"ok": true, "result": ...}` / `{"ok": false, "error": "..."}` out, per connection.
Socket `state/web.sock` is mode 0600. Requests are handled one at a time (the browser is a
single shared resource). Exits after OJ_WEB_IDLE_MIN minutes (default 20) without requests;
Chrome keeps running so logins/tabs survive, `stop` with quit_chrome=true closes it too.

`ping` answers `{"pid": ..., "code": <fingerprint of the .py files of this package>}`, i.e. the
code this process actually imported. `openjames.web.client` compares that with the files on disk and
replaces a daemon that runs older code by itself, so an edit under `openjames/web/` no longer
needs a manual restart. The fingerprint is fixed at the very top of `serve()`, before the socket
exists: computed any later it could describe an edit the process has not imported.

Run: `uv run python -m openjames.web.daemon_server` (normally started by openjames.web.client).
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import time
import traceback
from pathlib import Path

from .session import Session

ROOT = Path(__file__).resolve().parent.parent.parent
SOCK = Path(os.environ.get("OJ_WEB_SOCK", ROOT / "state" / "web.sock"))
IDLE_SEC = float(os.environ.get("OJ_WEB_IDLE_MIN", "20")) * 60


def code_fingerprint(root: Path | None = None) -> str:
    """sha256 over the .py files of this package: which code a daemon loaded."""
    base = Path(root) if root is not None else Path(__file__).resolve().parent
    h = hashlib.sha256()
    for p in sorted(base.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        try:
            h.update(p.relative_to(base).as_posix().encode("utf-8") + b"\0")
            h.update(p.read_bytes() + b"\0")
        except OSError:      # file vanished mid-scan: the next caller sees the new set
            continue
    return h.hexdigest()[:16]


_CODE: str | None = None


def loaded_code() -> str:
    """Fingerprint of the code this process runs; fixed the first time it is asked."""
    global _CODE
    if _CODE is None:
        _CODE = code_fingerprint()
    return _CODE


def _log(msg: str) -> None:
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}", flush=True)


def handle(session: Session, method: str, params: dict):
    if method == "ping":
        return {"pid": os.getpid(), "code": loaded_code()}
    if method == "close_tab":
        return {"closed": session.close_tab(str(params["tab"]))}
    if params.get("tab"):
        session.select_tab(str(params["tab"]))
    if method == "navigate":
        return session.navigate(params["url"])
    if method == "observe":
        if params.get("url"):
            session.navigate(params["url"])
        return session.observe(int(params.get("max_elements", 150)), bool(params.get("include_text", False)),
                               int(params.get("max_text", 3000)), bool(params.get("screenshot", False)),
                               str(params.get("view", "map")), str(params.get("find", "")))
    if method == "act":
        return session.act(params["verb"], params.get("target"), params.get("args") or {},
                           int(params.get("max_elements", 150)), bool(params.get("include_text", False)))
    if method == "tabs":
        return session.tabs()
    raise ValueError(f"unknown method {method!r}")


def serve() -> None:
    # Pin the fingerprint of the code this process runs before anything can talk to it: a client
    # compares it with the files on disk to decide about a restart, so it must not be
    # computed later, when an edit may already have happened that this process never imported.
    code = loaded_code()
    SOCK.parent.mkdir(parents=True, exist_ok=True)
    if SOCK.exists():
        # Refuse to start twice: a live daemon answers on the socket.
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(str(SOCK))
            s.close()
            _log("another daemon is already listening; exiting")
            return
        except OSError:
            SOCK.unlink()
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    old = os.umask(0o177)
    try:
        srv.bind(str(SOCK))
    finally:
        os.umask(old)
    os.chmod(SOCK, 0o600)
    srv.listen(4)
    srv.settimeout(30)
    session = Session()
    last = time.monotonic()
    _log(f"listening on {SOCK} pid={os.getpid()} code={code}")
    try:
        while True:
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                if time.monotonic() - last > IDLE_SEC:
                    _log("idle timeout; exiting")
                    break
                continue
            last = time.monotonic()
            with conn:
                conn.settimeout(120)
                buf = b""
                while not buf.endswith(b"\n"):
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                stop = False
                try:
                    req = json.loads(buf or b"{}")
                    method, params = req.get("method", ""), req.get("params") or {}
                    if method == "stop":
                        session.close(quit_chrome=bool(params.get("quit_chrome")))
                        resp, stop = {"ok": True, "result": "stopping"}, True
                    else:
                        resp = {"ok": True, "result": handle(session, method, params)}
                    _log(f"{method} ok")
                except Exception as e:  # report to the caller, keep serving
                    _log(f"error: {traceback.format_exc(limit=3)}")
                    resp = {"ok": False, "error": f"{type(e).__name__}: {e}"}
                    if "Target" in str(e) or "closed" in str(e):
                        session.close()   # Chrome window closed by hand: reconnect next time
                try:
                    conn.sendall((json.dumps(resp, default=str) + "\n").encode())
                except OSError:
                    pass
                if stop:
                    break
    finally:
        srv.close()
        try:
            SOCK.unlink()
        except FileNotFoundError:
            pass
        session.close()
        _log("stopped")


if __name__ == "__main__":
    serve()
    sys.exit(0)
