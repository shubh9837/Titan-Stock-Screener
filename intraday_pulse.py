import os
import time
import datetime
import pandas as pd
import numpy as np
import pandas_ta_classic as ta
import yfinance as yf
from supabase import create_client
from twilio.rest import Client

# --- Connections ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.environ.get("TWILIO_WHATSAPP_NUMBER") 
MY_PHONE = os.environ.get("MY_PHONE_NUMBER")           

def safe_float(val, default=0.0):
    if pd.isna(val) or np.isinf(val): return default
    return float(val)

def update_live_prices():
    print("🔄 Initiating 15-Min Live Price Sync...")
    master = pd.read_csv("Tickers.csv")
    symbols = [f"{str(s).strip()}.NS" for s in master['SYMBOL'].dropna().unique()]
    
    # We only need 5 days of data for a quick intraday price update to save time
    data = yf.download(symbols, period="5d", group_by="ticker", threads=True, ignore_tz=True)
    
    updates = []
    for t in symbols:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if t not in data.columns.get_level_values(0).unique(): continue
                df = data[t].copy()
            else:
                df = data.copy()

            df.dropna(inplace=True)
            if df.empty: continue

            curr_p = safe_float(df['Close'].iloc[-1])
            if curr_p == 0: continue
            
            updates.append({
                "SYMBOL": t.replace(".NS", ""),
                "PRICE": round(curr_p, 2),
                "UPDATED_AT": time.strftime('%Y-%m-%d %H:%M:%S')
            })
            
            # Push in small batches
            if len(updates) >= 200:
                supabase.table('market_scans').upsert(updates, on_conflict="SYMBOL").execute()
                updates = []
        except: continue
        
    if updates:
        supabase.table('market_scans').upsert(updates, on_conflict="SYMBOL").execute()
    print("✅ Live prices updated in database.")

def send_alert():
    try:
        # Fetch today's Pre-Breakouts
        res = supabase.table('market_scans').select("*").eq('PATTERN', '⚡ Pre-Breakout Squeeze').execute()
        df = pd.DataFrame(res.data)
        
        if df.empty:
            msg = "🤖 *TITAN QUANTUM: 2:00 PM PULSE*\nNo safe Breakout setups detected today. Stay in cash."
        else:
            top_targets = df.sort_values(by="SCORE", ascending=False).head(3)
            msg = "⚡ *TITAN QUANTUM: 2:00 PM BREAKOUT PULSE* ⚡\n\n"
            
            for _, r in top_targets.iterrows():
                msg += f"🎯 *{r['SYMBOL']}* (Score: {r['SCORE']})\n"
                msg += f"CMP: ₹{r['PRICE']} | Resistance: ₹{r['RESISTANCE']}\n"
                msg += f"Target: ₹{r['TARGET']} | Stop: ₹{r['STOP_LOSS']}\n"
                msg += f"Action: Check chart. Buy if it is crossing Resistance with volume!\n\n"
                
            msg += "Strategy: These are SWING TRADES. Do not exit today. Hold for days until Target or Stop Loss is hit."

        client = Client(TWILIO_SID, TWILIO_TOKEN)
        message = client.messages.create(
            from_=TWILIO_FROM,
            body=msg,
            to=MY_PHONE
        )
        print(f"📱 WhatsApp Alert sent! Message SID: {message.sid}")
    except Exception as e:
        print(f"❌ Error sending alert: {e}")

if __name__ == "__main__":
    # 1. Always update prices first
    update_live_prices()
    
    # 2. Check the time (Convert UTC to IST)
    ist_now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    print(f"Current IST Time: {ist_now.strftime('%H:%M')}")
    
    # 3. If it is between 2:00 PM and 2:14 PM IST, trigger the WhatsApp Alert
    if ist_now.hour == 14 and ist_now.minute < 15:
        print("⏰ 2:00 PM Threshold Reached. Triggering Twilio...")
        if TWILIO_SID and TWILIO_TOKEN:
            send_alert()
        else:
            print("⚠️ Twilio credentials missing in GitHub Secrets.")
