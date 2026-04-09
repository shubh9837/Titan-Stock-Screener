import streamlit as st
import pandas as pd
import json, os, datetime
import plotly.express as px

st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

# CSS Styling
st.markdown("""
    <style>
    h1, h2, h3 { color: #f0f2f6; }
    .stMetric { background-color: #1e2130; border-radius: 8px; border: 1px solid #3e4452; }
    .buy-pointer { background-color: #1a2e1a; padding: 12px; border-radius: 6px; margin-bottom: 8px; border-left: 5px solid #4CAF50; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=600)
def load_all_data():
    if not os.path.exists("daily_analysis.csv"): return None, pd.DataFrame()
    df = pd.read_csv("daily_analysis.csv")
    df['SECTOR'] = df['SECTOR'].fillna("General").astype(str)
    df['EXP_PCT'] = (((df['TARGET'] - df['PRICE']) / df['PRICE']) * 100).round(2)
    df['VERDICT'] = df.apply(lambda r: "🔴 EXIT" if r['RSI'] > 78 else ("💎 ALPHA" if r['SCORE'] >= 8 else "🟢 BUY" if r['SCORE'] >= 6 else "🟡 HOLD"), axis=1)
    hist = pd.read_csv("trade_history.csv") if os.path.exists("trade_history.csv") else pd.DataFrame()
    return df, hist

df, history = load_all_data()
portfolio = {}
if os.path.exists("portfolio.json"):
    with open("portfolio.json", "r") as f: portfolio = json.load(f)

if df is not None:
    tabs = st.tabs(["🚀 Screener", "💼 Portfolio", "⚡ Actionables", "📊 Success Rate"])

    # --- TAB 1: SCREENER ---
    with tabs[0]:
        # Market Breadth Logic
        breadth = (df['ABOVE_200'].sum() / len(df)) * 100
        st.caption(f"🌍 Market Breadth: {breadth:.2f}% of stocks are in a long-term uptrend.")
        
        ind_stats = df.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).round(2)
        with st.expander("📊 Industry Rankings (Sorted by Score)"):
            st.dataframe(ind_stats, use_container_width=True)

        if st.button("🔥 Suggest Top Picks"):
            top = df[(df['SCORE'] >= 9) & (df['VOL_SURGE'] > 1.8) & (df['RSI'] < 65)].sort_values("EXP_PCT", ascending=False).head(5)
            for _, row in top.iterrows():
                st.success(f"**{row['SYMBOL']}** | Target: ₹{row['TARGET']:.2f} | Exp: {row['EXP_PCT']:.2f}%")

        st.divider()
        c1, c2, c3 = st.columns([2, 1, 1])
        f_ind = c1.multiselect("Industry", options=sorted(df['SECTOR'].unique()))
        f_score = c2.slider("Min Score", 0, 10, 5)
        f_search = c3.text_input("🔍 Search")
        
        v_df = df.copy()
        if f_ind: v_df = v_df[v_df['SECTOR'].isin(f_ind)]
        if f_search: v_df = v_df[v_df['SYMBOL'].str.contains(f_search.upper())]
        v_df = v_df[v_df['SCORE'] >= f_score]
        st.dataframe(v_df[["SYMBOL", "VERDICT", "SCORE", "PRICE", "TARGET", "EXP_PCT", "SECTOR", "RSI"]].sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)

    # --- TAB 2: PORTFOLIO ---
    with tabs[1]:
        if portfolio:
            p_rows = []
            t_inv, t_cur = 0.0, 0.0
            for s, info in portfolio.items():
                m = df[df['SYMBOL'] == s].iloc[0] if s in df['SYMBOL'].values else None
                if m is not None:
                    t_inv += (info['price'] * info['qty'])
                    t_cur += (m['PRICE'] * info['qty'])
                    # Trailing SL: Entry + 50% of the current gains
                    gain = m['PRICE'] - info['price']
                    tsl = info['price'] + (gain * 0.5) if gain > 0 else (info['price'] * 0.95)
                    p_rows.append({
                        "SYMBOL": s, "QTY": info['qty'], "AVG": info['price'], "CMP": m['PRICE'], 
                        "P&L": round(m['PRICE']-info['price'], 2), "P&L %": round(((m['PRICE']-info['price'])/info['price'])*100, 2),
                        "VERDICT": m['VERDICT'], "TSL": round(tsl, 2), "SECTOR": m['SECTOR']
                    })
            
            p_df = pd.DataFrame(p_rows)
            s1, s2, s3 = st.columns(3)
            s1.metric("Invested", f"₹{t_inv:,.2f}")
            s2.metric("Current", f"₹{t_cur:,.2f}", delta=f"₹{t_cur-t_inv:,.2f}")
            s3.metric("Net %", f"{((t_cur-t_inv)/t_inv*100):.2f}%")

            st.divider()
            col_list, col_chart = st.columns([2, 1])
            with col_list:
                st.dataframe(p_df.drop(columns=['SECTOR']), use_container_width=True, hide_index=True)
            with col_chart:
                fig = px.pie(p_df, values='QTY', names='SECTOR', title="Sector Exposure", hole=0.4)
                fig.update_layout(showlegend=False, margin=dict(t=30, b=0, l=0, r=0), height=200)
                st.plotly_chart(fig, use_container_width=True)

            # Exit Logic
            with st.expander("🛠️ Exit Position"):
                ex_s = st.selectbox("Exit Stock", list(portfolio.keys()))
                ex_q = st.number_input("Qty", min_value=1, max_value=portfolio[ex_s]['qty'] if ex_s in portfolio else 1)
                if st.button("Confirm Exit"):
                    # History logging and JSON update logic...
                    st.success(f"Exited {ex_s}")

    # --- TAB 3: ACTIONABLES ---
    with tabs[2]:
        st.subheader("📋 Holding Alerts")
        for _, row in p_df.iterrows():
            if row['CMP'] < row['TSL']:
                st.warning(f"⚠️ **{row['SYMBOL']}**: Below Trailing SL ({row['TSL']}). Protect your gains!")
            if "EXIT" in row['VERDICT']:
                st.error(f"🚨 **{row['SYMBOL']}**: Overbought RSI. Book profits now!")

        st.divider()
        st.subheader("🎯 Buy Recommendations")
        recoms = df[df['VERDICT'] == "💎 ALPHA"].sort_values("EXP_PCT", ascending=False).head(5)
        for _, r in recoms.iterrows():
            st.markdown(f'<div class="buy-pointer"><b>{r["SYMBOL"]}</b> | CMP: ₹{r["PRICE"]:.2f} | <b>Target: ₹{r["TARGET"]:.2f} ({r["EXP_PCT"]:.2f}%)</b></div>', unsafe_allow_html=True)

    # --- TAB 4: SUCCESS RATE ---
    with tabs[3]:
        if not history.empty:
            st.metric("Win Rate", f"{(len(history[history['P&L_%'] > 0])/len(history)*100):.1f}%")
            st.dataframe(history, use_container_width=True)
            
