import os, shutil
from dotenv import dotenv_values
from . import channels
from .config import load
from .paths import CONFIG, ENV


def main():
    if not CONFIG.exists(): print("no config.toml: run `openjames init`"); return 1
    cfg, env, bad = load(), dotenv_values(ENV), 0
    for c in cfg.channels:
        ch = channels.get(c)
        miss = [k for k in ch.env_keys if k not in env]
        flag = "missing " + ",".join(miss) if miss else "ok"
        if not miss:
            os.environ.update({k: v for k, v in env.items() if v}); err = ch.check()
            if err: flag = err
        bad += flag != "ok"; print(f"channel {c}: {flag}; allowed={len(cfg.allowed_senders.get(c, []))}")
    for b in cfg.backends:
        cli = {"claude_code": "claude", "codex": "codex", "gemini": "gemini"}.get(b)
        ok = shutil.which(cli) if cli else True
        print(f"backend {b}: {'ok' if ok else 'CLI missing'}"); bad += not ok
    return 1 if bad else 0
