import os
import time
import datetime
import pandas as pd
import numpy as np
import yfinance as yf
from supabase import create_client

# --- Connections ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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

def check_portfolio_gap_downs():
    print("🔍 Checking Portfolio for Emergency Gap Downs...")
    res = supabase.table('portfolio').select("*").execute()
    portfolio = res.data
    
    if not portfolio:
        print("Portfolio is empty. All clear.")
        return

    for item in portfolio:
        sym = item['symbol']
        entry = float(item['entry_price'])
        
        # Pull live price
        try:
            live_data = yf.download(f"{sym}.NS", period="1d", progress=False, ignore_tz=True)
            if not live_data.empty:
                live_price = float(live_data['Close'].iloc[-1])
                
                # If price is 10% below entry, it's a catastrophic gap down
                if live_price <= (entry * 0.90):
                    print(f"🚨 EMERGENCY: {sym} has gapped down heavily! CMP: ₹{live_price:.2f} (Entry: ₹{entry:.2f}). EXIT IMMEDIATELY.")
                else:
                    print(f"✅ {sym} holding steady at ₹{live_price:.2f}.")
        except Exception as e:
            print(f"Could not check live status for {sym}: {e}")

if __name__ == "__main__":
    # 1. Always sync live prices first
    update_live_prices()
    
    # 2. Check the time (Convert UTC from GitHub to IST)
    ist_now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    print(f"Current IST Time: {ist_now.strftime('%H:%M')}")
    
    # 3. Check if the Indian Market is currently Open (9:00 AM to 3:30 PM IST)
    is_market_open = (ist_now.hour == 9 and ist_now.minute >= 0) or (10 <= ist_now.hour <= 14) or (ist_now.hour == 15 and ist_now.minute <= 30)
    
    if is_market_open:
        check_portfolio_gap_downs()
    else:
        print("Market is currently closed. Live price sync complete.")
