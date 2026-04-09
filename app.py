import streamlit as st
import pandas as pd
import json, os, requests, base64

st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

# --- 1. ROBUST DATA LOADER ---
@st.cache_data(ttl=600)
def load_data():
    analysis_df = None
    history_df = pd.DataFrame(columns=["SYMBOL", "SCORE", "PRICE", "TARGET", "DATE_SIGNAL", "HOLDING"])
    meta_df = pd.DataFrame(columns=["SYMBOL", "SECTOR", "PE_RATIO", "MARKET_CAP"])

    if os.path.exists("daily_analysis.csv"):
        try:
            analysis_df = pd.read_csv("daily_analysis.csv")
            if not analysis_df.empty:
                # Ensure essential columns exist to prevent KeyError
                cols_to_fix = ['PRICE', 'TARGET', 'SCORE', 'RSI', 'PE_RATIO', 'MARKET_CAP']
                for col in cols_to_fix:
                    if col not in analysis_df.columns:
                        analysis_df[col] = 0
                
                # Numeric Force
                analysis_df['PRICE'] = pd.to_numeric(analysis_df['PRICE'], errors='coerce').fillna(0)
                analysis_df['TARGET'] = pd.to_numeric(analysis_df['TARGET'], errors='coerce').fillna(0)
                analysis_df['SCORE'] = pd.to_numeric(analysis_df['SCORE'], errors='coerce').fillna(0)
                
                # Logic Prep
                analysis_df['STOP-LOSS'] = (analysis_df['PRICE'] * 0.95).round(2)
                analysis_df['POTENTIAL %'] = (((analysis_df['TARGET'] - analysis_df['PRICE']) / analysis_df['PRICE'].replace(0, 1)) * 100).round(2)
                
                risk = (analysis_df['PRICE'] - analysis_df['STOP-LOSS']).replace(0, 0.01)
                reward = (analysis_df['TARGET'] - analysis_df['PRICE'])
                analysis_df['RR_RATIO'] = (reward / risk).round(2)
        except Exception as e: 
            st.error(f"Loader Error (Analysis): {e}")

    if os.path.exists("trade_history.csv"):
        try: history_df = pd.read_csv("trade_history.csv")
        except: pass
    
    if os.path.exists("tickers_enriched.csv"):
        try: meta_df = pd.read_csv("tickers_enriched.csv")
        except: pass
    else:
        # Fallback: Create meta_df from analysis_df if enriched file missing
        if analysis_df is not None:
            meta_df = analysis_df[['SYMBOL']].copy()
            meta_df['SECTOR'] = 'General'
            meta_df['PE_RATIO'] = 25
            meta_df['MARKET_CAP'] = 0

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
    with open("portfolio.json", "w") as f:
        json.dump(p, f, indent=4)

# --- THE HYBRID DECISION ENGINE ---
def get_hybrid_verdict(row):
    # Using .get() with defaults to prevent crashing on missing data
    score = row.get('SCORE', 0)
    rr = row.get('RR_RATIO', 0)
    rsi = row.get('RSI', 50)
    pe = row.get('PE_RATIO', 25)
    
    if rsi > 78: return "🔴 SELL (OVERBOUGHT)"
    if score < 5: return "🔴 AVOID (WEAK TREND)"
    if pe > 85: return "🔴 AVOID (OVERVALUED)"
    if score >= 9 and rr >= 2.0 and rsi > 55 and pe < 50: return "💎 ALPHA BUY"
    if score >= 8 and rr >= 1.5 and pe < 65: return "🟢 STRONG BUY"
    if score >= 7 and rr >= 1.2: return "🟢 BUY"
    return "🟡 HOLD"

# --- INITIALIZE ---
analysis, history, meta = load_data()
portfolio = load_portfolio()

st.title("🛡️ Quantum-Sentinel Pro")

