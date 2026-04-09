import streamlit as st
import pandas as pd
import json, os, datetime

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

st.markdown("""
    <style>
    h1 { font-size: 1.6rem !important; color: #E0E0E0; }
    h2 { font-size: 1.2rem !important; color: #BDBDBD; }
    .stMetric { background-color: #1e2130; border-radius: 8px; padding: 10px !important; border: 1px solid #3e4452; }
    .stDataFrame td, .stDataFrame th { font-size: 0.85rem !important; }
    .buy-pointer { background-color: #1a2e1a; padding: 10px; border-radius: 5px; margin-bottom: 5px; border-left: 5px solid #4CAF50; }
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

def load_portfolio():
    if os.path.exists("portfolio.json"):
        with open("portfolio.json", "r") as f: return json.load(f)
    return {}

df, history = load_all_data()
portfolio = load_portfolio()

if df is not None:
    tabs = st.tabs(["🚀 Screener", "💼 Portfolio", "⚡ Actionables", "📊 Success Rate"])

    # --- TAB 1: SCREENER ---
    with tabs[0]:
        # Industry Dropdown (Sorted)
        ind_stats = df.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).round(2)
        with st.expander("📊 View Industry Strength (Ranked)"):
            st.dataframe(ind_stats, use_container_width=True)

        # Top Picks Button
        if st.button("🔥 Suggest Top Picks Immediately"):
            top_picks = df[df['VERDICT'] == "💎 ALPHA"].sort_values("SCORE", ascending=False).head(5)
            st.table(top_picks[["SYMBOL", "PRICE", "EXP_PCT", "SCORE"]])

        st.divider()
        c1, c2, c3 = st.columns([2, 1, 1])
        f_ind = c1.multiselect("Filter Industry", options=sorted(df['SECTOR'].unique()))
        f_score = c2.slider("Min Score", 0, 10, 5)
        f_search = c3.text_input("🔍 Search Stock")
        
        v_df = df.copy()
        if f_ind: v_df = v_df[v_df['SECTOR'].isin(f_ind)]
        if f_search: v_df = v_df[v_df['SYMBOL'].str.contains(f_search.upper())]
        v_df = v_df[v_df['SCORE'] >= f_score]
        
        st.dataframe(v_df[["SYMBOL", "VERDICT", "SCORE", "PRICE", "TARGET", "STOP-LOSS", "EXP_PCT", "SECTOR", "RSI"]].sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)

    # --- TAB 2: PORTFOLIO ---
    with tabs[1]:
        st.subheader("Add Stock")
        with st.expander("➕ New Entry"):
            a1, a2, a3 = st.columns(3)
            new_sym = a1.selectbox("Symbol", df['SYMBOL'].unique())
            new_prc = a2.number_input("Avg Price", step=0.01)
            new_qty = a3.number_input("Quantity", step=1)
            if st.button("Add to Portfolio"):
                portfolio[new_sym] = {"price": new_prc, "qty": new_qty}
                with open("portfolio.json", "w") as f: json.dump(portfolio, f)
                st.rerun()

        if portfolio:
            p_rows = []
            for s, info in portfolio.items():
                m = df[df['SYMBOL'] == s].iloc[0] if s in df['SYMBOL'].values else None
                if m is not None:
                    p_rows.append({
                        "SYMBOL": s, "CMP": f"{m['PRICE']:.2f}", "AVG": f"{info['price']:.2f}", 
                        "QTY": info['qty'], "TARGET": f"{m['TARGET']:.2f}", "EXP %": f"{m['EXP_PCT']:.2f}%",
                        "RSI": f"{m['RSI']:.2f}", "VERDICT": m['VERDICT'], "STOP LOSS": f"{m['STOP-LOSS']:.2f}"
                    })
            st.dataframe(pd.DataFrame(p_rows), use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("Exit Stock")
            e1, e2 = st.columns(2)
            exit_sym = e1.selectbox("Select to Exit", list(portfolio.keys()))
            exit_qty = e2.number_input("Qty to Exit", min_value=1, max_value=portfolio[exit_sym]['qty'] if exit_sym in portfolio else 1)
            
            if st.button("Confirm Partial/Full Exit"):
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
                if exit_qty >= portfolio[exit_sym]['qty']: del portfolio[exit_sym]
                else: portfolio[exit_sym]['qty'] -= exit_qty
                
                with open("portfolio.json", "w") as f: json.dump(portfolio, f)
                st.success(f"Exited {exit_qty} shares of {exit_sym}")
                st.rerun()

    # --- TAB 3: ACTIONABLES ---
    with tabs[2]:
        st.subheader("⚡ Portfolio Actions")
        for s, info in portfolio.items():
            m = df[df['SYMBOL'] == s].iloc[0] if s in df['SYMBOL'].values else None
            if m is not None:
                if "EXIT" in m['VERDICT']:
                    st.error(f"🚨 **BOOK PROFITS on {s}**: RSI is {m['RSI']:.2f} (Overbought). Target was {m['TARGET']:.2f}")
                elif m['PRICE'] <= m['STOP-LOSS']:
                    st.warning(f"⚠️ **STOP LOSS on {s}**: Price {m['PRICE']:.2f} below SL {m['STOP-LOSS']:.2f}")

        st.divider()
        st.subheader("🎯 Top Buy Recommendations")
        recoms = df[df['VERDICT'] == "💎 ALPHA"].sort_values("EXP_PCT", ascending=False).head(5)
        for _, row in recoms.iterrows():
            st.markdown(f"""
                <div class="buy-pointer">
                    <b>{row['SYMBOL']}</b> | CMP: ₹{row['PRICE']:.2f} | <b>Target: ₹{row['TARGET']:.2f}</b> | 
                    Expected: {row['EXP_PCT']:.2f}% | Verdict: {row['VERDICT']}
                </div>
            """, unsafe_allow_html=True)

    # --- TAB 4: SUCCESS RATE ---
    with tabs[3]:
        if not history.empty:
            st.metric("Total Profit/Loss %", f"{history['P&L_%'].mean():.2f}%")
            st.dataframe(history.tail(20), use_container_width=True)
        else:
            st.info("Exit trades in the Portfolio tab to track success.")
        
