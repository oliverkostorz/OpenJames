"""Local CDP websocket proxy.

Chrome 157 rejects `Browser.setDownloadBehavior` ("Browser context management is not
supported") and Playwright sends it at connect, so every attach failed. The proxy forwards
everything to Chrome unchanged, except the methods in STUB, which it answers with `{}`.
Playwright connects to the proxy's ws:// URL instead of http://host:port.
"""

from __future__ import annotations

import asyncio
import json
import threading

import httpx
import websockets

STUB = {"Browser.setDownloadBehavior"}


class CdpProxy:
    def __init__(self, port: int):
        self.port = port
        self.url = ""
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> str:
        self._thread.start()
        self._ready.wait(10)
        return self.url

    def stop(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        async def go():
            return await websockets.serve(self._handle, "127.0.0.1", 0, max_size=None)
        server = self._loop.run_until_complete(go())
        self.url = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/"
        self._ready.set()
        self._loop.run_forever()

    async def _handle(self, client) -> None:
        info = httpx.get(f"http://127.0.0.1:{self.port}/json/version", timeout=5).json()
        async with websockets.connect(info["webSocketDebuggerUrl"], max_size=None,
                                      ping_interval=None) as up:
            async def c2u():
                async for msg in client:
                    try:
                        d = json.loads(msg)
                    except Exception:
                        d = None
                    if isinstance(d, dict) and d.get("method") in STUB and "id" in d:
                        await client.send(json.dumps({"id": d["id"], "result": {}}))
                    else:
                        await up.send(msg)

            async def u2c():
                async for msg in up:
                    await client.send(msg)

            tasks = [asyncio.ensure_future(c2u()), asyncio.ensure_future(u2c())]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in tasks:
                t.cancel()
