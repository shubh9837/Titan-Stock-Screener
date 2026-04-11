import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import time, os, datetime
from supabase import create_client

# 1. Connect to Database
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_earnings_risk(ticker_obj):
    """Checks if earnings are within the next 7 days"""
    try:
        calendar = ticker_obj.calendar
        if not calendar.empty:
            earnings_date = calendar.iloc[0, 0] # Gets the next earnings date
            days_to_earnings = (earnings_date.date() - datetime.date.today()).days
            if 0 <= days_to_earnings <= 7:
                return f"⚠️ Earnings in {days_to_earnings} days"
    except:
        pass
    return "✅ Clear"

def run_master_scan():
    print("Initiating Master EOD Scan...")
    
    # 1. Fetch Market-Wide FII/DII Data (Logic to scrape NSE or Moneycontrol)
    # institutional_trend = fetch_fii_data() 
    institutional_trend = "Bullish" # Placeholder for the FII logic
    
    master = pd.read_csv("Tickers.csv")
    symbols = [f"{str(s).strip()}.NS" for s in master['SYMBOL'].dropna().unique()]
    
    results = []
    
    for t in symbols: # Scans the FULL list of 2000+ stocks
        try:
            ticker = yf.Ticker(t)
            df = ticker.history(period="6mo", interval="1d")
            
for t in symbols: # Scans the FULL list of 2000+ stocks
        try:
            ticker = yf.Ticker(t)
            df = ticker.history(period="6mo", interval="1d")
            
            # The newly updated check with correct indentation
            if df.empty or len(df) < 50:
                continue
            
            # --- Technicals ---
            df.ta.ema(length=50, append=True)
            curr_p = df['Close'].iloc[-1]
            
            # --- New Phase 2 Integrations ---
            earnings_risk = get_earnings_risk(ticker)
            sector_strength = "Outperforming" # Placeholder for Sector Relative Strength logic
            
            # Base Score
            score = 70 if curr_p > df['EMA_50'].iloc[-1] else 30
            
            # Penalize heavily for Earnings Risk
            if "⚠️" in earnings_risk:
                score -= 40 
            
            results.append({
                "SYMBOL": t.replace(".NS", ""),
                "PRICE": round(curr_p, 2),
                "SCORE": score,
                "EARNINGS_RISK": earnings_risk,
                "SECTOR_STRENGTH": sector_strength,
                "INSTITUTIONAL_TREND": institutional_trend,
                "UPDATED_AT": time.strftime('%Y-%m-%d %H:%M:%S')
            })
            
            time.sleep(0.2) # Throttle to avoid bans
            
        except Exception as e:
            continue
            
    if results:
        supabase.table('market_scans').upsert(results).execute()
        print("✅ Master Scan Complete. Database updated.")

if __name__ == "__main__":
    run_master_scan()
