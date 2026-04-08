import streamlit as st
import pandas as pd
import json, os, base64, requests

st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

# --- GITHUB SYNC SETTINGS ---
# Note: Ensure GH_TOKEN is in your Streamlit Secrets
GITHUB_REPO = "YourGitHubUsername/YourRepoName" 
PORTFOLIO_FILE = "portfolio.json"

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f: return json.load(f)
    return {}

def save_portfolio_to_github(p):
    """Saves portfolio locally and attempts to sync with GitHub."""
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(p, f, indent=4)
    
    token = st.secrets.get("GH_TOKEN")
    if token:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{PORTFOLIO_FILE}"
            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
            
            # Get current file SHA to update
            res = requests.get(url, headers=headers)
            sha = res.json().get("sha") if res.status_code == 200 else None
            
            content = base64.b64encode(json.dumps(p).encode()).decode()
            data = {"message": "Update portfolio via App", "content": content}
            if sha: data["sha"] = sha
            
            requests.put(url, headers=headers, json=data)
        except Exception as e:
            st.error(f"GitHub Sync Failed: {e}")

@st.cache_data(ttl=600)
def load_data():
    if not os.path.exists("daily_analysis.csv") or not os.path.exists("tickers_enriched.csv"):
        return None, None
    return pd.read_csv("daily_analysis.csv"), pd.read_csv("tickers_enriched.csv")

analysis, meta = load_data()
portfolio = load_portfolio()

# --- VERDICT LOGIC (Fixed & Icons Added) ---
def get_verdict(score):
    if score >= 8: return "🟢 STRONG BUY"
    if score >= 7: return "🟢 BUY"
    if score >= 5: return "🟡 HOLD"
    return "🔴 AVOID"

# --- UI LAYOUT ---
st.title("🎯 Quantum-Sentinel Pro")

tab1, tab2, tab3 = st.tabs(["🚀 Strategy Screener", "💼 My Portfolio", "⚡ Actionables"])

with tab1:
    if analysis is not None:
        merged = analysis.merge(meta[['SYMBOL', 'SECTOR']], on='SYMBOL', how='left')
        merged.insert(0, "VERDICT", merged['SCORE'].apply(get_verdict))
        
        # --- IMPROVED SEARCH & SORT ---
        c1, c2, c3 = st.columns([2, 2, 2])
        
        # 1. Searchable Dropdown for Quick Search
        search_list = ["ALL STOCKS"] + sorted(merged['SYMBOL'].unique().tolist())
        selected_stock = c1.selectbox("🔍 Search & Inspect Stock", options=search_list)
        
        selected_ind = c2.multiselect("Filter Industry", sorted(merged['SECTOR'].dropna().unique()))
        min_score = c3.slider("Min Strategy Score", 1, 10, 5)

        # Filtering Logic
        filtered = merged[merged['SCORE'] >= min_score]
        if selected_ind:
            filtered = filtered[filtered['SECTOR'].isin(selected_ind)]
        if selected_stock != "ALL STOCKS":
            filtered = filtered[filtered['SYMBOL'] == selected_stock]

        # Final Sorted Output
        st.dataframe(
            filtered.sort_values(by="SCORE", ascending=False), 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.warning("Data files missing. Run GitHub Action.")

with tab2:
    st.subheader("Holdings Management")
    all_symbols = sorted(meta['SYMBOL'].tolist()) if meta is not None else []
    
    # --- SEARCHABLE DROPDOWN FOR PORTFOLIO ---
    with st.expander("📝 Add/Edit Holdings", expanded=not bool(portfolio)):
        f1, f2, f3 = st.columns(3)
        pick = f1.selectbox("Pick Stock", options=[""] + all_symbols, help="Type to search your stock")
        buy_p = f2.number_input("Avg Price", min_value=0.0, step=0.1)
        qty = f3.number_input("Quantity", min_value=0, step=1)
        
        if st.button("💾 Save to Portfolio & GitHub"):
            if pick:
                if qty <= 0: portfolio.pop(pick, None)
                else: portfolio[pick] = {"price": buy_p, "qty": qty}
                save_portfolio_to_github(portfolio)
                st.success(f"Updated {pick} successfully!")
                st.rerun()

    # Portfolio Performance Table
    if portfolio and analysis is not None:
        p_rows = []
        for sym, info in portfolio.items():
            match = analysis[analysis['SYMBOL'] == sym]
            if not match.empty:
                r = match.iloc[0]
                cur_val = r['PRICE'] * info['qty']
                buy_val = info['price'] * info['qty']
                pl = cur_val - buy_val
                p_rows.append({
                    "Verdict": get_verdict(r['SCORE']),
                    "Stock": sym, "Qty": info['qty'], "Buy": info['price'],
                    "Current": r['PRICE'], "P&L": round(pl, 2), "P&L %": round((pl/buy_val)*100, 2) if buy_val else 0,
                    "Target": r['TARGET']
                })
        
        df_p = pd.DataFrame(p_rows)
        # Dynamic Sorting: Highest P&L first
        st.dataframe(
            df_p.sort_values("P&L", ascending=False).style.applymap(
                lambda x: 'color: #00ff00' if x > 0 else 'color: #ff4b4b', subset=['P&L', 'P&L %']
            ), 
            use_container_width=True
        )

with tab3:
    st.subheader("Priority Alerts")
    if portfolio and analysis is not None:
        for sym in portfolio.keys():
            r = analysis[analysis['SYMBOL'] == sym]
            if not r.empty:
                stock = r.iloc[0]
                if stock['PRICE'] >= stock['TARGET']:
                    st.success(f"💰 **EXIT**: {sym} hit Target ({stock['TARGET']}). Book profits!")
                if stock['RSI'] > 75:
                    st.warning(f"🔥 **CAUTION**: {sym} is Overbought (RSI: {stock['RSI']}).")
                if stock['SCORE'] >= 8:
                    st.info(f"🚀 **BOOMING**: {sym} has a high score of {stock['SCORE']}.")
    else:
        st.info("Add stocks to your portfolio to activate smart signals.")
        
