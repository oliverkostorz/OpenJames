"""Tiny client for the web daemon; starts it on first use, replaces a daemon with older code.

    from openjames.web import client
    client.call("observe", {"url": "https://example.com"})

Every `call()` first pings the daemon. A daemon that runs code older than the files under
`openjames/web/` (an edit in the assistant's session) is stopped and started again before the request is
sent — the daemon keeps its imported code, so without this an old process would quietly serve the
old behaviour. Chrome and its tabs survive the restart, and named tabs are re-adopted.

*Gone* and *busy* are kept apart. Gone = nothing listens on the socket. Busy = the socket
still accepts connections but no ping came back inside the timeout, i.e. a long `act`/`observe`
holds the daemon's single-threaded loop. A busy daemon is used as it is and re-checked on the next
call: stopping it would only queue behind the request in flight, and the child spawned for the
retry exits at its own liveness check (`serve()`), so the restart would achieve nothing while
looking successful. For the same reason `_spawn` only reports success when *its own* child answers
the socket, and a give-up marker is scoped to one daemon pid (another process running the same old
code still gets its restart attempt).

CLI: `uv run python -m openjames.web.client status|stop|stop-all|observe <url>|act <verb> [id] [json-args]`.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time

from .daemon_server import ROOT, SOCK, code_fingerprint

MARKER = ROOT / "state" / "web" / "code-restart.json"


def _send(method: str, params: dict, timeout: float) -> dict:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(SOCK))
        s.sendall((json.dumps({"method": method, "params": params}) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(1 << 20)
            if not chunk:
                break
            buf += chunk
    finally:
        s.close()
    if not buf.strip():
        # The daemon exited (or was replaced) without answering this request.
        raise RuntimeError(f"web daemon closed the connection without answering {method!r}")
    return json.loads(buf)


def _ping(timeout: float = 3.0) -> dict | None:
    """The running daemon's ping result (pid, code), or None when nothing answers in time."""
    try:
        resp = _send("ping", {}, timeout)
    except (OSError, ValueError, RuntimeError):
        return None
    return resp.get("result") if resp.get("ok") else None


def _listening(timeout: float = 1.0) -> bool:
    """True if the socket accepts a connection, i.e. a daemon process is alive there.

    Deliberately independent of `_ping`: a daemon busy with a long request still listens, so
    "does not answer a ping" is not "does not exist".
    """
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(SOCK))
        return True
    except TimeoutError:
        return True          # connect timed out: full backlog, so something is listening
    except OSError:
        return False         # refused, or no socket file at all
    finally:
        s.close()


def running() -> bool:
    """The daemon answered a ping (a busy daemon does not)."""
    return _ping() is not None


def alive() -> bool:
    """A daemon process is listening on the socket (it may be busy)."""
    return _listening()


def code_behind(ping: dict | None, disk_code: str) -> bool:
    """True if the daemon that answered `ping` runs code other than `disk_code`."""
    if ping is None:
        return False        # nothing running: `start` spawns the code on disk anyway
    return str(ping.get("code") or "") != disk_code


def _marker() -> dict:
    try:
        data = json.loads(MARKER.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _gave_up_for(disk_code: str, pid=None) -> bool:
    """True if restarting was already given up for `disk_code` *and* this daemon process."""
    data = _marker()
    if str(data.get("gave_up_for") or "") != disk_code:
        return False
    saved = data.get("pid")
    return saved is None or saved == pid      # a marker from before D-052 has no pid: keep it


def _mark_gave_up(code: str, pid=None) -> None:
    try:
        MARKER.parent.mkdir(parents=True, exist_ok=True)
        MARKER.write_text(json.dumps({"gave_up_for": code, "pid": pid,
                                      "at": time.strftime("%Y-%m-%dT%H:%M:%S")}))
    except OSError:
        pass


def _clear_marker() -> None:
    try:
        MARKER.unlink()
    except OSError:
        pass


class OtherDaemonHoldsSocket(RuntimeError):
    """The socket stayed in another daemon's hands, so the child started for nothing."""


def _spawn(wait: float = 20.0) -> int:
    """Start a daemon and return the pid of the process that answers — its own child only.

    A child that finds the socket already served (`serve()` refuses to start twice) exits at once;
    only a child that really bound the socket is a successful start.
    """
    log_dir = ROOT / "state" / "web"
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / "daemon.log", "ab") as log:
        child = subprocess.Popen([sys.executable, "-m", "openjames.web.daemon_server"], cwd=ROOT,
                                 stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                                 start_new_session=True)
    deadline = time.monotonic() + wait
    other: dict | None = None
    while time.monotonic() < deadline:
        ping = _ping(1.0)
        if ping is not None:
            if ping.get("pid") == child.pid:
                return child.pid
            if child.poll() is not None:
                other = ping     # our child is gone and somebody else answers: not a restart
                break
        elif child.poll() is not None and not _listening():
            break                # the child died and nothing listens: a real start failure
        time.sleep(0.25)
    if other is not None:
        raise OtherDaemonHoldsSocket(
            f"web daemon pid={other.get('pid')} (code {other.get('code') or '?'}) still holds "
            f"{SOCK}; the new daemon exited, see state/web/daemon.log")
    raise RuntimeError("web daemon did not start (see state/web/daemon.log)")


