from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.toml"      # gitignored, written by `openjames init`
ENV = ROOT / ".env"                # gitignored, secrets only
INBOX, OUTBOX, MEMORY = ROOT / "inbox", ROOT / "outbox", ROOT / "memory"
STATE = ROOT / "state"             # gitignored
