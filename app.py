import streamlit as st
import pandas as pd
import json, os, datetime

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

st.markdown("""
    <style>
    h1 { font-size: 1.6rem !important; }
    h2 { font-size: 1.2rem !important; }
    h3 { font-size: 1.0rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
    .stMetric { background-color: #1e2130; border-radius: 8px; padding: 10px !important; border: 1px solid #3e4452; }
    .stDataFrame td, .stDataFrame th { font-size: 0.85rem !important; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=600)
def load_all_data():
    if not os.path.exists("daily_analysis.csv"): return None, None, pd.DataFrame()
    df = pd.read_csv("daily_analysis.csv")
    df['SECTOR'] = df['SECTOR'].fillna("General").astype(str)
    
    nifty = df[df['SYMBOL'] == "^NSEI"].iloc[0] if "^NSEI" in df['SYMBOL'].values else None
    df = df[df['SYMBOL'] != "^NSEI"]
    
    df['STOP-LOSS'] = (df['PRICE'] * 0.95).round(2)
    df['EXP_PCT'] = (((df['TARGET'] - df['PRICE']) / df['PRICE']) * 100).round(2)
    df['VERDICT'] = df.apply(lambda r: "🔴 EXIT" if r['RSI'] > 78 else ("💎 ALPHA" if r['SCORE'] >= 8 else "🟢 BUY" if r['SCORE'] >= 6 else "🟡 HOLD"), axis=1)
    
    hist = pd.read_csv("trade_history.csv") if os.path.exists("trade_history.csv") else pd.DataFrame()
    return df, nifty, hist

def load_portfolio_file():
    if os.path.exists("portfolio.json"):
        try:
            with open("portfolio.json", "r") as f:
                return json.load(f)
        except: return {}
    return {}

df, nifty, history = load_all_data()
portfolio_data = load_portfolio_file()

if df is not None:
    tabs = st.tabs(["🚀 Screener", "💼 Portfolio", "⚡ Actionables", "📊 Success"])

    # --- TAB 1: SCREENER ---
    with tabs[0]:
        if nifty is not None:
            st.caption(f"🏁 Benchmark Nifty 50: {nifty['PRICE']:.2f} | RSI: {nifty['RSI']:.2f}")

        ind_stats = df.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).round(2)
        
        # Display Top 3 Industries as Metrics
        num_inds = len(ind_stats)
        if num_inds > 0:
            m_cols = st.columns(min(3, num_inds))
            icons = ["🥇", "🥈", "🥉"]
            for i in range(min(3, num_inds)):
                m_cols[i].metric(f"{icons[i]} {ind_stats.index[i]}", f"{ind_stats.values[i]:.2f}")
        
        # Remaining Industries in a clean expander
        if num_inds > 3:
            with st.expander("See More Industry Scores"):
                st.dataframe(ind_stats[3:], use_container_width=True)

        st.divider()
        c1, c2, c3 = st.columns([2, 1, 1])
        f_ind = c1.multiselect("Filter Industry", options=sorted(df['SECTOR'].unique()))
        f_score = c2.slider("Min Score", 0, 10, 5)
        f_search = c3.text_input("🔍 Ticker Search")
        
        v_df = df.copy()
        if f_ind: v_df = v_df[v_df['SECTOR'].isin(f_ind)]
        if f_search: v_df = v_df[v_df['SYMBOL'].str.contains(f_search.upper())]
        v_df = v_df[v_df['SCORE'] >= f_score]
        
        st.dataframe(v_df[["SYMBOL", "VERDICT", "SCORE", "PRICE", "TARGET", "STOP-LOSS", "EXP_PCT", "SECTOR", "RSI"]].sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)

    # --- TAB 2: PORTFOLIO ---
    with tabs[1]:
        if portfolio_data:
            p_rows = []
            inv_total, cur_total = 0.0, 0.0
            for s, info in portfolio_data.items():
                match = df[df['SYMBOL'] == s]
                if not match.empty:
                    m = match.iloc[0]
                    cost = info['price'] * info['qty']
                    current = m['PRICE'] * info['qty']
                    inv_total += cost
                    cur_total += current
                    p_rows.append({
                        "SYMBOL": s, "QTY": info['qty'], "AVG": f"{info['price']:.2f}", 
                        "CMP": f"{m['PRICE']:.2f}", "P&L %": f"{((m['PRICE']-info['price'])/info['price']*100):.2f}%", 
                        "VERDICT": m['VERDICT'], "EXP %": f"{m['EXP_PCT']:.2f}%"
                    })
            
            # Summary Header
            k1, k2, k3 = st.columns(3)
            k1.metric("Invested", f"₹{inv_total:,.2f}")
            k2.metric("Current", f"₹{cur_total:,.2f}", delta=f"₹{cur_total-inv_total:,.2f}")
            k3.metric("Net Return", f"{((cur_total-inv_total)/inv_total*100 if inv_total > 0 else 0):.2f}%")
            
            st.table(pd.DataFrame(p_rows))
        else:
            st.info("Portfolio is empty. Add data to portfolio.json.")

    # --- TAB 3: ACTIONABLES ---
    with tabs[2]:
        st.subheader("🎯 Swing Action Center")
        col_buys, col_alerts = st.columns(2)
        
        with col_buys:
            st.markdown("### 💎 Top Alpha Picks")
            alphas = df[df['VERDICT'] == "💎 ALPHA"].sort_values("EXP_PCT", ascending=False).head(5)
            if not alphas.empty:
                st.dataframe(alphas[["SYMBOL", "PRICE", "EXP_PCT", "VOL_SURGE"]], hide_index=True)
            else:
                st.write("No Alpha picks currently.")

        with col_alerts:
            st.markdown("### 🚨 Portfolio Alerts")
            alert_count = 0
            for s in portfolio_data:
                m = df[df['SYMBOL'] == s].iloc[0] if s in df['SYMBOL'].values else None
                if m is not None:
                    if "EXIT" in m['VERDICT']:
                        st.error(f"EXIT {s}: Overbought RSI ({m['RSI']:.2f})")
                        alert_count += 1
                    if m['PRICE'] <= m['STOP-LOSS']:
                        st.warning(f"SL HIT {s}: Under {m['STOP-LOSS']:.2f}")
                        alert_count += 1
            if alert_count == 0: st.write("All holdings are within safety zones.")

    # --- TAB 4: SUCCESS RATE ---
    with tabs[3]:
        st.subheader("📈 Trade Performance History")
        if not history.empty:
            win_rate = (len(history[history['P&L_%'] > 0]) / len(history) * 100) if len(history) > 0 else 0
            st.metric("Strategy Win Rate", f"{win_rate:.2f}%")
            st.dataframe(history, use_container_width=True, hide_index=True)
        else:
            st.info("History will populate once trades are exited in the Portfolio tab.")

else:
    st.error("Engine failed to generate data.")
            
