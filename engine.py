import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import os, time

def update_daily_analysis(ticker_list):
    results = []
    # 1. Prepare formatted symbols for bulk download
    # We strip whitespace and handle the .NS suffix for Indian markets
    formatted_to_raw = { (str(s).strip() if "." in str(s) else f"{str(s).strip()}.NS"): s for s in ticker_list }
    formatted_list = list(formatted_to_raw.keys())
    
    print(f"🚀 Batch downloading 2 YEARS of data for {len(formatted_list)} symbols...")
    
    try:
        # Download all data in one go for the 2y period
        # threads=True is essential for performance in GitHub Workflows
        all_data = yf.download(formatted_list, period="2y", group_by='ticker', threads=True, progress=False)
    except Exception as e:
        print(f"❌ Bulk Download Failed: {e}")
        return

    print("📊 Processing Technicals and Fundamentals...")
    
    for formatted_sym, raw_sym in formatted_to_raw.items():
        try:
            # Extract individual dataframe from the batch download
            if len(formatted_list) > 1:
                df = all_data[formatted_sym].dropna(subset=['Close'])
            else:
                # If only one stock is in the list, yfinance returns a slightly different structure
                df = all_data.dropna(subset=['Close'])

            if df.empty or len(df) < 50:
                continue
            
            # --- TECHNICAL CORE ---
            # Now benefiting from a 2-year lookback
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            
            # Volume Analysis (Compare current volume vs 20-day average)
            avg_vol = df['Volume'].tail(20).mean()
            curr_vol = df['Volume'].iloc[-1]
            vol_surge = round(curr_vol / avg_vol, 2) if avg_vol > 0 else 0
            
            cmp = df['Close'].iloc[-1]
            rsi = df['RSI'].iloc[-1]
            
            # --- FUNDAMENTALS ---
            # Individual ticker info fetch (kept minimal to avoid rate limits)
            try:
                ticker_obj = yf.Ticker(formatted_sym)
                info = ticker_obj.info
                pe = info.get('trailingPE', 0)
                m_cap = info.get('marketCap', 0) / 10000000 # To Crores
                sector = info.get('sector', 'General')
                time.sleep(0.1) # Safe buffer
            except:
                pe, m_cap, sector = 0, 0, 'General'
            
            # --- TITAN SCORING LOGIC (SWING FOCUS) ---
            score = 0
            if cmp > df['SMA_20'].iloc[-1]: score += 3 
            if 45 < rsi < 65: score += 3              
            if vol_surge > 1.5: score += 2            
            if cmp > df['SMA_50'].iloc[-1]: score += 2 
            
            # 10% target for swing trades
            target = cmp * 1.10
            
            results.append({
                "SYMBOL": raw_sym, 
                "PRICE": round(cmp, 2), 
                "TARGET": round(target, 2),
                "SCORE": score, 
                "RSI": round(rsi, 2), 
                "PE_RATIO": round(pe, 2),
                "MARKET_CAP": round(m_cap, 2), 
                "SECTOR": sector,
                "VOL_SURGE": vol_surge
            })
            print(f"✅ {raw_sym} analyzed successfully.")

        except Exception as e:
            print(f"❌ Error on {raw_sym}: {e}")
            
    if results:
        pd.DataFrame(results).to_csv("daily_analysis.csv", index=False)
        print(f"💾 Analysis Sync Complete. Processed {len(results)} stocks.")

if __name__ == "__main__":
    if os.path.exists('Tickers.csv'):
        ticker_df = pd.read_csv('Tickers.csv')
        # Unique symbols only to optimize API usage
        list_to_process = ticker_df['SYMBOL'].dropna().unique().tolist()
        update_daily_analysis(list_to_process)
    else:
        print("🔴 Critical Error: Tickers.csv not found!")
        
