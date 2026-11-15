from ._twilio import TwilioChannel


class WhatsApp(TwilioChannel):
    name = "whatsapp"
    env_keys = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM"]
    prefix = "whatsapp:"
    from_key = "TWILIO_WHATSAPP_FROM"
    help = "Twilio WhatsApp sandbox or sender: join the sandbox from your phone, copy SID, token and the sandbox number. Polled, no webhook."
    id_hint = "your WhatsApp number in E.164 form, e.g. +4915112345678"


CHANNEL = WhatsApp