if analysis is not None:
    # PRE-PROCESS VERDICTS to ensure column exists before tabs load
    analysis['VERDICT'] = analysis.apply(get_hybrid_verdict, axis=1)
    
    tabs = st.tabs(["🚀 Screener", "💼 Portfolio", "⚡ Actionables", "📊 Success Tracker"])

    # --- TAB 1: SCREENER ---
    with tabs[0]:
        # Merge safely
        merged = analysis.merge(meta[['SYMBOL', 'SECTOR']], on='SYMBOL', how='left')
        merged['SECTOR'] = merged['SECTOR'].fillna("General")

        # Leaderboard
        if not merged.empty:
            sector_ranks = merged.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).round(2)
            with st.expander("📊 Industry Leaderboard", expanded=True):
                st.table(sector_ranks.head(3))

        st.divider()
        c1, c2 = st.columns([3, 1])
        with c2: alpha_only = st.toggle("💎 Alpha Picks Only")
        with c1: search = st.selectbox("🔍 Search Ticker", ["ALL"] + sorted(merged['SYMBOL'].unique().tolist()))
        
        df_view = merged.copy()
        if alpha_only: df_view = df_view[df_view['VERDICT'] == "💎 ALPHA BUY"]
        if search != "ALL": df_view = df_view[df_view['SYMBOL'] == search]
        
        df_view = df_view.sort_values(by="SCORE", ascending=False)
        # Use only columns we are sure exist
        available_cols = [c for c in ["VERDICT", "SYMBOL", "PRICE", "STOP-LOSS", "TARGET", "RR_RATIO", "POTENTIAL %", "SECTOR"] if c in df_view.columns]
        st.dataframe(df_view[available_cols], use_container_width=True, hide_index=True)

    # --- TAB 2: PORTFOLIO ---
    with tabs[1]:
        with st.expander("➕ Add New Holding"):
            available = sorted(analysis['SYMBOL'].unique().tolist())
            f1, f2, f3 = st.columns(3)
            new_t = f1.selectbox("Ticker", options=[""] + available)
            new_p = f2.number_input("Avg Price", min_value=0.0)
            new_q = f3.number_input("Qty", min_value=1)
            if st.button("💾 Save"):
                if new_t:
                    portfolio[new_t] = {"price": float(new_p), "qty": int(new_q)}
                    save_portfolio_sync(portfolio)
                    st.rerun()

        if portfolio:
            p_rows = []
            inv, cur = 0.0, 0.0
            for sym, info in portfolio.items():
                row = analysis[analysis['SYMBOL'] == sym]
                if not row.empty:
                    r = row.iloc[0]
                    inv += (info['price'] * info['qty'])
                    cur += (r['PRICE'] * info['qty'])
                    p_rows.append({
                        "SIGNAL": r['VERDICT'],
                        "Stock": sym, "Qty": info['qty'], "Avg": info['price'], "CMP": r['PRICE'], 
                        "P&L": round((r['PRICE'] - info['price']) * info['qty'], 2), 
                        "SL": r['STOP-LOSS'], "TGT": r['TARGET'], "%": r['POTENTIAL %']
                    })
            
            if p_rows:
                st.divider()
                m1, m2, m3 = st.columns(3)
                m1.metric("Invested", f"₹{inv:,.0f}")
                m2.metric("Current", f"₹{cur:,.0f}", delta=f"₹{cur-inv:,.0f}")
                m3.metric("Net %", f"{((cur-inv)/inv*100):.2f}%" if inv > 0 else "0%")
                st.dataframe(pd.DataFrame(p_rows), use_container_width=True, hide_index=True)
            
            if list(portfolio.keys()):
                with st.expander("🗑️ Sell/Remove"):
                    to_del = st.selectbox("Select to Remove", list(portfolio.keys()))
                    if st.button("Delete"):
                        del portfolio[to_del]
                        save_portfolio_sync(portfolio)
                        st.rerun()

    # --- TAB 3: ACTIONABLES ---
    with tabs[2]:
        st.subheader("Action Alerts")
        alerts_found = False
        if portfolio:
            for s, info in portfolio.items():
                r_match = analysis[analysis['SYMBOL'] == s]
                if not r_match.empty:
                    r = r_match.iloc[0]
                    if r['PRICE'] <= r['STOP-LOSS']: 
                        st.error(f"🚨 **SL HIT**: {s} (Exit at {r['PRICE']})")
                        alerts_found = True
                    elif r['PRICE'] >= r['TARGET']: 
                        st.success(f"💰 **TGT HIT**: {s} (Target {r['TARGET']} Reached!)")
                        alerts_found = True
        if not alerts_found:
            st.write("No immediate Stop-Loss or Target alerts for your portfolio.")
        
        st.divider()
        st.write("🚀 **Top Alpha Opportunities**")
        top = analysis[analysis['VERDICT'] == "💎 ALPHA BUY"].head(7)
        if top.empty: top = analysis.sort_values("RR_RATIO", ascending=False).head(7)
        for _, p in top.iterrows():
            st.info(f"**{p['SYMBOL']}** | {p['VERDICT']} | Target: {p['TARGET']} (+{p['POTENTIAL %']}%)")

    # --- TAB 4: SUCCESS TRACKER ---
    with tabs[3]:
        st.subheader("Performance Tracker")
        if not history.empty:
            st.dataframe(history.tail(10), use_container_width=True)
        else:
            st.info("No trade history found yet. History builds as you close trades.")

else:
    st.error("🔴 Missing Data: `daily_analysis.csv` not found. Please run the Engine first.")
    
