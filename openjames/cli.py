import sys

HELP = "usage: openjames init | doctor | run | listen | deploy"

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "init": from .wizard import main as f
    elif cmd == "doctor": from .doctor import main as f
    elif cmd == "run": from .orchestrator import main as f
    elif cmd == "listen": from .listener import main as f
    elif cmd == "deploy": from .deploy import main as f
    else: print(HELP); return 2
    return f() or 0
