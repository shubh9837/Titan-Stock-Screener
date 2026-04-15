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
    print("Initiating Yahoo Chunked API Data Stream...")

    # 1. Load targets & map sectors directly from CSV
    master = pd.read_csv("Tickers.csv")
    symbols = [f"{str(s).strip()}.NS" for s in master['SYMBOL'].dropna().unique()]
    
    # Try to find a Sector or Industry column in your CSV
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
    CHUNK_SIZE = 300 # Added Chunking to prevent Yahoo Finance IP bans

    print(f"🚀 Phase 1: Downloading & Analyzing Technicals for {len(symbols)} stocks...")

    # THE CHUNKING FIX: Loop through symbols 300 at a time
    for i in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[i:i+CHUNK_SIZE]
        print(f"\n📥 Fetching Batch {i+1} to {min(i+CHUNK_SIZE, len(symbols))}...")
        
        # FIXED: Removed the unsupported 'show_errors=False' parameter
        data = yf.download(chunk, period="1y", group_by="ticker", threads=True, ignore_tz=True)
        
        # Give Yahoo a 1-second breather to clear anti-bot limits
        time.sleep(1)

        # 3. Process Locally for the current chunk
        for t in chunk:
            try:
                if len(chunk) > 1 and isinstance(data.columns, pd.MultiIndex):
                    if t not in data.columns.get_level_values(0).unique():
                        print(f"⚠️ SKIPPED {t}: Ticker not found on Yahoo Finance.")
                        continue
                    df = data[t].copy()
                else:
                    df = data.copy()

                df.dropna(inplace=True)

                # X-RAY VISION: Log why stocks are skipped
                if df.empty:
                    print(f"⚠️ SKIPPED {t}: Zero trading data returned.")
                    continue

                # UPGRADE: Need at least 100 days of data to calculate a 20-Week EMA safely
                if len(df) < 100:
                    print(f"⚠️ SKIPPED {t}: Only {len(df)} days of data (< 100 required for MTFA).")
                    continue

                curr_p = safe_float(df['Close'].iloc[-1])
                if curr_p == 0: 
                    print(f"⚠️ SKIPPED {t}: Last traded price is zero (Suspended).")
                    continue

                # --- UPGRADE: MTFA (Multi-Timeframe Alignment) ---
                # Compress daily data into Weekly data
                df_w = df.resample('W-FRI').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna()
                df_w.ta.ema(length=20, append=True)
                weekly_ema20 = safe_float(df_w['EMA_20'].iloc[-1] if 'EMA_20' in df_w else 0)
                
                # Check if the macro trend is safe
                weekly_trend = "Bullish" if curr_p > weekly_ema20 and weekly_ema20 > 0 else "Bearish"

                # --- PRESERVED: Your Exact Technical Math ---
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

                # --- PRESERVED: Your Pattern Fix ---
                pattern = "Uptrending" if curr_p > ema20 else "Consolidating"
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

                # MTFA Institutional Trend Score
                if weekly_trend == "Bullish": score += 20

                # --- UPGRADE: The "Suzlon Fix" (Liquidity Filter) ---
                turnover = avg_vol * curr_p
                # Penalize strictly if turnover is less than ₹2 Crores daily (Illiquid/Manipulation risk)
                if turnover < 20000000: 
                    score -= 30 

                # Temporarily store everything in all_results without pushing yet
                all_results.append({
                    "SYMBOL": t.replace(".NS", ""),
                    "PRICE": round(curr_p, 2),
                    "SCORE": max(0, min(100, score)), 
                    "RSI": round(rsi, 2),
                    "RVOL": round(rvol, 2),
                    "ATR": atr, # Temporarily save ATR to calculate dynamic target later
                    "SUPPORT": round(sup_20, 2),
                    "RESISTANCE": round(res_20, 2),
                    "PATTERN": pattern,
                    "EARNINGS_RISK": "✅ Clear", # Kept to maintain your exact database structure
                    "SECTOR": str(sector_map.get(t, "Unknown")),
                    "INSTITUTIONAL_TREND": weekly_trend,
                    "CAP_CATEGORY": "Large/Mid Cap" if turnover >= 20000000 else "Small/Penny Cap",
                    "UPDATED_AT": time.strftime('%Y-%m-%d %H:%M:%S')
                })
                success_count += 1

            except Exception as e:
                # X-RAY VISION: Catch the exact math error breaking the stock
                print(f"❌ CRASH ON {t}: {str(e)}")
                continue

    # --- PHASE 2: VIP FUNDAMENTAL EXTRACTION ---
    print(f"\n✅ Phase 1 Complete. {success_count} stocks technically analyzed.")
    print("🔍 Phase 2: Identifying VIP Stocks & Fetching Fundamentals...")
    
    df_res = pd.DataFrame(all_results)
    vip_symbols = set()
    
    if not df_res.empty:
        # Find the absolute best setups to fetch fundamentals for
        vip_symbols.update(df_res[df_res['CAP_CATEGORY'] == 'Large/Mid Cap'].nlargest(15, 'SCORE')['SYMBOL'])
        vip_symbols.update(df_res[df_res['CAP_CATEGORY'] == 'Small/Penny Cap'].nlargest(15, 'SCORE')['SYMBOL'])
        vip_symbols.update(df_res[df_res['PATTERN'] == '⚡ Pre-Breakout Squeeze'].nlargest(15, 'SCORE')['SYMBOL'])
    
    funda_data = {}
    print(f"Fetching Deep Fundamentals for {len(vip_symbols)} VIP setups...")
    
    for sym in vip_symbols:
        try:
            info = yf.Ticker(f"{sym}.NS").info
            funda_data[sym] = {
                "PE_RATIO": safe_float(info.get('trailingPE', 0)),
                "DEBT_EQUITY": safe_float(info.get('debtToEquity', 0)),
                "ROE": safe_float(info.get('returnOnEquity', 0)) * 100
            }
        except:
            funda_data[sym] = {"PE_RATIO": 0.0, "DEBT_EQUITY": 0.0, "ROE": 0.0}

    # --- PHASE 3: THE VERDICT LOGIC & DYNAMIC TARGETS ---
    final_payload = []
    
    for r in all_results:
        sym = r['SYMBOL']
        score = r['SCORE']
        curr_p = r['PRICE']
        atr = r.pop('ATR') # Extract ATR for the final math
        
        # Assign Fundamentals (Defaults to 0 if not a VIP stock)
        pe, de, roe = 0.0, 0.0, 0.0
        if sym in funda_data:
            pe = funda_data[sym]['PE_RATIO']
            de = funda_data[sym]['DEBT_EQUITY']
            roe = funda_data[sym]['ROE']
            
        r['PE_RATIO'] = round(pe, 2)
        r['DEBT_EQUITY'] = round(de, 2)
        r['ROE'] = round(roe, 2)

        # 🧠 THE VERDICT ENGINE
        stop_loss_price = curr_p - (2 * atr)
        
        if score >= 70 and roe >= 15.0 and de < 100.0 and de > 0:
            verdict = "💎 High Conviction (Hold 15-45 Days)"
            target_price = curr_p + (4 * atr) # 1:2 Risk/Reward
        elif score >= 70 and (de > 200.0 or roe < 0):
            verdict = "⚠️ High Risk Trap (Hit & Run 1-5 Days)"
            target_price = curr_p + (2 * atr) # 1:1 Risk/Reward
        elif score >= 50:
            verdict = "⚡ Tech Momentum (Hold 5-15 Days)"
            target_price = curr_p + (3 * atr) # 1:1.5 Risk/Reward
        else:
            verdict = "⏳ Weak Setup (Ignore)"
            target_price = curr_p + (3 * atr)

        r['VERDICT'] = verdict
        r['TARGET'] = round(target_price, 2) if atr > 0 else 0
        r['STOP_LOSS'] = round(stop_loss_price, 2) if atr > 0 else 0
        
        rr_ratio = ((target_price - curr_p) / (curr_p - stop_loss_price)) if (curr_p - stop_loss_price) > 0 else 0
        r['RR_RATIO'] = round(min(rr_ratio, 10.0), 2)
        
        final_payload.append(r)

    # --- PHASE 4: PUSH TO DATABASE ---
    print("\n📦 Phase 3: Pushing analyzed data to Supabase...")
    pushed = 0
    for i in range(0, len(final_payload), BATCH_SIZE):
        batch = final_payload[i:i+BATCH_SIZE]
        supabase.table('market_scans').upsert(batch, on_conflict="SYMBOL").execute()
        pushed += len(batch)
        print(f"📦 [STREAM] Scanned & Pushed a batch of {len(batch)}. Total Validated: {pushed}")

    print(f"✅ Full System Upgrade Complete. {pushed} stocks successfully processed with Techno-Funda metrics.")
