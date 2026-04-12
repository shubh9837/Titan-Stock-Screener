import yfinance as yf
import pandas as pd
import numpy as np
import pandas_ta_classic as ta
import time, os, datetime
from supabase import create_client

# --- 1. Connect to Database ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase Secrets! Check GitHub Secrets.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_earnings_risk(ticker_obj):
    try:
        calendar = ticker_obj.calendar
        if not calendar.empty:
            earnings_date = calendar.iloc[0, 0] 
            days_to_earnings = (earnings_date.date() - datetime.date.today()).days
            if 0 <= days_to_earnings <= 7:
                return f"⚠️ Earnings in {days_to_earnings} days"
    except:
        pass
    return "✅ Clear"

def safe_float(val, default=0.0):
    """Prevents JSON crashes when sending missing data (NaN) to Supabase"""
    if pd.isna(val) or np.isinf(val): return default
    return float(val)

# --- 2. Master Scan Engine ---
print("Initiating Full Universe Scan...")
institutional_trend = "Bullish"

master = pd.read_csv("Tickers.csv")
symbols = [f"{str(s).strip()}.NS" for s in master['SYMBOL'].dropna().unique()]

results = []
print(f"🚀 Starting master scan for ALL {len(symbols)} stocks...")

success_count = 0

for t in symbols: 
    try:
        ticker = yf.Ticker(t)
        df = ticker.history(period="6mo", interval="1d")
        
        # Keep everything. We apply penalties later instead of dropping.
        if df.empty:
            continue
            
        curr_p = safe_float(df['Close'].iloc[-1])
        if curr_p == 0: continue
        
        # --- Technicals ---
        df.ta.ema(length=20, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, append=True) 
        df.ta.atr(length=14, append=True)
        
        df['Vol_20_MA'] = df['Volume'].rolling(window=20).mean()
        
        avg_vol = safe_float(df['Vol_20_MA'].iloc[-1])
        current_vol = safe_float(df['Volume'].iloc[-1])
        rvol = current_vol / avg_vol if avg_vol > 0 else 0
        
        ema20 = safe_float(df['EMA_20'].iloc[-1] if 'EMA_20' in df else 0)
        ema50 = safe_float(df['EMA_50'].iloc[-1] if 'EMA_50' in df else 0)
        rsi = safe_float(df['RSI_14'].iloc[-1] if 'RSI_14' in df else 0)
        atr = safe_float(df['ATRr_14'].iloc[-1] if 'ATRr_14' in df else 0)
        
        bb_width = 100 
        if 'BBU_20_2.0' in df and 'BBL_20_2.0' in df:
            bb_upper = safe_float(df['BBU_20_2.0'].iloc[-1])
            bb_lower = safe_float(df['BBL_20_2.0'].iloc[-1])
            bb_width = (bb_upper - bb_lower) / curr_p * 100 
            
        # --- Lazy Fetching & Secondary Fallback ---
        try:
            info = ticker.info
            sector_strength = info.get('sector', info.get('industry', ''))
            mcap = info.get('marketCap', 0)
            
            if sector_strength == '' or mcap == 0:
                fast = ticker.fast_info
                if mcap == 0: mcap = fast.get('market_cap', 0)
                if sector_strength == '': sector_strength = "Unknown" 
        except:
            sector_strength = "Unknown"
            mcap = 0
            
        earnings_risk = get_earnings_risk(ticker)
        
        # --- MARKET CAP CLASSIFICATION ---
        if curr_p < 20 or mcap < 5000000000: cap_category = "Penny / Micro Cap"
        elif mcap < 50000000000: cap_category = "Small Cap"
        elif mcap < 200000000000: cap_category = "Mid Cap"
        else: cap_category = "Large Cap"
        
        # --- 100-POINT CONFLUENCE ALGORITHM ---
        score = 0
        
        if ema20 > 0 and curr_p > ema20: score += 15
        if ema50 > 0 and ema20 > ema50: score += 15
        if 55 <= rsi <= 70: score += 20 
        elif rsi > 70: score += 10 
        if rvol > 2.0: score += 25 
        elif rvol > 1.2: score += 15 
        if bb_width < 5.0: score += 25 
        elif bb_width < 10.0: score += 10 
        
        # --- AGGRESSIVE RISK PENALTIES ---
        if cap_category == "Penny / Micro Cap": score -= 30 
        
        turnover = avg_vol * curr_p
        if turnover < 10000000: score -= 30 
        elif turnover < 50000000: score -= 15 
        
        if len(df) < 50: score -= 40 
        if "⚠️" in earnings_risk: score -= 40 
        
        score = max(0, score)
        
        results.append({
            "SYMBOL": t.replace(".NS", ""),
            "PRICE": round(curr_p, 2),
            "SCORE": score,
            "RSI": round(rsi, 2),
            "TARGET": round(curr_p + (3 * atr), 2) if atr > 0 else 0,
            "STOP_LOSS": round(curr_p - (2 * atr), 2) if atr > 0 else 0,
            "EARNINGS_RISK": earnings_risk,
            "SECTOR_STRENGTH": sector_strength,
            "INSTITUTIONAL_TREND": institutional_trend,
            "CAP_CATEGORY": cap_category,
            "UPDATED_AT": time.strftime('%Y-%m-%d %H:%M:%S')
        })
        
        success_count += 1
        time.sleep(0.3) 
        
    except Exception as e:
        continue

# --- 3. Database Push ---
print(f"📊 Engine Report: Successfully Scanned {success_count} Stocks.")

if results:
    try:
        supabase.table('market_scans').delete().gt('id', 0).execute()
    except:
        pass 
        
    supabase.table('market_scans').insert(results).execute()
    print(f"✅ Full Universe Sync Complete. Pushed to database.")
