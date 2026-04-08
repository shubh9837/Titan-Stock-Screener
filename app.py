import streamlit as st
import pandas as pd
import json, os, base64, requests

st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

# --- 1. CONFIGURATION (REQUIRED FOR GITHUB SYNC) ---
# Update these with your specific details
GITHUB_REPO = "your-github-username/your-repo-name" 
PORTFOLIO_FILE = "portfolio.json"

# --- 2. DATA LOADERS ---
def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_portfolio_sync(p):
    """Saves portfolio locally and attempts to push to GitHub."""
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(p, f, indent=4)
    
    # Push to GitHub if Secret is present
    token = st.secrets.get("GH_TOKEN")
    if token:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{PORTFOLIO_FILE}"
            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
            
            # Get current file SHA to update correctly
            res = requests.get(url, headers=headers)
            sha = res.json().get("sha") if res.status_code == 200 else None
            
            content_encoded = base64.b64encode(json.dumps(p).encode()).decode()
            data = {"message": "Update portfolio from App", "content": content_encoded}
            if sha: data["sha"] = sha
            
            requests.put(url, headers=headers, json=data)
        except Exception as e:
            st.sidebar.error(f"GitHub Sync Error: {e}")

@st.cache_data(ttl=600)
def load_market_data():
    if not os.path.exists("daily_analysis.csv") or not os.path.exists("tickers_enriched.csv"):
        return None, None
    return pd.read_csv("daily_analysis.csv"), pd.read_csv("tickers_enriched.csv")

# Initialize Data
analysis, meta = load_market_data()
portfolio = load_portfolio()

# --- 3. UI HELPERS ---
def get_verdict_style(score):
    if score >= 8: return "🟢 STRONG BUY"
    if score >= 7: return "🟢 BUY"
    if score >= 5: return "🟡 HOLD"
    return "🔴 AVOID"

# --- 4. DASHBOARD TABS ---
st.title("🛡️ Quantum-Sentinel Pro")

tab1, tab2, tab3 = st.tabs(["🚀 Strategy Screener", "💼 My Portfolio", "⚡ Actionables"])

with tab1:
    if analysis is not None:
        # Merge Metadata
        merged = analysis.merge(meta[['SYMBOL', 'SECTOR']], on='SYMBOL', how='left')
        merged.insert(0, "VERDICT", merged['SCORE'].apply(get_verdict_style))
        
        # --- UI SEARCH & FILTERS ---
        c1, c2, c3 = st.columns([2, 1, 1])
        
        # This acts as your suggestion-based quick search
        search_options = ["ALL STOCKS"] + sorted(merged['SYMBOL'].tolist())
        search_stock = c1.selectbox("🔍 Instant Stock Lookup (Type name to search)", options=search_options)
        
        selected_sector = c2.multiselect("Industry", sorted(merged['SECTOR'].dropna().unique()))
        min_rate = c3.slider("Min Rating", 1, 10, 5)
        
        # Filtering logic
        df_view = merged.copy()
        if search_stock != "ALL STOCKS":
            df_view = df_view[df_view['SYMBOL'] == search_stock]
        if selected_sector:
            df_view = df_view[df_view['SECTOR'].isin(selected_sector)]
        df_view = df_view[df_view['SCORE'] >= min_rate]

        # Final Sorting: Best suggested at the top
        st.dataframe(df_view.sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.error("Market data missing. Please check your GitHub Actions.")

with tab2:
    st.subheader("Manage Portfolio")
    
    # SEARCHABLE DROPDOWN for adding/updating
    all_symbols = sorted(meta['SYMBOL'].tolist()) if meta is not None else []
    
    with st.expander("📝 Add/Update Stock to Portfolio"):
        f1, f2, f3 = st.columns(3)
        pick = f1.selectbox("Select Ticker", options=[""] + all_symbols, placeholder="Type symbol...")
        buy_price = f2.number_input("Avg Buy Price", min_value=0.0)
        quantity = f3.number_input("Quantity", min_value=0)
        
        if st.button("💾 Save Changes"):
            if pick:
                if quantity <= 0: portfolio.pop(pick, None)
                else: portfolio[pick] = {"price": buy_price, "qty": quantity}
                save_portfolio_sync(portfolio)
                st.success(f"Updated {pick} in local storage and GitHub.")
                st.rerun()

    # Portfolio Summary Table
    if portfolio and analysis is not None:
        p_data = []
        for s, info in portfolio.items():
            row = analysis[analysis['SYMBOL'] == s]
            if not row.empty:
                r = row.iloc[0]
                total_gain = (r['PRICE'] - info['price']) * info['qty']
                p_data.append({
                    "Verdict": get_verdict_style(r['SCORE']),
                    "Stock": s, "Qty": info['qty'], "Avg Price": info['price'],
                    "Current": r['PRICE'], "P&L": round(total_gain, 2),
                    "Target": r['TARGET'], "Potential": f"{r['MOVE_PCT']}%"
                })
        
        df_p = pd.DataFrame(p_data)
        if not df_p.empty:
            # FIX: Using .map for compatibility with newer Pandas and handling errors
            def color_pl(val):
                color = '#00ff00' if val > 0 else '#ff4b4b'
                return f'color: {color}'

            try:
                # Use .map (Pandas 2.1+) or fallback to .applymap
                styler = df_p.sort_values("P&L", ascending=False).style
                if hasattr(styler, "map"): styled_df = styler.map(color_pl, subset=['P&L'])
                else: styled_df = styler.applymap(color_pl, subset=['P&L'])
                
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
            except:
                st.dataframe(df_p, use_container_width=True, hide_index=True)
            
            total_net = df_p['P&L'].sum()
            st.metric("Total Net Profit/Loss", f"₹{total_net:,.2f}", delta=f"{total_net:,.2f}")

with tab3:
    st.subheader("Actionable Alerts")
    if portfolio and analysis is not None:
        for s in portfolio.keys():
            row = analysis[analysis['SYMBOL'] == s]
            if not row.empty:
                r = row.iloc[0]
                if r['PRICE'] >= r['TARGET']:
                    st.success(f"💰 **EXIT SIGNAL**: {s} hit target {r['TARGET']}.")
                elif r['RSI'] > 78:
                    st.warning(f"⚠️ **OVERBOUGHT**: {s} is exhausted (RSI: {r['RSI']}).")
                elif r['SCORE'] >= 8:
                    st.info(f"🚀 **HOLD STRONG**: {s} has high conviction score {r['SCORE']}.")
    else:
        st.info("Portfolio empty.")
        
