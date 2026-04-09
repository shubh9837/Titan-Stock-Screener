import streamlit as st
import pandas as pd
import json, os, datetime

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

# CSS to fix font sizes and spacing
st.markdown("""
    <style>
    /* Reduce Header Font Sizes */
    h1 { font-size: 1.8rem !important; margin-bottom: 0.5rem !important; }
    h2 { font-size: 1.4rem !important; }
    h3 { font-size: 1.1rem !important; color: #a1a1a1; }
    
    /* Shrink Metrics for a cleaner look */
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.85rem !important; }
    
    /* Tighten Metric Containers */
    .stMetric { 
        background-color: #1e2130; 
        border-radius: 8px; 
        padding: 10px 15px !important; 
        border: 1px solid #3e4452; 
    }
    
    /* Shrink Table Font */
    .stDataFrame td, .stDataFrame th { font-size: 0.85rem !important; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=600)
def load_all_data():
    if not os.path.exists("daily_analysis.csv"): return None, None, pd.DataFrame()
    df = pd.read_csv("daily_analysis.csv")
    
    # 1. CLEAN DATA TYPES (Prevents the TypeError)
    # Ensure all sectors are strings and handle empty/NaN values
    df['SECTOR'] = df['SECTOR'].fillna("General").astype(str)
    
    nifty = df[df['SYMBOL'] == "^NSEI"].iloc[0] if "^NSEI" in df['SYMBOL'].values else None
    df = df[df['SYMBOL'] != "^NSEI"]
    
    df['STOP-LOSS'] = (df['PRICE'] * 0.95).round(2)
    df['EXP_PCT'] = (((df['TARGET'] - df['PRICE']) / df['PRICE']) * 100).round(2)
    df['VERDICT'] = df.apply(lambda r: "🔴 EXIT" if r['RSI'] > 78 else ("💎 ALPHA" if r['SCORE'] >= 8 else "🟢 BUY" if r['SCORE'] >= 6 else "🟡 HOLD"), axis=1)
    
    hist = pd.read_csv("trade_history.csv") if os.path.exists("trade_history.csv") else pd.DataFrame()
    return df, nifty, hist

df, nifty, history = load_all_data()

if df is not None:
    tabs = st.tabs(["🚀 Screener", "💼 Portfolio", "⚡ Actionables", "📊 Success"])

    with tabs[0]:
        # --- Industry Header ---
        st.subheader("Industry Performance")
        ind_stats = df.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).round(2)
        
        num_inds = len(ind_stats)
        display_count = min(3, num_inds)
        if display_count > 0:
            m_cols = st.columns(display_count)
            icons = ["🥇", "🥈", "🥉"]
            for i in range(display_count):
                m_cols[i].metric(f"{icons[i]} {ind_stats.index[i]}", f"Score: {ind_stats.values[i]}")
        
        if num_inds > 3:
            with st.expander("Expand to see all Industry Scores"):
                st.table(ind_stats[3:])

        st.divider()
        
        # --- Filters (FIXED TYPEERROR HERE) ---
        c1, c2, c3 = st.columns([2, 1, 1])
        
        # Using sorted(set(...)) with forced string conversion for safety
        available_sectors = sorted([str(x) for x in df['SECTOR'].unique() if x])
        f_ind = c1.multiselect("Filter by Industry", options=available_sectors)
        
        f_score = c2.slider("Min Score Filter", 0, 10, 5)
        f_search = c3.text_input("🔍 Search Ticker")
        
        v_df = df.copy()
        if f_ind: v_df = v_df[v_df['SECTOR'].isin(f_ind)]
        if f_search: v_df = v_df[v_df['SYMBOL'].str.contains(f_search.upper())]
        v_df = v_df[v_df['SCORE'] >= f_score]
        
        st.dataframe(v_df[["SYMBOL", "VERDICT", "SCORE", "PRICE", "TARGET", "STOP-LOSS", "EXP_PCT", "SECTOR", "RSI"]].sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)

    with tabs[1]: # Portfolio Logic
        if os.path.exists("portfolio.json"):
            with open("portfolio.json", "r") as f:
                port_data = json.load(f)
                if port_data:
                    # Logic for displaying your specific portfolio file
                    st.success("Portfolio detected and loaded.")
                    # [Previous portfolio table logic goes here]

else:
    st.error("Engine failed to generate data. Please check Tickers.csv.")
    
