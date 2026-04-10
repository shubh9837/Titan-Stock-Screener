import yfinance as yf
import pandas as pd
# Switching to 'ta' for better compatibility with GitHub Actions
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange
import time, datetime

def run_engine():
    try:
        master = pd.read_csv("Tickers.csv")
        symbols = [f"{str(s).strip()}.NS" for s in master['SYMBOL'].unique()]
        
        results = [] # Renamed from all_results to match the append logic below
        chunk_size = 100 
        
        for i in range(0, len(symbols), chunk_size):
            batch = symbols[i:i+chunk_size]
            data = yf.download(batch, period="5d", interval="15m", progress=False)
            
            if data.empty: continue
            
            for t in batch:
                try:
                    s_price_data = data.iloc[:, data.columns.get_level_values(1) == t]
                    s_price_data.columns = s_price_data.columns.get_level_values(0)
                    s_price_data = s_price_data.dropna()
                    
                    if len(s_price_data) < 15: continue 
                    
                    # --- MATH SECTION (Formula preserved exactly) ---
                    # RSI Calculation
                    rsi_io = RSIIndicator(close=s_price_data['Close'], window=14)
                    rsi = rsi_io.rsi().iloc[-1]

                    # EMA 50 Calculation
                    ema_io = EMAIndicator(close=s_price_data['Close'], window=50)
                    ema50 = ema_io.ema_indicator().iloc[-1]

                    # ATR Calculation
                    atr_io = AverageTrueRange(high=s_price_data['High'], low=s_price_data['Low'], close=s_price_data['Close'], window=14)
                    atr = atr_io.average_true_range().iloc[-1]
                    
                    curr_p = s_price_data['Close'].iloc[-1]
                    
                    # --- SCORING LOGIC (Preserved exactly) ---
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
                except: continue
            print(f"Processed chunk {i//chunk_size + 1}")
            time.sleep(0.5)

        pd.DataFrame(results).to_csv("daily_analysis.csv", index=False)
        print("✅ Sync Success")
    except Exception as e:
        print(f"FATAL ERROR: {e}")

if __name__ == "__main__":
    run_engine()
    
