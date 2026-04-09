import streamlit as st
import pandas as pd
import json, os, requests, base64

st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

# --- 1. DATA LOADING ENGINE (CRASH-PROOF) ---
@st.cache_data(ttl=600)
def load_data():
    analysis_df = None
    history_df = pd.DataFrame(columns=["SYMBOL", "SCORE", "PRICE", "TARGET", "DATE_SIGNAL", "HOLDING"])
    meta_df = None

    if os.path.exists("daily_analysis.csv"):
        analysis_df = pd.read_csv("daily_analysis.csv")
        if not analysis_df.empty:
            # 1. Ensure columns exist and fill missing values
            analysis_df['SCORE'] = analysis_df['SCORE'].fillna(0)
            
            # 2. Calculate Derived Columns
            analysis_df['STOP-LOSS'] = (analysis_df['PRICE'] * 0.95).round(2)
            analysis_df['POTENTIAL %'] = (((analysis_df['TARGET'] - analysis_df['PRICE']) / analysis_df['PRICE']) * 100).round(2)
            
            # 3. Risk-Reward Ratio
            risk = (analysis_df['PRICE'] - analysis_df['STOP-LOSS']).replace(0, 0.01)
            reward = (analysis_df['TARGET'] - analysis_df['PRICE'])
            analysis_df['RR_RATIO'] = (reward / risk).round(2)
    
    if os.path.exists("trade_history.csv"):
        history_df = pd.read_csv("trade_history.csv")
    
    if os.path.exists("tickers_enriched.csv"):
        meta_df = pd.read_csv("tickers_enriched.csv")
    
    return analysis_df, history_df, meta_df

def load_portfolio():
    if os.path.exists("portfolio.json"):
        try:
            with open("portfolio.json", "r") as f: return json.load(f)
        except: return {}
    return {}

def save_portfolio_sync(p):
    with open("portfolio.json", "w") as f:
        json.dump(p, f, indent=4)

# --- INITIALIZE ---
analysis, history, meta = load_data()
portfolio = load_portfolio()

def get_verdict(score, rr, rsi):
    # Strict Alpha: High Score + High RR + Strong Momentum
    if score >= 9 and rr >= 2.0 and rsi > 55: 
        return "💎 ALPHA BUY"
    # Strong Buy: High Score + Good RR
    if score >= 8 and rr >= 1.5: 
        return "🟢 STRONG BUY"
    if score >= 7: 
        return "🟢 BUY"
    if score < 5 or rsi > 75: 
        return "🔴 SELL/OVERBOUGHT"
    return "🟡 HOLD"

st.title("🛡️ Quantum-Sentinel Pro")

if analysis is not None:
    tabs = st.tabs(["🚀 Screener", "💼 Portfolio", "⚡ Actionables", "📊 Success Tracker"])

    # --- TAB 1: SCREENER ---
    with tabs[0]:
        # Merge metadata
        if meta is not None:
            merged = analysis.merge(meta[['SYMBOL', 'SECTOR']], on='SYMBOL', how='left')
        else:
            merged = analysis.copy()
            merged['SECTOR'] = "Unknown"

        # Sector Rankings
        sector_ranks = merged.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).round(2)
        with st.expander("📊 Industry Leaderboard", expanded=True):
            st.table(sector_ranks.head(3))
            if st.checkbox("See More"):
                st.table(sector_ranks.tail(-3))

        st.divider()
        c1, c2 = st.columns([3, 1])
        with c2: best_only = st.toggle("💎 RR > 1.5 & Score 8+")
        with c1: search = st.selectbox("🔍 Search", ["ALL"] + sorted(merged['SYMBOL'].tolist()))
        
        # Step-by-step filtering to avoid KeyError
        df_view = merged.copy()
        if best_only: 
            df_view = df_view[(df_view['SCORE'] >= 8) & (df_view['RR_RATIO'] >= 1.5)]
        if search != "ALL": 
            df_view = df_view[df_view['SYMBOL'] == search]
        
        # Add Verdict Column
        df_view['VERDICT'] = df_view.apply(lambda x: get_verdict(x['SCORE'], x['RR_RATIO']), axis=1)
        
        # FINAL SORTING (Done before column selection)
        df_view = df_view.sort_values(by="SCORE", ascending=False)
        
        # Select and Display
        display_cols = ["VERDICT", "SYMBOL", "PRICE", "STOP-LOSS", "TARGET", "RR_RATIO", "POTENTIAL %", "HOLDING", "SECTOR"]
        st.dataframe(df_view[display_cols], use_container_width=True, hide_index=True)

    # --- TAB 2: PORTFOLIO ---
    # --- UPDATED PORTFOLIO TAB ---
