import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import os, time

def update_daily_analysis(ticker_list):
    results = []
    if "^NSEI" not in ticker_list: ticker_list.append("^NSEI") 
    
    packet_size = 50 
    formatted_to_raw = { (str(s).strip() if "." in str(s) or "^" in str(s) else f"{str(s).strip()}.NS"): s for s in ticker_list }
    f_list = list(formatted_to_raw.keys())

    for i in range(0, len(f_list), packet_size):
        packet = f_list[i:i+packet_size]
        try:
            batch_data = yf.download(packet, period="2y", group_by='ticker', threads=True, progress=False)
            for f_sym in packet:
                try:
                    df = batch_data[f_sym].dropna(subset=['Close']) if len(packet) > 1 else batch_data.dropna()
                    if df.empty or len(df) < 200: continue # Need 200 days for SMA_200
                    
                    # Technicals
                    df['RSI'] = ta.rsi(df['Close'], length=14)
                    df['SMA_20'] = df['Close'].rolling(window=20).mean()
                    df['SMA_50'] = df['Close'].rolling(window=50).mean()
                    df['SMA_200'] = df['Close'].rolling(window=200).mean()
                    
                    cmp = df['Close'].iloc[-1]
                    rsi = df['RSI'].iloc[-1]
                    vol_surge = round(df['Volume'].iloc[-1] / df['Volume'].tail(20).mean(), 2) if df['Volume'].tail(20).mean() > 0 else 1
                    
                    # Metadata
                    t_obj = yf.Ticker(f_sym)
                    info = t_obj.info
                    industry = info.get('sector', info.get('industry', 'General'))
                    
                    # Scoring Logic
                    score = 0
                    if cmp > df['SMA_20'].iloc[-1]: score += 2
                    if 45 < rsi < 65: score += 3
                    if vol_surge > 1.5: score += 2
                    if cmp > df['SMA_50'].iloc[-1]: score += 2
                    if cmp > df['SMA_200'].iloc[-1]: score += 1 # Long term trend bonus
                    
                    results.append({
                        "SYMBOL": formatted_to_raw[f_sym], "PRICE": round(cmp, 2),
                        "TARGET": round(cmp * 1.12, 2), "SCORE": score, "RSI": round(rsi, 2),
                        "PE": round(info.get('trailingPE', 0), 2), 
                        "MARKET_CAP": round(info.get('marketCap', 0) / 10000000, 2),
                        "SECTOR": industry, "VOL_SURGE": vol_surge,
                        "ABOVE_200": 1 if cmp > df['SMA_200'].iloc[-1] else 0
                    })
                except: continue
            time.sleep(1)
        except: continue

    if results:
        pd.DataFrame(results).to_csv("daily_analysis.csv", index=False)
