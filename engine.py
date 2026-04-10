import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import os, time
from concurrent.futures import ThreadPoolExecutor

def update_daily_analysis(ticker_list):
    results = []
    
    # 1. FORMAT TICKERS: Ensure all have .NS if they don't already (excluding Indices like ^NSEI)
    formatted_to_raw = {}
    for s in ticker_list:
        s_str = str(s).strip()
        if s_str.startswith("^") or "." in s_str:
            formatted_to_raw[s_str] = s_str
        else:
            formatted_to_raw[f"{s_str}.NS"] = s_str
            
    f_list = list(formatted_to_raw.keys())
    total = len(f_list)
    print(f"🚀 Starting Titan Analysis for {total} symbols...")

    # 2. BATCH DOWNLOAD: Using large batches for price data is 10x faster
    batch_size = 50
    for i in range(0, total, batch_size):
        packet = f_list[i:i+batch_size]
        print(f"📦 Processing batch {i//batch_size + 1}: {packet[0]}...")
        
        # Download 2 years of data for all tickers in the packet at once
        batch_data = yf.download(packet, period="2y", group_by='ticker', threads=True, progress=False)
        
        for f_sym in packet:
            try:
                # Extract individual DataFrame from the batch
                if len(packet) > 1:
                    df = batch_data[f_sym].dropna(subset=['Close'])
                else:
                    df = batch_data.dropna(subset=['Close'])
                
                if len(df) < 200: continue # Need history for 200 SMA
                
                # --- TECHNICAL ANALYSIS ---
                # MACD
                macd = ta.macd(df['Close'])
                # Bollinger Bands
                bb = ta.bbands(df['Close'], length=20, std=2)
                # Trend
                df['SMA_200'] = df['Close'].rolling(window=200).mean()
                
                cmp = df['Close'].iloc[-1]
                rsi = ta.rsi(df['Close'], length=14).iloc[-1]
                
                # --- FUNDAMENTALS (The bottleneck - handled with care) ---
                try:
                    t_obj = yf.Ticker(f_sym)
                    # We only pull the bare essentials to save time
                    info = t_obj.info
                    d_e = info.get('debtToEquity', 0) / 100 
                    sector = info.get('sector', 'General')
                except:
                    d_e = 0
                    sector = "General"
                
                # --- TITAN SCORING (10/10) ---
                score = 0
                if cmp > df['SMA_200'].iloc[-1]: score += 2 
                if macd['MACD_12_26_9'].iloc[-1] > macd['MACDs_12_26_9'].iloc[-1]: score += 2
                if 45 < rsi < 65: score += 2
                if bb['BBM_20_2.0'].iloc[-1] < cmp < bb['BBU_20_2.0'].iloc[-1]: score += 2
                if d_e < 1.5: score += 2 
                
                results.append({
                    "SYMBOL": formatted_to_raw[f_sym], 
                    "PRICE": round(cmp, 2),
                    "TARGET": round(cmp * 1.15, 2), 
                    "SCORE": score, 
                    "RSI": round(rsi, 2),
                    "DEBT_EQUITY": round(d_e, 2), 
                    "SECTOR": sector,
                    "VOL_SURGE": round(df['Volume'].iloc[-1] / df['Volume'].tail(20).mean(), 2)
                })
            except Exception as e:
                continue # Skip faulty data points but keep engine running
        
        # Incremental Save to prevent data loss
        if len(results) > 0:
            pd.DataFrame(results).to_csv("daily_analysis.csv", index=False)
            
        time.sleep(1) # Small pause to prevent API rate limiting

    print(f"✅ Analysis complete. {len(results)} stocks analyzed.")

if __name__ == "__main__":
    if os.path.exists("Tickers.csv"):
        t_df = pd.read_csv("Tickers.csv")
        # Ensure column name matches your CSV (usually 'Symbol' or 'Ticker')
        col_name = 'Symbol' if 'Symbol' in t_df.columns else t_df.columns[0]
        update_daily_analysis(t_df[col_name].tolist())
    else:
        print("❌ Tickers.csv not found!")
        
