import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange
import time

def run_engine():
    try:
        # 1. Load symbols
        master = pd.read_csv("Tickers.csv")
        symbols = [f"{str(s).strip()}.NS" for s in master['SYMBOL'].unique()]
        
        results = []
        chunk_size = 50 # Smaller chunks are more stable for Yahoo Finance
        
        for i in range(0, len(symbols), chunk_size):
            batch = symbols[i:i+chunk_size]
            print(f"📦 Processing Batch {i//chunk_size + 1}...")
            
            # 2. Use group_by='ticker' to make data extraction reliable
            data = yf.download(batch, period="1mo", interval="15m", progress=False, group_by='ticker')
            
            if data.empty: continue
            
            for t in batch:
                try:
                    # 3. Safe extraction logic
                    if len(batch) > 1:
                        s_price_data = data[t].copy()
                    else:
                        s_price_data = data.copy()
                    
                    s_price_data.dropna(subset=['Close'], inplace=True)
                    
                    # 4. CRITICAL: Need at least 50 periods for EMA50
                    if len(s_price_data) < 50: 
                        continue 
                    
                    # --- MATH SECTION ---
                    rsi = RSIIndicator(close=s_price_data['Close'], window=14).rsi().iloc[-1]
                    ema50 = EMAIndicator(close=s_price_data['Close'], window=50).ema_indicator().iloc[-1]
                    atr = AverageTrueRange(high=s_price_data['High'], low=s_price_data['Low'], close=s_price_data['Close'], window=14).average_true_range().iloc[-1]
                    
                    curr_p = s_price_data['Close'].iloc[-1]
                    
                    # Ensure no NaN values hit your scoring
                    if pd.isna(rsi) or pd.isna(ema50): continue

                    # --- SCORING LOGIC ---
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
                except Exception:
                    continue
            
            time.sleep(1) # Be kind to the API

        # 5. Save final results
        if results:
            pd.DataFrame(results).to_csv("daily_analysis.csv", index=False)
            print(f"🚀 Success! {len(results)} stocks analyzed.")
        else:
            print("❌ No stocks met the criteria.")
            
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")

if __name__ == "__main__":
    run_engine()
    
