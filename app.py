import streamlit as st
import pandas as pd
import json, os, datetime

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #1e2130; border-radius: 10px; padding: 15px; border: 1px solid #3e4452; }
    .stDataFrame { border: 1px solid #3e4452; border-radius: 10px; }
    h1, h2, h3 { color: #f0f2f6; }
    </style>
    """, unsafe_allow_html=True)

# --- DATA LOADERS ---
@st.cache_data(ttl=600)
def load_all_data():
    if not os.path.exists("daily_analysis.csv"): return None, None, pd.DataFrame()
    
    df = pd.read_csv("daily_analysis.csv")
    nifty = df[df['SYMBOL'] == "^NSEI"].iloc[0] if "^NSEI" in df['SYMBOL'].values else None
    df = df[df['SYMBOL'] != "^NSEI"] # Data for screener
    
    df['STOP-LOSS'] = (df['PRICE'] * 0.95).round(2)
    df['EXP_PCT'] = (((df['TARGET'] - df['PRICE']) / df['PRICE']) * 100).round(2)
    
    # Verdict Logic
    def get_verdict(row):
        if row['RSI'] > 78: return "🔴 EXIT"
        if row['SCORE'] >= 8: return "💎 ALPHA"
        return "🟢 BUY" if row['SCORE'] >= 6 else "🟡 HOLD"
    
    df['VERDICT'] = df.apply(get_verdict, axis=1)
    
    hist = pd.read_csv("trade_history.csv") if os.path.exists("trade_history.csv") else pd.DataFrame()
    return df, nifty, hist

def load_portfolio():
    if os.path.exists("portfolio.json"):
        with open("portfolio.json", "r") as f:
            return json.load(f)
    return {}

df, nifty, history = load_all_data()
portfolio = load_portfolio()

# --- APP LAYOUT ---
st.title("🛡️ Quantum-Sentinel Pro")

if df is not None:
    tabs = st.tabs(["🚀 Screener", "💼 My Portfolio", "⚡ Actionables", "📊 Success Rate"])

    # --- TAB 1: SCREENER ---
    with tabs[0]:
        if nifty is not None:
            st.info(f"📈 **Nifty 50 Benchmark:** {nifty['PRICE']} | RSI: {nifty['RSI']} | Trend: {'Bullish' if nifty['SCORE'] >= 6 else 'Neutral'}")

        # Industry Leaderboard
        st.subheader("Industry Insights")
        ind_stats = df.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).round(2)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("🥇 " + ind_stats.index[0], f"Score: {ind_stats.values[0]}")
        m2.metric("🥈 " + ind_stats.index[1], f"Score: {ind_stats.values[1]}")
        m3.metric("🥉 " + ind_stats.index[2], f"Score: {ind_stats.values[2]}")
        
        with st.expander("Expand to see all Industry Scores"):
            st.table(ind_stats[3:])

        st.divider()
        c1, c2, c3 = st.columns([2, 1, 1])
        f_ind = c1.multiselect("Filter by Industry", options=sorted(df['SECTOR'].unique()))
        f_score = c2.slider("Min Score Filter", 0, 10, 5)
        f_search = c3.text_input("🔍 Search Ticker")
        
        v_df = df.copy()
        if f_ind: v_df = v_df[v_df['SECTOR'].isin(f_ind)]
        if f_search: v_df = v_df[v_df['SYMBOL'].str.contains(f_search.upper())]
        v_df = v_df[v_df['SCORE'] >= f_score]
        
        cols = ["SYMBOL", "VERDICT", "SCORE", "PRICE", "TARGET", "STOP-LOSS", "EXP_PCT", "SECTOR", "RSI"]
        st.dataframe(v_df[cols].sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)

    # --- TAB 2: MY PORTFOLIO ---
    with tabs[1]:
        if portfolio:
            p_rows = []
            t_inv, t_cur = 0.0, 0.0
            
            for sym, info in portfolio.items():
                match = df[df['SYMBOL'] == sym]
                if not match.empty:
                    m = match.iloc[0]
                    t_inv += (info['price'] * info['qty'])
                    t_cur += (m['PRICE'] * info['qty'])
                    p_rows.append({
                        "SYMBOL": sym, "QTY": info['qty'], "AVG": info['price'], 
                        "CMP": m['PRICE'], "P&L %": round(((m['PRICE']-info['price'])/info['price'])*100, 2),
                        "VERDICT": m['VERDICT'], "TARGET": m['TARGET'], "RSI": m['RSI']
                    })
            
            # Summary Metrics
            s1, s2, s3 = st.columns(3)
            s1.metric("Invested", f"₹{t_inv:,.0f}")
            s2.metric("Current Value", f"₹{t_cur:,.0f}", delta=f"₹{t_cur-t_inv:,.0f}")
            s3.metric("Overall Return", f"{((t_cur-t_inv)/t_inv*100):.2f}%" if t_inv > 0 else "0%")
            
            st.divider()
            st.dataframe(pd.DataFrame(p_rows), use_container_width=True, hide_index=True)
            
            # Deletion Logic
            st.subheader("Manage Holdings")
            to_del = st.selectbox("Select stock to exit/clear", list(portfolio.keys()))
            if st.button("Confirm Exit & Log Performance"):
                # Append to history for Tab 4
                exit_price = df[df['SYMBOL'] == to_del].iloc[0]['PRICE']
                entry_price = portfolio[to_del]['price']
                new_h = pd.DataFrame([{"SYMBOL": to_del, "ENTRY": entry_price, "EXIT": exit_price, "P&L_%": round(((exit_price-entry_price)/entry_price)*100,2), "DATE": str(datetime.date.today())}])
                new_h.to_csv("trade_history.csv", mode='a', header=not os.path.exists("trade_history.csv"), index=False)
                
                # Update portfolio.json
                del portfolio[to_del]
                with open("portfolio.json", "w") as f: json.dump(portfolio, f)
                st.success(f"Exited {to_del}. History Updated.")
                st.rerun()
        else:
            st.warning("Portfolio is empty. Update portfolio.json in your repository.")

    # --- TAB 3: ACTIONABLES ---
    with tabs[2]:
        st.subheader("⚡ Immediate Swing Opportunities")
        # Logic: Alpha Buy + High Vol Surge
        best_buys = df[(df['VERDICT'] == "💎 ALPHA") & (df['VOL_SURGE'] > 1.8)].sort_values("EXP_PCT", ascending=False)
        st.table(best_buys[["SYMBOL", "PRICE", "TARGET", "EXP_PCT", "VOL_SURGE"]].head(10))
        
        st.divider()
        st.subheader("🚨 Portfolio Warnings")
        for sym in portfolio:
            row = df[df['SYMBOL'] == sym].iloc[0]
            if "EXIT" in row['VERDICT']: st.error(f"**{sym}**: Overbought (RSI: {row['RSI']}). Consider booking profits.")
            if row['PRICE'] <= row['STOP-LOSS']: st.warning(f"**{sym}**: Stop-Loss triggered. Review for exit.")

    # --- TAB 4: SUCCESS RATE ---
    with tabs[3]:
        if not history.empty:
            st.metric("Total Trades Executed", len(history))
            win_rate = (len(history[history['P&L_%'] > 0]) / len(history)) * 100
            st.metric("Historical Win Rate", f"{win_rate:.1f}%")
            st.dataframe(history, use_container_width=True)
        else:
            st.info("Performance history will appear here once you exit stocks in the Portfolio tab.")

else:
    st.error("Engine failure: daily_analysis.csv not found.")
        
