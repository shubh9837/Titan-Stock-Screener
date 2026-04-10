import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import os, time

def update_daily_analysis(ticker_list):
    results = []
    if "^NSEI" not in ticker_list: ticker_list.append("^NSEI") 
    
    # Ensure tickers are .NS formatted
    formatted_to_raw = {(str(s).strip() if "." in str(s) or "^" in str(s) else f"{str(s).strip()}.NS"): s for s in ticker_list}
    f_list = list(formatted_to_raw.keys())

    # Use a progress bar for large datasets
    import tqdm
    print(f"🚀 Analyzing {len(f_list)} tickers...")

    for i in range(0, len(f_list), 40):
        packet = f_list[i:i+40]
        # Download price data in bulk (Efficient)
        batch_data = yf.download(packet, period="2y", group_by='ticker', threads=True, progress=False)
        
        for f_sym in packet:
            try:
                # Get individual stock DF from batch
                df = batch_data[f_sym].dropna(subset=['Close']) if len(packet) > 1 else batch_data.dropna()
                if len(df) < 200: continue
                
                # TECHNICALS
                macd = ta.macd(df['Close'])
                bb = ta.bbands(df['Close'], length=20, std=2)
                df['SMA_200'] = df['Close'].rolling(window=200).mean()
                
                cmp = df['Close'].iloc[-1]
                rsi = ta.rsi(df['Close'], length=14).iloc[-1]
                
                # FUNDAMENTALS - This is the slow part
                # To speed up, we wrap this specifically to avoid skipping the whole stock if info fails
                try:
                    t_obj = yf.Ticker(f_sym)
                    info = t_obj.info
                    d_e = info.get('debtToEquity', 0) / 100 
                    sector = info.get('sector', 'General')
                except:
                    d_e = 0
                    sector = "General"
                
                # SCORING (10/10 Logic)
                score = 0
                if cmp > df['SMA_200'].iloc[-1]: score += 2 
                if macd['MACD_12_26_9'].iloc[-1] > macd['MACDs_12_26_9'].iloc[-1]: score += 2 
                if 45 < rsi < 65: score += 2 
                if bb['BBM_20_2.0'].iloc[-1] < cmp < bb['BBU_20_2.0'].iloc[-1]: score += 2 
                if d_e < 1.5: score += 2 
                
                results.append({
                    "SYMBOL": formatted_to_raw[f_sym], "PRICE": round(cmp, 2),
                    "TARGET": round(cmp * 1.15, 2), "SCORE": score, "RSI": round(rsi, 2),
                    "DEBT_EQUITY": round(d_e, 2), "SECTOR": sector,
                    "ABOVE_200": 1 if cmp > df['SMA_200'].iloc[-1] else 0,
                    "VOL_SURGE": round(df['Volume'].iloc[-1] / df['Volume'].tail(20).mean(), 2)
                })
            except Exception as e:
                continue
        
        # Incremental saving to prevent data loss if it crashes halfway
        if i % 200 == 0 and results:
            pd.DataFrame(results).to_csv("daily_analysis.csv", index=False)
            
        time.sleep(2) # Increased sleep to respect Yahoo Finance limits

    if results:
        pd.DataFrame(results).to_csv("daily_analysis.csv", index=False)
        print("✅ Analysis Complete.")
        
