import yfinance as yf
import pandas as pd
import numpy as np
import time, os
from datetime import datetime

def calculate_rsi(series, period=14):
    if len(series) < period: return 50
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)

def run_engine():
    try:
        df_tickers = pd.read_csv("Tickers.csv")
        symbols = [f"{str(s).strip()}.NS" for s in df_tickers['SYMBOL']]
    except Exception as e:
        print(f"Error: {e}"); return

    results = []
    # 1:00 AM UTC check (Finalized data)
    data = yf.download(symbols, period="1y", interval="1d", group_by='ticker', progress=False)

    for sym in symbols:
        try:
            df = data[sym].dropna()
            if len(df) < 50: continue
            
            c = df['Close'].iloc[-1]
            ema20 = df['Close'].ewm(span=20).mean().iloc[-1]
            ema200 = df['Close'].ewm(span=200).mean().iloc[-1]
            rsi = calculate_rsi(df['Close']).iloc[-1]
            
            # Volatility for Target & Days
            tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            daily_range = (df['High'] - df['Low']).rolling(10).mean().iloc[-1]

            # Scoring
            score = 5
            if c > ema20: score += 1
            if c > ema200: score += 1
            if df['Volume'].iloc[-1] > df['Volume'].rolling(20).mean().iloc[-1] * 1.5: score += 1
            if 45 < rsi < 65: score += 2

            target = c + (atr * 2.5)
            # DYNAMIC DAYS: Distance / Avg Daily Movement
            est_days = max(3, round((target - c) / daily_range)) if daily_range > 0 else 15

            results.append({
                "SYMBOL": sym.replace(".NS",""), "PRICE": round(c, 2), "SCORE": int(score),
                "TARGET": round(target, 2), "HOLDING": f"{est_days}-{est_days+3} Days",
                "RSI": round(rsi, 1), "DATE_SIGNAL": datetime.now().strftime("%Y-%m-%d")
            })
        except: continue

    # Save Analysis
    final_df = pd.DataFrame(results)
    final_df.to_csv("daily_analysis.csv", index=False)

    # SUCCESS TRACKER: Append to history for backtesting
    history_file = "trade_history.csv"
    if not os.path.exists(history_file):
        final_df.to_csv(history_file, index=False)
    else:
        hist = pd.read_csv(history_file)
        # Keep only last 60 days to save space
        combined = pd.concat([hist, final_df]).drop_duplicates(subset=['SYMBOL', 'DATE_SIGNAL'])
        combined.tail(5000).to_csv(history_file, index=False)

if __name__ == "__main__":
    run_engine()
    
