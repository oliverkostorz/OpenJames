from . import Channel


class Sms(Channel):
    \"\"\"Stub: implement poll()/send() per openjames/channels/__init__.py, then set implemented = True.\"\"\"
    name = "sms"
    env_keys = ["SMS_PROVIDER_KEY"]
    platforms = ["any"]
    implemented = False

    def poll(self): raise NotImplementedError("sms channel is a stub; see docs/ADDING_A_CHANNEL.md")
    def send(self, to, text): raise NotImplementedError("sms channel is a stub")


CHANNEL = Sms
