from . import Channel


class WhatsApp(Channel):
    \"\"\"Stub: implement poll()/send() per openjames/channels/__init__.py, then set implemented = True.\"\"\"
    name = "whatsapp"
    env_keys = ["WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_ID"]
    platforms = ["any"]
    implemented = False

    def poll(self): raise NotImplementedError("whatsapp channel is a stub; see docs/ADDING_A_CHANNEL.md")
    def send(self, to, text): raise NotImplementedError("whatsapp channel is a stub")


CHANNEL = WhatsApp
