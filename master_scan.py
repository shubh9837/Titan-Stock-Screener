import pandas as pd
import numpy as np
import pandas_ta_classic as ta
import time, os, datetime
from dateutil.relativedelta import relativedelta
from supabase import create_client
import concurrent.futures
from breeze_connect import BreezeConnect

# --- 1. Connections ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

ICICI_APP_KEY = os.environ.get("ICICI_APP_KEY")
ICICI_SECRET_KEY = os.environ.get("ICICI_SECRET_KEY")
ICICI_SESSION_TOKEN = os.environ.get("ICICI_SESSION_TOKEN")

breeze = BreezeConnect(api_key=ICICI_APP_KEY)
breeze.generate_session(api_secret=ICICI_SECRET_KEY, session_token=ICICI_SESSION_TOKEN)

# OPTIMIZATION 1: Reduced to 4 months. Less JSON data to download = Faster API response.
today_iso = datetime.datetime.utcnow().strftime('%Y-%m-%dT00:00:00.000Z')
four_months_ago_iso = (datetime.datetime.utcnow() - relativedelta(months=4)).strftime('%Y-%m-%dT00:00:00.000Z')

def safe_float(val, default=0.0):
    if pd.isna(val) or np.isinf(val): return default
    return float(val)

def fetch_icici_data(symbol, retries=3):
    """Fetches data with Exponential Backoff for maximum speed."""
    clean_symbol = symbol.strip().replace(".NS", "").upper()
    
    for attempt in range(retries):
        try:
            # OPTIMIZATION 2: Tiny jitter instead of massive 1.1s sleep
            time.sleep(np.random.uniform(0.1, 0.4)) 
            
            raw_data = breeze.get_historical_data(
                interval="1day",
                from_date=four_months_ago_iso,
                to_date=today_iso,
                stock_code=clean_symbol,
                exchange_code="NSE",
                product_type="cash"
            )
            
            # If ICICI returns valid data, parse and return it immediately
            if raw_data and 'Success' in raw_data and raw_data['Success']:
                df = pd.DataFrame(raw_data['Success'])
                df.rename(columns={'datetime': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index('Date', inplace=True)
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                return df, clean_symbol
            
            # If ICICI blocks us (Rate Limit), trigger Backoff Protocol
            else:
                time.sleep(2.5) # Wait 2.5 seconds and retry
                continue
                
        except Exception as e:
            time.sleep(2.5) # If network fails, wait and retry
            
    # If it fails 3 times in a row, the stock is invalid/delisted. Skip it.
    return pd.DataFrame(), clean_symbol

def process_stock(t):
    try:
        df, clean_symbol = fetch_icici_data(t)
        if df.empty or len(df) < 26: return None
            
        curr_p = safe_float(df['Close'].iloc[-1])
        res_20 = safe_float(df['High'].rolling(20).max().iloc[-1])
        sup_20 = safe_float(df['Low'].rolling(20).min().iloc[-1])
        open_tdy, close_tdy = safe_float(df['Open'].iloc[-1]), safe_float(df['Close'].iloc[-1])
        open_yst, close_yst = safe_float(df['Open'].iloc[-2]), safe_float(df['Close'].iloc[-2])
        
        df.ta.ema(length=20, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, append=True) 
        df.ta.atr(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True) 
        
        ema20 = safe_float(df['EMA_20'].iloc[-1] if 'EMA_20' in df else 0)
        ema50 = safe_float(df['EMA_50'].iloc[-1] if 'EMA_50' in df else 0)
        rsi = safe_float(df['RSI_14'].iloc[-1] if 'RSI_14' in df else 0)
        atr = safe_float(df['ATRr_14'].iloc[-1] if 'ATRr_14' in df else 0)
        macd_hist = safe_float(df['MACDh_12_26_9'].iloc[-1] if 'MACDh_12_26_9' in df else 0)
        macd_hist_prev = safe_float(df['MACDh_12_26_9'].iloc[-2] if 'MACDh_12_26_9' in df else 0)
        
        score = 0
        if curr_p > ema20: score += 20
        if ema20 > ema50: score += 20
        if 50 < rsi < 70: score += 20
        if macd_hist > macd_hist_prev: score += 40
        
        return {
            "SYMBOL": clean_symbol,
            "PRICE": round(curr_p, 2),
            "SCORE": score,
            "RSI": round(rsi, 2),
            "TARGET": round(curr_p + (2 * atr), 2),
            "STOP_LOSS": round(curr_p - (1.5 * atr), 2),
            "PATTERN": "Broker-Verified",
            "UPDATED_AT": time.strftime('%Y-%m-%d %H:%M:%S')
        }
    except: return None

if __name__ == "__main__":
    master = pd.read_csv("Tickers.csv")
    symbols = [str(s) for s in master['SYMBOL'].dropna().unique()]
    
    print(f"🚀 Smart Engine: Processing {len(symbols)} stocks with Exponential Backoff...")

    results = []
    
    # OPTIMIZATION 3: Back up to 3 workers for speed, relying on Backoff for safety.
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        for result in executor.map(process_stock, symbols):
            if result:
                results.append(result)
                if len(results) >= 50:
                    supabase.table('market_scans').upsert(results, on_conflict="SYMBOL").execute()
                    print(f"📦 Pushed batch. Total Validated: {len(results)}")
    
    if results:
        supabase.table('market_scans').upsert(results, on_conflict="SYMBOL").execute()
    
    print(f"✅ Fast Scan Complete. Total Stocks in Database: {len(results)}")
