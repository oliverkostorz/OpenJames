"""Minimal stdlib CDP websocket client for fire-and-forget input events.

Playwright's CDPSession.send waits for Chrome to acknowledge each Input.dispatchMouseEvent,
which takes 50–100 ms per event (Chrome acks on the next rendered frame). A human mouse
reports at 60–125 Hz, so cursor moves are streamed here instead: messages go out on our own
schedule and the acks are drained by a reader thread. Only used for 127.0.0.1.
"""

from __future__ import annotations

import base64
import itertools
import json
import os
import socket
import struct
import threading
from urllib.parse import urlparse


class CDPStream:
    def __init__(self, ws_url: str, timeout: float = 10.0):
        u = urlparse(ws_url)
        if u.hostname not in ("127.0.0.1", "localhost"):
            raise ValueError("CDPStream only connects to localhost")
        self.sock = socket.create_connection((u.hostname, u.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("websocket handshake failed")
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ConnectionError(f"websocket handshake refused: {head[:80]!r}")
        self.sock.settimeout(None)
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        self._pending: dict[int, threading.Event] = {}
        self._results: dict[int, dict] = {}
        self.closed = False
        threading.Thread(target=self._reader, daemon=True).start()

    # --- frames ------------------------------------------------------------------------
    def _send_frame(self, data: bytes) -> None:
        mask = os.urandom(4)
        n = len(data)
        if n < 126:
            hdr = struct.pack("!BB", 0x81, 0x80 | n)
        elif n < 1 << 16:
            hdr = struct.pack("!BBH", 0x81, 0x80 | 126, n)
        else:
            hdr = struct.pack("!BBQ", 0x81, 0x80 | 127, n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        with self._lock:
            self.sock.sendall(hdr + mask + masked)

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("closed")
            buf += chunk
        return buf

    def _reader(self) -> None:
        try:
            while True:
                b0, b1 = self._recv_exact(2)
                n = b1 & 0x7F
                if n == 126:
                    n = struct.unpack("!H", self._recv_exact(2))[0]
                elif n == 127:
                    n = struct.unpack("!Q", self._recv_exact(8))[0]
                payload = self._recv_exact(n)
                if b0 & 0x0F == 0x8:
                    break
                if b0 & 0x0F != 0x1:
                    continue
                msg = json.loads(payload)
                ev = self._pending.pop(msg.get("id"), None) if "id" in msg else None
                if ev is not None:
                    self._results[msg["id"]] = msg
                    ev.set()
        except (OSError, ConnectionError, ValueError):
            pass
        finally:
            self.closed = True
            for ev in list(self._pending.values()):
                ev.set()

    # --- API -----------------------------------------------------------------------------
    def post(self, method: str, params: dict) -> int:
        """Send without waiting for the reply."""
        i = next(self._ids)
        self._send_frame(json.dumps({"id": i, "method": method, "params": params}).encode())
        return i

    def call(self, method: str, params: dict, timeout: float = 10.0) -> dict:
        i = next(self._ids)
        ev = threading.Event()
        self._pending[i] = ev
        self._send_frame(json.dumps({"id": i, "method": method, "params": params}).encode())
        if not ev.wait(timeout):
            self._pending.pop(i, None)
            raise TimeoutError(method)
        msg = self._results.pop(i, {})
        if "error" in msg:
            raise RuntimeError(msg["error"].get("message"))
        return msg.get("result", {})

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass
        self.closed = True


def for_page(cdp, port: int) -> CDPStream:
    """Open a second CDP connection to the same tab as Playwright's CDPSession `cdp`."""
    tid = cdp.send("Target.getTargetInfo")["targetInfo"]["targetId"]
    return CDPStream(f"ws://127.0.0.1:{port}/devtools/page/{tid}")
