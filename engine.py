import yfinance as yf
import pandas as pd
import pandas_ta as ta
import time
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import feedparser
from supabase import create_client

# --- 1. CONFIG & CLOUD DB ---
# These will be stored in your GitHub Secrets
SUPABASE_URL = "YOUR_SUPABASE_URL"
SUPABASE_KEY = "YOUR_SUPABASE_KEY"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. SENTIMENT ENGINE ---
def get_market_sentiment():
    """Scrapes RSS feeds and scores general market sentiment."""
    print("📰 Fetching Market News...")
    rss_urls = [
        "https://www.moneycontrol.com/rss/business.xml",
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"
    ]
    analyzer = SentimentIntensityAnalyzer()
    news_text = ""
    
    for url in rss_urls:
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]: # Get top 10 from each
            news_text += entry.title + ". "
            
    sentiment_score = analyzer.polarity_scores(news_text)['compound']
    return sentiment_score # Returns between -1 (Bearish) and 1 (Bullish)

# --- 3. CONFLUENCE SCORING ---
def run_engine(scan_type="intraday"):
    try:
        # For intraday, scan top 500 to avoid yfinance bans. For EOD, scan all.
        master = pd.read_csv("Tickers.csv")
        symbols = [f"{str(s).strip()}.NS" for s in master['SYMBOL'].dropna().unique()]
        if scan_type == "intraday":
            symbols = symbols[:500] 
            
        market_sentiment = get_market_sentiment()
        print(f"🌍 Overall Market Sentiment: {market_sentiment:.2f}")
        
        results = []
        print(f"🚀 Starting {scan_type} scan for {len(symbols)} stocks...")

        for t in symbols:
            try:
                ticker = yf.Ticker(t)
                df = ticker.history(period="3mo", interval="1d") # Daily data for swing
                
                if df.empty or len(df) < 50:
                    continue
                
                # Technical Indicators (using pandas_ta for speed)
                df.ta.ema(length=20, append=True)
                df.ta.ema(length=50, append=True)
                df.ta.rsi(length=14, append=True)
                df.ta.atr(length=14, append=True)
                
                curr_p = df['Close'].iloc[-1]
                ema20 = df['EMA_20'].iloc[-1]
                ema50 = df['EMA_50'].iloc[-1]
                rsi = df['RSI_14'].iloc[-1]
                atr = df['ATRr_14'].iloc[-1]

                if pd.isna(rsi) or pd.isna(ema50): continue

                # --- 100-POINT CONFLUENCE SCORE LOGIC ---
                score = 0
                
                # 1. Trend (Max 40 points)
                if curr_p > ema20: score += 20
                if ema20 > ema50: score += 20
                
                # 2. Momentum (Max 30 points)
                if 40 < rsi < 65: score += 15 # Healthy zone
                elif rsi >= 65: score += 30   # Strong momentum
                
                # 3. Sentiment & Macro Context (Max 30 points)
                if market_sentiment > 0.2: score += 30
                elif market_sentiment > -0.2: score += 15
                
                # Format Ticker
                clean_sym = t.replace(".NS", "")
                
                results.append({
                    "SYMBOL": clean_sym,
                    "PRICE": round(curr_p, 2),
                    "SCORE": score,
                    "RSI": round(rsi, 2),
                    "STOP_LOSS": round(curr_p - (2 * atr), 2),
                    "TARGET": round(curr_p + (3 * atr), 2),
                    "UPDATED_AT": time.strftime('%Y-%m-%d %H:%M:%S')
                })
                
                time.sleep(0.2) # Throttle to protect API

            except Exception as e:
                continue

        if results:
            # Upsert data to Supabase table named 'market_scans'
            supabase.table('market_scans').upsert(results).execute()
            print(f"✅ Sync complete. {len(results)} stocks pushed to cloud database.")
            
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")

if __name__ == "__main__":
    # Can pass "eod" via argument for the master scan
    run_engine(scan_type="intraday")
