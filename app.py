import streamlit as st
import pandas as pd
import json, os, datetime
from github import Github
import base64

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="Titan Quantum Pro", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #0d1117; }
    div[data-testid="stMetric"] { background-color: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 15px; }
    .action-card { background: #1c2128; border-radius: 10px; padding: 15px; border-left: 5px solid; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. GITHUB & DATA PERSISTENCE ---
def get_github_repo():
    try:
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo(st.secrets["REPO_NAME"])
    except: return None

def sync_to_github(file_path, content, message):
    repo = get_github_repo()
    if not repo: return False
    try:
        try:
            contents = repo.get_contents(file_path)
            repo.update_file(contents.path, message, content, contents.sha)
        except:
            repo.create_file(file_path, message, content)
        st.toast(f"✅ Synced to GitHub: {file_path}")
        return True
    except Exception as e:
        st.error(f"Sync Failed: {e}")
        return False

@st.cache_data(ttl=300) 
def load_market_data():
    if not os.path.exists("daily_analysis.csv"):
        return pd.DataFrame()
    df = pd.read_csv("daily_analysis.csv")
    df['VERDICT'] = df['SCORE'].apply(lambda x: "💎 ALPHA" if x >= 8 else "🟢 BUY" if x >= 6 else "🟡 HOLD")
    return df

# --- 3. LOAD DATA ---
df = load_market_data()
repo = get_github_repo()

try:
    p_file = repo.get_contents("portfolio.json")
    portfolio = json.loads(base64.b64decode(p_file.content).decode())
except: portfolio = {}

try:
    h_file = repo.get_contents("trade_history.csv")
    history = pd.read_csv(base64.b64decode(h_file.content).decode())
except: history = pd.DataFrame()

# --- 4. UI TABS ---
tabs = st.tabs(["🔍 SCREENER", "💼 PORTFOLIO", "⚡ ACTIONABLES", "🏆 SUCCESS"])

# --- TAB 1: SCREENER ---
with tabs[0]:
    if not df.empty:
        col_a, col_b = st.columns([1, 2])
        with col_a:
            st.write("### 📂 Sector Strength")
            # Calculate sector average from the engine's scores
            if 'SECTOR' in df.columns:
                sec_stats = df.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).head(10)
                st.bar_chart(sec_stats)
        with col_b:
            st.write("### 💎 High Conviction Setups")
            st.dataframe(df[['VERDICT', 'SCORE', 'SYMBOL', 'PRICE', 'TARGET', 'STOP_LOSS', 'RSI']].sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.warning("Data sync in progress. Please trigger GitHub Action.")

# --- TAB 2: PORTFOLIO ---
with tabs[1]:
    if portfolio and not df.empty:
        p_rows = []
        t_inv, t_val = 0.0, 0.0
        for sym, d in portfolio.items():
            m_data = df[df['SYMBOL'] == sym]
            if not m_data.empty:
                m = m_data.iloc[0]
                cur_val = m['PRICE'] * d['qty']
                invested = d['price'] * d['qty']
                t_inv += invested; t_val += cur_val
                p_rows.append({
                    "SYMBOL": sym, "QTY": d['qty'], "AVG": d['price'], "CMP": m['PRICE'],
                    "INVESTED": round(invested, 2), "VALUE": round(cur_val, 2),
                    "P&L %": round(((cur_val-invested)/invested*100), 2),
                    "TSL": m['STOP_LOSS'], "TARGET": m['TARGET']
                })
        
        pdf = pd.DataFrame(p_rows)
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Invested", f"₹{t_inv:,.2f}")
        m2.metric("🏦 Portfolio Value", f"₹{t_val:,.2f}", delta=f"₹{t_val-t_inv:,.2f}")
        m3.metric("📈 Total Return", f"{((t_val-t_inv)/t_inv*100 if t_inv>0 else 0):.2f}%")
        
        st.dataframe(pdf.style.map(lambda x: 'color: #238636' if isinstance(x, (int,float)) and x > 0 else 'color: #da3633', subset=['P&L %']), use_container_width=True, hide_index=True)

    with st.expander("➕ Execute New Trade"):
        ticker = st.selectbox("Select Alpha Stock", df['SYMBOL'].unique() if not df.empty else [])
        if ticker:
            s_data = df[df['SYMBOL']==ticker].iloc[0]
            c1, c2 = st.columns(2)
            cap = c1.number_input("Capital Allocation", value=50000)
            risk_p = c2.slider("Risk per trade (%)", 1, 3, 1)
            
            # Position Sizing Logic
            risk_amt = cap * (risk_p/100)
            risk_per_share = s_data['PRICE'] - s_data['STOP_LOSS']
            qty = int(risk_amt / risk_per_share) if risk_per_share > 0 else 1
            
            st.info(f"💡 Recommended: Buy **{qty}** shares. Total risk: ₹{risk_amt:.0f}")
            
            if st.button("Add to Portfolio & Sync"):
                portfolio[ticker] = {"price": float(s_data['PRICE']), "qty": qty, "date": str(datetime.date.today())}
                sync_to_github("portfolio.json", json.dumps(portfolio, indent=4), f"Buy {ticker}")
                st.rerun()

# --- TAB 3: ACTIONABLES ---
with tabs[2]:
    st.markdown("### 🛡️ Risk & Exit Alerts")
    if portfolio and not df.empty:
        for _, r in pdf.iterrows():
            if r['CMP'] < r['TSL']:
                st.markdown(f'<div class="action-card" style="border-left-color: #da3633;">🚨 <b>{r["SYMBOL"]}</b>: HIT STOP-LOSS (₹{r["TSL"]})<br>Current: ₹{r["CMP"]}. Exit immediately.</div>', unsafe_allow_html=True)
            elif r['P&L %'] > 5:
                st.markdown(f'<div class="action-card" style="border-left-color: #238636;">✅ <b>{r["SYMBOL"]}</b>: Target 1 Secured. SL moved to Break-even (₹{r["AVG"]}).</div>', unsafe_allow_html=True)

# --- TAB 4: SUCCESS ---
with tabs[3]:
    if not history.empty:
        wr = (len(history[history['P&L_%'] > 0]) / len(history)) * 100
        st.metric("🎯 Cumulative Win Rate", f"{wr:.1f}%")
        st.dataframe(history, use_container_width=True, hide_index=True)
    else:
        st.info("No closed trades in history yet.")
        
