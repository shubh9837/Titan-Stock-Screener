import pandas as pd
import yfinance as yf
import os

print("🔍 Loading raw Tickers.csv...")
# 1. Load your raw list of symbols
df = pd.read_csv("Tickers.csv")
symbols = df['SYMBOL'].dropna().astype(str).str.strip().tolist()

results = []
print(f"📡 Scanning {len(symbols)} symbols... Please wait.\n")

for sym in symbols:
    ticker = f"{sym}.NS" 
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1y")
        
        if hist.empty:
            reason = "❌ Invalid Symbol / Unlisted / RE"
            sector = "Unknown"
        elif len(hist) < 100:
            reason = f"⚠️ Recent IPO (< 100 days). Has {len(hist)} days."
            sector = t.info.get('sector', 'Unknown')
        else:
            reason = "✅ Success"
            sector = t.info.get('sector', 'Unknown')
            
        print(f"{sym}: {reason} | Sector: {sector}")
        
    except Exception as e:
        reason = "❌ Error / Delisted"
        sector = "Unknown"
        
    results.append({
        "SYMBOL": sym,
        "SECTOR": sector,
        "STATUS": reason
    })

res_df = pd.DataFrame(results)

# 2. Create a clean file strictly with successful stocks
clean_df = res_df[res_df['STATUS'] == '✅ Success'][['SYMBOL', 'SECTOR']]
clean_df = clean_df[clean_df['SECTOR'] != 'Unknown']

# 3. Overwrite the original Tickers.csv with the mapped data
clean_df.to_csv("Tickers.csv", index=False)

print("\n🎉 COMPLETE!")
print(f"Original Symbols: {len(symbols)}")
print(f"Valid, Mapped Symbols: {len(clean_df)}")
print("Tickers.csv has been successfully overwritten with the clean data.")
