import secrets, string
from .. import vault

TOOL_SCHEMA = {"type": "function", "function": {"name": "gen_password",
    "description": "Generate a password with real randomness (Python `secrets`); never invent one by hand. With store_file+key it is also saved to the vault and NOT returned (use secret_use to type it into a page).",
    "parameters": {"type": "object", "properties": {
        "length": {"type": "integer", "description": "default 20, 8-128"}, "symbols": {"type": "boolean", "description": "default true"},
        "passphrase_words": {"type": "integer", "description": "if set, generate a word-style passphrase of N hex-word groups instead"},
        "store_file": {"type": "string", "description": "vault file, e.g. 'github.txt'"}, "key": {"type": "string", "description": "key inside the file, default 'password'"},
        "note": {"type": "string", "description": "non-secret note line (site, username)"}}}}}


def run(a):
    n = max(8, min(int(a.get("length") or 20), 128))
    if a.get("passphrase_words"):
        pw = "-".join(secrets.token_hex(2) for _ in range(max(3, min(int(a["passphrase_words"]), 12))))
    else:
        alpha = string.ascii_letters + string.digits + ("!@#$%^&*-_=+?" if a.get("symbols", True) else "")
        while True:
            pw = "".join(secrets.choice(alpha) for _ in range(n))
            if any(c.islower() for c in pw) and any(c.isupper() for c in pw) and any(c.isdigit() for c in pw) and (not a.get("symbols", True) or any(c in "!@#$%^&*-_=+?" for c in pw)): break
    if a.get("store_file"):
        vault.set_key(a["store_file"], a.get("key") or "password", pw, a.get("note"))
        return {"stored": a["store_file"], "key": a.get("key") or "password", "chars": len(pw)}
    return {"password": pw, "note": "use it directly; do not write it to memory or chat logs"}
