import os
import yfinance as yf
from supabase import create_client
import requests

# --- 1. Connect to Database ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. Twilio WhatsApp Setup ---
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.environ.get("TWILIO_WHATSAPP_NUMBER")
MY_PHONE = os.environ.get("MY_PHONE_NUMBER")

def send_whatsapp(body):
    if not TWILIO_SID or not TWILIO_TOKEN: return
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
    data = {"From": TWILIO_FROM, "To": MY_PHONE, "Body": body}
    try:
        requests.post(url, data=data, auth=(TWILIO_SID, TWILIO_TOKEN))
        print(f"📲 WhatsApp Alert Sent: {body}")
    except Exception as e:
        print("Failed to send WhatsApp:", e)

def run_intraday_pulse():
    print("⚡ Initiating 15-Minute Intraday Pulse...")

    # Fetch active portfolio
    res_port = supabase.table('portfolio').select("*").execute()
    portfolio = res_port.data

    # Fetch Top Gems (Score > 80) and Breakout Watchlist
    res_gems = supabase.table('market_scans').select("SYMBOL, STOP_LOSS, TARGET, PRICE").gte("SCORE", 80).execute()
    
    port_symbols = [p['symbol'] for p in portfolio]
    gem_symbols = [g['SYMBOL'] for g in res_gems.data]

    watch_symbols = list(set(port_symbols + gem_symbols))
    if not watch_symbols:
        print("No active portfolio or gems to track currently.")
        return

    print(f"Tracking {len(watch_symbols)} high-priority stocks...")

    for sym in watch_symbols:
        try:
            ticker = yf.Ticker(sym + ".NS")
            # fast_info uses a lightweight API endpoint to just grab the live price
            live_price = round(ticker.fast_info.last_price, 2) 
            
            # 1. Update the live price in the dashboard
supabase.table('market_scans').update({"PRICE": live_price, "UPDATED_AT": time.strftime('%Y-%m-%d %H:%M:%S')}).eq("SYMBOL", sym).execute()

            # 2. Check for Portfolio Alerts
            port_match = next((p for p in portfolio if p['symbol'] == sym), None)
            if port_match:
                # Get limits from the market_scans table
                db_data = next((g for g in res_gems.data if g['SYMBOL'] == sym), None)
                if not db_data:
                    # Fallback fetch if portfolio stock dropped below 80 score
                    res_single = supabase.table('market_scans').select("STOP_LOSS, TARGET").eq("SYMBOL", sym).execute()
                    if res_single.data: db_data = res_single.data[0]

                if db_data:
                    entry = float(port_match['entry_price'])
                    target = float(db_data['TARGET'])
                    orig_sl = float(db_data['STOP_LOSS'])
                    
                    # Trailing Stop Loss Logic
                    if live_price > (entry * 1.10): trailing_sl = entry * 1.05
                    elif live_price > (entry * 1.05): trailing_sl = entry
                    else: trailing_sl = orig_sl
                    
                    # Fire Alerts
                    if live_price <= trailing_sl:
                        send_whatsapp(f"🚨 ALERT: {sym} hit Stop Loss (₹{live_price}). Close the trade to protect capital.")
                    elif live_price >= target:
                        send_whatsapp(f"✅ ALERT: {sym} hit Target (₹{live_price}). Consider booking profits!")
                        
        except Exception as e:
            continue

    print("✅ Intraday Pulse Complete. Dashboard live prices updated and risk limits checked.")

if __name__ == "__main__":
    run_intraday_pulse()
