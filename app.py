import streamlit as st
import pandas as pd
import json, os, datetime
import numpy as np
from github import Github
import base64

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #0d1117; }
    .top-pick-bar {
        background: #161b22; border: 1px solid #30363d; border-radius: 6px;
        padding: 10px; margin-bottom: 20px; display: flex; gap: 20px; overflow-x: auto;
    }
    .pick-item { font-size: 0.85rem; border-right: 1px solid #30363d; padding-right: 20px; min-width: 200px; }
    div[data-testid="stMetric"] { background-color: #161b22; border: 1px solid #30363d; border-radius: 12px; }
    .action-card { background: #1c2128; border-radius: 10px; padding: 15px; border-left: 5px solid; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- GITHUB SYNC ENGINE ---
def sync_to_github(file_path, content, message):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo_name = st.secrets["REPO_NAME"]
        g = Github(token)
        repo = g.get_repo(repo_name)
        
        try:
            contents = repo.get_contents(file_path)
            repo.update_file(contents.path, message, content, contents.sha)
        except:
            repo.create_file(file_path, message, content)
        return True
    except Exception as e:
        st.error(f"GitHub Sync Error: {e}")
        return False

# --- DYNAMIC CALCULATION ENGINE ---
def calculate_trade_metrics(row):
    # Dynamic Expected % based on Score and RSI
    base_target = 10 + (row['SCORE'] * 1.5)
    if row['RSI'] < 40: base_target += 5 
    # Dynamic Holding Period (Days)
    hold_days = int(25 - (row['SCORE'] * 2))
    return round(base_target, 2), max(5, hold_days)

@st.cache_data(ttl=600)
def load_all_data():
    if not os.path.exists("daily_analysis.csv"): return None, pd.DataFrame()
    df = pd.read_csv("daily_analysis.csv")
    metrics = df.apply(calculate_trade_metrics, axis=1)
    df['EXP_PCT'] = [m[0] for m in metrics]
    df['HOLD_DAYS'] = [m[1] for m in metrics]
    df['TARGET'] = (df['PRICE'] * (1 + df['EXP_PCT']/100)).round(2)
    df['STOP-LOSS'] = (df['PRICE'] * 0.94).round(2)
    df['VERDICT'] = df.apply(lambda r: "💎 ALPHA" if r['SCORE'] >= 8 else "🟢 BUY" if r['SCORE'] >= 6 else "🟡 HOLD", axis=1)
    df.loc[df['RSI'] > 78, 'VERDICT'] = "🔴 EXIT"
    hist = pd.read_csv("trade_history.csv") if os.path.exists("trade_history.csv") else pd.DataFrame()
    return df, hist

df, history = load_all_data()

# Portfolio Persistence
if os.path.exists("portfolio.json"):
    with open("portfolio.json", "r") as f:
        try: portfolio = json.load(f)
        except: portfolio = {}
else: portfolio = {}

def save_portfolio_and_sync(p):
    content = json.dumps(p, indent=4)
    with open("portfolio.json", "w") as f:
        f.write(content)
    sync_to_github("portfolio.json", content, f"Update Portfolio: {datetime.datetime.now()}")

if df is not None:
    tabs = st.tabs(["🔍 SCREENER", "💼 PORTFOLIO", "⚡ ACTIONABLES", "🏆 SUCCESS"])

    # --- TAB 1: SCREENER ---
    with tabs[0]:
        ind_stats = df.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False)
        ind_options = ["All Sectors"] + [f"{sector} ({score:.1f})" for sector, score in ind_stats.items()]
        selected_option = st.selectbox("📂 Sector Strength (Sorted)", ind_options)
        selected_ind = selected_option.split(" (")[0] if selected_option != "All Sectors" else "All"

        filtered_df = df.copy()
        if selected_ind != "All": filtered_df = filtered_df[filtered_df['SECTOR'] == selected_ind]
            
        top_picks = filtered_df[filtered_df['SCORE'] >= 7.5].sort_values("SCORE", ascending=False).head(8)
        if not top_picks.empty:
            pick_html = '<div class="top-pick-bar">'
            for _, r in top_picks.iterrows():
                pick_html += f'<div class="pick-item"><b style="color:#58a6ff;">{r["SYMBOL"]}</b><br><span style="color:#4CAF50;">Target: +{r["EXP_PCT"]}%</span> | ⏳ {r["HOLD_DAYS"]}d</div>'
            st.markdown(pick_html + '</div>', unsafe_allow_html=True)
        st.dataframe(filtered_df[["VERDICT", "SCORE", "SYMBOL", "PRICE", "TARGET", "EXP_PCT", "HOLD_DAYS", "STOP-LOSS", "RSI", "SECTOR"]].sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)

    # --- TAB 2: PORTFOLIO ---
    with tabs[1]:
        if portfolio:
            p_rows = []
            for sym, data in portfolio.items():
                m = df[df['SYMBOL'] == sym].iloc[0] if sym in df['SYMBOL'].values else None
                if m is not None:
                    inv, cur = data['price'] * data['qty'], m['PRICE'] * data['qty']
                    p_rows.append({"SYMBOL": sym, "VERDICT": m['VERDICT'], "SCORE": m['SCORE'], "QTY": data['qty'], "AVG": data['price'], "CMP": m['PRICE'], "INVESTED": inv, "VALUE": cur, "P&L %": round(((cur-inv)/inv*100), 2), "TARGET": m['TARGET'], "EXP %": m['EXP_PCT'], "STOP-LOSS": m['STOP-LOSS'], "DAYS": m['HOLD_DAYS']})
            pdf = pd.DataFrame(p_rows)
            st.markdown(f"### 📋 Portfolio Overview ({len(pdf)} Holdings)")
            st.dataframe(pdf, use_container_width=True, hide_index=True)
            st.markdown("### ⚠️ Holding Actions")
            holding_actions = pdf[(pdf['P&L %'] < -4) | (pdf['SCORE'] < 5) | (pdf['VERDICT'] == "🔴 EXIT")]
            if not holding_actions.empty:
                st.warning("Immediate Review Required:")
                st.table(holding_actions[["SYMBOL", "P&L %", "VERDICT", "STOP-LOSS"]])
            else: st.success("✅ Holdings Stable.")
        
        mcol1, mcol2 = st.columns(2)
        with mcol1:
            with st.expander("📥 Add New Trade"):
                asym = st.selectbox("Symbol", sorted(df['SYMBOL'].unique()))
                aprc = st.number_input("Entry Price", value=float(df[df['SYMBOL']==asym]['PRICE'].iloc[0]))
                aqty = st.number_input("Quantity", min_value=1)
                if st.button("Save & Sync Trade"):
                    portfolio[asym] = {"price": aprc, "qty": aqty, "date": str(datetime.date.today())}
                    save_portfolio_and_sync(portfolio)
                    st.rerun()
        with mcol2:
            if portfolio:
                with st.expander("📤 Close Position"):
                    esym = st.selectbox("Symbol to Exit", list(portfolio.keys()))
                    if st.button("Confirm Sell & Sync"):
                        m_data = df[df['SYMBOL'] == esym].iloc[0]
                        # Fix for the Syntax Error Parentheses
                        p_n_l = round(((m_data['PRICE'] - portfolio[esym]['price']) / portfolio[esym]['price']) * 100, 2)
                        
                        hist_row = pd.DataFrame([{
                            "SYMBOL": esym, 
                            "BUY_DATE": portfolio[esym].get('date', 'N/A'), 
                            "EXIT_DATE": str(datetime.date.today()), 
                            "BUY_PRICE": portfolio[esym]['price'], 
                            "SELL_PRICE": m_data['PRICE'], 
                            "P&L_%": p_n_l
                        }])
                        
                        full_hist = pd.concat([history, hist_row], ignore_index=True)
                        full_hist.to_csv("trade_history.csv", index=False)
                        sync_to_github("trade_history.csv", full_hist.to_csv(index=False), f"Exit Trade: {esym}")
                        
                        del portfolio[esym]
                        save_portfolio_and_sync(portfolio)
                        st.rerun()

    # --- TAB 3: ACTIONABLES ---
    with tabs[2]:
        st.markdown("### ⚡ Portfolio Insights")
        if portfolio:
            for sym in portfolio.keys():
                m = df[df['SYMBOL'] == sym].iloc[0]
                if m['SCORE'] < 6: st.markdown(f'<div class="action-card" style="border-left-color: #da3633;">🔴 <b>{sym}</b>: Weak Score ({m["SCORE"]}). Check Verdict.</div>', unsafe_allow_html=True)
        
        st.markdown("### 💎 New Alpha Opportunities")
        new_opps = df[df['SCORE'] >= 8.5].sort_values("SCORE", ascending=False).head(5)
        for _, r in new_opps.iterrows():
            st.markdown(f'<div class="action-card" style="border-left-color: #238636;"><b>{r["SYMBOL"]}</b> | CMP: ₹{r["PRICE"]} | <b>Target: ₹{r["TARGET"]} (+{r["EXP_PCT"]}%)</b><br><small>Technical Score: {r["SCORE"]} | RSI: {r["RSI"]} | Est. Hold: {r["HOLD_DAYS"]} days.</small></div>', unsafe_allow_html=True)

    # --- TAB 4: SUCCESS ---
    with tabs[3]:
        if not history.empty:
            st.markdown("### 🏆 Performance Track Record")
            c1, c2 = st.columns(2)
            c1.metric("Win Rate", f"{(len(history[history['P&L_%'] > 0])/len(history)*100):.1f}%")
            c2.metric("Total Trades", len(history))
            st.dataframe(history.sort_values("EXIT_DATE", ascending=False), use_container_width=True, hide_index=True)
else:
    st.error("Engine data (daily_analysis.csv) not found.")
    
