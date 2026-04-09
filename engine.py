import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import os
import time

def update_daily_analysis(ticker_list):
    results = []
    print(f"🚀 Starting analysis for {len(ticker_list)} symbols...")
    
    for symbol in ticker_list:
        try:
            # FIX: Yahoo Finance needs .NS for NSE or .BO for BSE
            # Adding .NS as default for Indian markets
            formatted_symbol = f"{symbol.strip()}.NS"
            
            ticker = yf.Ticker(formatted_symbol)
            # Use a slightly longer period to ensure RSI has enough data to warm up
            df = ticker.history(period="100d")
            
            if df.empty or len(df) < 20: 
                print(f"⚠️ No data found for {formatted_symbol} (Possibly delisted or wrong suffix)")
                continue
            
            # CALCULATE TECHNICALS
            df['RSI'] = ta.rsi(df['Close'], length=14)
            current_rsi = df['RSI'].iloc[-1]
            
            # FETCH FUNDAMENTALS
            # Note: ticker.info is slow and often fails in automation. 
            # We wrap it in a secondary try block.
            try:
                info = ticker.info
                pe_ratio = info.get('trailingPE', 0)
                m_cap = info.get('marketCap', 0) / 10000000  # Convert to Crores
            except:
                pe_ratio, m_cap = 0, 0
            
            cmp = df['Close'].iloc[-1]
            score = 8 
            target = cmp * 1.10 
            
            results.append({
                "SYMBOL": symbol,
                "PRICE": round(cmp, 2),
                "TARGET": round(target, 2),
                "SCORE": score,
                "RSI": round(current_rsi, 2) if not pd.isna(current_rsi) else 0,
                "PE_RATIO": round(pe_ratio, 2),
                "MARKET_CAP": round(m_cap, 2)
            })
            print(f"✅ Processed {formatted_symbol}")
            
            # Tiny sleep to avoid getting rate-limited by Yahoo
            time.sleep(0.1)

        except Exception as e:
            print(f"❌ Error on {symbol}: {e}")
            
    if results:
        df_final = pd.DataFrame(results)
        df_final.to_csv("daily_analysis.csv", index=False)
        print(f"💾 Successfully saved {len(results)} rows to daily_analysis.csv")
    else:
        print("❌ Empty results. Check if Tickers.csv symbols are valid for NSE (.NS)")

if __name__ == "__main__":
    if os.path.exists('Tickers.csv'):
        # Check if CSV is empty or malformed
        try:
            ticker_df = pd.read_csv('Tickers.csv')
            if 'SYMBOL' in ticker_df.columns:
                list_to_process = ticker_df['SYMBOL'].dropna().tolist()
                update_daily_analysis(list_to_process)
            else:
                print("🔴 Error: Column 'SYMBOL' not found in Tickers.csv")
        except Exception as e:
            print(f"🔴 Error reading CSV: {e}")
    else:
        print("🔴 Critical Error: Tickers.csv not found!")
        
