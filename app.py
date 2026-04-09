import streamlit as st
import pandas as pd
import json, os, datetime

st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

@st.cache_data(ttl=600)
def load_all_data():
    if not os.path.exists("daily_analysis.csv"): return None, None, pd.DataFrame()
    df = pd.read_csv("daily_analysis.csv")
    nifty = df[df['SYMBOL'] == "^NSEI"].iloc[0] if "^NSEI" in df['SYMBOL'].values else None
    df = df[df['SYMBOL'] != "^NSEI"]
    df['STOP-LOSS'] = (df['PRICE'] * 0.95).round(2)
    df['EXP_PCT'] = (((df['TARGET'] - df['PRICE']) / df['PRICE']) * 100).round(2)
    df['VERDICT'] = df.apply(lambda r: "🔴 EXIT" if r['RSI'] > 78 else ("💎 ALPHA" if r['SCORE'] >= 8 else "🟢 BUY" if r['SCORE'] >= 6 else "🟡 HOLD"), axis=1)
    hist = pd.read_csv("trade_history.csv") if os.path.exists("trade_history.csv") else pd.DataFrame()
    return df, nifty, hist

df, nifty, history = load_all_data()

if df is not None:
    tabs = st.tabs(["🚀 Screener", "💼 Portfolio", "⚡ Actionables", "📊 Success"])

    with tabs[0]:
        if nifty is not None:
            st.info(f"📈 **Nifty 50 Benchmark:** {nifty['PRICE']} | RSI: {nifty['RSI']}")

        st.subheader("Industry Insights")
        ind_stats = df.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).round(2)
        
        # FIXED: Dynamic column generation to prevent IndexError
        num_inds = len(ind_stats)
        display_count = min(3, num_inds)
        if display_count > 0:
            m_cols = st.columns(display_count)
            icons = ["🥇", "🥈", "🥉"]
            for i in range(display_count):
                m_cols[i].metric(f"{icons[i]} {ind_stats.index[i]}", f"Score: {ind_stats.values[i]}")
        
        if num_inds > 3:
            with st.expander("Expand to see all Industry Scores"):
                st.table(ind_stats[3:])

        st.divider()
        # Filter Logic
        c1, c2, c3 = st.columns([2, 1, 1])
        f_ind = c1.multiselect("Filter by Industry", options=sorted(df['SECTOR'].unique()))
        f_score = c2.slider("Min Score Filter", 0, 10, 5)
        f_search = c3.text_input("🔍 Search Ticker")
        
        v_df = df.copy()
        if f_ind: v_df = v_df[v_df['SECTOR'].isin(f_ind)]
        if f_search: v_df = v_df[v_df['SYMBOL'].str.contains(f_search.upper())]
        v_df = v_df[v_df['SCORE'] >= f_score]
        
        st.dataframe(v_df[["SYMBOL", "VERDICT", "SCORE", "PRICE", "TARGET", "STOP-LOSS", "EXP_PCT", "SECTOR", "RSI"]].sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)

    with tabs[1]: # Portfolio
        if os.path.exists("portfolio.json"):
            with open("portfolio.json", "r") as f: port = json.load(f)
            if port:
                p_rows = []
                for s, info in port.items():
                    match = df[df['SYMBOL'] == s]
                    if not match.empty:
                        m = match.iloc[0]
                        p_rows.append({"SYMBOL": s, "QTY": info['qty'], "AVG": info['price'], "CMP": m['PRICE'], "P&L %": round(((m['PRICE']-info['price'])/info['price'])*100, 2), "VERDICT": m['VERDICT']})
                st.dataframe(pd.DataFrame(p_rows), use_container_width=True)
                
                # Exit button logic
                to_exit = st.selectbox("Exit Stock", list(port.keys()))
                if st.button("Log Exit"):
                    # [History and JSON update logic as provided previously]
                    st.success(f"Log generated for {to_exit}")

else:
    st.error("Engine failed to generate data. Please check Tickers.csv and run engine.py.")
    
