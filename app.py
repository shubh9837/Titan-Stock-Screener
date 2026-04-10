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
        padding: 15px; 
        border-radius: 8px; 
        margin-bottom: 10px; 
        border-left: 5px solid #4CAF50;
        line-height: 1.6;
    }
    .sell-pointer { 
        background-color: #2e1a1a; 
        padding: 15px; 
        border-radius: 8px; 
        margin-bottom: 10px; 
        border-left: 5px solid #ff4b4b;
    }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=600)
def load_all_data():
    if not os.path.exists("daily_analysis.csv"): return None, pd.DataFrame()
    df = pd.read_csv("daily_analysis.csv")
    df['SECTOR'] = df['SECTOR'].fillna("General").astype(str)
    df['STOP-LOSS'] = (df['PRICE'] * 0.95).round(2)
    df['EXP_PCT'] = (((df['TARGET'] - df['PRICE']) / df['PRICE']) * 100).round(2)
    df['VERDICT'] = df.apply(lambda r: "🔴 EXIT" if r['RSI'] > 78 else ("💎 ALPHA" if r['SCORE'] >= 8 else "🟢 BUY" if r['SCORE'] >= 6 else "🟡 HOLD"), axis=1)
    
    hist = pd.read_csv("trade_history.csv") if os.path.exists("trade_history.csv") else pd.DataFrame()
    return df, hist

def save_portfolio(data):
    with open("portfolio.json", "w") as f:
        json.dump(data, f)

