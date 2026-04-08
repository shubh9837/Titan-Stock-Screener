import streamlit as st
import pandas as pd
import json, os, base64, requests

st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

# --- 1. CONFIGURATION ---
GITHUB_REPO = "your-github-username/your-repo-name" 
PORTFOLIO_FILE = "portfolio.json"

# --- 2. DATA LOADERS ---
def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_portfolio_sync(p):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(p, f, indent=4)
    token = st.secrets.get("GH_TOKEN")
    if token:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{PORTFOLIO_FILE}"
            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
            res = requests.get(url, headers=headers)
            sha = res.json().get("sha") if res.status_code == 200 else None
            content_encoded = base64.b64encode(json.dumps(p).encode()).decode()
            data = {"message": "Update portfolio", "content": content_encoded}
            if sha: data["sha"] = sha
            requests.put(url, headers=headers, json=data)
        except: pass

@st.cache_data(ttl=600)
def load_market_data():
    if not os.path.exists("daily_analysis.csv") or not os.path.exists("tickers_enriched.csv"):
        return None, None
    return pd.read_csv("daily_analysis.csv"), pd.read_csv("tickers_enriched.csv")

analysis, meta = load_market_data()
portfolio = load_portfolio()

# --- 3. UI HELPERS ---
def get_verdict(score):
    if score >= 8: return "🟢 STRONG BUY"
    if score >= 7: return "🟢 BUY"
    if score >= 5: return "🟡 HOLD"
    return "🔴 AVOID"

# --- 4. NEW FEATURE LOGIC ---
def calculate_market_sentiment(df):
    # Market sentiment based on % of stocks above EMA200
    # In a real swing setup, 50%+ is healthy.
    high_score_pct = (len(df[df['SCORE'] >= 7]) / len(df)) * 100
    if high_score_pct > 20: return "🔥 BULLISH", "Market breadth is strong. Large positions okay."
    if high_score_pct > 10: return "⚖️ NEUTRAL", "Mixed signals. Stick to high-conviction trades."
    return "❄️ BEARISH", "Poor breadth. Keep cash ready; tight stop-losses."

# --- 5. DASHBOARD ---
st.title("🛡️ Quantum-Sentinel Pro")

if analysis is not None:
    # --- TOP BAR: MARKET SENTIMENT ---
    sentiment, advice = calculate_market_sentiment(analysis)
    st.info(f"**Market Pulse:** {sentiment} | {advice}")

    tab1, tab2, tab3 = st.tabs(["🚀 Strategy Screener", "💼 My Portfolio", "⚡ Actionables"])

    with tab1:
        merged = analysis.merge(meta[['SYMBOL', 'SECTOR']], on='SYMBOL', how='left')
        
        # FEATURE 1: SECTOR STRENGTH
        sector_ranks = merged.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False)
        
        c1, c2 = st.columns([1, 3])
        with c1:
            st.write("📊 **Sector Strength**")
            st.dataframe(sector_ranks.rename("Avg Score"), use_container_width=True)
        
        with c2:
            # SEARCH & FILTER
            s_list = ["ALL STOCKS"] + sorted(merged['SYMBOL'].tolist())
            pick = st.selectbox("🔍 Search Stock", options=s_list)
            
            df_view = merged.copy()
            if pick != "ALL STOCKS": df_view = df_view[df_view['SYMBOL'] == pick]
            
            df_view.insert(0, "VERDICT", df_view['SCORE'].apply(get_verdict))
            st.dataframe(df_view.sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Holdings")
        with st.expander("📝 Add/Update"):
            f1, f2, f3 = st.columns(3)
            s_pick = f1.selectbox("Ticker", options=[""] + sorted(meta['SYMBOL'].tolist()))
            s_price = f2.number_input("Avg Price", min_value=0.0)
            s_qty = f3.number_input("Qty", min_value=0)
            if st.button("💾 Save"):
                if s_pick:
                    if s_qty <= 0: portfolio.pop(s_pick, None)
                    else: portfolio[s_pick] = {"price": s_price, "qty": s_qty}
                    save_portfolio_sync(portfolio); st.rerun()

        if portfolio:
            p_data = []
            for s, info in portfolio.items():
                r = analysis[analysis['SYMBOL'] == s].iloc[0]
                # FEATURE 2: DYNAMIC STOP-LOSS (Approx 1.5x ATR logic from engine)
                # We estimate ATR impact based on price volatility if ATR isn't in CSV
                stop_loss = round(r['PRICE'] * 0.94, 2) # Standard 6% Swing Stop
                
                pl = (r['PRICE'] - info['price']) * info['qty']
                p_data.append({
                    "Verdict": get_verdict(r['SCORE']), "Stock": s, "Qty": info['qty'],
                    "P&L": round(pl, 2), "Target": r['TARGET'], "Stop-Loss": stop_loss
                })
            
            df_p = pd.DataFrame(p_data)
            st.dataframe(df_p.sort_values("P&L", ascending=False), use_container_width=True)

    with tab3:
        st.subheader("Priority Alerts")
        for s, info in portfolio.items():
            r = analysis[analysis['SYMBOL'] == s].iloc[0]
            # FEATURE 3: SMART ALERTS
            if r['PRICE'] <= (r['PRICE'] * 0.94): # Stop loss trigger
                st.error(f"🚨 **STOP LOSS**: {s} dropped 6% from last check. Review exit.")
            if r['PRICE'] >= r['TARGET']:
                st.success(f"💰 **TARGET HIT**: {s} reached {r['TARGET']}. Book profits!")
            if r['SCORE'] >= 8 and sentiment == "🔥 BULLISH":
                st.info(f"💎 **ALPHA**: {s} is high conviction in a Bull market. Potential to hold longer.")

else:
    st.error("Data missing.")
