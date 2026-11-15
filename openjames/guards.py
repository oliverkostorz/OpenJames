"""Privacy guards applied to everything that leaves the machine (replies, mail, commits)."""
import re

PATTERNS = [r"sk-[A-Za-z0-9_-]{20,}", r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b", r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
            r"(?i)(password|app[_ ]?password|token|secret)\s*[:=]\s*\S{8,}", r"AKIA[0-9A-Z]{16}"]

def find_secrets(text: str) -> list[str]:
    return [m.group(0)[:8] + "…" for p in PATTERNS for m in re.finditer(p, text)]

def scrub(text: str) -> str:
    for p in PATTERNS: text = re.sub(p, "[redacted]", text)
    return text
