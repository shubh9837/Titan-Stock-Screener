import streamlit as st
import pandas as pd
import json, os, requests, base64

st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

# --- GITHUB SYNC CONFIG ---
# Replace with your details
GITHUB_REPO = "your-username/your-repo-name" 
GITHUB_TOKEN = st.secrets.get("GH_TOKEN") # Add this to Streamlit Secrets

def load_portfolio():
    if os.path.exists("portfolio.json"):
        with open("portfolio.json", "r") as f: return json.load(f)
    return {}

def save_portfolio(p):
    with open("portfolio.json", "w") as f: json.dump(p, f)
    # Optional: Logic to push portfolio.json to GitHub can be added here 
    # if st.secrets are configured.

@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists("daily_analysis.csv") or not os.path.exists("tickers_enriched.csv"):
        return None, None
    return pd.read_csv("daily_analysis.csv"), pd.read_csv("tickers_enriched.csv")

data, meta = load_data()
portfolio = load_portfolio()

# --- UI HEADER ---
st.title("🛡️ Quantum-Sentinel Pro")

tab1, tab2, tab3 = st.tabs(["🚀 Strategy Screener", "💼 My Portfolio", "⚡ Daily Actionables"])

with tab1:
    if data is not None:
        # Merge for sector info
        merged = data.merge(meta[['SYMBOL', 'SECTOR']], on='SYMBOL', how='left')
        
        # UI Filters
        c1, c2, c3 = st.columns([1, 1, 2])
        search_query = c1.text_input("🔍 Quick Search Stock", "").upper()
        selected_ind = c2.multiselect("Industry", sorted(merged['SECTOR'].dropna().unique()))
        min_score = c3.slider("Min Strategy Rating", 1, 10, 7)
        
        # Apply Logic Icons
        def get_verdict(score):
            if score >= 8: return "🟢 STRONG BUY"
            if score >= 7: return "🟢 BUY"
            if score >= 5: return "🟡 HOLD"
            return "🔴 AVOID"

        merged.insert(0, "VERDICT", merged['SCORE'].apply(get_verdict))
        
        # Filtering & Sorting
        filtered = merged[merged['SCORE'] >= min_score]
        if selected_ind: filtered = filtered[filtered['SECTOR'].isin(selected_ind)]
        if search_query: filtered = filtered[filtered['SYMBOL'].str.contains(search_query)]
        
        st.dataframe(
            filtered.sort_values(by=["SCORE", "MOVE_PCT"], ascending=False), 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.warning("⚠️ Market data not found. Please run GitHub Action.")

with tab2:
    st.subheader("Manage Holdings")
    
    # Searchable Dropdown for adding stocks
    all_tickers = sorted(meta['SYMBOL'].tolist()) if meta is not None else []
    
    with st.expander("➕ Add / Update Stock"):
        f1, f2, f3 = st.columns(3)
        s_selected = f1.selectbox("Select Stock", options=[""] + all_tickers)
        s_buy = f2.number_input("Avg Buy Price", min_value=0.0)
        s_qty = f3.number_input("Quantity", min_value=0)
        
        if st.button("Update Portfolio"):
            if s_selected:
                if s_qty <= 0: portfolio.pop(s_selected, None)
                else: portfolio[s_selected] = {"price": s_buy, "qty": s_qty}
                save_portfolio(portfolio)
                st.success(f"Updated {s_selected}")
                st.rerun()

    # Portfolio Display
    if portfolio and data is not None:
        p_list = []
        for s, info in portfolio.items():
            row = data[data['SYMBOL'] == s]
            if not row.empty:
                r = row.iloc[0]
                gain = (r['PRICE'] - info['price']) * info['qty']
                p_list.append({
                    "Verdict": get_verdict(r['SCORE']),
                    "Stock": s, "Qty": info['qty'], "Buy Price": info['price'],
                    "Current": r['PRICE'], "P&L": round(gain, 2),
                    "Target": r['TARGET'], "Potential": f"{r['MOVE_PCT']}%"
                })
        
        df_p = pd.DataFrame(p_list)
        if not df_p.empty:
            # Color coding P&L
            st.dataframe(df_p.style.applymap(lambda x: 'color: green' if x > 0 else 'color: red', subset=['P&L']), use_container_width=True)
            
            total_pl = df_p['P&L'].sum()
            st.metric("Total Portfolio P&L", f"₹{total_pl:,.2f}", delta=f"{total_pl}")

with tab3:
    st.subheader("Smart Actionables")
    if portfolio and data is not None:
        for s in portfolio.keys():
            row = data[data['SYMBOL'] == s]
            if not row.empty:
                r = row.iloc[0]
                # High-Value Signals
                if r['PRICE'] >= r['TARGET']:
                    st.success(f"💰 **EXIT SIGNAL**: {s} hit target {r['TARGET']}. Book Profits!")
                elif r['RSI'] > 80:
                    st.warning(f"⚠️ **OVERBOUGHT**: {s} RSI is {r['RSI']}. Reversal risk high.")
                elif r['SCORE'] >= 8:
                    st.info(f"🚀 **ACCELERATION**: {s} has a score of {r['SCORE']}. Strong momentum.")
    else:
        st.info("Your portfolio is empty. Add stocks to see automated signals.")
