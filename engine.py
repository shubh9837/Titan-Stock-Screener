import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import os, time

def update_daily_analysis(ticker_list):
    results = []
    # Add Nifty 50 for benchmarking
    if "^NSEI" not in ticker_list:
        ticker_list.append("^NSEI") 
    
    packet_size = 100
    # Create mapping and ensure .NS suffix for Indian stocks
    formatted_to_raw = { (str(s).strip() if "." in str(s) or "^" in str(s) else f"{str(s).strip()}.NS"): s for s in ticker_list }
    f_list = list(formatted_to_raw.keys())

    print(f"🚀 Processing {len(f_list)} symbols in packets of {packet_size}...")

    for i in range(0, len(f_list), packet_size):
        packet = f_list[i:i+packet_size]
        try:
            # Bulk download price data
            batch_data = yf.download(packet, period="2y", group_by='ticker', threads=True, progress=False)
            
            for f_sym in packet:
                try:
                    df = batch_data[f_sym].dropna(subset=['Close']) if len(packet) > 1 else batch_data.dropna()
                    if df.empty or len(df) < 50: continue
                    
                    # Technical Analysis
                    df['RSI'] = ta.rsi(df['Close'], length=14)
                    df['SMA_20'] = df['Close'].rolling(window=20).mean()
                    df['SMA_50'] = df['Close'].rolling(window=50).mean()
                    
                    # Sentiment/Volume Surge
                    avg_vol = df['Volume'].tail(20).mean()
                    vol_surge = round(df['Volume'].iloc[-1] / avg_vol, 2) if avg_vol > 0 else 1
                    
                    cmp = df['Close'].iloc[-1]
                    rsi = df['RSI'].iloc[-1]
                    
                    # Fundamental/Industry Fetch
                    t_obj = yf.Ticker(f_sym)
                    info = t_obj.info
                    industry = info.get('sector', info.get('industry', 'General'))
                    pe = info.get('trailingPE', 0)
                    m_cap = info.get('marketCap', 0) / 10000000 # To Crores

                    # 10/10 SCORING: Trend (3) + RSI (3) + Volume (2) + Structural (2)
                    score = 0
                    if cmp > df['SMA_20'].iloc[-1]: score += 3
                    if 45 < rsi < 65: score += 3
                    if vol_surge > 1.5: score += 2
                    if cmp > df['SMA_50'].iloc[-1]: score += 2
                    
                    results.append({
                        "SYMBOL": formatted_to_raw[f_sym], 
                        "PRICE": round(cmp, 2),
                        "TARGET": round(cmp * 1.12, 2), 
                        "SCORE": score, 
                        "RSI": round(rsi, 2),
                        "PE_RATIO": round(pe, 2), 
                        "MARKET_CAP": round(m_cap, 2),
                        "SECTOR": industry, 
                        "VOL_SURGE": vol_surge
                    })
                except: continue
            # Sleep to prevent GitHub Action IP block
            time.sleep(2) 
        except Exception as e:
            print(f"Packet error: {e}")
            continue

    if results:
        df_final = pd.DataFrame(results)
        df_final.to_csv("daily_analysis.csv", index=False)
        print(f"💾 Sync Complete: {len(df_final)} stocks updated.")

if __name__ == "__main__":
    if os.path.exists('Tickers.csv'):
        symbols = pd.read_csv('Tickers.csv')['SYMBOL'].dropna().unique().tolist()
        update_daily_analysis(symbols)
        
