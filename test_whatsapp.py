import os
from twilio.rest import Client

TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID", "MISSING")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "MISSING")
TWILIO_FROM = os.environ.get("TWILIO_WHATSAPP_NUMBER", "MISSING")
MY_PHONE = os.environ.get("MY_PHONE_NUMBER", "MISSING")

print("--- X-RAY DIAGNOSTIC ---")
# Using quotes to reveal any hidden spaces at the beginning or end
print(f"Account SID   : '{TWILIO_SID[:4]}...[MASKED]...' (Length: {len(TWILIO_SID)})")
print(f"From Number   : '{TWILIO_FROM}'")
print(f"To Number     : '{MY_PHONE}'")
print("------------------------\n")

if "MISSING" in [TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, MY_PHONE]:
    print("❌ ERROR: One or more GitHub Secrets are completely missing!")
    exit()

try:
    print("Attempting to connect to Twilio...")
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    message = client.messages.create(
        from_=TWILIO_FROM,
        body="🚀 *TITAN QUANTUM TEST*: Diagnostic successful!",
        to=MY_PHONE
    )
    print(f"✅ Success! Message SID: {message.sid}")
except Exception as e:
    print(f"❌ Twilio Error: {e}")
