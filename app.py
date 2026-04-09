import streamlit as st
import pandas as pd
import json, os, base64, requests

st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

# --- 1. CONFIGURATION ---
GITHUB_REPO = "your-username/your-repo" 
PORTFOLIO_FILE = "portfolio.json"

# --- 2. DATA LOADERS ---
@st.cache_data(ttl=600)
def load_market_data():
    if not os.path.exists("daily_analysis.csv") or not os.path.exists("tickers_enriched.csv"):
        return None, None
    return pd.read_csv("daily_analysis.csv"), pd.read_csv("tickers_enriched.csv")

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

analysis, meta = load_market_data()
portfolio = load_portfolio()

# --- 3. UI HELPERS ---
def get_verdict(score):
    if score >= 8: return "🟢 STRONG BUY"
    if score >= 7: return "🟢 BUY"
    if score >= 5: return "🟡 HOLD"
    return "🔴 AVOID"

# --- 4. DASHBOARD HEADER ---
st.title("🛡️ Quantum-Sentinel Pro")

if analysis is not None:
    # --- MARKET PULSE ---
    high_conv_df = analysis[analysis['SCORE'] >= 8]
    mood = "🔥 BULLISH" if len(high_conv_df) > 15 else "⚖️ NEUTRAL"
    if len(high_conv_df) < 5: mood = "❄️ BEARISH"
    st.info(f"**Market Pulse:** {mood} ({len(high_conv_df)} High-Conviction Setups)")

    tab1, tab2, tab3 = st.tabs(["🚀 Strategy Screener", "💼 My Portfolio", "⚡ Actionables"])

    with tab1:
        merged = analysis.merge(meta[['SYMBOL', 'SECTOR']], on='SYMBOL', how='left')
        
        # SECTOR LEADERBOARD
        with st.expander("📊 Sector Leaders (Top 3)", expanded=True):
            sec_ranks = merged.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).head(3).round(2)
            cols = st.columns(3)
            for i, (sector, score) in enumerate(sec_ranks.items()):
                cols[i].metric(sector, score)

        # --- PROGRESSIVE FILTERING SECTION ---
        st.divider()
        c1, c2 = st.columns([3, 1])
        with c2:
            # The "Magic Button" for filtering
            use_progressive = st.toggle("💎 High Conviction Only", help="Filters for Score 8+ and Top sectors")
        
        with c1:
            search_stock = st.selectbox("🔍 Search Ticker", ["ALL"] + sorted(merged['SYMBOL'].tolist()))

        # Filtering Logic
        df_view = merged.copy()
        if use_progressive:
            # Filter for Score 8+ AND only stocks in the top-scoring sectors
            top_sectors = merged.groupby('SECTOR')['SCORE'].mean().nlargest(5).index
            df_view = df_view[(df_view['SCORE'] >= 8) & (df_view['SECTOR'].isin(top_sectors))]
        
        if search_stock != "ALL":
            df_view = df_view[df_view['SYMBOL'] == search_stock]

        df_view.insert(0, "VERDICT", df_view['SCORE'].apply(get_verdict))
        
        # Display Table
        st.dataframe(df_view.sort_values("SCORE", ascending=False).round(2), use_container_width=True, hide_index=True)

    with tab2:
        if portfolio:
            p_rows = []
            total_invested = 0
            current_value = 0
            for s, info in portfolio.items():
                r = analysis[analysis['SYMBOL'] == s].iloc[0]
                val = r['PRICE'] * info['qty']
                cost = info['price'] * info['qty']
                total_invested += cost
                current_value += val
                p_rows.append({
                    "Verdict": get_verdict(r['SCORE']), "Stock": s, "Qty": info['qty'],
                    "Avg": round(info['price'], 2), "CMP": round(r['PRICE'], 2),
                    "P&L": round(val - cost, 2), "Target": round(r['TARGET'], 2)
                })
            
            # Executive Metric Row
            m1, m2, m3 = st.columns(3)
            m1.metric("Invested", f"₹{total_invested:,.0f}")
            m2.metric("Value", f"₹{current_value:,.0f}", delta=f"₹{current_value-total_invested:,.0f}")
            ret_pct = ((current_value-total_invested)/total_invested)*100 if total_invested > 0 else 0
            m3.metric("Net Return", f"{ret_pct:.2f}%")
            
            st.dataframe(pd.DataFrame(p_rows).sort_values("P&L", ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Portfolio is empty. Use the 'Add' section below.")

    with tab3:
        st.subheader("Automated Exit Strategy")
        for s, info in portfolio.items():
            r = analysis[analysis['SYMBOL'] == s].iloc[0]
            if r['PRICE'] >= r['TARGET']:
                st.success(f"💰 **BOOK PROFIT**: {s} hit target {round(r['TARGET'], 2)}.")
            elif r['RSI'] > 78:
                st.warning(f"⚠️ **OVERBOUGHT**: {s} (RSI: {round(r['RSI'], 2)}). Tighten Stop-Loss.")
else:
    st.error("Market data not available.")
    
