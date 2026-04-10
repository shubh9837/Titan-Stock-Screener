import yfinance as yf
import pandas as pd
# Switching to 'ta' for better compatibility with GitHub Actions
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange
import time, datetime

def run_engine():
    try:
        # Load your master ticker list
        master = pd.read_csv("Tickers.csv")
        symbols = [f"{str(s).strip()}.NS" for s in master['SYMBOL'].unique()]
        
        results = [] 
        chunk_size = 100 
        
        for i in range(0, len(symbols), chunk_size):
            batch = symbols[i:i+chunk_size]
            # Fetching 5 days of data to ensure enough points for 15m indicators
            data = yf.download(batch, period="5d", interval="15m", progress=False)
            
            if data.empty: continue
            
            for t in batch:
                try:
                    # Isolate specific ticker data from the batch download
                    s_price_data = data.iloc[:, data.columns.get_level_values(1) == t]
                    s_price_data.columns = s_price_data.columns.get_level_values(0)
                    s_price_data = s_price_data.dropna()
                    
                    # Ensure minimum data points for EMA-50 and RSI-14
                    if len(s_price_data) < 15: continue 
                    
                    # --- MATH SECTION (Using 'ta' library) ---
                    # RSI 14
                    rsi_io = RSIIndicator(close=s_price_data['Close'], window=14)
                    rsi_series = rsi_io.rsi()
                    if rsi_series.empty or pd.isna(rsi_series.iloc[-1]): continue
                    rsi = rsi_series.iloc[-1]

                    # EMA 50
                    ema_io = EMAIndicator(close=s_price_data['Close'], window=50)
                    ema50_series = ema_io.ema_indicator()
                    if ema50_series.empty or pd.isna(ema50_series.iloc[-1]): continue
                    ema50 = ema50_series.iloc[-1]

                    # ATR 14
                    atr_io = AverageTrueRange(high=s_price_data['High'], low=s_price_data['Low'], close=s_price_data['Close'], window=14)
                    atr_series = atr_io.average_true_range()
                    if atr_series.empty or pd.isna(atr_series.iloc[-1]): continue
                    atr = atr_series.iloc[-1]
                    
                    curr_p = s_price_data['Close'].iloc[-1]
                    
                    # --- SCORING LOGIC (Alpha Formula) ---
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
            
            print(f"✅ Processed chunk {i//chunk_size + 1}")
            time.sleep(0.7) # Slightly increased delay to be extra safe with Yahoo Finance

        # Save to CSV for the Streamlit app to consume
        if results:
            pd.DataFrame(results).to_csv("daily_analysis.csv", index=False)
            print(f"🚀 Successfully analyzed {len(results)} stocks.")
        else:
            print("⚠️ No results generated. Check Tickers.csv or connection.")
            
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")

if __name__ == "__main__":
    run_engine()
    
