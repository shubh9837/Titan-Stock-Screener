import streamlit as st
import pandas as pd
import json, os, datetime
import plotly.express as px # Ensure 'plotly' is in requirements.txt

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

st.markdown("""
    <style>
    h1 { font-size: 1.6rem !important; }
    .stMetric { background-color: #1e2130; border-radius: 8px; border: 1px solid #3e4452; padding: 10px !important; }
    .buy-pointer { background-color: #1a2e1a; padding: 12px; border-radius: 6px; margin-bottom: 8px; border-left: 5px solid #4CAF50; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=600)
def load_all_data():
    if not os.path.exists("daily_analysis.csv"): return None, pd.DataFrame()
    df = pd.read_csv("daily_analysis.csv")
    df['SECTOR'] = df['SECTOR'].fillna("General").astype(str)
    # Ensure 2 decimal points for calculations
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
        ind_stats = df.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).round(2)
        with st.expander("📊 Industry Rankings (Ranked by Score)"):
            st.table(ind_stats)

        if st.button("🔍 Suggest Top Picks"):
            top = df[(df['SCORE'] >= 9) & (df['VOL_SURGE'] > 1.8) & (df['RSI'] < 65)].sort_values("EXP_PCT", ascending=False).head(5)
            if not top.empty:
                for _, row in top.iterrows():
                    st.success(f"**{row['SYMBOL']}** | Price: ₹{row['PRICE']:.2f} | Target: ₹{row['TARGET']:.2f} ({row['EXP_PCT']:.2f}%)")
            else:
                st.info("No 'Super-Alpha' setups found right now.")

        st.divider()
        c1, c2, c3 = st.columns([2, 1, 1])
        f_ind = c1.multiselect("Industry", options=sorted(df['SECTOR'].unique()))
        f_score = c2.slider("Min Score", 0, 10, 5)
        f_search = c3.text_input("🔍 Search Ticker")
        
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
                    gain = m['PRICE'] - info['price']
                    tsl = info['price'] + (gain * 0.5) if gain > 0 else (info['price'] * 0.95)
                    p_rows.append({
                        "SYMBOL": s, "QTY": info['qty'], "AVG": f"{info['price']:.2f}", 
                        "CMP": f"{m['PRICE']:.2f}", "P&L": f"{(m['PRICE']-info['price']):.2f}", 
                        "P&L %": f"{(((m['PRICE']-info['price'])/info['price'])*100):.2f}%",
                        "VERDICT": m['VERDICT'], "TSL": f"{tsl:.2f}", "SECTOR": m['SECTOR']
                    })
            
            p_df = pd.DataFrame(p_rows)
            # Portfolio Summary Cards
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Invested", f"₹{t_inv:,.2f}")
            s2.metric("Current", f"₹{t_cur:,.2f}")
            s3.metric("P&L Amount", f"₹{t_cur-t_inv:,.2f}", delta=f"{((t_cur-t_inv)/t_inv*100):.2f}%" if t_inv > 0 else "0%")
            s4.metric("Holdings", len(portfolio))

            st.divider()
            col_list, col_chart = st.columns([2, 1])
            with col_list:
                st.dataframe(p_df.drop(columns=['SECTOR']), use_container_width=True, hide_index=True)
            with col_chart:
                # Use a color sequence that looks professional
                fig = px.pie(p_df, names='SECTOR', title="Sector Exposure", hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_layout(showlegend=False, margin=dict(t=30, b=0, l=0, r=0), height=250)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Portfolio is empty. Add stocks to portfolio.json.")

    # --- TAB 3: ACTIONABLES ---
    with tabs[2]:
        if portfolio:
            st.subheader("📋 Holding Alerts")
            for _, row in p_df.iterrows():
                # Fix: Convert strings back to float for comparison if needed, 
                # but better to do comparison in the loop above and store flags.
                curr_cmp = float(row['CMP'])
                curr_tsl = float(row['TSL'])
                if curr_cmp < curr_tsl:
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
            st.metric("Strategy Win Rate", f"{(len(history[history['P&L_%'] > 0])/len(history)*100):.2f}%")
            st.dataframe(history, use_container_width=True, hide_index=True)

else:
    st.error("Data source (daily_analysis.csv) not found. Run engine.py.")
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
            
