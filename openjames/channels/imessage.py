from . import Channel


class IMessage(Channel):
    """Stub: implement poll()/send() per openjames/channels/__init__.py, then set implemented = True."""
    name = "imessage"
    env_keys = []
    platforms = ["darwin"]
    implemented = False

    def poll(self): raise NotImplementedError("imessage channel is a stub; see docs/ADDING_A_CHANNEL.md")
    def send(self, to, text): raise NotImplementedError("imessage channel is a stub")


CHANNEL = IMessage
