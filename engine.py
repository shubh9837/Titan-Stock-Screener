import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange
import time

def run_engine():
    try:
        master = pd.read_csv("Tickers.csv")
        # Clean symbols and remove any empty rows
        raw_symbols = master['SYMBOL'].dropna().unique()
        symbols = [f"{str(s).strip()}.NS" for s in raw_symbols]
        
        results = []
        total = len(symbols)
        
        print(f"🚀 Starting Analysis for {total} stocks...")

        for index, t in enumerate(symbols):
            try:
                # Individual fetch to bypass GitHub IP rate-limiting
                # We fetch 1 month of 15m data for accuracy
                ticker_obj = yf.Ticker(t)
                s_price_data = ticker_obj.history(period="1mo", interval="15m")
                
                if s_price_data.empty or len(s_price_data) < 50:
                    continue
                
                # --- MATH ---
                rsi = RSIIndicator(close=s_price_data['Close'], window=14).rsi().iloc[-1]
                ema50 = EMAIndicator(close=s_price_data['Close'], window=50).ema_indicator().iloc[-1]
                atr = AverageTrueRange(high=s_price_data['High'], low=s_price_data['Low'], close=s_price_data['Close'], window=14).average_true_range().iloc[-1]
                
                curr_p = s_price_data['Close'].iloc[-1]
                
                # Validation to skip any NaN results
                if pd.isna(rsi) or pd.isna(ema50) or pd.isna(atr):
                    continue

                # --- SCORING LOGIC ---
                score = 0
                if curr_p > ema50: score += 5
                if 40 < rsi < 65: score += 3
                if rsi > 65: score += 1 
                
                results.append({
                    "SYMBOL": t.replace(".NS",""),
                    "PRICE": round(curr_p, 2),
                    "SCORE": score,
                    "RSI": round(rsi, 2),
                    "STOP_LOSS": round(curr_p - (2 * atr), 2),
                    "TARGET": round(curr_p + (3 * atr), 2)
                })
                
                if (index + 1) % 10 == 0:
                    print(f"📊 Progress: {index + 1}/{total} processed...")
                
                # Tiny sleep to avoid triggering the rate limit again
                time.sleep(0.2)

            except Exception:
                continue

        # 5. Save final results
        if results:
            final_df = pd.DataFrame(results)
            # Sort by highest score first
            final_df = final_df.sort_values(by="SCORE", ascending=False)
            final_df.to_csv("daily_analysis.csv", index=False)
            print(f"✅ Success! Generated analysis for {len(results)} stocks.")
        else:
            print("❌ No data was retrieved. Yahoo Finance might be blocking the IP.")
            
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")

if __name__ == "__main__":
    run_engine()
