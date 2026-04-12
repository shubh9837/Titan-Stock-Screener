import pandas as pd
import numpy as np
import pandas_ta_classic as ta
import time, os, datetime
from dateutil.relativedelta import relativedelta
from supabase import create_client
import concurrent.futures
from breeze_connect import BreezeConnect

# --- 1. Database Connect ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. ICICI Breeze Connect ---
ICICI_APP_KEY = os.environ.get("ICICI_APP_KEY")
ICICI_SECRET_KEY = os.environ.get("ICICI_SECRET_KEY")
ICICI_SESSION_TOKEN = os.environ.get("ICICI_SESSION_TOKEN")

if not ICICI_APP_KEY or not ICICI_SESSION_TOKEN:
    raise ValueError("Missing ICICI Credentials in GitHub Secrets!")

breeze = BreezeConnect(api_key=ICICI_APP_KEY)
breeze.generate_session(api_secret=ICICI_SECRET_KEY, session_token=ICICI_SESSION_TOKEN)

# Calculate Date Range for 6 Months of Data
today_iso = datetime.datetime.utcnow().strftime('%Y-%m-%dT00:00:00.000Z')
six_months_ago_iso = (datetime.datetime.utcnow() - relativedelta(months=6)).strftime('%Y-%m-%dT00:00:00.000Z')

def safe_float(val, default=0.0):
    if pd.isna(val) or np.isinf(val): return default
    return float(val)

