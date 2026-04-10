import yfinance as yf
import pandas as pd
import pandas_ta as ta
import time, os, datetime

def calculate_alpha_score(df, sector_avg_map):
    # 1. Technical Indicators
    df['RSI'] = ta.rsi(df['Close'], length=14)
    adx = ta.adx(df['High'], df['Low'], df['Close'])
    df['ADX'] = adx['ADX_14']
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    
    # 2. Scoring Logic (Weighted 0-10)
    # Trend (4 pts) + Momentum (3 pts) + Sector (3 pts)
    t_score = 0
    if df['Close'].iloc[-1] > df['EMA_50'].iloc[-1]: t_score += 4
    if 45 < df['RSI'].iloc[-1] < 65: t_score += 3
    
    # Sector Tailwind (Fetched from pre-calculated map)
    sector = df['SECTOR'].iloc[0]
    s_score = sector_avg_map.get(sector, 0)
    
    final_score = t_score + s_score
    
    # 3. Risk Management (ATR Based)
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    return final_score, df['ATR'].iloc[-1]

def run_engine():
    master = pd.read_csv("Tickers.csv")
    symbols = [f"{s}.NS" for s in master['SYMBOL'].tolist()]
    
    # Batch Download for Speed (200 at a time)
    results = []
    chunk_size = 200
    for i in range(0, len(symbols), chunk_size):
        batch = symbols[i:i+chunk_size]
        data = yf.download(batch, period="5d", interval="15m", progress=False)['Close']
        
        # Calculate Sector Strength first for this batch
        # (Simplified logic for the script)
        for sym in batch:
            try:
                price = data[sym].iloc[-1]
                s_name = master[master['SYMBOL'] == sym.replace(".NS","")]['SECTOR'].values[0]
                results.append({"SYMBOL": sym.replace(".NS",""), "PRICE": round(price, 2), "SECTOR": s_name})
            except: continue
            
    final_df = pd.DataFrame(results)
    # Add dummy scores for this example; in production, use the calculate_alpha_score function
    final_df['SCORE'] = np.random.uniform(5, 9, len(final_df)) 
    final_df['STOP_LOSS'] = (final_df['PRICE'] * 0.94).round(2)
    final_df['TARGET'] = (final_df['PRICE'] * 1.12).round(2)
    
    final_df.to_csv("daily_analysis.csv", index=False)

if __name__ == "__main__":
    run_engine()
    
