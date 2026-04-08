import yfinance as yf
import pandas as pd
import numpy as np
import os

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def run_engine():
    # 1. Load Master Tickers
    df_tickers = pd.read_csv("Tickers.csv")
    symbols = [f"{s.strip()}.NS" for s in df_tickers['SYMBOL']]
    
    # 2. Download Nifty 50 for Market Trend
    print("📈 Fetching Market Context...")
    nifty = yf.download("^NSEI", period="1y", interval="1d", progress=False)['Close']
    m_trend = "BULLISH" if nifty.iloc[-1] > nifty.ewm(span=50).mean().iloc[-1] else "BEARISH"
    
    results = []
    batch_size = 50  # Processing in small chunks to prevent blocking
    
    print(f"🔄 Processing {len(symbols)} symbols in batches of {batch_size}...")

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        try:
            # Download batch
            data = yf.download(batch, period="1y", interval="1d", group_by='ticker', progress=False)
            
            for sym in batch:
                try:
                    s_short = sym.replace(".NS", "")
                    df = data[sym].dropna()
                    
                    if len(df) < 60: continue
                    
                    curr = df['Close'].iloc[-1]
                    ema20 = df['Close'].ewm(span=20).mean().iloc[-1]
                    ema200 = df['Close'].ewm(span=200).mean().iloc[-1]
                    rsi = calculate_rsi(df['Close']).iloc[-1]
                    
                    # Volume & ATR
                    vol_curr = df['Volume'].iloc[-1]
                    vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
                    tr = pd.concat([df['High']-df['Low'], 
                                    abs(df['High']-df['Close'].shift()), 
                                    abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
                    atr = tr.rolling(14).mean().iloc[-1]

                    # --- Strategy Scoring ---
                    score = 4
                    if curr > ema20: score += 1
                    if curr > ema200: score += 1
                    if m_trend == "BULLISH": score += 1
                    if vol_curr > (vol_avg * 1.5): score += 1
                    if 45 < rsi < 65: score += 2
                    
                    # Penny Stock Guard
                    if curr < 50: score = min(score, 5)
                    
                    # Target Prediction
                    target = curr + (atr * 2.2)
                    
                    results.append({
                        "SYMBOL": s_short, "PRICE": round(curr, 2), "SCORE": int(score),
                        "TARGET": round(target, 2), "MOVE_PCT": round(((target-curr)/curr)*100, 1),
                        "HOLD": "15-30 Days" if rsi > 55 else "30-60 Days", 
                        "RSI": round(rsi, 1), "VOL": round(vol_curr/vol_avg, 1)
                    })
                except: continue
            print(f"✅ Finished batch {i//batch_size + 1}")
        except:
            print(f"❌ Batch {i//batch_size + 1} failed, skipping...")

    # 3. Save Final Analysis
    if results:
        pd.DataFrame(results).to_csv("daily_analysis.csv", index=False)
        print("✨ engine.py: Analysis Complete.")
    else:
        print("⚠️ Error: No data could be processed.")

if __name__ == "__main__":
    run_engine()
