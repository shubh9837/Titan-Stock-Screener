import pandas as pd
import numpy as np
import pandas_ta_classic as ta
import yfinance as yf
import time, os
from supabase import create_client
import datetime

# --- Database Connect ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def safe_float(val, default=0.0):
    if pd.isna(val) or np.isinf(val): return default
    return float(val)

if __name__ == "__main__":
    print("Initiating Yahoo Bulk API Data Stream...")

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

    all_results = []
    success_count = 0
    BATCH_SIZE = 100
    CHUNK_SIZE = 300 

    print(f"🚀 Phase 1: Technical Scan for {len(symbols)} stocks...")

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
                
                # UPGRADE: Smart Volume (OBV)
                df.ta.obv(append=True)
                obv = safe_float(df['OBV'].iloc[-1] if 'OBV' in df else 0)
                obv_20_max = safe_float(df['OBV'].rolling(20).max().iloc[-1] if 'OBV' in df else 0)
                is_obv_breakout = obv >= obv_20_max and obv != 0

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
                    bb_width = (safe_float(df['BBU_20_2.0'].iloc[-1]) - safe_float(df['BBL_20_2.0'].iloc[-1])) / curr_p * 100 

                pattern = "Uptrending" if curr_p > ema20 else "Consolidating"
                is_bull_engulf = (close_yst < open_yst) and (open_tdy < close_yst) and (close_tdy > open_yst)
                if is_bull_engulf: pattern = "🟢 Bullish Engulfing"
                
                vol_dry_up = False
                if len(df) > 5 and df['Volume'].iloc[-4:-1].mean() < avg_vol and rvol > 1.5: vol_dry_up = True

                is_pre_breakout = False
                if bb_width < 6.0 and ((res_20 - curr_p) / curr_p) < 0.03 and macd_hist > macd_hist_prev:
                    is_pre_breakout = True
                    pattern = "⚡ Pre-Breakout Squeeze"

                score = 0
                if ema20 > 0 and curr_p > ema20: score += 10
                if ema50 > 0 and ema20 > ema50: score += 10
                if 55 <= rsi <= 70: score += 10 
                if vol_dry_up: score += 20 
                
                # UPGRADE: Volume only counts if OBV confirms institutional accumulation
                elif rvol > 1.5 and is_obv_breakout: score += 15 
                
                if is_pre_breakout: score += 30 
                elif bb_width < 5.0: score += 15 
                if is_bull_engulf: score += 20 
                if weekly_trend == "Bullish": score += 20

                turnover = avg_vol * curr_p
                if turnover < 20000000: score -= 30 

                # UPGRADE: Dynamic Pivot Targets (6-Month Historical Resistance)
                target_price = curr_p + (3 * atr)
                stop_loss_price = curr_p - (2 * atr)
                
                max_high_6m = safe_float(df['High'].tail(125).max())
                if max_high_6m > curr_p and target_price > max_high_6m:
                    target_price = max_high_6m # Respect historical ceilings

                rr_ratio = ((target_price - curr_p) / (curr_p - stop_loss_price)) if (curr_p - stop_loss_price) > 0 else 0

                all_results.append({
                    "SYMBOL": t.replace(".NS", ""),
                    "PRICE": round(curr_p, 2),
                    "SCORE": max(0, min(100, score)), 
                    "RSI": round(rsi, 2),
                    "RVOL": round(rvol, 2),
                    "TARGET": round(target_price, 2) if atr > 0 else 0,
                    "STOP_LOSS": round(stop_loss_price, 2) if atr > 0 else 0,
                    "RR_RATIO": round(min(rr_ratio, 10.0), 2),
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
            except: continue

    # --- Phase 2: Earnings Shield ---
    print("\n🛡️ Phase 2: Checking Earnings Risk for Top Setups...")
    df_res = pd.DataFrame(all_results)
    
    if not df_res.empty:
        top_stocks = df_res.nlargest(25, 'SCORE')['SYMBOL'].tolist()
        now = datetime.datetime.now()
        
        for idx, r in enumerate(all_results):
            if r['SYMBOL'] in top_stocks:
                try:
                    cal = yf.Ticker(f"{r['SYMBOL']}.NS").calendar
                    if cal and 'Earnings Date' in cal:
                        # yfinance calendar format handles lists or single dates
                        earn_date = cal['Earnings Date'][0] if isinstance(cal['Earnings Date'], list) else cal['Earnings Date']
                        if pd.notnull(earn_date):
                            days_to_earn = (earn_date.replace(tzinfo=None) - now).days
                            if 0 <= days_to_earn <= 7:
                                all_results[idx]['EARNINGS_RISK'] = f"⚠️ RISK: Earnings in {days_to_earn}d"
                except: pass

    print("\n📦 Pushing analyzed
