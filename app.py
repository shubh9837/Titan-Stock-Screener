import streamlit as st
import pandas as pd
import json, os, requests, base64

st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

# --- 1. DATA LOADING ENGINE ---
@st.cache_data(ttl=600)
def load_data():
    analysis_df = None
    history_df = pd.DataFrame(columns=["SYMBOL", "SCORE", "PRICE", "TARGET", "DATE_SIGNAL", "HOLDING"])
    meta_df = None

    if os.path.exists("daily_analysis.csv"):
        analysis_df = pd.read_csv("daily_analysis.csv")
        # Calculate Target % Increase immediately
        if 'PRICE' in analysis_df.columns and 'TARGET' in analysis_df.columns:
            analysis_df['POTENTIAL %'] = ((analysis_df['TARGET'] - analysis_df['PRICE']) / analysis_df['PRICE'] * 100).round(2)
    
    if os.path.exists("trade_history.csv"):
        history_df = pd.read_csv("trade_history.csv")
    
    if os.path.exists("tickers_enriched.csv"):
        meta_df = pd.read_csv("tickers_enriched.csv")
    
    return analysis_df, history_df, meta_df

def load_portfolio():
    if os.path.exists("portfolio.json"):
        try:
            with open("portfolio.json", "r") as f: return json.load(f)
        except: return {}
    return {}

# --- INITIALIZE ---
analysis, history, meta = load_data()
portfolio = load_portfolio()

def get_verdict(score):
    if score >= 8: return "🟢 STRONG BUY"
    if score >= 7: return "🟢 BUY"
    if score >= 5: return "🟡 HOLD"
    return "🔴 AVOID"

st.title("🛡️ Quantum-Sentinel Pro")

if analysis is not None:
    # Market Pulse
    high_conv = len(analysis[analysis['SCORE'] >= 8])
    mood = "🔥 BULLISH" if high_conv > 15 else "⚖️ NEUTRAL"
    if high_conv < 5: mood = "❄️ BEARISH"
    st.info(f"**Market Pulse:** {mood} ({high_conv} High-Conviction Signals Found)")

    tabs = st.tabs(["🚀 Screener", "💼 Portfolio", "⚡ Actionables", "📊 Success Tracker"])

    # --- TAB 1: SCREENER ---
    with tabs[0]:
        merged = analysis.merge(meta[['SYMBOL', 'SECTOR']], on='SYMBOL', how='left')
        
        # RESTORED SECTOR SCORES
        sector_ranks = merged.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).round(2)
        with st.expander("📊 Industry Leaderboard (Top 3 Leading)", expanded=True):
            st.table(sector_ranks.head(3).rename("Avg Strategy Score"))
            if st.checkbox("See More Industry Performance"):
                st.table(sector_ranks.tail(-3))

        st.divider()
        c1, c2 = st.columns([3, 1])
        with c2: best_only = st.toggle("💎 High Conviction Only (8+)")
        with c1: search = st.selectbox("🔍 Quick Lookup", ["ALL"] + sorted(merged['SYMBOL'].tolist()))
        
        df = merged.copy()
        if best_only: df = df[df['SCORE'] >= 8]
        if search != "ALL": df = df[df['SYMBOL'] == search]
        
        # Ensure Verdict is at the start
        df.insert(0, "VERDICT", df['SCORE'].apply(get_verdict))
        
        # Display with POTENTIAL %
        cols_to_show = ["VERDICT", "SYMBOL", "PRICE", "SCORE", "TARGET", "POTENTIAL %", "HOLDING", "SECTOR"]
        st.dataframe(df[cols_to_show].sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)

    # --- TAB 2: PORTFOLIO ---
    with tabs[1]:
        if portfolio:
            p_list = []
            total_inv, total_cur = 0, 0
            for s, info in portfolio.items():
                match = analysis[analysis['SYMBOL'] == s]
                if not match.empty:
                    r = match.iloc[0]
                    val, cost = r['PRICE']*info['qty'], info['price']*info['qty']
                    total_inv += cost; total_cur += val
                    p_list.append({
                        "Verdict": get_verdict(r['SCORE']), "Stock": s, "Qty": info['qty'], 
                        "Avg": info['price'], "CMP": r['PRICE'], "P&L": round(val-cost, 2), 
                        "Potential": f"{r['POTENTIAL %']}%", "Days": r['HOLDING']
                    })
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Invested", f"₹{total_inv:,.2f}")
            m2.metric("Current", f"₹{total_cur:,.2f}", delta=f"₹{total_cur-total_inv:,.2f}")
            m3.metric("Net %", f"{((total_cur-total_inv)/total_inv)*100:.2f}%" if total_inv > 0 else "0%")
            st.dataframe(pd.DataFrame(p_list), use_container_width=True, hide_index=True)
        else:
            st.info("Portfolio empty.")

    # --- TAB 3: ACTIONABLES (EXPANDED) ---
    with tabs[2]:
        st.subheader("Priority Insights")
        if portfolio:
            for s, info in portfolio.items():
                r = analysis[analysis['SYMBOL'] == s].iloc[0]
                if r['PRICE'] >= r['TARGET']:
                    st.success(f"💰 **EXIT**: {s} hit target. Re-deploy capital.")
        
        st.divider()
        st.write("🚀 **Top 7 Market Opportunities (High Conviction)**")
        # Filter for top scoring stocks with best potential
        top_7 = analysis[analysis['SCORE'] >= 8].sort_values(by=["SCORE", "POTENTIAL %"], ascending=False).head(7)
        
        for _, pick in top_7.iterrows():
            with st.container():
                st.info(f"**{pick['SYMBOL']}** | Score: {pick['SCORE']} | Target: {pick['TARGET']} (+{pick['POTENTIAL %']}%) | Est. Time: {pick['HOLDING']}")

    # --- TAB 4: SUCCESS TRACKER ---
    with tabs[3]:
        if not history.empty:
            st.subheader("System Accuracy")
            high_score_hist = history[history['SCORE'] >= 8]
            # Success approximation
            success_count = len(high_score_hist[high_score_hist['PRICE'] >= (high_score_hist['TARGET'] * 0.98)]) # 2% buffer
            total = len(high_score_hist['SYMBOL'].unique())
            rate = (success_count / total * 100) if total > 0 else 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Win Rate", f"{rate:.1f}%")
            c2.metric("Targets Hit", f"{success_count}")
            c3.metric("Avg Duration", "5-8 Days")
            st.dataframe(high_score_hist[['SYMBOL', 'DATE_SIGNAL', 'TARGET']].tail(10), use_container_width=True)
        else:
            st.info("Collecting historical data. Accuracy metrics will appear in 48 hours.")

else:
    st.error("Engine data (daily_analysis.csv) not found. Please run the GitHub Action.")
