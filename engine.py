import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import os, time

def update_daily_analysis(ticker_list):
    results = []
    print(f"🚀 Analyzing {len(ticker_list)} symbols for Swing Opportunities...")
    
    for symbol in ticker_list:
        try:
            sym = str(symbol).strip()
            formatted_symbol = sym if "." in sym else f"{sym}.NS"
            ticker = yf.Ticker(formatted_symbol)
            df = ticker.history(period="150d") 
            
            if df.empty or len(df) < 50: continue
            
            # --- TECHNICAL CORE ---
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            
            # Volume Analysis (Swing trading fuel)
            avg_vol = df['Volume'].tail(20).mean()
            curr_vol = df['Volume'].iloc[-1]
            vol_surge = round(curr_vol / avg_vol, 2)
            
            cmp = df['Close'].iloc[-1]
            rsi = df['RSI'].iloc[-1]
            
            # --- FUNDAMENTALS ---
            try:
                info = ticker.info
                pe = info.get('trailingPE', 0)
                m_cap = info.get('marketCap', 0) / 10000000 
                sector = info.get('sector', 'General')
            except:
                pe, m_cap, sector = 0, 0, 'General'
            
            # --- TITAN SCORING LOGIC (SWING FOCUS) ---
            score = 0
            if cmp > df['SMA_20'].iloc[-1]: score += 3  # Short term trend
            if 45 < rsi < 65: score += 3               # Momentum zone
            if vol_surge > 1.5: score += 2             # Volume breakout
            if cmp > df['SMA_50'].iloc[-1]: score += 2  # Structural health
            
            # Dynamic Target (10% for Swing)
            target = cmp * 1.10
            
            results.append({
                "SYMBOL": sym, 
                "PRICE": round(cmp, 2), 
                "TARGET": round(target, 2),
                "SCORE": score, 
                "RSI": round(rsi, 2), 
                "PE_RATIO": round(pe, 2),
                "MARKET_CAP": round(m_cap, 2), 
                "SECTOR": sector,
                "VOL_SURGE": vol_surge
            })
            print(f"✅ {formatted_symbol} | Score: {score} | Vol: {vol_surge}")
            time.sleep(0.1)
        except Exception as e: print(f"❌ {symbol}: {e}")
            
    if results:
        pd.DataFrame(results).to_csv("daily_analysis.csv", index=False)
        print("💾 Analysis Sync Complete.")

if __name__ == "__main__":
    if os.path.exists('Tickers.csv'):
        ticker_df = pd.read_csv('Tickers.csv')
        update_daily_analysis(ticker_df['SYMBOL'].dropna().tolist())
        
