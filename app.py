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

def calculate_market_sentiment(df):
    high_score_pct = (len(df[df['SCORE'] >= 7]) / len(df)) * 100
    if high_score_pct > 20: return "🔥 BULLISH", "Market breadth is strong. Large positions okay."
    if high_score_pct > 10: return "⚖️ NEUTRAL", "Mixed signals. Stick to high-conviction trades."
    return "❄️ BEARISH", "Poor breadth. Keep cash ready; tight stop-losses."

# --- 4. DASHBOARD ---
st.title("🛡️ Quantum-Sentinel Pro")

if analysis is not None:
    sentiment, advice = calculate_market_sentiment(analysis)
    st.info(f"**Market Pulse:** {sentiment} | {advice}")

    tab1, tab2, tab3 = st.tabs(["🚀 Strategy Screener", "💼 My Portfolio", "⚡ Actionables"])

    with tab1:
        merged = analysis.merge(meta[['SYMBOL', 'SECTOR']], on='SYMBOL', how='left')
        
        # --- SECTOR STRENGTH (COMPRESSED) ---
        sector_ranks = merged.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).round(2)
        with st.expander("📊 View Sector Strength (Top 3 Leading Now)", expanded=True):
            st.table(sector_ranks.head(3).rename("Avg Score"))
            if st.checkbox("See More Sectors"):
                st.table(sector_ranks.tail(-3))

        # --- FILTERS (RESTORED) ---
        st.divider()
        c1, c2, c3 = st.columns([2, 2, 2])
        search_list = ["ALL STOCKS"] + sorted(merged['SYMBOL'].tolist())
        pick = c1.selectbox("🔍 Search Stock", options=search_list)
        selected_ind = c2.multiselect("Industry", sorted(merged['SECTOR'].dropna().unique()))
        min_rate = c3.slider("Min Strategy Score", 1, 10, 5)

        df_view = merged.copy()
        if pick != "ALL STOCKS": df_view = df_view[df_view['SYMBOL'] == pick]
        if selected_ind: df_view = df_view[df_view['SECTOR'].isin(selected_ind)]
        df_view = df_view[df_view['SCORE'] >= min_rate]
        
        df_view.insert(0, "VERDICT", df_view['SCORE'].apply(get_verdict))
        st.dataframe(df_view.sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)

        # --- TRADING GUIDE ---
        st.info("""
        💡 **Quick Guide:** - **Buying:** Target stocks with a Score ≥ 7 that belong to a top-performing sector. Ensure the verdict is 🟢.
        - **Profit Taking:** Exit or move Stop-Loss to cost when Target is hit. If RSI crosses 75, consider partial profit booking.
        """)

    with tab2:
        st.subheader("Holdings Management")
        with st.expander("📝 Add/Update Stock"):
            f1, f2, f3 = st.columns(3)
            s_pick = f1.selectbox("Ticker", options=[""] + sorted(meta['SYMBOL'].tolist()))
            s_price = f2.number_input("Avg Price", min_value=0.0)
            s_qty = f3.number_input("Qty", min_value=0)
            if st.button("💾 Save to Portfolio"):
                if s_pick:
                    if s_qty <= 0: portfolio.pop(s_pick, None)
                    else: portfolio[s_pick] = {"price": s_price, "qty": s_qty}
                    save_portfolio_sync(portfolio); st.rerun()

        if portfolio:
            p_data = []
            for s, info in portfolio.items():
                r = analysis[analysis['SYMBOL'] == s].iloc[0]
                total_gain = (r['PRICE'] - info['price']) * info['qty']
                p_data.append({
                    "Verdict": get_verdict(r['SCORE']), "Stock": s, "Qty": info['qty'],
                    "Avg": round(info['price'], 2), "CMP": round(r['PRICE'], 2),
                    "P&L": round(total_gain, 2), "Target": round(r['TARGET'], 2)
                })
            
            df_p = pd.DataFrame(p_data)
            st.dataframe(df_p.sort_values("P&L", ascending=False), use_container_width=True)
            
            # --- PORTFOLIO SUMMARY (RESTORED) ---
            net_pl = df_p['P&L'].sum()
            color = "green" if net_pl >= 0 else "red"
            st.markdown(f"### Overall Net P&L: :{color}[₹{net_pl:,.2f}]")
        
        # --- VERDICT GUIDE ---
        with st.expander("📚 Understanding Your Verdicts"):
            st.markdown("""
            - **STRONG BUY:** High momentum, high volume, and trend alignment. (Action: Entry or Add)
            - **BUY:** Good technical setup, positive score. (Action: Fresh Entry)
            - **HOLD:** Neutral trend. (Action: Maintain existing positions, avoid fresh buying)
            - **AVOID:** Bearish trend or low volume. (Action: Do not buy, review exit if held)
            """)

    with tab3:
        st.subheader("Priority Alerts")
        for s, info in portfolio.items():
            r = analysis[analysis['SYMBOL'] == s].iloc[0]
            if r['PRICE'] >= r['TARGET']:
                st.success(f"💰 **TARGET HIT**: {s} reached {round(r['TARGET'], 2)}. Book profits!")
            if r['RSI'] > 75:
                st.warning(f"⚠️ **OVERBOUGHT**: {s} (RSI: {round(r['RSI'], 2)}). Reversal risk high.")
else:
    st.error("Data missing.")
    
