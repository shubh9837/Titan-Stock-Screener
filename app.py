import streamlit as st
import pandas as pd
import json, os, requests, base64

st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

# --- 1. DEFENSIVE DATA LOADER ---
@st.cache_data(ttl=600)
def load_data():
    analysis_df = None
    history_df = pd.DataFrame(columns=["SYMBOL", "SCORE", "PRICE", "TARGET", "DATE_SIGNAL", "HOLDING"])
    meta_df = pd.DataFrame(columns=["SYMBOL", "SECTOR"]) # Default empty frame

    if os.path.exists("daily_analysis.csv"):
        try:
            analysis_df = pd.read_csv("daily_analysis.csv")
            if not analysis_df.empty:
                # Ensure all required columns exist to avoid KeyErrors
                for col in ['PRICE', 'TARGET', 'SCORE']:
                    if col not in analysis_df.columns:
                        analysis_df[col] = 0
                
                analysis_df['SCORE'] = pd.to_numeric(analysis_df['SCORE'], errors='coerce').fillna(0)
                analysis_df['STOP-LOSS'] = (analysis_df['PRICE'] * 0.95).round(2)
                analysis_df['POTENTIAL %'] = (((analysis_df['TARGET'] - analysis_df['PRICE']) / analysis_df['PRICE'].replace(0, 1)) * 100).round(2)
                
                risk = (analysis_df['PRICE'] - analysis_df['STOP-LOSS']).replace(0, 0.01)
                reward = (analysis_df['TARGET'] - analysis_df['PRICE'])
                analysis_df['RR_RATIO'] = (reward / risk).round(2)
        except Exception as e:
            st.error(f"Error loading daily_analysis: {e}")

    if os.path.exists("trade_history.csv"):
        try: history_df = pd.read_csv("trade_history.csv")
        except: pass
    
    if os.path.exists("tickers_enriched.csv"):
        try: meta_df = pd.read_csv("tickers_enriched.csv")
        except: pass
    
    return analysis_df, history_df, meta_df

