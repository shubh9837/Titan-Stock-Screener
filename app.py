import streamlit as st
import pandas as pd
import json, os, datetime
import plotly.express as px

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #0d1117; }
    
    /* Compact Top Picks Bar */
    .top-pick-bar {
        background: #161b22; border: 1px solid #30363d; border-radius: 6px;
        padding: 8px 15px; margin-bottom: 20px; display: flex; gap: 20px;
        overflow-x: auto; white-space: nowrap;
    }
    .pick-item { font-size: 0.85rem; border-right: 1px solid #30363d; padding-right: 20px; }
    
    /* Metric & Card Styling */
    div[data-testid="stMetric"] { background-color: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 12px !important; }
    .action-card { background: #1c2128; border-radius: 10px; padding: 15px; border-left: 5px solid; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- DATA ENGINE ---
@st.cache_data(ttl=600)
def load_all_data():
    if not os.path.exists("daily_analysis.csv"): return None, pd.DataFrame()
    df = pd.read_csv("daily_analysis.csv")
    df['STOP-LOSS'] = (df['PRICE'] * 0.95).round(2)
    df['EXP_PCT'] = (((df['TARGET'] - df['PRICE']) / df['PRICE']) * 100).round(2)
    df['VERDICT'] = df.apply(lambda r: "💎 ALPHA" if r['SCORE'] >= 8 else "🟢 BUY" if r['SCORE'] >= 6 else "🟡 HOLD", axis=1)
    df.loc[df['RSI'] > 78, 'VERDICT'] = "🔴 EXIT"
    hist = pd.read_csv("trade_history.csv") if os.path.exists("trade_history.csv") else pd.DataFrame()
    return df, hist

df, history = load_all_data()

# Portfolio Persistence
portfolio = {}
if os.path.exists("portfolio.json"):
    with open("portfolio.json", "r") as f:
        try: portfolio = json.load(f)
        except: portfolio = {}

def save_portfolio(p):
    with open("portfolio.json", "w") as f:
        json.dump(p, f)

if df is not None:
    tabs = st.tabs(["🔍 SCREENER", "💼 PORTFOLIO", "⚡ ACTIONABLES", "🏆 SUCCESS"])

    # --- TAB 1: SCREENER ---
    with tabs[0]:
        ind_stats = df.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False)
        ind_options = ["All Sectors"] + [f"{sector} ({score:.1f})" for sector, score in ind_stats.items()]
        selected_option = st.selectbox("📂 Industry Rankings", ind_options)
        selected_ind = selected_option.split(" (")[0] if selected_option != "All Sectors" else "All"

        filtered_df = df.copy()
        if selected_ind != "All": filtered_df = filtered_df[filtered_df['SECTOR'] == selected_ind]
            
        top_picks = filtered_df[filtered_df['SCORE'] >= 8.5].sort_values("EXP_PCT", ascending=False).head(6)
        if not top_picks.empty:
            pick_html = '<div class="top-pick-bar">'
            for _, r in top_picks.iterrows():
                pick_html += f'<div class="pick-item"><b style="color:#58a6ff;">{r["SYMBOL"]}</b> | <span style="color:#4CAF50;">₹{r["PRICE"]:.2f}</span> | ⭐ {r["SCORE"]}</div>'
            st.markdown(pick_html + '</div>', unsafe_allow_html=True)

        search = st.text_input("🔍 Search Ticker", placeholder="e.g. RELIANCE")
        if search: filtered_df = filtered_df[filtered_df['SYMBOL'].str.contains(search.upper())]

        st.dataframe(filtered_df[["VERDICT", "SCORE", "SYMBOL", "PRICE", "TARGET", "EXP_PCT", "STOP-LOSS", "RSI", "SECTOR"]].sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)

    # --- TAB 2: PORTFOLIO ---
    with tabs[1]:
        p_col_left, p_col_right = st.columns([2, 1])
        
        with p_col_left:
            st.markdown("### 📊 Holdings & Analysis")
            if portfolio:
                p_rows = []
                t_inv, t_cur = 0.0, 0.0
                for sym, data in portfolio.items():
                    m = df[df['SYMBOL'] == sym].iloc[0] if sym in df['SYMBOL'].values else None
                    if m is not None:
                        inv = data['price'] * data['qty']
                        cur = m['PRICE'] * data['qty']
                        t_inv += inv; t_cur += cur
                        p_rows.append({"TICKER": sym, "QTY": data['qty'], "AVG": data['price'], "CMP": m['PRICE'], "P&L %": round(((m['PRICE']-data['price'])/data['price']*100), 2), "SECTOR": m['SECTOR']})
                
                p_df = pd.DataFrame(p_rows)
                m1, m2, m3 = st.columns(3)
                m1.metric("💰 Total Invested", f"₹{t_inv:,.2f}")
                m2.metric("🏦 Current Value", f"₹{t_cur:,.2f}", delta=f"₹{t_cur-t_inv:,.2f}")
                m3.metric("📈 Portfolio Return", f"{((t_cur-t_inv)/t_inv*100 if t_inv>0 else 0):.2f}%")
                
                st.dataframe(p_df, use_container_width=True, hide_index=True)
                
                # Sector Distribution Chart
                st.markdown("#### Sector Allocation")
                fig = px.pie(p_df, values='QTY', names='SECTOR', hole=0.5, color_discrete_sequence=px.colors.sequential.Greens_r)
                fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300, showlegend=True, template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Portfolio is empty.")

        with p_col_right:
            st.markdown("### ⚙️ Management")
            with st.expander("📥 Add Entry"):
                add_s = st.selectbox("Ticker", sorted(df['SYMBOL'].unique()))
                add_p = st.number_input("Buy Price", step=0.1)
                add_q = st.number_input("Qty", min_value=1)
                if st.button("Add to Portfolio"):
                    portfolio[add_s] = {"price": add_p, "qty": add_q}
                    save_portfolio(portfolio); st.rerun()

            if portfolio:
                with st.expander("📤 Exit Entry"):
                    ex_s = st.selectbox("Exit Ticker", list(portfolio.keys()))
                    ex_q = st.number_input("Sell Qty", min_value=1, max_value=portfolio[ex_s]['qty'])
                    if st.button("Confirm Exit"):
                        m_data = df[df['SYMBOL'] == ex_s].iloc[0]
                        # Log History
                        new_h = pd.DataFrame([{"SYMBOL": ex_s, "BUY": portfolio[ex_s]['price'], "SELL": m_data['PRICE'], "QTY": ex_q, "P&L_%": round(((m_data['PRICE'] - portfolio[ex_s]['price']) / portfolio[ex_s]['price']) * 100, 2), "DATE": str(datetime.date.today())}])
                        new_h.to_csv("trade_history.csv", mode='a', header=not os.path.exists("trade_history.csv"), index=False)
                        # Update Dict
                        if ex_q >= portfolio[ex_s]['qty']: del portfolio[ex_s]
                        else: portfolio[ex_s]['qty'] -= ex_q
                        save_portfolio(portfolio); st.rerun()

    # --- TAB 3: ACTIONABLES ---
    with tabs[2]:
        st.markdown("### ⚡ Critical System Alerts")
        a_left, a_right = st.columns(2)
        
        with a_left:
            st.markdown("#### 🛡️ Risk Management (Holdings)")
            risk_count = 0
            for s, d in portfolio.items():
                m = df[df['SYMBOL'] == s].iloc[0]
                if m['PRICE'] < m['STOP-LOSS'] or m['RSI'] > 78:
                    risk_count += 1
                    color = "#da3633" if m['PRICE'] < m['STOP-LOSS'] else "#d4a017"
                    st.markdown(f'<div class="action-card" style="border-left-color: {color};">🚨 <b>{s}</b>: {"STOP-LOSS HIT" if m["PRICE"] < m["STOP-LOSS"] else "OVERBOUGHT (RSI)"}<br>Price: ₹{m["PRICE"]} | RSI: {m["RSI"]}</div>', unsafe_allow_html=True)
            if risk_count == 0: st.success("✅ All holdings are within safe technical limits.")

        with a_right:
            st.markdown("#### 🎯 Market Opportunities")
            for _, r in top_picks.head(3).iterrows():
                st.markdown(f'<div class="action-card" style="border-left-color: #238636;">💎 <b>{r["SYMBOL"]}</b>: High Conviction ALPHA Pick<br>Score: {r["SCORE"]} | Exp. Gain: {r["EXP_PCT"]}%</div>', unsafe_allow_html=True)

    # --- TAB 4: SUCCESS ---
    with tabs[3]:
        if not history.empty:
            win_rate = (len(history[history['P&L_%'] > 0]) / len(history)) * 100
            st.metric("🎯 Cumulative Win Rate", f"{win_rate:.1f}%")
            
            fig_hist = px.histogram(history, x="P&L_%", color_discrete_sequence=['#238636'])
            fig_hist.update_layout(template="plotly_dark", height=300)
            st.plotly_chart(fig_hist, use_container_width=True)
            
            st.dataframe(history.sort_values("DATE", ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("No trade history found. Exits will be logged here.")
else:
    st.error("Engine data not found.")
    
