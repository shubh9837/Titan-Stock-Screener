import yfinance as yf
import pandas as pd
import pandas_ta as ta  # Ensure you have pip install pandas-ta

def update_daily_analysis(ticker_list):
    results = []
    
    for symbol in ticker_list:
        try:
            # 1. DOWNLOAD DATA (Technical)
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="60d") # Get 2 months for RSI/EMA math
            
            if df.empty: continue
            
            # 2. CALCULATE TECHNICALS
            # RSI (14-day)
            df['RSI'] = ta.rsi(df['Close'], length=14)
            current_rsi = df['RSI'].iloc[-1]
            
            # 3. FETCH FUNDAMENTALS
            info = ticker.info
            pe_ratio = info.get('trailingPE', 25) # Default to 25 if not found
            m_cap = info.get('marketCap', 1000000000) / 10000000 # Convert to Crores
            
            # 4. EXISTING LOGIC (Targets/Scores)
            cmp = df['Close'].iloc[-1]
            # [Your existing scoring logic here...]
            score = 8 # Placeholder for your actual scoring logic
            target = cmp * 1.10 # Placeholder for your ATR target
            
            results.append({
                "SYMBOL": symbol,
                "PRICE": round(cmp, 2),
                "TARGET": round(target, 2),
                "SCORE": score,
                "RSI": round(current_rsi, 2),
                "PE_RATIO": round(pe_ratio, 2),
                "MARKET_CAP": round(m_cap, 2)
            })
        except Exception as e:
            print(f"Error on {symbol}: {e}")
            
    # Save to the CSV the app reads
    pd.DataFrame(results).to_csv("daily_analysis.csv", index=False)
    
