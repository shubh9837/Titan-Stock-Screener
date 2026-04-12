import pandas as pd
import numpy as np
import pandas_ta_classic as ta
import yfinance as yf
import time, os
from supabase import create_client

# --- 1. Database Connect ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def safe_float(val, default=0.0):
    if pd.isna(val) or np.isinf(val): return default
    return float(val)

if __name__ == "__main__":
    print("Initiating Yahoo Bulk API Data Stream...")

    # 1. Load targets
    master = pd.read_csv("Tickers.csv")
    # Add .NS for Yahoo Finance compatibility
    symbols = [f"{str(s).strip()}.NS" for s in master['SYMBOL'].dropna().unique()]

    print(f"🚀 Downloading 4 months of data for {len(symbols)} stocks in ONE massive request...")
    
    # 2. THE BULK HACK
    # This downloads everything in one go, completely bypassing the "rapid fire" IP ban.
    data = yf.download(symbols, period="4mo", group_by="ticker", threads=True, ignore_tz=True)

    print(f"✅ Download complete! Processing technical indicators locally in RAM...")

    results = []
    success_count = 0
    BATCH_SIZE = 100

    # 3. Process Locally (Lightning Fast)
    for t in symbols:
        try:
            # Extract this specific stock's data from the bulk payload
            if isinstance(data.columns, pd.MultiIndex):
                if t not in data.columns.get_level_values(0).unique():
                    continue
                df = data[t].copy()
            else:
                df = data.copy()

            df.dropna(inplace=True)

            # Ignore dead stocks or brand new IPOs
            if df.empty or len(df) < 26:
                continue

            curr_p = safe_float(df['Close'].iloc[-1])
            if curr_p == 0: continue

            # --- Technical Math ---
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

            # --- Core Algorithm Score ---
            score = 0
            if ema20 > 0 and curr_p > ema20: score += 10
            if ema50 > 0 and ema20 > ema50: score += 10
            if 55 <= rsi <= 70: score += 10 
            if vol_dry_up: score += 20 
            elif rvol > 1.5: score += 10
            if is_pre_breakout: score += 30 
            elif bb_width < 5.0: score += 15 
            if is_bull_engulf: score += 20 

            if curr_p < 20: score -= 30 
            turnover = avg_vol * curr_p
            if turnover < 10000000: score -= 30 

            target_price = curr_p + (3 * atr)
            stop_loss_price = curr_p - (2 * atr)
            rr_ratio = ((target_price - curr_p) / (curr_p - stop_loss_price)) if (curr_p - stop_loss_price) > 0 else 0

            # 4. Save to Results array
            results.append({
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
                "EARNINGS_RISK": "✅ Clear",
                "SECTOR_STRENGTH": "Unknown",
                "INSTITUTIONAL_TREND": "Bullish",
                "CAP_CATEGORY": "Large/Mid Cap" if curr_p >= 20 else "Penny / Micro Cap",
                "UPDATED_AT": time.strftime('%Y-%m-%d %H:%M:%S')
            })
            success_count += 1

            # 5. Push to Database in Batches of 100 to save memory
            if len(results) >= BATCH_SIZE:
                supabase.table('market_scans').upsert(results, on_conflict="SYMBOL").execute()
                print(f"📦 [STREAM] Scanned & Pushed a batch of {BATCH_SIZE}. Validated: {success_count}")
                results = [] 

        except Exception as e:
            continue

    # Push final batch
    if results: 
        supabase.table('market_scans').upsert(results, on_conflict="SYMBOL").execute()

    print(f"✅ Full Bulk Stream Complete. Validated: {success_count} stocks.")
