import streamlit as st
import pandas as pd
import json, os

st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

# --- DATA HELPERS ---
def load_portfolio():
    if os.path.exists("portfolio.json"):
        with open("portfolio.json", "r") as f: return json.load(f)
    return {}

def save_portfolio(p):
    with open("portfolio.json", "w") as f: json.dump(p, f)

@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists("daily_analysis.csv") or not os.path.exists("tickers_enriched.csv"):
        return None, None
    return pd.read_csv("daily_analysis.csv"), pd.read_csv("tickers_enriched.csv")

data, meta = load_data()
portfolio = load_portfolio()

st.title("🎯 Quantum-Sentinel Pro")

# --- NAVIGATION ---
tab1, tab2, tab3 = st.tabs(["🚀 Strategy Screener", "💼 My Portfolio", "⚡ Daily Actionables"])

with tab1:
    if data is not None:
        st.subheader("High Conviction Breakout Scanner")
        c1, c2 = st.columns([1, 2])
        # Industry Filter (Merged from metadata)
        merged = data.merge(meta[['SYMBOL', 'SECTOR']], on='SYMBOL', how='left')
        industries = sorted(merged['SECTOR'].dropna().unique())
        selected_ind = c1.multiselect("Select Industries", industries)
        min_score = c2.slider("Min Strategy Rating", 1, 10, 7)
        
        filtered = merged[merged['SCORE'] >= min_score]
        if selected_ind:
            filtered = filtered[filtered['SECTOR'].isin(selected_ind)]
            
        st.dataframe(filtered.sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Data not ready. Please run the GitHub Engine.")

with tab2:
    st.subheader("Holdings & Performance")
    # Form to add to portfolio
    with st.expander("Update Holdings"):
        f1, f2, f3 = st.columns(3)
        s_name = f1.text_input("Symbol (e.g. INFOSYS)").upper().replace(".NS", "")
        s_buy = f2.number_input("Avg Buy Price", min_value=0.0)
        s_qty = f3.number_input("Quantity", min_value=0)
        if st.button("Update Portfolio"):
            if s_qty <= 0: portfolio.pop(s_name, None)
            else: portfolio[s_name] = {"price": s_buy, "qty": s_qty}
            save_portfolio(portfolio)
            st.rerun()

    if portfolio and data is not None:
        p_list = []
        for s, info in portfolio.items():
            row = data[data['SYMBOL'] == s]
            if not row.empty:
                r = row.iloc[0]
                p_and_l = (r['PRICE'] - info['price']) * info['qty']
                p_list.append({
                    "Stock": s, "Qty": info['qty'], "Buy Price": info['price'],
                    "Current": r['PRICE'], "P&L": round(p_and_l, 2),
                    "Target": r['TARGET'], "Hold Period": r['HOLD']
                })
        st.dataframe(pd.DataFrame(p_list), use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Smart Actionables")
    if portfolio and data is not None:
        for s in portfolio.keys():
            row = data[data['SYMBOL'] == s]
            if not row.empty:
                r = row.iloc[0]
                if r['PRICE'] >= r['TARGET']:
                    st.success(f"✅ **TARGET ACHIEVED**: {s} hit target of {r['TARGET']}. Consider booking profits.")
                if r['RSI'] > 75:
                    st.warning(f"🔥 **OVERBOUGHT**: {s} RSI is {r['RSI']}. High risk of cooling off.")
                if r['SCORE'] <= 4:
                    st.error(f"⚠️ **WEAKENING**: {s} strategy score dropped to {r['SCORE']}. Review stop-loss.")
    else:
        st.info("Add stocks to your portfolio to generate actionable signals.")
