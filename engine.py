import yfinance as yf
import pandas as pd
import numpy as np
import time

def calculate_rsi(series, period=14):
    if len(series) < period: return 50
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def run_engine():
    # 1. Load Master Tickers
    try:
        df_tickers = pd.read_csv("Tickers.csv")
        symbols = [f"{str(s).strip()}.NS" for s in df_tickers['SYMBOL']]
    except Exception as e:
        print(f"Error loading Tickers.csv: {e}")
        return

    # 2. Market Context
    print("📈 Checking Nifty...")
    try:
        nifty_data = yf.download("^NSEI", period="1y", interval="1d", progress=False)
        nifty_close = nifty_data['Close']
        m_trend = "BULLISH" if nifty_close.iloc[-1] > nifty_close.ewm(span=50).mean().iloc[-1] else "BEARISH"
    except:
        m_trend = "NEUTRAL"

    results = []
    # Smaller batches to satisfy Yahoo's servers
    batch_size = 30 
    
    print(f"🚀 Processing {len(symbols)} stocks...")

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        try:
            # The 'auto_adjust=True' and 'multi_level_index=False' make data much cleaner
            data = yf.download(batch, period="1y", interval="1d", group_by='ticker', progress=False, threads=True)
            
            if data is None or data.empty:
                continue

            for sym in batch:
                try:
                    # Safety check: Does the symbol exist in the downloaded data?
                    if sym not in data.columns.get_level_values(0) if isinstance(data.columns, pd.MultiIndex) else [sym]:
                        continue
                    
                    df = data[sym].dropna() if isinstance(data.columns, pd.MultiIndex) else data.dropna()
                    if df.empty or len(df) < 30: continue
                    
                    # Technicals
                    c = df['Close'].iloc[-1]
                    ema20 = df['Close'].ewm(span=20).mean().iloc[-1]
                    ema200 = df['Close'].ewm(span=200).mean().iloc[-1]
                    rsi_val = calculate_rsi(df['Close']).iloc[-1]
                    
                    # Vol/ATR
                    v_curr = df['Volume'].iloc[-1]
                    v_avg = df['Volume'].rolling(20).mean().iloc[-1]
                    tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
                    atr = tr.rolling(14).mean().iloc[-1]

                    # Scoring
                    score = 4
                    if c > ema20: score += 1
                    if c > ema200: score += 1
                    if m_trend == "BULLISH": score += 1
                    if v_curr > (v_avg * 1.5): score += 1
                    if 45 < rsi_val < 65: score += 2
                    if c < 50: score = min(score, 5) # Penny guard

                    target = c + (atr * 2.2)
                    results.append({
                        "SYMBOL": sym.replace(".NS",""), "PRICE": round(c, 2), "SCORE": int(score),
                        "TARGET": round(target, 2), "MOVE_PCT": round(((target-c)/c)*100, 1),
                        "HOLD": "15-30 Days" if rsi_val > 55 else "30-60 Days", 
                        "RSI": round(rsi_val, 1), "VOL": round(v_curr/v_avg, 1) if v_avg > 0 else 1
                    })
                except Exception: continue # Skip individual stock errors
            print(f"✅ Batch {i//batch_size + 1} Done")
        except Exception as e:
            print(f"⚠️ Batch Error: {e}")
            continue

    # 3. Save
    if results:
        final_df = pd.DataFrame(results)
        final_df.to_csv("daily_analysis.csv", index=False)
        print(f"✨ Successfully analyzed {len(results)} stocks.")
    else:
        print("❌ No data analyzed. Check Tickers.csv format.")

if __name__ == "__main__":
    run_engine()
    
