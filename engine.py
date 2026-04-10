import yfinance as yf
import pandas as pd
import pandas_ta as ta
import time, datetime

def run_engine():
    try:
        master = pd.read_csv("Tickers.csv")
        # Ensure symbols are clean and have .NS
        symbols = [f"{str(s).strip()}.NS" for s in master['SYMBOL'].unique()]
        
        all_results = []
        chunk_size = 100 # Reduced slightly for better stability
        
        for i in range(0, len(symbols), chunk_size):
            batch = symbols[i:i+chunk_size]
            # Download 5 days to ensure TA indicators have enough data points
            data = yf.download(batch, period="5d", interval="15m", progress=False)
            
            if data.empty: continue
            
            for t in batch:
                try:
                    # Robust slicing for multi-index columns
                    s_price_data = data.iloc[:, data.columns.get_level_values(1) == t]
                    s_price_data.columns = s_price_data.columns.get_level_values(0)
                    s_price_data = s_price_data.dropna()
                    
                    if len(s_price_data) < 10: continue # Skip if insufficient data
                    
                    # Calculate Math
                    rsi = ta.rsi(s_price_data['Close'], length=14).iloc[-1]
                    ema50 = ta.ema(s_price_data['Close'], length=50).iloc[-1]
                    atr = ta.atr(s_price_data['High'], s_price_data['Low'], s_price_data['Close'], length=14).iloc[-1]
                    
                    curr_p = s_price_data['Close'].iloc[-1]
                    
                    # Scoring Logic
                    score = 0
                    if curr_p > ema50: score += 5
                    if 40 < rsi < 65: score += 3
                    if rsi > 65: score += 1 # Trend is strong but cooling
                    
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
    
