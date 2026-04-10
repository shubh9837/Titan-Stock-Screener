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
def get_github_repo():
    token = st.secrets["GITHUB_TOKEN"]
    repo_name = st.secrets["REPO_NAME"]
    g = Github(token)
    return g.get_repo(repo_name)

def sync_to_github(file_path, content, message):
    try:
        repo = get_github_repo()
        try:
            contents = repo.get_contents(file_path)
            repo.update_file(contents.path, message, content, contents.sha)
        except:
            repo.create_file(file_path, message, content)
        return True
    except Exception as e:
        st.error(f"GitHub Sync Error: {e}")
        return False

def load_portfolio_from_github():
    try:
        repo = get_github_repo()
        file_content = repo.get_contents("portfolio.json")
        return json.loads(base64.b64decode(file_content.content).decode())
    except:
        if os.path.exists("portfolio.json"):
            with open("portfolio.json", "r") as f:
                return json.load(f)
        return {}

def calculate_trade_metrics(row):
    base_target = 10 + (row['SCORE'] * 1.5)
    if row['RSI'] < 40: base_target += 5 
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
portfolio = load_portfolio_from_github()

def save_portfolio_and_sync(p):
    content = json.dumps(p, indent=4)
    with open("portfolio.json", "w") as f:
        f.write(content)
    sync_to_github("portfolio.json", content, f"UI Update: {datetime.datetime.now()}")

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
        pdf = pd.DataFrame() # Initialize empty
        if portfolio:
            p_rows = []
            t_inv, t_val = 0.0, 0.0
            for sym, data in portfolio.items():
                m = df[df['SYMBOL'] == sym].iloc[0] if sym in df['SYMBOL'].values else None
                if m is not None:
                    inv, cur = data['price'] * data['qty'], m['PRICE'] * data['qty']
                    t_inv += inv; t_val += cur
                    p_rows.append({"SYMBOL": sym, "VERDICT": m['VERDICT'], "SCORE": m['SCORE'], "QTY": data['qty'], "AVG": data['price'], "CMP": m['PRICE'], "INVESTED": inv, "VALUE": cur, "P&L %": round(((cur-inv)/inv*100), 2), "TARGET": m['TARGET'], "EXP %": m['EXP_PCT'], "STOP-LOSS": m['STOP-LOSS'], "DAYS": m['HOLD_DAYS']})
            
            if p_rows:
                pdf = pd.DataFrame(p_rows)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("💰 Invested", f"₹{t_inv:,.2f}")
                m2.metric("🏦 Value", f"₹{t_val:,.2f}", delta=f"₹{t_val-t_inv:,.2f}")
                m3.metric("📈 Return", f"{((t_val-t_inv)/t_inv*100 if t_inv>0 else 0):.2f}%")
                m4.metric("📂 Stocks", len(pdf))

                st.markdown("### 📋 Detailed Holdings")
                # Fix: Changed applymap to map for modern Pandas compatibility
                st.dataframe(
                    pdf.style.map(lambda x: 'color: #238636' if isinstance(x, float) and x > 0 else ('color: #da3633' if isinstance(x, float) and x < 0 else ''), subset=['P&L %']), 
                    use_container_width=True, 
                    hide_index=True
                )
                
                st.markdown("### 🛠️ Portfolio Management Actions")
                bad_holds = pdf[(pdf['P&L %'] < -4) | (pdf['SCORE'] < 5.5) | (pdf['VERDICT'] == "🔴 EXIT")]
                if not bad_holds.empty:
                    for _, row in bad_holds.iterrows():
                        st.error(f"🚩 **{row['SYMBOL']}**: {row['VERDICT']} | P&L: {row['P&L %']}% | Action Needed")
                else: st.success("✅ Your holdings are fundamentally strong.")
        else:
            st.info("Portfolio is currently empty. Add a trade below to start tracking.")
        
        col_add, col_del = st.columns(2)
        with col_add:
            with st.expander("➕ Add Stock"):
                asym = st.selectbox("Ticker", sorted(df['SYMBOL'].unique()))
                aprc = st.number_input("Cost Price", value=float(df[df['SYMBOL']==asym]['PRICE'].iloc[0]))
                aqty = st.number_input("Quantity", min_value=1)
                if st.button("Confirm Addition"):
                    portfolio[asym] = {"price": aprc, "qty": aqty, "date": str(datetime.date.today())}
                    save_portfolio_and_sync(portfolio); st.rerun()
        with col_del:
            if portfolio:
                with st.expander("➖ Exit Stock"):
                    esym = st.selectbox("Exit Ticker", list(portfolio.keys()))
                    if st.button("Confirm Exit"):
                        m_data = df[df['SYMBOL'] == esym].iloc[0]
                        p_l = round(((m_data['PRICE'] - portfolio[esym]['price']) / portfolio[esym]['price']) * 100, 2)
                        hist_row = pd.DataFrame([{"SYMBOL": esym, "BUY_DATE": portfolio[esym].get('date', 'N/A'), "EXIT_DATE": str(datetime.date.today()), "BUY_PRICE": portfolio[esym]['price'], "SELL_PRICE": m_data['PRICE'], "P&L_%": p_l}])
                        full_h = pd.concat([history, hist_row], ignore_index=True)
                        full_h.to_csv("trade_history.csv", index=False)
                        sync_to_github("trade_history.csv", full_h.to_csv(index=False), f"Trade Exit: {esym}")
                        del portfolio[esym]; save_portfolio_and_sync(portfolio); st.rerun()

    # --- TAB 3: ACTIONABLES ---
    with tabs[2]:
        st.markdown("### 🛡️ Urgent Portfolio Alerts")
        if portfolio:
            risk_alert = False
            for s, d in portfolio.items():
                m = df[df['SYMBOL'] == s].iloc[0]
                if m['RSI'] > 78 or m['PRICE'] < m['STOP-LOSS'] or m['SCORE'] < 5.5:
                    risk_alert = True
                    st.markdown(f'<div class="action-card" style="border-left-color: #da3633;">⚠️ <b>{s}</b>: Check required (Verdict: {m["VERDICT"]})<br>Price: ₹{m["PRICE"]} | RSI: {m["RSI"]} | Score: {m["SCORE"]}</div>', unsafe_allow_html=True)
            if not risk_alert: st.success("✅ No urgent risks detected in your portfolio.")

        st.markdown("---")
        st.markdown("### 💎 Fresh Alpha Setups")
        for _, r in df[df['SCORE'] >= 8.5].sort_values("SCORE", ascending=False).head(5).iterrows():
            st.markdown(f'<div class="action-card" style="border-left-color: #238636;">✨ <b>{r["SYMBOL"]}</b>: High Conviction Alpha<br>Target: ₹{r["TARGET"]} (+{r["EXP_PCT"]}%) | Score: {r["SCORE"]}</div>', unsafe_allow_html=True)

    # --- TAB 4: SUCCESS ---
    with tabs[3]:
        if not history.empty:
            st.metric("🎯 Win Rate", f"{(len(history[history['P&L_%'] > 0])/len(history)*100):.1f}%")
            st.dataframe(history.sort_values("EXIT_DATE", ascending=False), use_container_width=True, hide_index=True)
