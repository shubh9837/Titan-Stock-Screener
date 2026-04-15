import os
from twilio.rest import Client

TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.environ.get("TWILIO_WHATSAPP_NUMBER")
MY_PHONE = os.environ.get("MY_PHONE_NUMBER")

print(f"Connecting to Twilio...")
print(f"Sending from: {TWILIO_FROM}")
print(f"Sending to: {MY_PHONE}")

try:
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    message = client.messages.create(
        from_=TWILIO_FROM,
        body="🚀 *TITAN QUANTUM TEST*: If you are reading this, your Twilio API is perfectly connected!",
        to=MY_PHONE
    )
    print(f"✅ Success! Message SID: {message.sid}")
except Exception as e:
    print(f"❌ Twilio Error: {e}")
