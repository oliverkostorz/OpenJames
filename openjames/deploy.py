"""Render deploy/ templates for this machine and print the install commands. Never installs by itself."""
import platform, sys
from .paths import ROOT

def main():
    py, mac = sys.executable, platform.system() == "Darwin"
    src = ROOT / "deploy" / ("openjames.plist.tmpl" if mac else "openjames.service.tmpl")
    out = ROOT / "state" / src.name.replace(".tmpl", "")
    out.parent.mkdir(exist_ok=True)
    out.write_text(src.read_text().replace("{{ROOT}}", str(ROOT)).replace("{{PYTHON}}", py))
    print(f"Rendered {out}. Review it, then:")
    print(f"  cp {out} ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/{out.name}" if mac else
          f"  mkdir -p ~/.config/systemd/user && cp {out} ~/.config/systemd/user/ && systemctl --user enable --now {out.name}")
