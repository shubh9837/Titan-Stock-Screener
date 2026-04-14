import os
import time
import datetime
import pandas as pd
import numpy as np
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
    
    # We only need 5 days of data for a quick intraday price update
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

def monitor_breakouts():
    print("🔍 Checking for fresh intraday breakouts...")
    
    # 1. Get all stocks that are currently resting at resistance (Pre-Breakouts)
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
        
        # 2. THE TRIGGER: Live price just crossed the resistance line
        if live_price > resistance:
            upside = ((target - live_price) / live_price) * 100
            
            # Recreate Dynamic Holding Period Logic
            est_period = "5-14 Days" if score >= 85 else "15-30 Days" if score >= 65 else "30-45 Days"
            
            # Build the beautiful WhatsApp message
            fresh_breakouts.append(
                f"🚀 *{sym}* is BREAKING OUT!\n"
                f"Entry: ₹{live_price:.2f} (Crossed ₹{resistance:.2f})\n"
                f"Target: ₹{target:.2f} (+{upside:.1f}%)\n"
                f"Stop Loss: ₹{stop:.2f}\n"
                f"Hold Period: {est_period}\n"
                f"Score: {score}/100"
            )
            
            # 3. Stage database update to prevent spamming the user on the next 15-min run
            db_updates.append({
                "SYMBOL": sym,
                "PATTERN": "🟢 BREAKOUT CONFIRMED",
                "UPDATED_AT": time.strftime('%Y-%m-%d %H:%M:%S')
            })

    # 4. Send WhatsApp Alert if we found any fresh breakouts
    if fresh_breakouts:
        msg = "⚡ *TITAN QUANTUM: LIVE BREAKOUT ALERT* ⚡\n\n"
        msg += "\n\n---\n".join(fresh_breakouts)
        msg += "\n\n_Note: Verify volume on your chart before entering._"

        try:
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            message = client.messages.create(
                from_=TWILIO_FROM,
                body=msg,
                to=MY_PHONE
            )
            print(f"📱 WhatsApp Alert sent! {len(fresh_breakouts)} new breakouts.")
            
            # Instantly update the DB so we don't send this alert again today
            supabase.table('market_scans').upsert(db_updates, on_conflict="SYMBOL").execute()
            print("✅ Database patterns updated to 'BREAKOUT CONFIRMED' to prevent duplicate alerts.")
        except Exception as e:
            print(f"❌ Error sending alert: {e}")
    else:
        print("No new resistance crossovers in this 15-minute window.")

if __name__ == "__main__":
    # 1. Always sync live prices first
    update_live_prices()
    
    # 2. Check the time (Convert UTC from GitHub to IST)
    ist_now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    print(f"Current IST Time: {ist_now.strftime('%H:%M')}")
    
    # 3. Check if the Indian Market is currently Open (9:00 AM to 3:30 PM IST)
    is_market_open = (ist_now.hour == 9 and ist_now.minute >= 0) or (10 <= ist_now.hour <= 14) or (ist_now.hour == 15 and ist_now.minute <= 30)
    
    if is_market_open:
        if TWILIO_SID and TWILIO_TOKEN:
            monitor_breakouts()
        else:
            print("⚠️ Twilio credentials missing in GitHub Secrets.")
    else:
        print("Market is currently closed. Live price sync complete, skipping breakout monitor.")
