from ._twilio import TwilioChannel


class Sms(TwilioChannel):
    name = "sms"
    env_keys = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM"]
    from_key = "TWILIO_FROM"
    help = "Twilio console: copy Account SID + Auth Token and a phone number (E.164, e.g. +4915...). Polled, no webhook needed."
    id_hint = "your mobile number in E.164 form, e.g. +4915112345678"


CHANNEL = Sms
