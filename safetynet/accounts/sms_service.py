import africastalking
from django.conf import settings

africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
sms = africastalking.SMS


def send_sms(phone_number, message):
    try:
        kwargs = {}
        if settings.AT_SENDER_ID:
            kwargs["sender_id"] = settings.AT_SENDER_ID
        return sms.send(message, [phone_number], **kwargs)
    except Exception as e:
        print(f"SMS failed: {e}")
        return None