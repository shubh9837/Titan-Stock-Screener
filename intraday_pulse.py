import os
import time
import datetime
import pandas as pd
import numpy as np
import yfinance as yf
from supabase import create_client
from twilio.rest import Client

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
            
            if len(updates) >= 200:
                supabase.table('market_scans').upsert(updates, on_conflict="SYMBOL").execute()
                updates = []
        except: continue
        
    if updates:
        supabase.table('market_scans').upsert(updates, on_conflict="SYMBOL").execute()
    print("✅ Live prices updated in database.")

def monitor_breakouts(ist_now):
    print("🔍 Checking for confirmed afternoon breakouts...")
    
    res = supabase.table('market_scans').select("*").eq('PATTERN', '⚡ Pre-Breakout Squeeze').execute()
    candidates = res.data
    
    if not candidates:
        print("No Pre-Breakout candidates to monitor right now.")
        return

    fresh_breakouts = []
    db_updates = []
    
    for c in candidates:
        sym = c['SYMBOL']
        live_price = float(c['PRICE'])
        resistance = float(c['RESISTANCE'])
        target = float(c['TARGET'])
        stop = float(c['STOP_LOSS'])
        score = float(c['SCORE'])
        
        # UPGRADE: The 2:00 PM Confirmation Rule
        if live_price > resistance and ist_now.hour >= 14:
            upside = ((target - live_price) / live_price) * 100
            est_period = "5-14 Days" if score >= 85 else "15-30 Days" if score >= 65 else "30-45 Days"
            
            fresh_breakouts.append(
                f"🚀 *{sym}* is BREAKING OUT!\n"
                f"Entry: ₹{live_price:.2f} (Crossed ₹{resistance:.2f})\n"
                f"Target: ₹{target:.2f} (+{upside:.1f}%)\n"
                f"Stop Loss: ₹{stop:.2f}\n"
                f"Hold Period: {est_period}\n"
                f"Score: {score}/100"
            )
            
            db_updates.append({
                "SYMBOL": sym,
                "PATTERN": "🟢 BREAKOUT CONFIRMED",
                "UPDATED_AT": time.strftime('%Y-%m-%d %H:%M:%S')
            })

    if fresh_breakouts:
        msg = "⚡ *TITAN QUANTUM: 2:00 PM CONFIRMED BREAKOUT* ⚡\n\n"
        msg += "\n\n---\n".join(fresh_breakouts)
        msg += "\n\n_Note: Afternoon breakout confirmed. Proceed with sizing rules._"

        try:
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            client.messages.create(from_=TWILIO_FROM, body=msg, to=MY_PHONE)
            print(f"📱 WhatsApp Alert sent! {len(fresh_breakouts)} confirmed breakouts.")
            
            supabase.table('market_scans').upsert(db_updates, on_conflict="SYMBOL").execute()
            print("✅ Database updated to prevent duplicate alerts.")
        except Exception as e:
            print(f"❌ Error sending alert: {e}")
    else:
        print("No confirmed crossovers in this window.")

if __name__ == "__main__":
    update_live_prices()
    
    ist_now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    print(f"Current IST Time: {ist_now.strftime('%H:%M')}")
    
    is_market_open = (ist_now.hour == 9 and ist_now.minute >= 0) or (10 <= ist_now.hour <= 14) or (ist_now.hour == 15 and ist_now.minute <= 30)
    
    if is_market_open:
        if TWILIO_SID and TWILIO_TOKEN:
            monitor_breakouts(ist_now) # Pass the time to the function
        else:
            print("⚠️ Twilio credentials missing.")
    else:
        print("Market is currently closed. Live price sync complete.")