df, history = load_all_data()

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
        # Industry Dropdown Sorted
        ind_stats = df.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).reset_index()
        ind_stats['SCORE'] = ind_stats['SCORE'].map('{:,.2f}'.format)
        
        with st.expander("📊 View All Industry Scores (Ranked)"):
            st.dataframe(ind_stats, use_container_width=True, hide_index=True)

        # Top Pick Suggestion Button
        if st.button("🔥 Suggest Top High-Conviction Picks"):
            top = df[(df['SCORE'] >= 9) & (df['VOL_SURGE'] > 1.8) & (df['RSI'] < 65)].sort_values("EXP_PCT", ascending=False).head(5)
            if not top.empty:
                st.subheader("Targeting 10-15% short-term breakouts:")
                for _, row in top.iterrows():
                    st.success(f"**{row['SYMBOL']}** | Price: ₹{row['PRICE']:.2f} | Target: ₹{row['TARGET']:.2f} ({row['EXP_PCT']:.2f}%) | Score: {row['SCORE']}")
            else:
                st.info("No 'Super-Alpha' setups found currently. Maintain patience.")

        st.divider()
        c1, c2, c3 = st.columns([2, 1, 1])
        f_ind = c1.multiselect("Filter Industry", options=sorted(df['SECTOR'].unique()))
        f_score = c2.slider("Min Score Filter", 0, 10, 5)
        f_search = c3.text_input("🔍 Search Ticker")
        
        v_df = df.copy()
        if f_ind: v_df = v_df[v_df['SECTOR'].isin(f_ind)]
        if f_search: v_df = v_df[v_df['SYMBOL'].str.contains(f_search.upper())]
        v_df = v_df[v_df['SCORE'] >= f_score]
        st.dataframe(v_df[["SYMBOL", "VERDICT", "SCORE", "PRICE", "TARGET", "STOP-LOSS", "EXP_PCT", "SECTOR", "RSI"]].sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)

    # --- TAB 2: PORTFOLIO ---
    p_df = pd.DataFrame()
    with tabs[1]:
        st.subheader("Manage Holdings")
        with st.expander("➕ Add New Stock to Portfolio"):
            col_a, col_b, col_c = st.columns(3)
            add_sym = col_a.selectbox("Select Ticker", options=sorted(df['SYMBOL'].unique()))
            add_avg = col_b.number_input("Avg Purchase Price", min_value=0.01, step=0.01)
            add_qty = col_c.number_input("Quantity", min_value=1, step=1)
            if st.button("Add to Portfolio"):
                portfolio[add_sym] = {"price": add_avg, "qty": add_qty}
                save_portfolio(portfolio)
                st.rerun()

        if portfolio:
            p_rows = []
            t_inv, t_cur = 0.0, 0.0
            for s, info in portfolio.items():
                m_list = df[df['SYMBOL'] == s]
                if not m_list.empty:
                    m = m_list.iloc[0]
                    t_inv += (info['price'] * info['qty'])
                    t_cur += (m['PRICE'] * info['qty'])
                    p_rows.append({
                        "SYMBOL": s, "QTY": info['qty'], "AVG": info['price'], "CMP": m['PRICE'], 
                        "TARGET": m['TARGET'], "EXP %": m['EXP_PCT'], "RSI": m['RSI'],
                        "VERDICT": m['VERDICT'], "STOP LOSS": m['STOP-LOSS'], "SECTOR": m['SECTOR']
                    })
            
            if p_rows:
                p_df = pd.DataFrame(p_rows)
                # Summary Header
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("Invested", f"₹{t_inv:,.2f}")
                s2.metric("Current", f"₹{t_cur:,.2f}")
                p_amt = t_cur - t_inv
                p_pct = (p_amt / t_inv * 100) if t_inv > 0 else 0
                s3.metric("P&L", f"₹{p_amt:,.2f}", delta=f"{p_pct:.2f}%")
                s4.metric("Holdings", len(portfolio))

                # Styled Dataframe
                def color_verdict(val):
                    color = '#ff4b4b' if 'EXIT' in val else ('#4CAF50' if 'BUY' in val or 'ALPHA' in val else '#BDBDBD')
                    return f'color: {color}'
                
                st.dataframe(p_df.style.applymap(color_verdict, subset=['VERDICT']).format(precision=2), use_container_width=True, hide_index=True)

                st.divider()
                st.subheader("🚪 Exit Position")
                col_ex1, col_ex2 = st.columns(2)
                exit_sym = col_ex1.selectbox("Ticker to Exit", options=list(portfolio.keys()))
                exit_qty = col_ex2.number_input("Quantity to Sell", min_value=1, max_value=portfolio[exit_sym]['qty'], step=1)
                
                if st.button("Confirm Exit"):
                    m_data = df[df['SYMBOL'] == exit_sym].iloc[0]
                    # Log to History
                    new_h = pd.DataFrame([{
                        "SYMBOL": exit_sym, "BUY_PRICE": portfolio[exit_sym]['price'], 
                        "SELL_PRICE": m_data['PRICE'], "QTY": exit_qty,
                        "P&L_%": round(((m_data['PRICE'] - portfolio[exit_sym]['price']) / portfolio[exit_sym]['price']) * 100, 2),
                        "DATE": str(datetime.date.today())
                    }])
                    new_h.to_csv("trade_history.csv", mode='a', header=not os.path.exists("trade_history.csv"), index=False)
                    
                    # Update JSON
                    if exit_qty >= portfolio[exit_sym]['qty']:
                        del portfolio[exit_sym]
                    else:
                        portfolio[exit_sym]['qty'] -= exit_qty
                    
                    save_portfolio(portfolio)
                    st.success(f"Exited {exit_qty} shares of {exit_sym} at {m_data['PRICE']:.2f}")
                    st.rerun()
        else:
            st.info("Portfolio is empty.")

    # --- TAB 3: ACTIONABLES ---
    with tabs[2]:
        if not p_df.empty:
            st.subheader("📋 Portfolio-Based Actions")
            for _, row in p_df.iterrows():
                if "EXIT" in row['VERDICT']:
                    st.markdown(f'<div class="sell-pointer">🚨 <b>{row["SYMBOL"]}</b>: Overbought RSI ({row["RSI"]:.2f}). Book profits now.</div>', unsafe_allow_html=True)
                if row['CMP'] < row['STOP LOSS']:
                    st.markdown(f'<div class="sell-pointer">⚠️ <b>{row["SYMBOL"]}</b>: Below Stop Loss ({row["STOP LOSS"]:.2f}). Consider exiting.</div>', unsafe_allow_html=True)
        
        st.divider()
        st.subheader("🎯 Market Top Picks (Pointer Mode)")
        recoms = df[df['VERDICT'] == "💎 ALPHA"].sort_values("EXP_PCT", ascending=False).head(5)
        for _, r in recoms.iterrows():
            st.markdown(f"""
                <div class="buy-pointer">
                    <b>{r['SYMBOL']}</b> | CMP: ₹{r['PRICE']:.2f} | <b>Target: ₹{r['TARGET']:.2f}</b><br>
                    Verdict: {r['VERDICT']} | Expected: {r['EXP_PCT']:.2f}% | Score: {r['SCORE']:.2f}
                </div>
            """, unsafe_allow_html=True)

    # --- TAB 4: SUCCESS RATE ---
    with tabs[3]:
        st.subheader("📈 Strategy Performance Tracking")
        if not history.empty:
            win_rate = (len(history[history['P&L_%'] > 0]) / len(history) * 100) if len(history) > 0 else 0
            avg_gain = history['P&L_%'].mean()
            
            c1, c2 = st.columns(2)
            c1.metric("Win Rate", f"{win_rate:.2f}%")
            c2.metric("Avg Return / Trade", f"{avg_gain:.2f}%")
            
            st.divider()
            st.dataframe(history.sort_values("DATE", ascending=False).style.format({"P&L_%": "{:.2f}%"}), use_container_width=True, hide_index=True)
        else:
            st.info("No trade history. Complete an exit in the Portfolio tab to see results.")

else:
    st.error("Engine failed to generate data. Check daily_analysis.csv.")
    