with tabs[1]:
    # 1. ADD NEW HOLDING SECTION (Unchanged)
    with st.expander("➕ Add New Stock to Portfolio"):
        ticker_list = sorted(meta['SYMBOL'].tolist()) if meta is not None else []
        f1, f2, f3 = st.columns(3)
        new_ticker = f1.selectbox("Select Ticker", options=[""] + ticker_list)
        new_price = f2.number_input("Avg Buy Price", min_value=0.0)
        new_qty = f3.number_input("Quantity", min_value=1)
        if st.button("💾 Save to Portfolio"):
            if new_ticker:
                portfolio[new_ticker] = {"price": new_price, "qty": new_qty}
                save_portfolio_sync(portfolio)
                st.rerun()

    st.divider()

    # 2. DISPLAY WITH SIGNAL LIGHTS
    if portfolio:
        p_list = []
        total_inv, total_cur = 0, 0
        for s, info in portfolio.items():
            match = analysis[analysis['SYMBOL'] == s]
            if not match.empty:
                r = match.iloc[0]
                val, cost = r['PRICE']*info['qty'], info['price']*info['qty']
                total_inv += cost; total_cur += val
                
                # Fetch RSI safely for the refined verdict
                stock_rsi = r.get('RSI', 50) 
                
                p_list.append({
                    "SIGNAL": get_verdict(r['SCORE'], r['RR_RATIO'], stock_rsi),
                    "Stock": s, 
                    "Qty": info['qty'], 
                    "Avg": round(info['price'], 2), 
                    "CMP": round(r['PRICE'], 2), 
                    "P&L": round(val-cost, 2), 
                    "SL": r['STOP-LOSS'], 
                    "TGT": r['TARGET'], 
                    "Potential": f"{r['POTENTIAL %']}%"
                })
        
        if p_list:
            # Metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Invested", f"₹{total_inv:,.0f}")
            m2.metric("Current Value", f"₹{total_cur:,.0f}", delta=f"₹{total_cur-total_inv:,.0f}")
            m3.metric("Net %", f"{((total_cur-total_inv)/total_inv)*100:.2f}%" if total_inv > 0 else "0%")
            
            # Display Table with Signals as the FIRST column
            st.dataframe(pd.DataFrame(p_list), use_container_width=True, hide_index=True)
        
        # 3. REMOVE HOLDING (Unchanged)
        with st.expander("🗑️ Remove Stock"):
            to_remove = st.selectbox("Select to Remove", list(portfolio.keys()))
            if st.button("Delete"):
                del portfolio[to_remove]
                save_portfolio_sync(portfolio)
                st.rerun()

    # --- TAB 3: ACTIONABLES ---
    with tabs[2]:
        st.subheader("Priority Alerts")
        if portfolio:
            for s, info in portfolio.items():
                r = analysis[analysis['SYMBOL'] == s].iloc[0]
                if r['PRICE'] <= r['STOP-LOSS']:
                    st.error(f"🚨 **STOP LOSS**: {s} hit {r['STOP-LOSS']}. Protective exit suggested.")
                elif r['PRICE'] >= r['TARGET']:
                    st.success(f"💰 **TARGET**: {s} hit {r['TARGET']}. Profit booking suggested.")

        st.divider()
        st.write("🚀 **Top 7 Alpha Opportunities**")
        top_7 = analysis[analysis['SCORE'] >= 8].sort_values("RR_RATIO", ascending=False).head(7)
        for _, pick in top_7.iterrows():
            st.info(f"**{pick['SYMBOL']}** | RR: {pick['RR_RATIO']} | Tgt: {pick['TARGET']} (+{pick['POTENTIAL %']}%)")

    # --- TAB 4: SUCCESS TRACKER ---
    with tabs[3]:
        st.subheader("Historical Win Rate")
        if not history.empty:
            wins = len(history[history['PRICE'] >= history['TARGET']])
            total = len(history)
            st.metric("System Accuracy", f"{(wins/total*100):.1f}%" if total > 0 else "0%")
            st.dataframe(history[['SYMBOL', 'DATE_SIGNAL', 'TARGET']].tail(10), use_container_width=True)
        else:
            st.info("Accuracy data will populate after 48 hours of automated runs.")
else:
    st.error("No analysis data found. Run your GitHub Action manually once.")
    
