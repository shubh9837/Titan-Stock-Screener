import streamlit as st
import pandas as pd
import json, os, datetime

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #0d1117; }
    
    /* Metrics & Cards */
    div[data-testid="stMetric"] { background-color: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 12px !important; }
    .titan-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 15px; }
    
    /* Status Pointers */
    .buy-pointer { border-left: 5px solid #238636; background: rgba(35, 134, 54, 0.05); padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    .sell-pointer { border-left: 5px solid #da3633; background: rgba(218, 54, 51, 0.05); padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    
    /* Alpha Picks Grid */
    .alpha-box { background: #1c2128; border: 1px solid #238636; border-radius: 8px; padding: 10px; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=600)
def load_all_data():
    if not os.path.exists("daily_analysis.csv"): return None, pd.DataFrame()
    df = pd.read_csv("daily_analysis.csv")
    df['STOP-LOSS'] = (df['PRICE'] * 0.95).round(2)
    df['EXP_PCT'] = (((df['TARGET'] - df['PRICE']) / df['PRICE']) * 100).round(2)
    df['VERDICT'] = df.apply(lambda r: "💎 ALPHA" if r['SCORE'] >= 8 else "🟢 BUY" if r['SCORE'] >= 6 else "🟡 HOLD", axis=1)
    df.loc[df['RSI'] > 78, 'VERDICT'] = "🔴 EXIT"
    hist = pd.read_csv("trade_history.csv") if os.path.exists("trade_history.csv") else pd.DataFrame()
    return df, hist

df, history = load_all_data()

# Load Portfolio
portfolio = {}
if os.path.exists("portfolio.json"):
    with open("portfolio.json", "r") as f:
        try: portfolio = json.load(f)
        except: portfolio = {}

def save_portfolio(p):
    with open("portfolio.json", "w") as f:
        json.dump(p, f)

if df is not None:
    tabs = st.tabs(["🔍 SCREENER", "💼 PORTFOLIO", "⚡ ACTIONABLES", "🏆 SUCCESS"])

    # --- TAB 1: SCREENER ---
    with tabs[0]:
        ind_stats = df.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).reset_index()
        selected_ind = st.selectbox("📂 Filter by Industry:", ["All"] + list(ind_stats['SECTOR']))
        
        st.markdown("### 🔥 High-Conviction Alpha Picks")
        top_picks = df[df['SCORE'] >= 9].sort_values("EXP_PCT", ascending=False).head(4)
        if not top_picks.empty:
            cols = st.columns(4)
            for i, (_, row) in enumerate(top_picks.iterrows()):
                with cols[i]:
                    st.markdown(f'<div class="alpha-box"><span style="color:#8b949e; font-size:0.8rem;">{row["SYMBOL"]}</span><br><b style="color:#4CAF50;">₹{row["PRICE"]:.2f}</b><br><small style="color:#58a6ff;">Score: {row["SCORE"]}</small></div>', unsafe_allow_html=True)
        
        st.divider()
        search = st.text_input("🔍 Search Ticker", placeholder="Enter symbol...")
        v_df = df.copy()
        if selected_ind != "All": v_df = v_df[v_df['SECTOR'] == selected_ind]
        if search: v_df = v_df[v_df['SYMBOL'].str.contains(search.upper())]
        st.dataframe(v_df.sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)

    # --- TAB 2: PORTFOLIO (FULL FUNCTIONALITY) ---
    with tabs[1]:
        p_col_data, p_col_mgt = st.columns([2.5, 1])
        
        with p_col_data:
            st.markdown("### 📋 Current Holdings")
            if portfolio:
                p_list = []
                total_inv, total_val = 0.0, 0.0
                for sym, data in portfolio.items():
                    m_row = df[df['SYMBOL'] == sym]
                    if not m_row.empty:
                        m = m_row.iloc[0]
                        cur_val = m['PRICE'] * data['qty']
                        inv_val = data['price'] * data['qty']
                        total_inv += inv_val
                        total_val += cur_val
                        p_list.append({
                            "TICKER": sym, "QTY": data['qty'], "AVG": f"₹{data['price']:.2f}", 
                            "CMP": f"₹{m['PRICE']:.2f}", "P&L": f"{((m['PRICE']-data['price'])/data['price']*100):.2f}%",
                            "VERDICT": m['VERDICT'], "STOP LOSS": m['STOP-LOSS'], "RSI": m['RSI']
                        })
                
                # Summary Header
                m1, m2, m3 = st.columns(3)
                m1.metric("💰 Invested", f"₹{total_inv:,.2f}")
                m2.metric("🏦 Value", f"₹{total_val:,.2f}", delta=f"₹{total_val-total_inv:,.2f}")
                p_pct = ((total_val-total_inv)/total_inv*100) if total_inv > 0 else 0
                m3.metric("📈 Net Return", f"{p_pct:.2f}%")
                
                st.dataframe(pd.DataFrame(p_list), use_container_width=True, hide_index=True)
            else:
                st.info("Your portfolio is currently empty. Add stocks using the panel on the right. ➡️")

        with p_col_mgt:
            st.markdown("### ⚙️ Management")
            with st.expander("📥 Add Stock", expanded=not portfolio):
                add_sym = st.selectbox("Ticker", sorted(df['SYMBOL'].unique()), key="add_s")
                add_prc = st.number_input("Purchase Price", step=0.1, key="add_p")
                add_qty = st.number_input("Quantity", min_value=1, step=1, key="add_q")
                if st.button("➕ Confirm Addition"):
                    portfolio[add_sym] = {"price": add_prc, "qty": add_qty}
                    save_portfolio(portfolio)
                    st.success(f"Added {add_sym}")
                    st.rerun()

            if portfolio:
                with st.expander("📤 Exit Position"):
                    ex_sym = st.selectbox("Ticker to Sell", list(portfolio.keys()), key="ex_s")
                    ex_qty = st.number_input("Sell Qty", min_value=1, max_value=portfolio[ex_sym]['qty'], step=1)
                    if st.button("⛔ Confirm Exit"):
                        m_data = df[df['SYMBOL'] == ex_sym].iloc[0]
                        # Log to History
                        new_h = pd.DataFrame([{
                            "SYMBOL": ex_sym, "BUY": portfolio[ex_sym]['price'], "SELL": m_data['PRICE'],
                            "QTY": ex_qty, "P&L_%": round(((m_data['PRICE'] - portfolio[ex_sym]['price']) / portfolio[ex_sym]['price']) * 100, 2),
                            "DATE": str(datetime.date.today())
                        }])
                        new_h.to_csv("trade_history.csv", mode='a', header=not os.path.exists("trade_history.csv"), index=False)
                        
                        # Update Portfolio
                        if ex_qty >= portfolio[ex_sym]['qty']: del portfolio[ex_sym]
                        else: portfolio[ex_sym]['qty'] -= ex_qty
                        save_portfolio(portfolio)
                        st.rerun()

    # --- TAB 3: ACTIONABLES ---
    with tabs[2]:
        st.markdown("### ⚡ Critical Actions")
        if portfolio:
            for s, d in portfolio.items():
                m = df[df['SYMBOL'] == s].iloc[0]
                if "EXIT" in m['VERDICT'] or m['PRICE'] < m['STOP-LOSS']:
                    st.markdown(f'<div class="sell-pointer">🚨 <b>{s}</b>: Action Required. RSI: {m["RSI"]} | SL: ₹{m["STOP-LOSS"]}</div>', unsafe_allow_html=True)
        
        st.markdown("#### 💎 High Conviction Buy Suggestions")
        for _, r in top_picks.iterrows():
            st.markdown(f'<div class="buy-pointer">✅ <b>{r["SYMBOL"]}</b>: Score {r["SCORE"]} | Target: ₹{r["TARGET"]}</div>', unsafe_allow_html=True)

    # --- TAB 4: SUCCESS ---
    with tabs[3]:
        if not history.empty:
            st.metric("🎯 Accuracy", f"{(len(history[history['P&L_%'] > 0])/len(history)*100):.2f}%")
            st.dataframe(history.sort_values("DATE", ascending=False), use_container_width=True, hide_index=True)
else:
    st.error("Engine data not found.")
    
