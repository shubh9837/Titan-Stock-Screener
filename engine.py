import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import os

def update_daily_analysis(ticker_list):
    results = []
    print(f"🚀 Starting analysis for {len(ticker_list)} symbols...")
    
    for symbol in ticker_list:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="60d")
            
            if df.empty: 
                print(f"⚠️ No data found for {symbol}")
                continue
            
            # CALCULATE TECHNICALS
            df['RSI'] = ta.rsi(df['Close'], length=14)
            current_rsi = df['RSI'].iloc[-1]
            
            # FETCH FUNDAMENTALS
            info = ticker.info
            pe_ratio = info.get('trailingPE', 25)
            m_cap = info.get('marketCap', 0) / 10000000 # Convert to Crores
            
            cmp = df['Close'].iloc[-1]
            # Replace '8' with your actual scoring logic if you have one
            score = 8 
            target = cmp * 1.10 
            
            results.append({
                "SYMBOL": symbol,
                "PRICE": round(cmp, 2),
                "TARGET": round(target, 2),
                "SCORE": score,
                "RSI": round(current_rsi, 2),
                "PE_RATIO": round(pe_ratio, 2),
                "MARKET_CAP": round(m_cap, 2)
            })
            print(f"✅ Processed {symbol}")
        except Exception as e:
            print(f"❌ Error on {symbol}: {e}")
            
    if results:
        df_final = pd.DataFrame(results)
        df_final.to_csv("daily_analysis.csv", index=False)
        print(f"💾 Successfully saved {len(results)} rows to daily_analysis.csv")
    else:
        print("Empty results. Nothing saved.")

# --- THE EXECUTIVE BLOCK (This makes it run) ---
if __name__ == "__main__":
    if os.path.exists('tickers.csv'):
        # Load tickers from your CSV
        ticker_df = pd.read_csv('tickers.csv')
        # Ensure the column name is 'SYMBOL'
        list_to_process = ticker_df['SYMBOL'].tolist()
        
        # Trigger the function
        update_daily_analysis(list_to_process)
    else:
        print("🔴 Critical Error: tickers.csv not found!")
        
