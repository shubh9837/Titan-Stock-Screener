import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange
import time

def run_engine():
    try:
        master = pd.read_csv("Tickers.csv")
        symbols = [f"{str(s).strip()}.NS" for s in master['SYMBOL'].dropna().unique()]
        results = []
        
        print(f"🚀 Starting stable fetch for {len(symbols)} stocks...")

        for t in symbols:
            try:
                # Fetching 1 month to ensure 50-period EMA has enough data
                ticker = yf.Ticker(t)
                df = ticker.history(period="1mo", interval="15m")
                
                if df.empty or len(df) < 50:
                    continue
                
                # --- CORE STRATEGY (Mathematical logic preserved) ---
                rsi = RSIIndicator(close=df['Close'], window=14).rsi().iloc[-1]
                ema50 = EMAIndicator(close=df['Close'], window=50).ema_indicator().iloc[-1]
                atr = AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], window=14).average_true_range().iloc[-1]
                curr_p = df['Close'].iloc[-1]
                
                if pd.isna(rsi) or pd.isna(ema50): continue

                score = 0
                if curr_p > ema50: score += 5
                if 40 < rsi < 65: score += 3
                if rsi > 65: score += 1 
                
                results.append({
                    "SYMBOL": t.replace(".NS",""),
                    "PRICE": round(curr_p, 2),
                    "SCORE": score,
                    "RSI": round(rsi, 2),
                    "STOP_LOSS": round(curr_p - (2 * atr), 2),
                    "TARGET": round(curr_p + (3 * atr), 2)
                })
                
                # Delay to prevent IP blocking from GitHub
                time.sleep(0.1) 

            except Exception:
                continue

        if results:
            pd.DataFrame(results).to_csv("daily_analysis.csv", index=False)
            print(f"✅ Analysis complete. {len(results)} stocks processed.")
            
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")

if __name__ == "__main__":
    run_engine()
    
