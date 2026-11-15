"""CLI bridge: `python -m openjames.toolcli <tool> '<json args>'` (for CLI backends that cannot use the API loop)."""
import json, sys
from .toolloop import execute

if __name__ == "__main__":
    print(execute(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "{}"))
