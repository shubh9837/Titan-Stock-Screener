import streamlit as st
import pandas as pd
import json, os, datetime
import plotly.express as px

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide", page_icon="📈")

# TITAN UI CUSTOM CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .main { background-color: #0d1117; }
    
    div[data-testid="stMetric"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 15px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    .titan-card {
        background: rgba(22, 27, 34, 0.8);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        border: 1px solid #30363d;
    }
    
    .buy-pointer { 
        border-left: 6px solid #238636;
        background: linear-gradient(90deg, rgba(35, 134, 54, 0.1) 0%, rgba(22, 27, 34, 1) 100%);
    }
    
    .sell-pointer { 
        border-left: 6px solid #da3633;
        background: linear-gradient(90deg, rgba(218, 54, 51, 0.1) 0%, rgba(22, 27, 34, 1) 100%);
    }

    h1, h2, h3 { color: #f0f6fc !important; font-weight: 700; }
    .stCaption { color: #8b949e !important; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=600)
def load_all_data():
    if not os.path.exists("daily_analysis.csv"): return None, pd.DataFrame()
    df = pd.read_csv("daily_analysis.csv")
    df['STOP-LOSS'] = (df['PRICE'] * 0.95).round(2)
    df['EXP_PCT'] = (((df['TARGET'] - df['PRICE']) / df['PRICE']) * 100).round(2)
    df['VERDICT'] = df.apply(lambda r: "🔴 EXIT" if r['RSI'] > 78 else ("💎 ALPHA" if r['SCORE'] >= 8 else "🟢 BUY" if r['SCORE'] >= 6 else "🟡 HOLD"), axis=1)
    hist = pd.read_csv("trade_history.csv") if os.path.exists("trade_history.csv") else pd.DataFrame()
    return df, hist

df, history = load_all_data()
portfolio = {}
if os.path.exists("portfolio.json"):
    with open("portfolio.json", "r") as f: portfolio = json.load(f)

if df is not None:
    # Added Icons to Tab Headers
    tabs = st.tabs(["🔍 SCREENER", "💼 PORTFOLIO", "⚡ ACTIONABLES", "🏆 SUCCESS"])

    # --- TAB 1: SCREENER ---
    with tabs[0]:
        st.markdown("### 🏗️ Industry Momentum")
        ind_stats = df.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).reset_index()
        selected_ind = st.selectbox("📂 Select Industry to view score details:", ind_stats['SECTOR'])
        score_val = ind_stats[ind_stats['SECTOR'] == selected_ind]['SCORE'].values[0]
        st.info(f"📊 The average Technical Score for **{selected_ind}** is **{score_val:.2f}**")

        if st.button("🔭 SCAN FOR TOP ALPHA PICKS"):
            top = df[df['SCORE'] >= 9].sort_values("EXP_PCT", ascending=False).head(5)
            if not top.empty:
                cols = st.columns(len(top))
                for i, (_, row) in enumerate(top.iterrows()):
                    with cols[i]:
                        st.markdown(f"**{row['SYMBOL']}**")
                        st.code(f"₹{row['PRICE']:.2f}")
                        st.caption(f"⭐ Score: {row['SCORE']}")
            else:
                st.info("🌑 No 9+ Score stocks found. Waiting for setup...")

        st.divider()
        st.dataframe(df[["SYMBOL", "VERDICT", "SCORE", "PRICE", "TARGET", "EXP_PCT", "SECTOR", "RSI"]].sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)

    # --- TAB 2: PORTFOLIO ---
    p_df = pd.DataFrame()
    with tabs[1]:
        col_left, col_right = st.columns([3, 1])
        
        with col_right:
            with st.expander("📥 ADD STOCK"):
                s_name = st.selectbox("Ticker", sorted(df['SYMBOL'].unique()))
                s_avg = st.number_input("💵 Avg Price", step=0.01)
                s_qty = st.number_input("🔢 Qty", min_value=1)
                if st.button("✅ Save Entry"):
                    portfolio[s_name] = {"price": s_avg, "qty": s_qty}
                    with open("portfolio.json", "w") as f: json.dump(portfolio, f)
                    st.rerun()
            
            if portfolio:
                with st.expander("📤 EXIT POSITION"):
                    ex_s = st.selectbox("Exit Ticker", list(portfolio.keys()))
                    ex_q = st.number_input("Sell Qty", min_value=1, max_value=portfolio[ex_s]['qty'] if ex_s in portfolio else 1)
                    if st.button("⛔ Confirm Exit"):
                        st.success(f"Logging exit for {ex_s}...")

        with col_left:
            if portfolio:
                p_rows = []
                t_inv, t_cur = 0.0, 0.0
                for s, info in portfolio.items():
                    m = df[df['SYMBOL'] == s].iloc[0] if s in df['SYMBOL'].values else None
                    if m is not None:
                        t_inv += (info['price'] * info['qty'])
                        t_cur += (m['PRICE'] * info['qty'])
                        p_rows.append({"SYMBOL": s, "QTY": info['qty'], "AVG": info['price'], "CMP": m['PRICE'], "TARGET": m['TARGET'], "EXP %": m['EXP_PCT'], "RSI": m['RSI'], "VERDICT": m['VERDICT'], "STOP LOSS": m['STOP-LOSS']})
                p_df = pd.DataFrame(p_rows)
                
                m1, m2, m3 = st.columns(3)
                m1.metric("💰 Invested", f"₹{t_inv:,.2f}")
                m2.metric("🏦 Current Value", f"₹{t_cur:,.2f}", delta=f"₹{t_cur-t_inv:,.2f}")
                m3.metric("📈 Net Change", f"{((t_cur-t_inv)/t_inv*100):.2f}%" if t_inv > 0 else "0%")
                
                st.dataframe(p_df.style.format(precision=2), use_container_width=True, hide_index=True)
            else:
                st.info("📭 Your portfolio is currently empty.")

    # --- TAB 3: ACTIONABLES ---
    with tabs[2]:
        col_act1, col_act2 = st.columns([1, 1.5])
        
        with col_act1:
            st.markdown("### 🛡️ Portfolio Risk")
            if not p_df.empty:
                for _, row in p_df.iterrows():
                    if "EXIT" in row['VERDICT'] or row['CMP'] < row['STOP LOSS']:
                        st.markdown(f"""
                        <div class="titan-card sell-pointer">
                            <b>🚨 {row['SYMBOL']}</b><br>
                            <span style="color:#da3633;">Action: Book Profits/Cut Loss</span><br>
                            📉 RSI: {row['RSI']:.2f} | 🛑 SL: ₹{row['STOP LOSS']:.2f}
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.caption("✨ No urgent alerts for your holdings.")

        with col_act2:
            st.markdown("### 🎯 Alpha Opportunities")
            risk_amt = st.number_input("🏦 Risk Capital per Trade (₹)", value=2000, step=500)
            
            alphas = df[df['VERDICT'] == "💎 ALPHA"].sort_values("SCORE", ascending=False).head(5)
            for _, r in alphas.iterrows():
                risk_per_share = r['PRICE'] - r['STOP-LOSS']
                qty = int(risk_amt / risk_per_share) if risk_per_share > 0 else 0
                
                st.markdown(f"""
                <div class="titan-card buy-pointer">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="font-size:1.2rem; font-weight:700;">💎 {r['SYMBOL']}</span>
                        <span style="color:#238636; font-weight:700;">⭐ {r['SCORE']:.2f}</span>
                    </div>
                    <div style="margin-top:10px; font-size:0.9rem;">
                        💵 CMP: <b>₹{r['PRICE']:.2f}</b> | 🎯 Target: <b>₹{r['TARGET']:.2f}</b> ({r['EXP_PCT']:.2f}%)<br>
                        ⚖️ D/E: {r['DEBT_EQUITY']:.2f} | 🌡️ RSI: {r['RSI']:.2f}<br>
                        <hr style="border:0.5px solid #30363d;">
                        📦 <b>SUGGESTED QTY: {qty} SHARES</b><br>
                        <span style="font-size:0.8rem; color:#8b949e;">(Risking ₹{risk_amt} total if SL hits at ₹{r['STOP-LOSS']})</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # --- TAB 4: SUCCESS RATE ---
    with tabs[3]:
        st.markdown("### 📈 Performance Metrics")
        if not history.empty:
            st.metric("🎯 Strategy Accuracy", f"{(len(history[history['P&L_%'] > 0])/len(history)*100):.2f}%")
            st.dataframe(history.sort_values("DATE", ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("⏳ Trade history will appear here once you log exits.")

else:
    st.error("⚠️ Engine data not found. Please run engine.py first.")
    
