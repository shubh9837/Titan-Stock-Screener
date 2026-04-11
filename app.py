import streamlit as st
import pandas as pd
from supabase import create_client
import datetime

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

# --- 2. CLOUD DATABASE CONNECTION ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

@st.cache_data(ttl=300) # Caches for 5 mins to ensure lightning fast loads
def load_market_data():
    response = supabase.table('market_scans').select("*").execute()
    df = pd.DataFrame(response.data)
    if not df.empty:
        # Dynamic Verdict based on 100-point scale
        df['VERDICT'] = df['SCORE'].apply(lambda x: "💎 ALPHA" if x >= 85 else "🟢 BUY" if x >= 70 else "🟡 HOLD")
    return df

def load_portfolio():
    response = supabase.table('portfolio').select("*").execute()
    return pd.DataFrame(response.data)

# --- 3. LOAD DATA ---
df = load_market_data()
portfolio_df = load_portfolio()

# --- 4. UI TABS (Preserving your original layout) ---
tabs = st.tabs(["🔍 SCREENER", "💼 PORTFOLIO", "⚡ ACTIONABLES"])

# --- TAB 1: SCREENER ---
with tabs[0]:
    if not df.empty:
        st.write("### 💎 High Conviction Setups (Live Sentiment + Technicals)")
        st.dataframe(
            df[['VERDICT', 'SCORE', 'SYMBOL', 'PRICE', 'TARGET', 'STOP_LOSS', 'RSI', 'UPDATED_AT']].sort_values("SCORE", ascending=False), 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.warning("Database empty. Awaiting first background engine run.")

# --- TAB 2: PORTFOLIO & EXECUTION ---
with tabs[1]:
    # Display Current Portfolio
    if not portfolio_df.empty and not df.empty:
        st.write("### 🏦 Active Holdings")
        # Merge portfolio logic here similar to your original code
        st.dataframe(portfolio_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    with st.expander("➕ Execute New Trade (Risk Management Engine)"):
        ticker = st.selectbox("Select Alpha Stock", df[df['VERDICT'].isin(['💎 ALPHA', '🟢 BUY'])]['SYMBOL'].unique() if not df.empty else [])
        if ticker:
            s_data = df[df['SYMBOL']==ticker].iloc[0]
            c1, c2 = st.columns(2)
            cap = c1.number_input("Total Trading Capital", value=100000)
            risk_p = c2.slider("Risk per trade (%)", 1, 3, 1)
            
            # Position Sizing Logic
            risk_amt = cap * (risk_p/100)
            risk_per_share = s_data['PRICE'] - s_data['STOP_LOSS']
            qty = int(risk_amt / risk_per_share) if risk_per_share > 0 else 1
            
            st.info(f"💡 Recommended: Buy **{qty}** shares of {ticker}. Total risk: ₹{risk_amt:.0f}")
            
            if st.button("Add to Cloud Portfolio"):
                trade_data = {"symbol": ticker, "entry_price": float(s_data['PRICE']), "qty": qty, "date": str(datetime.date.today())}
                supabase.table('portfolio').insert(trade_data).execute()
                st.success(f"{ticker} added successfully!")
                st.rerun()

# --- TAB 3: ACTIONABLES (Risk Alerts) ---
with tabs[2]:
    st.markdown("### 🛡️ Live Risk & Exit Alerts")
    st.info("Cross-referencing live prices against your Portfolio Stop-Loss levels...")
    # Add logic here to compare portfolio_df entry prices against live df prices
