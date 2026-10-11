import json
import logging
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


def _simulate(to, body):
    print(f"[SIMULATED SMS to {to}] {body}")
    return "simulated"


def _twilio(to, body):
    from twilio.rest import Client
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(to=to, from_=settings.TWILIO_FROM_NUMBER, body=body)
    return "sent"


def _africastalking(to, body):
    host = "api.sandbox.africastalking.com" if settings.AT_SANDBOX else "api.africastalking.com"
    fields = {"username": settings.AT_USERNAME, "to": to, "message": body}
    if settings.AT_SENDER_ID:
        fields["from"] = settings.AT_SENDER_ID
    request = urllib.request.Request(
        f"https://{host}/version1/messaging",
        data=urllib.parse.urlencode(fields).encode(),
        headers={
            "apiKey": settings.AT_API_KEY,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode())
    recipients = data.get("SMSMessageData", {}).get("Recipients", [])
    if recipients and all(r.get("statusCode") in (100, 101, 102) for r in recipients):
        return "sent"
    logger.error("Africa's Talking did not accept the message: %s", data)
    return "failed"


PROVIDERS = {
    "simulate": _simulate,
    "twilio": _twilio,
    "africastalking": _africastalking,
}


def is_configured(name):
    if name == "simulate":
        return True
    if name == "twilio":
        return all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_FROM_NUMBER])
    if name == "africastalking":
        return all([settings.AT_USERNAME, settings.AT_API_KEY])
    return False


def send_sms(to, body):
    """Returns 'sent', 'simulated' or 'failed'. Never raises, so one bad send cannot stop the run."""
    name = settings.SMS_PROVIDER
    sender = PROVIDERS.get(name)
    if sender is None:
        logger.error("Unknown SMS_PROVIDER '%s'. Use simulate, twilio or africastalking.", name)
        return "failed"
    if not is_configured(name):
        logger.error("SMS provider '%s' is missing its settings.", name)
        return "failed"
    try:
        return sender(to, body)
    except Exception:
        logger.exception("SMS delivery failed with provider '%s'", name)
        return "failed"