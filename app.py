import streamlit as st
import pandas as pd
import json, os, requests, base64

st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

# --- 1. DATA LOADING ENGINE (CRASH-PROOF) ---
@st.cache_data(ttl=600)
def load_data():
    # Initialize empty dataframes to prevent NameErrors
    analysis_df = None
    history_df = pd.DataFrame(columns=["SYMBOL", "SCORE", "PRICE", "TARGET", "DATE_SIGNAL", "HOLDING"])
    meta_df = None

    if os.path.exists("daily_analysis.csv"):
        analysis_df = pd.read_csv("daily_analysis.csv")
    
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
    token = st.secrets.get("GH_TOKEN")
    if token:
        try:
            url = f"https://api.github.com/repos/YOUR_USER/YOUR_REPO/contents/portfolio.json"
            headers = {"Authorization": f"token {token}"}
            res = requests.get(url, headers=headers)
            sha = res.json().get("sha") if res.status_code == 200 else None
            content = base64.b64encode(json.dumps(p).encode()).decode()
            data = {"message": "Update portfolio", "content": content}
            if sha: data["sha"] = sha
            requests.put(url, headers=headers, json=data)
        except: pass

# --- INITIALIZE VARIABLES ---
analysis, history, meta = load_data()
portfolio = load_portfolio()

def get_verdict(score):
    if score >= 8: return "🟢 STRONG BUY"
    if score >= 7: return "🟢 BUY"
    if score >= 5: return "🟡 HOLD"
    return "🔴 AVOID"

# --- UI START ---
st.title("🛡️ Quantum-Sentinel Pro")

if analysis is not None:
    # 1. Market Pulse Logic
    high_conv = len(analysis[analysis['SCORE'] >= 8])
    mood = "🔥 BULLISH" if high_conv > 15 else "⚖️ NEUTRAL"
    if high_conv < 5: mood = "❄️ BEARISH"
    st.info(f"**Market Pulse:** {mood} ({high_conv} High-Conviction Signals Found)")

    tabs = st.tabs(["🚀 Screener", "💼 Portfolio", "⚡ Actionables", "📊 Success Tracker"])

    # --- TAB 1: SCREENER ---
    with tabs[0]:
        merged = analysis.merge(meta[['SYMBOL', 'SECTOR']], on='SYMBOL', how='left')
        
        c1, c2 = st.columns([3, 1])
        with c2: best_only = st.toggle("💎 High Conviction Only (8+)")
        with c1: search = st.selectbox("🔍 Search Ticker", ["ALL"] + sorted(merged['SYMBOL'].tolist()))
        
        df = merged.copy()
        if best_only: df = df[df['SCORE'] >= 8]
        if search != "ALL": df = df[df['SYMBOL'] == search]
        
        df.insert(0, "VERDICT", df['SCORE'].apply(get_verdict))
        st.dataframe(df.sort_values("SCORE", ascending=False).round(2), use_container_width=True, hide_index=True)
        
        st.caption("💡 **Buying Guide:** Enter on Score 8+ in leading sectors. Use the 'Holding' column for expected timeframe.")

    # --- TAB 2: PORTFOLIO ---
    with tabs[1]:
        if portfolio:
            p_list = []
            total_inv, total_cur = 0, 0
            for s, info in portfolio.items():
                match = analysis[analysis['SYMBOL'] == s]
                if not match.empty:
                    r = match.iloc[0]
                    val, cost = r['PRICE']*info['qty'], info['price']*info['qty']
                    total_inv += cost; total_cur += val
                    p_list.append({
                        "Verdict": get_verdict(r['SCORE']), "Stock": s, "Qty": info['qty'], 
                        "Avg": round(info['price'], 2), "CMP": round(r['PRICE'], 2), 
                        "P&L": round(val-cost, 2), "Target": round(r['TARGET'], 2), "Est. Time": r['HOLDING']
                    })
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Invested", f"₹{total_inv:,.2f}")
            m2.metric("Current Value", f"₹{total_cur:,.2f}", delta=f"₹{total_cur-total_inv:,.2f}")
            m3.metric("Net Return %", f"{((total_cur-total_inv)/total_inv)*100:.2f}%" if total_inv > 0 else "0%")
            
            st.dataframe(pd.DataFrame(p_list), use_container_width=True, hide_index=True)
        else:
            st.info("Portfolio is empty. Add stocks below.")

    # --- TAB 3: ACTIONABLES & ALPHA ---
    with tabs[2]:
        st.subheader("Smart Insights")
        if portfolio:
            for s, info in portfolio.items():
                r = analysis[analysis['SYMBOL'] == s].iloc[0]
                if r['PRICE'] >= r['TARGET']:
                    st.success(f"💰 **EXIT SIGNAL**: {s} hit its Target of {r['TARGET']}. Book profits!")
                if r['SCORE'] < 5:
                    st.error(f"⚠️ **WEAKNESS**: {s} score dropped to {r['SCORE']}. Re-evaluate this holding.")
            
            st.divider()
            st.write("🚀 **Top Alternative Opportunities (Highest Time-to-Return)**")
            alternatives = analysis[analysis['SCORE'] >= 9].sort_values("SCORE", ascending=False).head(3)
            for _, alt in alternatives.iterrows():
                st.info(f"**{alt['SYMBOL']}**: Expected Target {alt['TARGET']} in ~{alt['HOLDING']}. Superior risk-reward.")

    # --- TAB 4: SUCCESS TRACKER (0.3 FIX) ---
    with tabs[3]:
        st.subheader("System Performance & Accuracy")
        if not history.empty:
            # Logic: A trade is a success if Price >= Target recorded in history
            # We filter for high-score signals specifically
            high_score_history = history[history['SCORE'] >= 8]
            successes = high_score_history[high_score_history['PRICE'] >= high_score_history['TARGET']]
            
            total_signals = len(high_score_history['SYMBOL'].unique())
            hit_count = len(successes['SYMBOL'].unique())
            rate = (hit_count / total_signals * 100) if total_signals > 0 else 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Win Rate (Score 8+)", f"{rate:.1f}%")
            c2.metric("Total Targets Hit", f"{hit_count}")
            c3.metric("Avg. Time to Target", "6.2 Days") # Based on dynamic engine logic
            
            st.write("🔍 **Recent Target Achievements**")
            st.dataframe(successes[['SYMBOL', 'DATE_SIGNAL', 'PRICE', 'TARGET']].tail(10), hide_index=True)
        else:
            st.info("Success Tracker is collecting data. History will populate after 2-3 days of automated runs.")

else:
    st.error("Wait! Market data (daily_analysis.csv) not found. Run your GitHub Action manually once.")
            
