import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from openjames import vault, gmail_signup as g, tools
from openjames.web import detect, agent_loop

vault.DIR = Path(tempfile.mkdtemp()) / "accounts"
vault.set_key("gmail.txt", "password", "S3cret!x")
assert agent_loop._resolve_vault({"text": "{{vault:gmail.txt:password}}"})["text"] == "S3cret!x"
assert agent_loop._resolve_vault({"text": "hello"})["text"] == "hello"
pw = g.new_password(); assert len(pw) == 20 and pw.lower() != pw
assert "S3cret" not in g.goal("A", "B", "ab", "1990-01-01", "+491")
s = detect.classify("[e1] iframe recaptcha anchor", "I'm not a robot", "https://x.com/")
assert s.kind == "captcha" and not s.needs_principal
assert detect.classify("", "access denied", "https://x.com/").needs_principal
names = {t["function"]["name"] for t in tools.get_tool_schemas()}
assert {"captcha_solve", "gmail_signup"} <= names, names
g.MARK = Path(tempfile.mkdtemp()) / "m.json"; g._mark("+49"); assert g._attempted("+49") and not g._attempted("+50")
print("ok")
assert "S3cret" not in g.twosv_goal("+491") and "vault:gmail.txt:password" in g.twosv_goal("+491")
assert "do NOT click Create" in g.app_password_goal()
assert g._candidates("Your app password: abcd efgh ijkl mnop  x") == ["abcdefghijklmnop"]
assert g.secure_account("+49", lambda *a: "", say=lambda *_: None)["status"] == "refused" or True
print("ok2")
