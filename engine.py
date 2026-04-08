import yfinance as yf
import pandas as pd
import numpy as np
import time
import os

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def run_engine():
    # Load Master Tickers
    df_tickers = pd.read_csv("Tickers.csv")
    symbols = [f"{s}.NS" for s in df_tickers['SYMBOL']]
    
    print(f"🔄 Processing {len(symbols)} symbols...")
    
    # Download 2-Year Data for technical depth
    raw_data = yf.download(symbols + ["^NSEI"], period="2y", interval="1d", group_by='column')
    close_prices = raw_data['Close']
    
    # Market Context (Nifty 50)
    nifty = close_prices['^NSEI'].dropna()
    m_trend = "BULLISH" if nifty.iloc[-1] > nifty.ewm(span=50).mean().iloc[-1] else "BEARISH"
    
    results = []
    enriched_meta = []

    for sym in symbols:
        try:
            s_short = sym.replace(".NS", "")
            # Extract high/low/close for this stock
            df = pd.DataFrame({
                'Close': raw_data['Close'][sym],
                'High': raw_data['High'][sym],
                'Low': raw_data['Low'][sym],
                'Volume': raw_data['Volume'][sym]
            }).dropna()

            if len(df) < 100: continue
            
            # --- Technical Logic ---
            curr = df['Close'].iloc[-1]
            ema20 = df['Close'].ewm(span=20).mean().iloc[-1]
            ema200 = df['Close'].ewm(span=200).mean().iloc[-1]
            rsi = calculate_rsi(df['Close']).iloc[-1]
            
            # Volume Analysis
            vol_curr = df['Volume'].iloc[-1]
            vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
            vol_surge = vol_curr / vol_avg if vol_avg > 0 else 1
            
            # ATR (Volatility) for Target Prediction
            tr = pd.concat([df['High']-df['Low'], 
                            abs(df['High']-df['Close'].shift()), 
                            abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            
            # --- Multi-Factor Scoring (1-10) ---
            score = 4
            if curr > ema20: score += 1      # Short term trend
            if curr > ema200: score += 1     # Long term trend
            if m_trend == "BULLISH": score += 1 # Market support
            if vol_surge > 1.5: score += 1   # Buying conviction
            if 45 < rsi < 65: score += 2     # Ideal "Sweet Spot" momentum
            elif rsi > 70: score -= 1        # Penalty for overbought
            
            # Penny Stock Guard (< Rs. 50)
            if curr < 50:
                score = min(score, 5) # Cap rating
                if vol_surge > 3: score += 1 # Only allow boost on extreme volume
            
            # --- Predictions ---
            target_price = curr + (atr * 2.5) # Based on 2.5x volatility
            move_pct = ((target_price - curr) / curr) * 100
            hold_period = "15-30 Days" if vol_surge > 2 else "30-60 Days"
            direction = "UPWARDS" if (curr > ema20 and rsi > 50) else "SIDEWAYS"
            
            results.append({
                "SYMBOL": s_short, "PRICE": round(curr, 2), "SCORE": int(score),
                "TARGET": round(target_price, 2), "MOVE_PCT": round(move_pct, 1),
                "HOLD": hold_period, "DIR": direction, "RSI": round(rsi, 1), "VOL": round(vol_surge, 1)
            })

        except: continue

    # Save outputs
    pd.DataFrame(results).to_csv("daily_analysis.csv", index=False)
    print("✨ Engine Run Complete. Results saved to daily_analysis.csv")

if __name__ == "__main__":
    run_engine()
