import streamlit as st
import pandas as pd
import json, os, datetime
import plotly.express as px

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

st.markdown("""
    <style>
    h1 { font-size: 1.6rem !important; color: #E0E0E0; }
    h2 { font-size: 1.2rem !important; color: #BDBDBD; }
    .stMetric { background-color: #1e2130; border-radius: 8px; border: 1px solid #3e4452; padding: 10px !important; }
    .buy-pointer { 
        background-color: #1a2e1a; 
        padding: 12px; 
        border-radius: 6px; 
        margin-bottom: 8px; 
        border-left: 5px solid #4CAF50;
        line-height: 1.6;
    }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=600)
def load_all_data():
    if not os.path.exists("daily_analysis.csv"): return None, pd.DataFrame()
    df = pd.read_csv("daily_analysis.csv")
    df['SECTOR'] = df['SECTOR'].fillna("General").astype(str)
    df['EXP_PCT'] = (((df['TARGET'] - df['PRICE']) / df['PRICE']) * 100).round(2)
    df['VERDICT'] = df.apply(lambda r: "🔴 EXIT" if r['RSI'] > 78 else ("💎 ALPHA" if r['SCORE'] >= 8 else "🟢 BUY" if r['SCORE'] >= 6 else "🟡 HOLD"), axis=1)
    
    # Load history for Tab 4
    hist = pd.read_csv("trade_history.csv") if os.path.exists("trade_history.csv") else pd.DataFrame()
    return df, hist

df, history = load_all_data()

# Load Portfolio for Tab 2 & 3
portfolio = {}
if os.path.exists("portfolio.json"):
    try:
        with open("portfolio.json", "r") as f:
            portfolio = json.load(f)
    except: portfolio = {}

if df is not None:
    tabs = st.tabs(["🚀 Screener", "💼 Portfolio", "⚡ Actionables", "📊 Success Rate"])

    # --- TAB 1: SCREENER ---
    with tabs[0]:
        ind_stats = df.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).round(2)
        with st.expander("📊 Industry Rankings (Sorted by Score)"):
            st.table(ind_stats)

        if st.button("🔍 Suggest High-Probability Top Picks"):
            top = df[(df['SCORE'] >= 9) & (df['VOL_SURGE'] > 1.8) & (df['RSI'] < 65)].sort_values("EXP_PCT", ascending=False).head(5)
            if not top.empty:
                for _, row in top.iterrows():
                    st.success(f"**{row['SYMBOL']}** | Price: ₹{row['PRICE']:.2f} | Target: ₹{row['TARGET']:.2f} ({row['EXP_PCT']:.2f}%)")
            else:
                st.info("No 'Super-Alpha' setups found currently.")

        st.divider()
        c1, c2, c3 = st.columns([2, 1, 1])
        f_ind = c1.multiselect("Filter Industry", options=sorted(df['SECTOR'].unique()))
        f_score = c2.slider("Min Score", 0, 10, 5)
        f_search = c3.text_input("🔍 Search Ticker")
        
        v_df = df.copy()
        if f_ind: v_df = v_df[v_df['SECTOR'].isin(f_ind)]
        if f_search: v_df = v_df[v_df['SYMBOL'].str.contains(f_search.upper())]
        v_df = v_df[v_df['SCORE'] >= f_score]
        st.dataframe(v_df[["SYMBOL", "VERDICT", "SCORE", "PRICE", "TARGET", "EXP_PCT", "SECTOR", "RSI"]].sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)

    # --- TAB 2: PORTFOLIO ---
    p_df = pd.DataFrame() # Initialized for global use in other tabs
    with tabs[1]:
        if portfolio:
            p_rows = []
            t_inv, t_cur = 0.0, 0.0
            for s, info in portfolio.items():
                m_list = df[df['SYMBOL'] == s]
                if not m_list.empty:
                    m = m_list.iloc[0]
                    t_inv += (info['price'] * info['qty'])
                    t_cur += (m['PRICE'] * info['qty'])
                    # Trailing SL Calculation
                    gain = m['PRICE'] - info['price']
                    tsl = info['price'] + (gain * 0.5) if gain > 0 else (info['price'] * 0.95)
                    
                    p_rows.append({
                        "SYMBOL": s, "QTY": info['qty'], "AVG": info['price'], 
                        "CMP": m['PRICE'], "P&L %": round(((m['PRICE']-info['price'])/info['price'])*100, 2),
                        "VERDICT": m['VERDICT'], "TSL": round(tsl, 2), "SECTOR": m['SECTOR']
                    })
            
            if p_rows:
                p_df = pd.DataFrame(p_rows)
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
                    fig = px.pie(p_df, names='SECTOR', title="Sector Exposure", hole=0.5)
                    fig.update_layout(showlegend=False, height=250, margin=dict(t=30, b=0, l=0, r=0))
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Portfolio is empty. Update portfolio.json to see insights.")

    # --- TAB 3: ACTIONABLES (REINSTATED) ---
    with tabs[2]:
        if not p_df.empty:
            st.subheader("📋 Holding Alerts & Actions")
            for _, row in p_df.iterrows():
                if row['CMP'] < row['TSL']:
                    st.warning(f"⚠️ **{row['SYMBOL']}**: Below Trailing SL ({row['TSL']:.2f}). Protect your capital.")
                if "EXIT" in row['VERDICT']:
                    st.error(f"🚨 **{row['SYMBOL']}**: Overbought RSI. Consider booking profits.")
        else:
            st.info("No active holdings to analyze for alerts.")

        st.divider()
        st.subheader("🎯 Market Buy Pointers")
        recoms = df[df['VERDICT'] == "💎 ALPHA"].sort_values("EXP_PCT", ascending=False).head(5)
        for _, r in recoms.iterrows():
            st.markdown(f"""
                <div class="buy-pointer">
                    <b>{r['SYMBOL']}</b> | CMP: ₹{r['PRICE']:.2f} | <b>Target: ₹{r['TARGET']:.2f}</b><br>
                    Expected Return: {r['EXP_PCT']:.2f}% | Technical Score: {r['SCORE']}/10
                </div>
            """, unsafe_allow_html=True)

    # --- TAB 4: SUCCESS RATE (REINSTATED) ---
    with tabs[3]:
        st.subheader("📊 Performance Tracker")
        if not history.empty:
            win_rate = (len(history[history['P&L_%'] > 0]) / len(history) * 100) if len(history) > 0 else 0
            avg_gain = history['P&L_%'].mean()
            
            c1, c2 = st.columns(2)
            c1.metric("Win Rate", f"{win_rate:.2f}%")
            c2.metric("Avg Profit/Trade", f"{avg_gain:.2f}%")
            
            st.divider()
            st.dataframe(history.sort_values("DATE", ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("No historical trades found. Log exits in the Portfolio tab to track success.")

else:
    st.error("Engine failed to generate data. Check daily_analysis.csv.")
                
