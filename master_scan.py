import yfinance as yf
import pandas as pd
import numpy as np
import pandas_ta_classic as ta
import time, os, datetime
from supabase import create_client
import concurrent.futures

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_earnings_risk(ticker_obj):
    try:
        calendar = ticker_obj.calendar
        if not calendar.empty:
            earnings_date = calendar.iloc[0, 0] 
            days = (earnings_date.date() - datetime.date.today()).days
            if 0 <= days <= 7: return f"⚠️ In {days} days"
    except: pass
    return "✅ Clear"

def safe_float(val, default=0.0):
    if pd.isna(val) or np.isinf(val): return default
    return float(val)

def process_stock(t):
    """This function processes a single stock. It will be run in parallel by our workers."""
    try:
        # Add a tiny random sleep to prevent hitting Yahoo Finance too hard
        time.sleep(np.random.uniform(0.5, 1.5)) 
        
        ticker = yf.Ticker(t)
        df = ticker.history(period="6mo", interval="1d")
        if df.empty or len(df) < 26: return None
            
        curr_p = safe_float(df['Close'].iloc[-1])
        if curr_p == 0: return None
        
        # --- Support, Resistance & Candles ---
        res_20 = safe_float(df['High'].rolling(20).max().iloc[-1])
        sup_20 = safe_float(df['Low'].rolling(20).min().iloc[-1])
        open_tdy, close_tdy = safe_float(df['Open'].iloc[-1]), safe_float(df['Close'].iloc[-1])
        open_yst, close_yst = safe_float(df['Open'].iloc[-2]), safe_float(df['Close'].iloc[-2])
        
        # --- Technicals ---
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

        # --- Advanced Pattern & Breakout Detection ---
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
            
        try:
            info = ticker.info
            sector_strength = info.get('sector', info.get('industry', 'Unknown'))
            mcap = info.get('marketCap', 0)
            if sector_strength == '' or mcap == 0:
                fast = ticker.fast_info
                if mcap == 0: mcap = fast.get('market_cap', 0)
                if sector_strength == '': sector_strength = "Unknown" 
        except: sector_strength, mcap = "Unknown", 0
            
        earnings_risk = get_earnings_risk(ticker)
        if curr_p < 20 or mcap < 5000000000: cap_category = "Penny / Micro Cap"
        elif mcap < 50000000000: cap_category = "Small Cap"
        elif mcap < 200000000000: cap_category = "Mid Cap"
        else: cap_category = "Large Cap"
        
        # --- 100-POINT ALGORITHM ---
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
        if "⚠️" in earnings_risk: score -= 40 
        
        target_price = curr_p + (3 * atr)
        stop_loss_price = curr_p - (2 * atr)
        rr_ratio = ((target_price - curr_p) / (curr_p - stop_loss_price)) if (curr_p - stop_loss_price) > 0 else 0
        
        return {
            "SYMBOL": t.replace(".NS", ""),
            "PRICE": round(curr_p, 2),
            "SCORE": max(0, min(100, score)), 
            "RSI": round(rsi, 2),
            "TARGET": round(target_price, 2) if atr > 0 else 0,
            "STOP_LOSS": round(stop_loss_price, 2) if atr > 0 else 0,
            "RR_RATIO": round(rr_ratio, 2),
            "SUPPORT": round(sup_20, 2),
            "RESISTANCE": round(res_20, 2),
            "PATTERN": pattern,
            "EARNINGS_RISK": earnings_risk,
            "SECTOR_STRENGTH": sector_strength,
            "INSTITUTIONAL_TREND": "Bullish",
            "CAP_CATEGORY": cap_category,
            "UPDATED_AT": time.strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e: return None

if __name__ == "__main__":
    print("Initiating Multi-Threaded Master Scan...")
    master = pd.read_csv("Tickers.csv")
    symbols = [f"{str(s).strip()}.NS" for s in master['SYMBOL'].dropna().unique()]
    
    print(f"🚀 Engine started. Total targets: {len(symbols)}. Processing with 4 concurrent threads...")

    batch_results = []
    success_count = 0
    BATCH_SIZE = 100 

    # --- MULTI-THREADING ENGINE (2 Workers) ---
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(process_stock, t): t for t in symbols}
        
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            
            if result is not None:
                batch_results.append(result)
                success_count += 1
                
            if len(batch_results) >= BATCH_SIZE:
                # ADDED on_conflict="SYMBOL" TO PREVENT CRASHES
                supabase.table('market_scans').upsert(batch_results, on_conflict="SYMBOL").execute()
                print(f"📦 [STREAM] Scanned & Pushed a batch of {BATCH_SIZE}. Total Validated so far: {success_count}")
                batch_results = [] 

    if batch_results: 
        # ADDED on_conflict="SYMBOL" TO PREVENT CRASHES
        supabase.table('market_scans').upsert(batch_results, on_conflict="SYMBOL").execute()

    print(f"✅ Full Multi-Threaded Universe Stream Complete. Validated: {success_count} stocks.")
