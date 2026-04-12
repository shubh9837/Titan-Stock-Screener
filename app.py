import streamlit as st
import pandas as pd
from supabase import create_client
import datetime
import numpy as np

st.set_page_config(page_title="Titan Quantum Pro", layout="wide", page_icon="💎")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #0E1117; color: #FAFAFA;}
    div[data-testid="stMetric"] { background-color: #1A1C24; border: 1px solid #2D313A; border-radius: 12px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .gem-card { background: linear-gradient(145deg, #1A1C24, #12141A); border: 1px solid #2D313A; border-radius: 12px; padding: 20px; margin-bottom: 15px;}
    .action-card-red { background: rgba(255, 75, 75, 0.1); border-left: 4px solid #FF4B4B; padding: 15px; border-radius: 8px; margin-bottom: 10px;}
    .action-card-green { background: rgba(0, 255, 136, 0.1); border-left: 4px solid #00FF88; padding: 15px; border-radius: 8px; margin-bottom: 10px;}
    .info-box { background: rgba(0, 184, 255, 0.1); border-left: 4px solid #00B8FF; padding: 15px; border-radius: 8px; margin-top: 20px; font-size: 14px;}
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

@st.cache_data(ttl=300)
def load_market_data():
    all_data, limit, offset = [], 1000, 0
    while True:
        res = supabase.table('market_scans').select("*").range(offset, offset + limit - 1).execute()
        if not res.data: break
        all_data.extend(res.data)
        if len(res.data) < limit: break
        offset += limit
        
    df = pd.DataFrame(all_data)
    if df.empty: return df
    
    expected_cols = ['SECTOR_STRENGTH', 'EARNINGS_RISK', 'CAP_CATEGORY', 'SUPPORT', 'RESISTANCE', 'PATTERN', 'RR_RATIO']
    for col in expected_cols:
        if col not in df.columns: df[col] = "N/A" if "RISK" in col or "PATTERN" in col else "Unknown" if "SECTOR" in col else 0
            
    df['UPSIDE_%'] = ((df['TARGET'] - df['PRICE']) / df['PRICE'] * 100)
    df['VERDICT'] = df['SCORE'].apply(lambda x: "💎 ALPHA" if x >= 85 else "🟢 BUY" if x >= 70 else "🟡 HOLD" if x >= 40 else "🔴 AVOID")
    df['EST_PERIOD'] = df['SCORE'].apply(lambda x: "5-14 Days" if x >= 85 else "15-30 Days" if x >= 65 else "30-45 Days")
    return df

def load_table(table_name):
    res = supabase.table(table_name).select("*").execute()
    return pd.DataFrame(res.data)

df = load_market_data()
port_df = load_table('portfolio')
hist_df = load_table('trade_history')

with st.sidebar:
    st.markdown("### ⚙️ System Controls")
    if st.button("🔄 Force Live Data Sync", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Last Sync: {datetime.datetime.now().strftime('%H:%M:%S')}")

st.markdown("<h1 style='text-align: center; font-size: 40px; color: #00FF88; margin-bottom: 0px;'>💎 Titan Quantum Pro</h1>", unsafe_allow_html=True)

# --- SYSTEM HEALTH HEARTBEAT ---
if not df.empty and 'UPDATED_AT' in df.columns:
    try:
        latest_update_str = df['UPDATED_AT'].max()
        latest_update = pd.to_datetime(latest_update_str)
        now_utc = datetime.datetime.utcnow()
        
        delta_hours = (now_utc - latest_update).total_seconds() / 3600
        is_market_hours = now_utc.weekday() < 5 and (4 <= now_utc.hour <= 10)
        
        if delta_hours > 24 and now_utc.weekday() < 5:
            st.error(f"🔴 CRITICAL ALARM: The Master EOD Scan failed to update! Data is {int(delta_hours)} hours old. Please check GitHub Actions logs immediately.", icon="🚨")
        elif is_market_hours and delta_hours > 1:
            st.warning(f"⚠️ INTRADAY WARNING: The 15-Minute Pulse has missed its schedule. Live prices may be delayed by {int(delta_hours * 60)} minutes.", icon="⚠️")
    except:
        pass

# 6 Tabs
tabs = st.tabs(["📊 Market Screener", "🎯 Breakout Watchlist", "💼 Portfolio", "🚀 Swing Gems", "🎰 Penny Sandbox", "🏆 History"])

def render_df_with_progress(data, cols_to_show):
    st.dataframe(
        data[cols_to_show].sort_values("SCORE", ascending=False),
        column_config={
            "SCORE": st.column_config.ProgressColumn("Score (0-100)", format="%f", min_value=0, max_value=100),
            "PRICE": st.column_config.NumberColumn("CMP (₹)", format="%.2f"),
            "TARGET": st.column_config.NumberColumn("Target (₹)", format="%.2f"),
            "UPSIDE_%": st.column_config.NumberColumn("Upside %", format="%.2f%%"),
            "RR_RATIO": st.column_config.NumberColumn("R:R Ratio", format="1:%.2f"),
            "SUPPORT": st.column_config.NumberColumn("Support", format="%.2f"),
            "RESISTANCE": st.column_config.NumberColumn("Resistance", format="%.2f"),
        },
        use_container_width=True, hide_index=True
    )

# ==========================================
# TAB 1: MARKET SCREENER 
# ==========================================
with tabs[0]:
    if not df.empty:
        inst_df = df[df['CAP_CATEGORY'] != "Penny / Micro Cap"]
        
        c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
        search_q = c1.selectbox("🔍 Search Symbol", ["ALL"] + sorted(inst_df['SYMBOL'].dropna().unique().tolist()))
        min_score = c2.slider("Min Score", 0, 100, 0)
        min_upside = c3.number_input("Min Upside (%)", value=-50) 
        show_alpha = c4.checkbox("💎 High Conviction Only", value=False)
        
        filtered_df = inst_df[(inst_df['SCORE'] >= min_score) & (inst_df['UPSIDE_%'] >= min_upside)]
        if search_q != "ALL": filtered_df = filtered_df[filtered_df['SYMBOL'] == search_q]
        if show_alpha: filtered_df = filtered_df[filtered_df['VERDICT'] == '💎 ALPHA']
        
        st.markdown("---")
        st.subheader("🏢 Top Performing Industries")
        sec_df = inst_df.groupby('SECTOR_STRENGTH')['SCORE'].mean().reset_index().sort_values('SCORE', ascending=False)
        sec_df = sec_df[sec_df['SECTOR_STRENGTH'] != 'Unknown']
        
        top_3 = sec_df.head(3)
        for _, r in top_3.iterrows():
            with st.expander(f"🏆 {r['SECTOR_STRENGTH']} (Avg Score: {r['SCORE']:.1f}/100)"):
                st.write("**Top 3 Swing Opportunities:**")
                sec_stocks = inst_df[(inst_df['SECTOR_STRENGTH'] == r['SECTOR_STRENGTH']) & (inst_df['VERDICT'] != '🔴 AVOID')].sort_values('SCORE', ascending=False).head(3)
                if not sec_stocks.empty:
                    render_df_with_progress(sec_stocks, ['SYMBOL', 'VERDICT', 'SCORE', 'PATTERN', 'PRICE', 'TARGET', 'UPSIDE_%'])
                else: st.write("No safe setups found.")
        
        st.markdown("---")
        st.subheader(f"📋 Master Screener ({len(filtered_df)})")
        disp_cols = ['VERDICT', 'SCORE', 'SYMBOL', 'SECTOR_STRENGTH', 'PATTERN', 'PRICE', 'TARGET', 'UPSIDE_%', 'RR_RATIO', 'SUPPORT', 'RESISTANCE', 'EST_PERIOD']
        render_df_with_progress(filtered_df, disp_cols)
        
        # EDUCATIONAL BLOCK - SCREENER
        st.divider()
        with st.expander("📖 Beginner's Guide: How to read the Screener & pick Swing Trades"):
            st.markdown("""
            ### 🎯 1. The Total Score (0 to 100)
            * **80 to 100 (Alpha Gems):** High momentum. The stock has strong institutional backing and is ready to move. Look for entries near the 'Support' price.
            * **70 to 79 (Buy):** Solid setups, but wait for volume confirmation before entering.
            
            ### 📊 2. RSI (Relative Strength Index)
            * **Below 40:** Oversold. The stock is beaten down and might bounce, but lacks current momentum.
            * **50 to 70:** The "Sweet Spot" for Breakouts. The stock is strong and climbing.
            * **Above 75:** Overbought. The stock has rallied too hard. Wait for a pullback; do not buy at the absolute top.
            
            ### ⚖️ 3. R:R Ratio (Risk to Reward)
            * This tells you if the trade is mathematically worth taking. 
            * A ratio of **2.0** means you are risking ₹1 to make ₹2. 
            * **Rule of Thumb:** Never take a swing trade if the R:R Ratio is below **1.5**. 
            """)

# ==========================================
# TAB 2: BREAKOUT WATCHLIST 
# ==========================================
with tabs[1]:
    st.subheader("⚡ Imminent Pre-Breakouts")
    if not df.empty:
        breakouts = df[df['PATTERN'] == '⚡ Pre-Breakout Squeeze']
        if not breakouts.empty:
            st.write("These stocks are currently squeezing tightly right below their resistance line with rising MACD momentum. Watch these closely at 3:15 PM for entry.")
            render_df_with_progress(breakouts, ['VERDICT', 'SCORE', 'SYMBOL', 'CAP_CATEGORY', 'PRICE', 'RESISTANCE', 'TARGET', 'UPSIDE_%'])
        else:
            st.success("No imminent breakouts detected today. The market is likely extended or choppy.")
            
        # EDUCATIONAL BLOCK - BREAKOUTS
        st.divider()
        with st.expander("📖 Beginner's Guide: How to Trade Pre-Breakouts"):
            st.markdown("""
            ### ⚡ What is a Pre-Breakout Squeeze?
            * The stock's volatility has shrunk to almost zero (Bollinger Bands are pinching), and it is hovering just below a major **Resistance** level. It is acting like a coiled spring.
            
            ### 🎯 How to Trade It
            * **Do NOT buy blindly.** A squeeze can break out upwards or downwards. 
            * **The Trigger:** Set an alert at the 'Resistance' price. If the stock crosses that price with high trading volume, buy immediately.
            
            ### 🕯️ Candlestick Confirmation
            * Look for a **🟢 Bullish Engulfing** candle on the chart. This means buyers have completely overwhelmed sellers today, confirming the breakout direction is upwards.
            """)

# ==========================================
# TAB 3: PORTFOLIO MANAGER
