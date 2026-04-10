import streamlit as st
import pandas as pd
import json, os, datetime

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #0d1117; }
    
    /* Ultra-Compact Top Picks Bar */
    .top-pick-bar {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 8px 15px;
        margin-bottom: 20px;
        display: flex;
        gap: 20px;
        overflow-x: auto;
        white-space: nowrap;
    }
    .pick-item {
        font-size: 0.85rem;
        border-right: 1px solid #30363d;
        padding-right: 20px;
    }
    .pick-item:last-child { border-right: none; }
    
    div[data-testid="stMetric"] { background-color: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 12px !important; }
    .stDataFrame { border: 1px solid #30363d; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=600)
def load_all_data():
    if not os.path.exists("daily_analysis.csv"): return None, pd.DataFrame()
    df = pd.read_csv("daily_analysis.csv")
    # Derived Columns
    df['STOP-LOSS'] = (df['PRICE'] * 0.95).round(2)
    df['EXP_PCT'] = (((df['TARGET'] - df['PRICE']) / df['PRICE']) * 100).round(2)
    # Ensure Score is rounded for display
    df['SCORE'] = df['SCORE'].round(1)
    # Logic-based Verdict
    df['VERDICT'] = df.apply(lambda r: "💎 ALPHA" if r['SCORE'] >= 8 else "🟢 BUY" if r['SCORE'] >= 6 else "🟡 HOLD", axis=1)
    df.loc[df['RSI'] > 78, 'VERDICT'] = "🔴 EXIT"
    hist = pd.read_csv("trade_history.csv") if os.path.exists("trade_history.csv") else pd.DataFrame()
    return df, hist

df, history = load_all_data()

if df is not None:
    tabs = st.tabs(["🔍 SCREENER", "💼 PORTFOLIO", "⚡ ACTIONABLES", "🏆 SUCCESS"])

    # --- TAB 1: SCREENER (COMPACT REDESIGN) ---
    with tabs[0]:
        # 1. Industry Dropdown with Scores in Label
        ind_stats = df.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False)
        ind_options = ["All Sectors"] + [f"{sector} ({score:.1f})" for sector, score in ind_stats.items()]
        
        selected_option = st.selectbox("📂 Select Sector (Technical Strength)", ind_options)
        selected_ind = selected_option.split(" (")[0] if selected_option != "All Sectors" else "All"

        # 2. Single-Line Top Picks (High Conviction)
        filtered_df = df.copy()
        if selected_ind != "All":
            filtered_df = filtered_df[filtered_df['SECTOR'] == selected_ind]
            
        top_picks = filtered_df[filtered_df['SCORE'] >= 8.5].sort_values("EXP_PCT", ascending=False).head(6)
        
        if not top_picks.empty:
            pick_html = '<div class="top-pick-bar">'
            for _, r in top_picks.iterrows():
                pick_html += f"""
                <div class="pick-item">
                    <b style="color:#58a6ff;">{r['SYMBOL']}</b> | 
                    <span style="color:#4CAF50;">₹{r['PRICE']:.2f}</span> | 
                    <span style="color:#8b949e;">Exp: {r['EXP_PCT']:.1f}%</span> | 
                    <b>⭐ {r['SCORE']}</b>
                </div>
                """
            pick_html += '</div>'
            st.markdown(pick_html, unsafe_allow_html=True)
        else:
            st.caption("No high-conviction ALPHA setups in this sector currently.")

        # 3. Search and Table
        search = st.text_input("🔍 Search Ticker...", placeholder="RELIANCE, HDFC, etc.")
        if search:
            filtered_df = filtered_df[filtered_df['SYMBOL'].str.contains(search.upper())]

        # Reordered Table Columns: Verdict & Score first
        display_cols = [
            "VERDICT", "SCORE", "SYMBOL", "PRICE", "TARGET", 
            "EXP_PCT", "STOP-LOSS", "RSI", "SECTOR", "DEBT_EQUITY", "VOL_SURGE"
        ]
        
        st.dataframe(
            filtered_df[display_cols].sort_values("SCORE", ascending=False),
            use_container_width=True, hide_index=True
        )

    # --- TAB 2: PORTFOLIO ---
    with tabs[1]:
        # Portfolio logic stays consistent with management console
        st.markdown("### 💼 Active Management")
        # [Existing Portfolio code here...]

    # --- TAB 3: ACTIONABLES ---
    with tabs[2]:
        st.markdown("### ⚡ Critical Insights")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🛡️ Portfolio Risk")
            # Logic for Risk alerts
        with col2:
            st.markdown("#### 🎯 Fresh Breakouts")
            # Logic for Volume Surges

    # --- TAB 4: SUCCESS ---
    with tabs[3]:
        if not history.empty:
            st.metric("🎯 Win Rate", f"{(len(history[history['P&L_%'] > 0])/len(history)*100):.2f}%")
            st.dataframe(history.sort_values("DATE", ascending=False), use_container_width=True, hide_index=True)
else:
    st.error("Engine data not found.")
