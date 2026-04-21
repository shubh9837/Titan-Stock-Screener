import pandas as pd
import numpy as np
import pandas_ta_classic as ta
import yfinance as yf
import time, os
from supabase import create_client

# --- Database Connect ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def safe_float(val, default=0.0):
    if pd.isna(val) or np.isinf(val): return default
    return float(val)

if __name__ == "__main__":
    print("Initiating Yahoo Bulk API Data Stream...")

    # --- ADVANCED: Fetch NIFTY 50 baseline for Relative Strength (RS) ---
    print("Fetching NIFTY 50 baseline for Relative Strength comparison...")
    try:
        nifty_data = yf.download("^NSEI", period="6mo", progress=False, ignore_tz=True)['Close']
        if isinstance(nifty_data, pd.DataFrame): nifty_data = nifty_data["^NSEI"]
        nifty_data.dropna(inplace=True)
        nifty_return_50d = (nifty_data.iloc[-1] - nifty_data.iloc[-50]) / nifty_data.iloc[-50]
        print(f"NIFTY 50-Day Return: {nifty_return_50d * 100:.2f}%")
    except Exception as e:
        print("Warning: Could not fetch NIFTY baseline. RS calculations will default to 0.")
        nifty_return_50d = 0.0

    master = pd.read_csv("Tickers.csv")
    symbols = [f"{str(s).strip()}.NS" for s in master['SYMBOL'].dropna().unique()]
    
    sector_col = None
    for col in master.columns:
        col_clean = str(col).upper().replace(" ", "").replace("-", "")
        if 'SECTOR' in col_clean or 'INDUSTRY' in col_clean or 'MACRO' in col_clean:
            sector_col = col
            break
            
    sector_map = {}
    if sector_col:
        master['Clean_Sym'] = master['SYMBOL'].astype(str).str.strip() + '.NS'
        sector_map = dict(zip(master['Clean_Sym'], master[sector_col].fillna("Unknown")))

    results = []
    success_count = 0
    BATCH_SIZE = 100
    CHUNK_SIZE = 300 

    print(f"🚀 Downloading data for {len(symbols)} stocks in chunks...")

    for i in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[i:i+CHUNK_SIZE]
        print(f"\n📥 Fetching Batch {i+1} to {min(i+CHUNK_SIZE, len(symbols))}...")
        
        data = yf.download(chunk, period="1y", group_by="ticker", threads=True, ignore_tz=True)
        time.sleep(1) 

        for t in chunk:
            try:
                if len(chunk) > 1 and isinstance(data.columns, pd.MultiIndex):
                    if t not in data.columns.get_level_values(0).unique(): continue
                    df = data[t].copy()
                else:
                    df = data.copy()

                df.dropna(inplace=True)
                if df.empty or len(df) < 100: continue

                curr_p = safe_float(df['Close'].iloc[-1])
                if curr_p == 0: continue

                df_w = df.resample('W-FRI').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()
                df_w.ta.ema(length=20, append=True)
                weekly_ema20 = safe_float(df_w['EMA_20'].iloc[-1] if 'EMA_20' in df_w else 0)
                weekly_trend = "Bullish" if curr_p > weekly_ema20 and weekly_ema20 > 0 else "Bearish"

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

                pattern = "Uptrending" if curr_p > ema20 else "Consolidating"
                is_bull_engulf = (close_yst < open_yst) and (open_tdy < close_yst) and (close_tdy > open_yst)
                if is_bull_engulf: pattern = "🟢 Bullish Engulfing"

                # --- ADVANCED: VCP (Volatility Contraction) Volume Analysis ---
                recent_df = df.iloc[-15:]
                up_vol = recent_df[recent_df['Close'] > recent_df['Open']]['Volume'].mean()
                down_vol = recent_df[recent_df['Close'] < recent_df['Open']]['Volume'].mean()
                up_vol = safe_float(up_vol, 1.0)
                down_vol = safe_float(down_vol, 1.0)
                
                is_vcp = down_vol < (up_vol * 0.75) # Down days have 25% less volume than up days
                
                is_pre_breakout = False
                if bb_width < 6.0 and ((res_20 - curr_p) / curr_p) < 0.03 and macd_hist > macd_hist_prev:
                    is_pre_breakout = True
                    pattern = "⚡ VCP Squeeze" if is_vcp else "⚡ Pre-Breakout Squeeze"

                # --- ADVANCED: Relative Strength vs NIFTY ---
                stock_return_50d = (curr_p - safe_float(df['Close'].iloc[-50])) / safe_float(df['Close'].iloc[-50])
                rs_outperformance = stock_return_50d - nifty_return_50d

                # --- Core Algorithm Score ---
                score = 0
                if ema20 > 0 and curr_p > ema20: score += 10
                if ema50 > 0 and ema20 > ema50: score += 10
                if 55 <= rsi <= 70: score += 10 
                
                # Volume Rewards
                if is_vcp: score += 20 
                elif rvol > 1.5: score += 10
                
                # Squeeze Rewards
                if is_pre_breakout: score += 30 
                elif bb_width < 5.0: score += 15 
                
                if is_bull_engulf: score += 20 
                if weekly_trend == "Bullish": score += 20
                if rs_outperformance > 0.10: score += 20 # +20 points if outperforming NIFTY by 10%

                turnover = avg_vol * curr_p
                if turnover < 20000000: score -= 30 

                target_price = curr_p + (3 * atr)
                stop_loss_price = curr_p - (2 * atr)
                rr_ratio = ((target_price - curr_p) / (curr_p - stop_loss_price)) if (curr_p - stop_loss_price) > 0 else 0
                if rr_ratio > 10: rr_ratio = 10.0 

                results.append({
                    "SYMBOL": t.replace(".NS", ""),
                    "PRICE": round(curr_p, 2),
                    "SCORE": max(0, min(100, score)), 
                    "RSI": round(rsi, 2),
                    "RVOL": round(rvol, 2),
                    "TARGET": round(target_price, 2) if atr > 0 else 0,
                    "STOP_LOSS": round(stop_loss_price, 2) if atr > 0 else 0,
                    "RR_RATIO": round(rr_ratio, 2),
                    "SUPPORT": round(sup_20, 2),
                    "RESISTANCE": round(res_20, 2),
                    "PATTERN": pattern,
                    "EARNINGS_RISK": "✅ Clear",
                    "SECTOR": str(sector_map.get(t, "Unknown")),
                    "INSTITUTIONAL_TREND": weekly_trend,
                    "CAP_CATEGORY": "Large/Mid Cap" if turnover >= 20000000 else "Small/Penny Cap",
                    "UPDATED_AT": time.strftime('%Y-%m-%d %H:%M:%S')
                })
                success_count += 1

                if len(results) >= BATCH_SIZE:
                    supabase.table('market_scans').upsert(results, on_conflict="SYMBOL").execute()
                    print(f"📦 [STREAM] Scanned & Pushed a batch of {BATCH_SIZE}. Validated: {success_count}")
                    results = [] 

            except Exception as e:
                print(f"❌ CRASH ON {t}: {str(e)}")
                continue

    if results: 
        supabase.table('market_scans').upsert(results, on_conflict="SYMBOL").execute()

    print(f"✅ Full Bulk Stream Complete. Validated: {success_count} stocks.")
