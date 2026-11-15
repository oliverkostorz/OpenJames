import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from openjames import guards, backends, tools, config

assert guards.find_secrets("password: hunter2hunter2")
assert "sk-" not in guards.scrub("key sk-abcdefghijklmnopqrstuvwxyz123456")
assert "list_tools" in [s["function"]["name"] for s in tools.get_tool_schemas()]

# fallback chain honours priority and skips unavailable/exhausted backends
import types
def fake(name, exc=None):
    m = types.ModuleType(name)
    def run(s, p):
        if exc: raise exc(name)
        return name
    m.run = run; sys.modules[f"openjames.backends.{name}"] = m
fake("a", backends.Unavailable); fake("b", backends.Exhausted); fake("c")
assert backends.run_chain(["a", "b", "c"], "", "") == ("c", "c")
cfg = config.Config(["telegram"], ["c", "a"], {"telegram": ["1"]})
import tomllib; assert tomllib.loads(config.dump(cfg))["backends"]["priority"] == ["c", "a"]
for c in config.CHANNELS:
    from openjames import channels; channels.get(c)
print("ok")