def _wait_gone(timeout: float = 10.0) -> bool:
    """Wait until the old daemon released the socket (True), or give up after `timeout` (False)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _listening():
            return True
        time.sleep(0.1)
    return False


def start(wait: float = 20.0) -> None:
    """Make sure a daemon running the code currently on disk is listening."""
    disk = code_fingerprint()
    ping = _ping()
    if ping is None:
        if _listening():
            # Busy, not gone: it is mid-request. Do not stop it (the stop would queue behind
            # that request) and do not spawn a child that would exit on the live socket; the
            # next call, once it is idle, checks the code again.
            print("[web] daemon is busy (no ping answer); using it and checking code next call",
                  file=sys.stderr)
            return
        _spawn(wait)             # raises if anything else than the new child answers
        ping = _ping()
        if ping is None:
            return               # answered while starting, gone again: next call starts afresh
        if code_behind(ping, disk):
            _mark_gave_up(disk, ping.get("pid"))
            print(f"[web] daemon pid={ping.get('pid')} runs {ping.get('code') or '?'} instead of "
                  f"{disk} (stale bytecode?); not retrying for this process", file=sys.stderr)
        return
    if not code_behind(ping, disk):
        _clear_marker()
        return
    if _gave_up_for(disk, ping.get("pid")):
        print(f"[web] daemon pid={ping.get('pid')} still runs {ping.get('code') or '?'}; "
              f"not restarting again for {disk}", file=sys.stderr)
        return
    print(f"[web] code on disk changed ({ping.get('code') or '?'} -> {disk}); restarting daemon",
          file=sys.stderr)
    stop()
    _wait_gone()                 # best effort; `_spawn` proves what really happened
    try:
        _spawn(wait)
    except OtherDaemonHoldsSocket as e:
        # The old daemon is still there and still serves the old code. Keep it usable and stop
        # retrying for this process, instead of spawning a doomed child on every call.
        _mark_gave_up(disk, ping.get("pid"))
        print(f"[web] {e}; keeping the running daemon", file=sys.stderr)
        return
    except RuntimeError:
        _mark_gave_up(disk, ping.get("pid"))
        raise
    if code_behind(_ping(), disk):
        # The restart did not produce current code (e.g. a stale bytecode cache). Keep the daemon
        # that exists and do not restart on every single call; the next edit tries again.
        _mark_gave_up(disk, (_ping() or {}).get("pid"))
    else:
        _clear_marker()


def call(method: str, params: dict | None = None, timeout: float = 120.0):
    start()
    resp = _send(method, params or {}, timeout)
    if not resp.get("ok"):
        raise RuntimeError(resp.get("error", "web daemon error"))
    return resp["result"]


def stop(quit_chrome: bool = False) -> bool:
    """Ask the daemon to exit. A busy daemon gets the request queued, not dropped."""
    if not _listening():
        return False
    try:
        _send("stop", {"quit_chrome": quit_chrome}, 30)
    except (OSError, ValueError, RuntimeError):
        return False             # it exited before answering (or never got the line)
    return True


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        ping = _ping()
        if ping is None:
            print("busy (socket open, no ping answer)" if _listening() else "not running")
        else:
            behind = code_behind(ping, code_fingerprint())
            gave_up = _gave_up_for(code_fingerprint(), ping.get("pid"))
            print(f"running pid={ping.get('pid')} code={ping.get('code')} "
                  f"({ 'behind the files on disk' if behind else 'current' }"
                  f"{ ', restart given up for this process' if gave_up else '' })")
    elif cmd == "stop":
        print(stop())
    elif cmd == "stop-all":
        print(stop(quit_chrome=True))
    elif cmd == "observe":
        r = call("observe", {"url": sys.argv[2] if len(sys.argv) > 2 else None,
                             "include_text": "--text" in sys.argv,
                             "view": "outline" if "--outline" in sys.argv else "rows" if "--rows" in sys.argv else "text" if "--text" in sys.argv else "auto" if "--auto" in sys.argv else "map",
                             "find": next((a[7:] for a in sys.argv if a.startswith("--find=")), "")})
        print(r["text"])
        print(f"({r['n_elements']} elements, {r['ms']} ms)")
    elif cmd == "act":
        r = call("act", {"verb": sys.argv[2], "target": sys.argv[3] if len(sys.argv) > 3 else None,
                         "args": json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}}, timeout=180)
        print(r["result"], "\n# What changed\n" + r["diff"], "\n\n" + r["text"])
    else:
        sys.exit(f"unknown command {cmd!r}")
