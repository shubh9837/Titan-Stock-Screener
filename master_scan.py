import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import time, os, datetime
from supabase import create_client

# 1. Connect to Database
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase Secrets! Check GitHub Secrets.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_earnings_risk(ticker_obj):
    """Checks if earnings are within the next 7 days"""
    try:
        calendar = ticker_obj.calendar
        if not calendar.empty:
            earnings_date = calendar.iloc[0, 0] 
            days_to_earnings = (earnings_date.date() - datetime.date.today()).days
            if 0 <= days_to_earnings <= 7:
                return f"⚠️ Earnings in {days_to_earnings} days"
    except:
        pass
    return "✅ Clear"

def run_master_scan():
    print("Initiating Master EOD Scan...")
    
    # Market-Wide Institutional Trend (Placeholder for Macro level)
    institutional_trend = "Bullish"
    
    master = pd.read_csv("Tickers.csv")
    symbols = [f"{str(s).strip()}.NS" for s in master['SYMBOL'].dropna().unique()]
    
    results = []
    print(f"🚀 Starting master scan for {len(symbols)} stocks...")

    for t in symbols: 
        try:
            ticker = yf.Ticker(t)
            df = ticker.history(period="6mo", interval="1d")
            
            if df.empty or len(df) < 50:
                continue
                
            # --- Fetch Actual Sector/Industry Data ---
            try:
                info = ticker.info
                sector_strength = info.get('sector', info.get('industry', 'Unknown'))
            except:
                sector_strength = "Unknown"
            
            # --- Technicals & Volatility ---
            df.ta.ema(length=20, append=True)
            df.ta.ema(length=50, append=True)
            df.ta.rsi(length=14, append=True)
            df.ta.bbands(length=20, append=True) 
            df.ta.atr(length=14, append=True)
            
            # Calculate Relative Volume (RVOL)
            df['Vol_20_MA'] = df['Volume'].rolling(window=20).mean()
            current_vol = df['Volume'].iloc[-1]
            avg_vol = df['Vol_20_MA'].iloc[-1]
            rvol = current_vol / avg_vol if avg_vol > 0 else 0
            
            curr_p = df['Close'].iloc[-1]
            ema20 = df['EMA_20'].iloc[-1]
            ema50 = df['EMA_50'].iloc[-1]
            rsi = df['RSI_14'].iloc[-1]
            atr = df['ATRr_14'].iloc[-1]
            
            if pd.isna(rsi) or pd.isna(ema50): continue
            
            # Bollinger Band Squeeze Calculation (Width %)
            bb_upper = df['BBU_20_2.0'].iloc[-1]
            bb_lower = df['BBL_20_2.0'].iloc[-1]
            bb_width = (bb_upper - bb_lower) / curr_p * 100 
            
            # --- THE NEW 100-POINT CONFLUENCE ALGORITHM ---
            score = 0
            
            if curr_p > ema20: score += 15
            if ema20 > ema50: score += 15
            
            if 55 <= rsi <= 70: score += 20 
            elif rsi > 70: score += 10 
            
            if rvol > 2.0: score += 25 
            elif rvol > 1.2: score += 15 
            
            if bb_width < 5.0: score += 25 
            elif bb_width < 10.0: score += 10 
            
            earnings_risk = get_earnings_risk(ticker)
            if "⚠️" in earnings_risk:
                score -= 40 
            
            results.append({
                "SYMBOL": t.replace(".NS", ""),
                "PRICE": round(curr_p, 2),
                "SCORE": score,
                "RSI": round(rsi, 2),
                "TARGET": round(curr_p + (3 * atr), 2),
                "STOP_LOSS": round(curr_p - (2 * atr), 2),
                "EARNINGS_RISK": earnings_risk,
                "SECTOR_STRENGTH": sector_strength,
                "INSTITUTIONAL_TREND": institutional_trend,
                "UPDATED_AT": time.strftime('%Y-%m-%d %H:%M:%S')
            })
            
            time.sleep(0.2) 
            
        except Exception as e:
            continue
            
    if results:
        # 1. Delete old market data to prevent ghost duplicates
        try:
            supabase.table('market_scans').delete().gt('id', 0).execute()
        except:
            pass 
            
        # 2. Push the fresh data
        supabase.table('market_scans').insert(results).execute()
        print(f"✅ Master Scan Complete. {len(results)} fresh stocks pushed to database.")

if __name__ == "__main__":
    run_master_scan()
