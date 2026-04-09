import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import os, time

def update_daily_analysis(ticker_list):
    results = []
    formatted_to_raw = { (str(s).strip() if "." in str(s) else f"{str(s).strip()}.NS"): s for s in ticker_list }
    formatted_list = list(formatted_to_raw.keys())
    
    print(f"🚀 Batch downloading 2 YEARS of data for {len(formatted_list)} symbols...")
    
    try:
        all_data = yf.download(formatted_list, period="2y", group_by='ticker', threads=True, progress=False)
    except Exception as e:
        print(f"❌ Bulk Download Failed: {e}")
        return

    for formatted_sym, raw_sym in formatted_to_raw.items():
        try:
            if len(formatted_list) > 1:
                df = all_data[formatted_sym].dropna(subset=['Close'])
            else:
                df = all_data.dropna(subset=['Close'])

            if df.empty or len(df) < 50:
                continue
            
            # --- TECHNICALS ---
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            
            # Volume Analysis
            avg_vol = df['Volume'].tail(20).mean()
            curr_vol = df['Volume'].iloc[-1]
            # Safety: avoid division by zero
            vol_surge = round(curr_vol / avg_vol, 2) if avg_vol > 0 else 1.0
            
            cmp = df['Close'].iloc[-1]
            rsi = df['RSI'].iloc[-1]
            
            # --- FUNDAMENTALS ---
            try:
                ticker_obj = yf.Ticker(formatted_sym)
                info = ticker_obj.info
                pe = info.get('trailingPE', 0)
                m_cap = info.get('marketCap', 0) / 10000000 
                sector = info.get('sector', 'General')
                time.sleep(0.1) 
            except:
                pe, m_cap, sector = 0, 0, 'General'
            
            # --- SCORING ---
            score = 0
            if cmp > df['SMA_20'].iloc[-1]: score += 3 
            if 45 < rsi < 65: score += 3              
            if vol_surge > 1.5: score += 2            
            if cmp > df['SMA_50'].iloc[-1]: score += 2 
            
            results.append({
                "SYMBOL": raw_sym, 
                "PRICE": round(cmp, 2), 
                "TARGET": round(cmp * 1.10, 2),
                "SCORE": score, 
                "RSI": round(rsi, 2), 
                "PE_RATIO": round(pe, 2),
                "MARKET_CAP": round(m_cap, 2), 
                "SECTOR": sector,
                "VOL_SURGE": vol_surge  # <-- CRITICAL: Exactly matches app.py
            })
            print(f"✅ {raw_sym} Analyzed")

        except Exception as e:
            print(f"❌ Error on {raw_sym}: {e}")
            
    if results:
        df_final = pd.DataFrame(results)
        # Final safety check: fill any NaN values in VOL_SURGE to prevent app crashes
        if 'VOL_SURGE' in df_final.columns:
            df_final['VOL_SURGE'] = df_final['VOL_SURGE'].fillna(1.0)
            
        df_final.to_csv("daily_analysis.csv", index=False)
        print(f"💾 Saved {len(results)} stocks to daily_analysis.csv")

if __name__ == "__main__":
    if os.path.exists('Tickers.csv'):
        ticker_df = pd.read_csv('Tickers.csv')
        update_daily_analysis(ticker_df['SYMBOL'].dropna().unique().tolist())
        
