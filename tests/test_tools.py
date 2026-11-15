import sys, pathlib, tempfile, json, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from openjames import tools, vault, timers, paths, config, principal as pr
import openjames.tools.notify_principal as np_

names = {s["function"]["name"] for s in tools.get_tool_schemas()}
for n in "notify_principal ask_principal gen_password store_secret secret_use timer http_get web_observe web_act web_task subagent delegate".split(): assert n in names, n

tmp = pathlib.Path(tempfile.mkdtemp())
vault.DIR = tmp / "accounts"
cfg = config.Config(["telegram"], ["x"], {"telegram": ["42"]})
pr.load = lambda: cfg
paths.OUTBOX = np_.OUTBOX = tmp / "out"; np_.STATE = tmp / "state"; timers.STATE = tmp / "state"; timers.F = tmp / "state" / "timers.json"; timers.INBOX = tmp / "in"
timers.principal = pr.principal

# passwords: random, strong, stored without echo
a, b = (tools.call_tool("gen_password", {})["password"] for _ in range(2))
assert a != b and len(a) == 20 and any(c.isdigit() for c in a) and any(c.isupper() for c in a)
r = tools.call_tool("gen_password", {"store_file": "site.txt", "key": "password", "note": "site"})
assert "password" not in r and r["stored"] == "site.txt"
assert oct((vault.DIR / "site.txt").stat().st_mode)[-3:] == "600"
assert tools.call_tool("store_secret", {"action": "list"}) == {"site.txt": ["password"]}
v = tools.call_tool("secret_use", {"action": "reveal", "file": "site.txt"})["value"]
assert v in (vault.DIR / "site.txt").read_text() and "value" not in tools.call_tool("secret_use", {"action": "info", "file": "site.txt"})
try: vault.path("../x"); assert 0
except ValueError: pass

# notify: queued for the allow-listed principal only; secrets refused
r = tools.call_tool("notify_principal", {"text": "hello"}); assert r["status"] == "queued"
f = next((tmp / "out").glob("notify-*.md")); assert f.read_text().startswith("channel: telegram\nsender: 42\n")
assert tools.call_tool("notify_principal", {"text": "password: hunter2hunter2"})["status"] == "refused"

# timers: due ones become inbox tasks for the principal, recurring ones reschedule
t = tools.call_tool("timer", {"action": "set", "prompt": "ping", "in_minutes": -1, "every_minutes": 60})
assert timers.due() == 1 and "sender: 42" in next((tmp / "in").glob("timer-*.md")).read_text()
assert dt.datetime.fromisoformat(timers.load()[0]["at"]) > timers.now()
assert tools.call_tool("timer", {"action": "cancel", "id": t["id"]}) == "cancelled"
print("ok")
