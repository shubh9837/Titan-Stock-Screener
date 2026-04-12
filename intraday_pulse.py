import os
import pandas as pd
from supabase import create_client
from twilio.rest import Client

# 1. Connect to Database
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. Connect to Twilio (WhatsApp/SMS)
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.environ.get("TWILIO_WHATSAPP_NUMBER") # e.g., 'whatsapp:+14155238886'
MY_PHONE = os.environ.get("MY_PHONE_NUMBER")           # e.g., 'whatsapp:+919876543210'

def send_alert():
    try:
        # Fetch only today's Pre-Breakouts
        res = supabase.table('market_scans').select("*").eq('PATTERN', '⚡ Pre-Breakout Squeeze').execute()
        df = pd.DataFrame(res.data)
        
        if df.empty:
            msg = "🤖 Titan Quantum: No safe Breakout setups detected at 2:00 PM today. Stay in cash."
        else:
            # Get the top 3 highest scoring breakouts
            top_targets = df.sort_values(by="SCORE", ascending=False).head(3)
            msg = "⚡ *TITAN QUANTUM: 2:00 PM BREAKOUT PULSE* ⚡\n\n"
            
            for _, r in top_targets.iterrows():
                msg += f"🎯 *{r['SYMBOL']}* (Score: {r['SCORE']})\n"
                msg += f"CMP: ₹{r['PRICE']} | Resistance: ₹{r['RESISTANCE']}\n"
                msg += f"Target: ₹{r['TARGET']} | Stop: ₹{r['STOP_LOSS']}\n"
                msg += f"Action: Set alert at ₹{r['RESISTANCE']}. Buy if it crosses with volume!\n\n"
                
            msg += "Strategy: These are SWING TRADES. Hold for days until Target or Stop Loss is hit."

        # Send the message
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        message = client.messages.create(
            from_=TWILIO_FROM,
            body=msg,
            to=MY_PHONE
        )
        print(f"Alert sent successfully! Message SID: {message.sid}")
        
    except Exception as e:
        print(f"Error sending alert: {e}")

if __name__ == "__main__":
    if TWILIO_SID and TWILIO_TOKEN:
        send_alert()
    else:
        print("Twilio credentials missing. Skipping WhatsApp alert.")