def load_portfolio():
    if os.path.exists("portfolio.json"):
        try:
            with open("portfolio.json", "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except: return {}
    return {}

def save_portfolio_sync(p):
    try:
        with open("portfolio.json", "w") as f:
            json.dump(p, f, indent=4)
    except Exception as e:
        st.error(f"Failed to save portfolio: {e}")

# --- INITIALIZE ---
analysis, history, meta = load_data()
portfolio = load_portfolio()

def get_verdict(score, rr, rsi=50):
    # Hardened Logic: RR must be healthy for any positive signal
    if score >= 9 and rr >= 2.0 and rsi > 55: return "💎 ALPHA BUY"
    if score >= 8 and rr >= 1.5: return "🟢 STRONG BUY"
    if score >= 7 and rr >= 1.2: return "🟢 BUY"
    if score < 5 or rsi > 78: return "🔴 SELL/OVERBOUGHT"
    return "🟡 HOLD"

st.title("🛡️ Quantum-Sentinel Pro")

if analysis is not None:
    tabs = st.tabs(["🚀 Screener", "💼 Portfolio", "⚡ Actionables", "📊 Success Tracker"])

    # --- TAB 1: SCREENER ---
    with tabs[0]:
        # Safe Merge
        merged = analysis.merge(meta[['SYMBOL', 'SECTOR']], on='SYMBOL', how='left')
        merged['SECTOR'] = merged['SECTOR'].fillna("General")

        # Sector Leaderboard
        if not merged.empty:
            sector_ranks = merged.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).round(2)
            with st.expander("📊 Industry Leaderboard", expanded=True):
                st.table(sector_ranks.head(3))
                if st.checkbox("Show All Sectors"):
                    st.table(sector_ranks)

        st.divider()
        c1, c2 = st.columns([3, 1])
        with c2: best_only = st.toggle("💎 Alpha Filter (RR > 2.0)")
        with c1: search = st.selectbox("🔍 Search", ["ALL"] + sorted(merged['SYMBOL'].unique().tolist()))
        
        df_view = merged.copy()
        if best_only: 
            df_view = df_view[(df_view['SCORE'] >= 8) & (df_view['RR_RATIO'] >= 2.0)]
        if search != "ALL": 
            df_view = df_view[df_view['SYMBOL'] == search]
        
        # Safely handle missing RSI column
        rsi_col = 'RSI' if 'RSI' in df_view.columns else None
        df_view['VERDICT'] = df_view.apply(lambda x: get_verdict(x['SCORE'], x['RR_RATIO'], x[rsi_col] if rsi_col else 50), axis=1)
        
        df_view = df_view.sort_values(by="SCORE", ascending=False)
        cols = ["VERDICT", "SYMBOL", "PRICE", "STOP-LOSS", "TARGET", "RR_RATIO", "POTENTIAL %", "HOLDING", "SECTOR"]
        st.dataframe(df_view[cols], use_container_width=True, hide_index=True)

    # --- TAB 2: PORTFOLIO ---
    with tabs[1]:
        with st.expander("➕ Add New Stock"):
            # Use analysis symbols if meta is empty
            available_tickers = sorted(merged['SYMBOL'].unique().tolist()) if not merged.empty else []
            f1, f2, f3 = st.columns(3)
            new_ticker = f1.selectbox("Ticker", options=[""] + available_tickers)
            new_price = f2.number_input("Avg Buy Price", min_value=0.0, format="%.2f")
            new_qty = f3.number_input("Quantity", min_value=1, step=1)
            if st.button("💾 Add Holding"):
                if new_ticker and new_price > 0:
                    portfolio[new_ticker] = {"price": float(new_price), "qty": int(new_qty)}
                    save_portfolio_sync(portfolio)
                    st.success(f"Added {new_ticker}")
                    st.rerun()

        if portfolio:
            p_rows = []
            inv, cur = 0.0, 0.0
            for sym, info in portfolio.items():
                row = analysis[analysis['SYMBOL'] == sym]
                if not row.empty:
                    r = row.iloc[0]
                    c_price = float(r['PRICE'])
                    b_price = float(info['price'])
                    q = int(info['qty'])
                    
                    inv += (b_price * q)
                    cur += (c_price * q)
                    
                    rsi_val = r.get('RSI', 50)
                    p_rows.append({
                        "SIGNAL": get_verdict(r['SCORE'], r['RR_RATIO'], rsi_val),
                        "Stock": sym, "Qty": q, "Avg": b_price, "CMP": c_price, 
                        "P&L": round((c_price - b_price) * q, 2), 
                        "SL": r['STOP-LOSS'], "TGT": r['TARGET'], "Pot. %": r['POTENTIAL %']
                    })
            
            if p_rows:
                st.divider()
                m1, m2, m3 = st.columns(3)
                m1.metric("Invested", f"₹{inv:,.2f}")
                m2.metric("Current", f"₹{cur:,.2f}", delta=f"₹{cur-inv:,.2f}")
                m3.metric("Net %", f"{((cur-inv)/inv*100):.2f}%" if inv > 0 else "0%")
                st.dataframe(pd.DataFrame(p_rows), use_container_width=True, hide_index=True)
            
            with st.expander("🗑️ Remove Stock"):
                to_del = st.selectbox("Select to Remove", list(portfolio.keys()))
                if st.button("Confirm Delete"):
                    del portfolio[to_del]
                    save_portfolio_sync(portfolio)
                    st.rerun()
        else:
            st.info("No holdings found.")

    # --- TAB 3 & 4 (STABLE) ---
    with tabs[2]:
        st.subheader("Action Alerts")
        if portfolio:
            for s, info in portfolio.items():
                r_match = analysis[analysis['SYMBOL'] == s]
                if not r_match.empty:
                    r = r_match.iloc[0]
                    if r['PRICE'] <= r['STOP-LOSS']: st.error(f"🚨 **SL HIT**: {s} ({r['PRICE']})")
                    elif r['PRICE'] >= r['TARGET']: st.success(f"💰 **TGT HIT**: {s} ({r['PRICE']})")
        
        st.write("🚀 **Top 7 Alpha Picks**")
        top_picks = analysis.sort_values("RR_RATIO", ascending=False).head(7)
        for _, p in top_picks.iterrows():
            st.info(f"**{p['SYMBOL']}** | RR: {p['RR_RATIO']} | +{p['POTENTIAL %']}%")

    with tabs[3]:
        if not history.empty:
            st.metric("System Accuracy", "Tracking...")
            st.dataframe(history.tail(10), use_container_width=True)

else:
    st.warning("⚠️ daily_analysis.csv not found. Please trigger your GitHub Action.")
    