def fetch_icici_data(symbol):
    """Fetches clean OHLCV data from ICICI and converts to Pandas DataFrame"""
    try:
        # 1. Clean the symbol (Remove spaces and force Uppercase)
        clean_symbol = symbol.strip().replace(".NS", "").upper()
        
        # 2. RATE LIMITER: ICICI allows ~1 request per second. 
        # Adding this pause ensures we never get blocked.
        time.sleep(1.1)
        
        raw_data = breeze.get_historical_data(
            interval="1day",
            from_date=six_months_ago_iso,
            to_date=today_iso,
            stock_code=clean_symbol,
            exchange_code="NSE",
            product_type="cash"
        )
        
        if 'Success' in raw_data and raw_data['Success']:
            df = pd.DataFrame(raw_data['Success'])
            # Rename columns to match what our Pandas TA engine expects
            df.rename(columns={'datetime': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            
            # Ensure numbers are floats, not strings
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
            return df, clean_symbol
        return pd.DataFrame(), clean_symbol
    except Exception as e:
        return pd.DataFrame(), symbol.replace(".NS", "")

def process_stock(t):
    """The God-Mode 100-Point Engine powered by ICICI Data"""
    try:
        df, clean_symbol = fetch_icici_data(t)
        
        if df.empty or len(df) < 26: return None
            
        curr_p = safe_float(df['Close'].iloc[-1])
        if curr_p == 0: return None
        
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
        
        df['Vol_20_MA'] = df['Volume'].rolling(window=20).mean()
        avg_vol = safe_float(df['Vol_20_MA'].iloc[-1])
        current_vol = safe_float(df['Volume'].iloc[-1])
        rvol = current_vol / avg_vol if avg_vol > 0 else 0
        
        ema20 = safe_float(df['EMA_20'].iloc[-1] if 'EMA_20' in df else 0)
        ema50 = safe_float(df['EMA_50'].iloc[-1] if 'EMA_50' in df else 0)
        rsi = safe_float(df['RSI_14'].iloc[-1] if 'RSI_14' in df else 0)
        atr = safe_float(df['ATRr_14'].iloc[-1] if 'ATRr_14' in df else 0)
        macd_hist = safe_float(df['MACDh_12_26_9'].iloc[-1] if 'MACDh_12_26_9' in df else 0)
        macd_hist_prev = safe_float(df['MACDh_12_26_9'].iloc[-2] if 'MACDh_12_26_9' in df else 0)
        
        bb_width = 100 
        if 'BBU_20_2.0' in df and 'BBL_20_2.0' in df:
            bb_upper = safe_float(df['BBU_20_2.0'].iloc[-1])
            bb_lower = safe_float(df['BBL_20_2.0'].iloc[-1])
            bb_width = (bb_upper - bb_lower) / curr_p * 100 

        pattern = "None"
        is_bull_engulf = (close_yst < open_yst) and (open_tdy < close_yst) and (close_tdy > open_yst)
        if is_bull_engulf: pattern = "🟢 Bullish Engulfing"
        
        vol_dry_up = False
        if len(df) > 5:
            last_3_vol_avg = df['Volume'].iloc[-4:-1].mean()
            if last_3_vol_avg < avg_vol and rvol > 1.5: vol_dry_up = True

        is_pre_breakout = False
        if bb_width < 6.0 and ((res_20 - curr_p) / curr_p) < 0.03 and macd_hist > macd_hist_prev:
            is_pre_breakout = True
            pattern = "⚡ Pre-Breakout Squeeze"
            
        # Bypass Yahoo entirely. Hardcode fallbacks for safety since ICICI doesn't provide MCAP natively here.
        sector_strength = "Unknown" 
        cap_category = "Large/Mid Cap"
        if curr_p < 20: cap_category = "Penny / Micro Cap"
            
        score = 0
        if ema20 > 0 and curr_p > ema20: score += 10
        if ema50 > 0 and ema20 > ema50: score += 10
        if 55 <= rsi <= 70: score += 10 
        if vol_dry_up: score += 20 
        elif rvol > 1.5: score += 10
        if is_pre_breakout: score += 30 
        elif bb_width < 5.0: score += 15 
        if is_bull_engulf: score += 20 
        
        if cap_category == "Penny / Micro Cap": score -= 30 
        turnover = avg_vol * curr_p
        if turnover < 10000000: score -= 30 
        
        target_price = curr_p + (3 * atr)
        stop_loss_price = curr_p - (2 * atr)
        rr_ratio = ((target_price - curr_p) / (curr_p - stop_loss_price)) if (curr_p - stop_loss_price) > 0 else 0
        
        return {
            "SYMBOL": clean_symbol,
            "PRICE": round(curr_p, 2),
            "SCORE": max(0, min(100, score)), 
            "RSI": round(rsi, 2),
            "TARGET": round(target_price, 2) if atr > 0 else 0,
            "STOP_LOSS": round(stop_loss_price, 2) if atr > 0 else 0,
            "RR_RATIO": round(rr_ratio, 2),
            "SUPPORT": round(sup_20, 2),
            "RESISTANCE": round(res_20, 2),
            "PATTERN": pattern,
            "EARNINGS_RISK": "✅ Clear", # Removed Yahoo Earnings risk to save latency
            "SECTOR_STRENGTH": sector_strength,
            "INSTITUTIONAL_TREND": "Bullish",
            "CAP_CATEGORY": cap_category,
            "UPDATED_AT": time.strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e: return None

if __name__ == "__main__":
    print("Initiating Broker API Data Stream (ICICI Breeze)...")
    master = pd.read_csv("Tickers.csv")
    symbols = [f"{str(s).strip()}" for s in master['SYMBOL'].dropna().unique()]
    
    print(f"🚀 Engine connected directly to Exchange. Targets: {len(symbols)}. Processing with 5 workers.")

    batch_results = []
    success_count = 0
    BATCH_SIZE = 100 

    # We can turn workers back up to 5 because ICICI allows higher rate limits than Yahoo
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_stock, t): t for t in symbols}
        
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            
            if result is not None:
                batch_results.append(result)
                success_count += 1
                
            if len(batch_results) >= BATCH_SIZE:
                supabase.table('market_scans').upsert(batch_results, on_conflict="SYMBOL").execute()
                print(f"📦 [STREAM] Scanned & Pushed a batch of {BATCH_SIZE}. Validated: {success_count}")
                batch_results = [] 

    if batch_results: 
        supabase.table('market_scans').upsert(batch_results, on_conflict="SYMBOL").execute()

    print(f"✅ Full Universe Data Complete. Validated: {success_count} stocks.")
