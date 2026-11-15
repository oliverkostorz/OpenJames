from . import Channel


class Signal(Channel):
    """Stub: implement poll()/send() per openjames/channels/__init__.py, then set implemented = True."""
    name = "signal"
    env_keys = ["SIGNAL_NUMBER"]
    platforms = ["any"]
    implemented = False

    def poll(self): raise NotImplementedError("signal channel is a stub; see docs/ADDING_A_CHANNEL.md")
    def send(self, to, text): raise NotImplementedError("signal channel is a stub")


CHANNEL = Signal
