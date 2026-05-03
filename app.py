import streamlit as st
import pandas as pd
from supabase import create_client
import datetime
import numpy as np
import yfinance as yf
import pytz
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="Titan Quantum Pro", layout="wide", page_icon="💎")

# --- UI STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #0E1117; color: #FAFAFA;}
    div[data-testid="stMetric"] { background-color: #1A1C24; border: 1px solid #2D313A; border-radius: 12px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .gem-card { background: linear-gradient(145deg, #1A1C24, #12141A); border: 1px solid #2D313A; border-radius: 12px; padding: 20px; margin-bottom: 15px;}
    .action-card { background: #1A1C24; border-left: 4px solid #00B8FF; padding: 15px; border-radius: 8px; margin-top: 10px; margin-bottom: 10px;}
    .info-box { background: rgba(0, 184, 255, 0.1); border-left: 4px solid #00B8FF; padding: 15px; border-radius: 8px; margin-top: 20px; font-size: 14px;}
    .weather-green { background: rgba(0, 255, 136, 0.1); border: 1px solid #00FF88; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px;}
    .weather-yellow { background: rgba(255, 193, 7, 0.1); border: 1px solid #FFC107; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px;}
    .weather-red { background: rgba(255, 75, 75, 0.1); border: 1px solid #FF4B4B; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px;}
    .macro-text { margin:0px; font-size:14px; font-weight:500; }
    .market-expectation { margin-top: 10px; font-size: 15px; font-weight: 600; color: #E2E8F0; }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE CONNECTIONS ---
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

@st.cache_data(ttl=60) 
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
    
    expected_cols = ['SECTOR', 'EARNINGS_RISK', 'CAP_CATEGORY', 'SUPPORT', 'RESISTANCE', 'PATTERN', 'RR_RATIO', 'RVOL']
    for col in expected_cols:
        if col not in df.columns: 
            if col == 'RVOL': df[col] = 0.0
            else: df[col] = "N/A" if "RISK" in col or "PATTERN" in col else "Unknown" if "SECTOR" in col else 0
            
    df['PRICE'] = pd.to_numeric(df['PRICE'], errors='coerce').fillna(0)
    df['TARGET'] = pd.to_numeric(df['TARGET'], errors='coerce').fillna(0)
    df['STOP_LOSS'] = pd.to_numeric(df['STOP_LOSS'], errors='coerce').fillna(0)
            
    df['UPSIDE_%'] = np.where(df['PRICE'] > 0, ((df['TARGET'] - df['PRICE']) / df['PRICE'] * 100), 0)
    
    risk = df['PRICE'] - df['STOP_LOSS']
    reward = df['TARGET'] - df['PRICE']
    df['RR_RATIO'] = np.where(risk > 0, reward / risk, 0)
    df['RR_RATIO'] = df['RR_RATIO'].clip(lower=0, upper=10.0) 
    
    df['VERDICT'] = df['SCORE'].apply(lambda x: "💎 ALPHA" if x >= 95 else "🟢 BUY" if x >= 75 else "🟡 HOLD" if x >= 40 else "🔴 AVOID")
    df['EST_PERIOD'] = df['SCORE'].apply(lambda x: "5-14 Days" if x >= 85 else "15-30 Days" if x >= 65 else "30-45 Days")
    return df

def get_index_data(ticker_symbol):
    try:
        idx = yf.Ticker(ticker_symbol)
        hist = idx.history(period="5d") 
        if len(hist) >= 2:
            close_tdy = hist['Close'].iloc[-1]
            close_yst = hist['Close'].iloc[-2]
            pct_change = ((close_tdy - close_yst) / close_yst) * 100
            return close_tdy, pct_change
        return None, None
    except: return None, None

def render_interactive_chart(symbol, unique_key_suffix=""):
    try:
        # 1. Fetch data safely
        data = yf.download(f"{symbol}.NS", period="3mo", progress=False)
        
        if data.empty: 
            return st.error(f"Chart data currently unavailable for {symbol}.")
            
        # 2. BULLETPROOF FIX: Flatten columns for newer yfinance versions
        if isinstance(data.columns, pd.MultiIndex):
            data = data.copy()
            data.columns = [col[0] for col in data.columns]
            
        # 3. EXPANDER FIX: Strip timezones so Plotly doesn't turn invisible inside st.expander
        if data.index.tzinfo is not None:
            data.index = data.index.tz_localize(None)

        # 4. Calculate EMAs
        data['EMA20'] = data['Close'].ewm(span=20, adjust=False).mean()
        data['EMA50'] = data['Close'].ewm(span=50, adjust=False).mean()
        
        # 5. Build the chart
        fig = go.Figure(data=[go.Candlestick(
            x=data.index, open=data['Open'], high=data['High'], 
            low=data['Low'], close=data['Close'], name='Price'
        )])
        fig.add_trace(go.Scatter(x=data.index, y=data['EMA20'], line=dict(color='#00B8FF', width=1.5), name='20 EMA'))
        fig.add_trace(go.Scatter(x=data.index, y=data['EMA50'], line=dict(color='#FFC107', width=1.5), name='50 EMA'))
        
        fig.update_layout(
            title=f"{symbol} - Live Technicals", 
            template='plotly_dark', 
            height=400, 
            margin=dict(l=0, r=0, t=40, b=0), 
            xaxis_rangeslider_visible=False
        )
        
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{symbol}_{unique_key_suffix}")
        
    except Exception as e:
        st.error(f"Could not render chart. Engine Error: {str(e)}")

@st.cache_data(ttl=60) 
def get_macro_weather():
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.datetime.now(ist)
        
        if now_ist.hour < 9:
            gift, gift_pct = get_index_data("GIFNIF.NS") 
            sp500, sp_pct = get_index_data("^GSPC")     
            nikkei, nik_pct = get_index_data("^N225")   
            
            direction = gift_pct if gift_pct is not None else sp_pct if sp_pct is not None else 0
            status = "🟢 PRE-MARKET: POSITIVE" if direction > 0.2 else "🔴 PRE-MARKET: NEGATIVE" if direction < -0.2 else "🟡 PRE-MARKET: FLAT / CHOPPY"
            css_class = "weather-green" if direction > 0.2 else "weather-red" if direction < -0.2 else "weather-yellow"
            
            msg = "<b>Live Global Cues:</b> "
            msg += f"GIFT Nifty: {gift:.0f} ({gift_pct:+.2f}%) | " if gift else ""
            msg += f"S&P 500: {sp500:.0f} ({sp_pct:+.2f}%) | " if sp500 else ""
            msg += f"Nikkei: {nikkei:.0f} ({nik_pct:+.2f}%)" if nikkei else ""
            
            expectation = "📈 Expectation: Strong Gap-Up opening." if direction > 0.4 else "↗️ Expectation: Mildly positive opening." if direction > 0.1 else "📉 Expectation: Heavy Gap-Down opening." if direction < -0.4 else "↘️ Expectation: Mildly negative opening." if direction < -0.1 else "⚖️ Expectation: Flat opening expected."
            msg += f"<div class='market-expectation'>{expectation}</div>"
            return status, msg, css_class
            
        else:
            nifty_val, nifty_pct = get_index_data("^NSEI")
            sensex_val, sensex_pct = get_index_data("^BSESN")
            
            nifty_hist = yf.download("^NSEI", period="3mo", progress=False, ignore_tz=True)
            if nifty_hist.empty: return "🟡 UNKNOWN (Live Market)", "Unable to fetch NIFTY data from Yahoo Finance right now.", "weather-yellow"
            
            close_series = nifty_hist['Close']["^NSEI"] if isinstance(nifty_hist.columns, pd.MultiIndex) else nifty_hist['Close']
            close = float(close_series.iloc[-1])
            ema20 = close_series.ewm(span=20, adjust=False).mean().iloc[-1]
            ema50 = close_series.ewm(span=50, adjust=False).mean().iloc[-1]
            
            idx_str = "<b>Live Indices (1-Min Delay):</b> "
            idx_str += f"NIFTY: {nifty_val:.0f} ({nifty_pct:+.2f}%) | " if nifty_val else "NIFTY: Data delayed | "
            idx_str += f"SENSEX: {sensex_val:.0f} ({sensex_pct:+.2f}%)" if sensex_val else "SENSEX: Data delayed"
            
            if close > ema20: return "🟢 RISK OFF (Live Market)", f"{idx_str}<br><div class='market-expectation'>NIFTY is in a strong uptrend. Safe to deploy full sizes.</div>", "weather-green"
            elif close > ema50: return "🟡 CAUTION (Live Market)", f"{idx_str}<br><div class='market-expectation'>NIFTY chopping below 20 EMA. Cut position sizes by 50%.</div>", "weather-yellow"
            else: return "🔴 RISK ON (Live Market)", f"{idx_str}<br><div class='market-expectation'>NIFTY is below 50 EMA. Cash is king. DO NOT take new swing trades.</div>", "weather-red"
    except Exception as e:
        return "🟡 UNKNOWN", "Macro weather currently unavailable due to API limits.", "weather-yellow"

def load_table(table_name):
    res = supabase.table(table_name).select("*").execute()
    return pd.DataFrame(res.data)

df = load_market_data()
port_df = load_table('portfolio')
hist_df = load_table('trade_history')

# BACKWARD COMPATIBILITY
if not port_df.empty and 'owner' not in port_df.columns: port_df['owner'] = "My Portfolio"
if not port_df.empty: port_df['owner'] = port_df['owner'].fillna("My Portfolio")
if not hist_df.empty and 'owner' not in hist_df.columns: hist_df['owner'] = "My Portfolio"
if not hist_df.empty: hist_df['owner'] = hist_df['owner'].fillna("My Portfolio")

# --- SIDEBAR & HEADER ---
with st.sidebar:
    st.markdown("### ⚙️ System Controls")
    if st.button("🔄 Force Live Data Sync", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Last Sync: {datetime.datetime.now().strftime('%H:%M:%S')} (Data refreshes every 60s)")

st.markdown("<h1 style='text-align: center; font-size: 40px; color: #00FF88; margin-bottom: 5px;'>💎 Titan Quantum Pro</h1>", unsafe_allow_html=True)

# --- MACRO WEATHER FILTER ---
status, msg, css_class = get_macro_weather()
st.markdown(f"""
<div class="{css_class}">
    <h3 style='margin:0px;'>{status}</h3>
    <p class='macro-text'>{msg}</p>
</div>
""", unsafe_allow_html=True)

# System Health Alarm
if not df.empty and 'UPDATED_AT' in df.columns:
    try:
        latest_update = pd.to_datetime(df['UPDATED_AT'].max())
        now_utc = datetime.datetime.utcnow()
        delta_hours = (now_utc - latest_update).total_seconds() / 3600
        if delta_hours > 24 and now_utc.weekday() < 5:
            st.error(f"🔴 CRITICAL ALARM: The Master EOD Scan failed to update! Data is {int(delta_hours)} hours old.", icon="🚨")
    except: pass

# --- UI TABS ---
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
            "RVOL": st.column_config.NumberColumn("Vol Spike", format="%.1fx"),
        },
        use_container_width=True, hide_index=True
    )

# ==========================================
# TAB 1: MARKET SCREENER & SECTOR BREADTH
# ==========================================
with tabs[0]:
    if not df.empty:
        inst_df = df[df['CAP_CATEGORY'] != "Small/Penny Cap"]
        
        # --- NEW: TOP-DOWN SECTOR BREADTH HEATMAP ---
        st.subheader("🌍 Sector Breadth Heatmap (Institutional Money Flow)")
        
        # Calculate Breadth: % of stocks in each sector in an Institutional Weekly Uptrend
        breadth_df = inst_df[inst_df['SECTOR'] != 'Unknown'].groupby('SECTOR').agg(
            Total_Stocks=('SYMBOL', 'count'),
            Bullish_Stocks=('INSTITUTIONAL_TREND', lambda x: (x == 'Bullish').sum()),
            Avg_Score=('SCORE', 'mean')
        ).reset_index()
        
        # Calculate the health percentage
        breadth_df['Breadth_%'] = (breadth_df['Bullish_Stocks'] / breadth_df['Total_Stocks']) * 100
        breadth_df = breadth_df[breadth_df['Total_Stocks'] >= 3] # Filter out tiny sectors with < 3 stocks
        breadth_df = breadth_df.sort_values('Breadth_%', ascending=False)
        
        if not breadth_df.empty:
            # Draw the Interactive Treemap
            fig_treemap = px.treemap(
                breadth_df, 
                path=[px.Constant("Indian Market"), 'SECTOR'], 
                values='Total_Stocks',
                color='Breadth_%',
                color_continuous_scale=['#FF4B4B', '#1A1C24', '#00FF88'], # Red -> Black -> Green
                color_continuous_midpoint=50,
                custom_data=['Breadth_%', 'Avg_Score', 'Bullish_Stocks', 'Total_Stocks']
            )
            
            fig_treemap.update_traces(
                hovertemplate="<b>%{label}</b><br>Sector Breadth: %{customdata[0]:.1f}% Bullish<br>Bullish Stocks: %{customdata[2]} / %{customdata[3]}<br>Avg Algo Score: %{customdata[1]:.1f}/100",
                texttemplate="<b>%{label}</b>"
            )
            fig_treemap.update_layout(margin=dict(t=10, l=0, r=0, b=0), height=400, template='plotly_dark')
            st.plotly_chart(fig_treemap, use_container_width=True)
            
        st.markdown("---")
        
        # --- EXISTING SCREENER CONTROLS ---
        c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
        search_q = c1.selectbox("🔍 Search Symbol", ["ALL"] + sorted(inst_df['SYMBOL'].dropna().unique().tolist()))
        min_score = c2.slider("Min Score", 0, 100, 0)
        min_upside = c3.number_input("Min Upside (%)", value=-50) 
        show_alpha = c4.checkbox("💎 High Conviction Only", value=False)
        
        filtered_df = inst_df[(inst_df['SCORE'] >= min_score) & (inst_df['UPSIDE_%'] >= min_upside)]
        if search_q != "ALL": 
            filtered_df = filtered_df[filtered_df['SYMBOL'] == search_q]
            if not filtered_df.empty:
                render_interactive_chart(search_q, "screener")
                
        if show_alpha: filtered_df = filtered_df[filtered_df['VERDICT'].str.contains('💎', na=False)]
        
        st.markdown("---")
        st.subheader(f"📋 Master Screener ({len(filtered_df)})")
        disp_cols = ['VERDICT', 'SCORE', 'SYMBOL', 'SECTOR', 'PATTERN', 'EST_PERIOD', 'PRICE', 'TARGET', 'UPSIDE_%', 'RVOL', 'RR_RATIO', 'SUPPORT', 'RESISTANCE']
        render_df_with_progress(filtered_df, disp_cols)

        st.markdown("---")
        st.subheader("🏢 Top Performing Industries")
        sec_df = inst_df.groupby('SECTOR')['SCORE'].mean().reset_index().sort_values('SCORE', ascending=False)
        sec_df = sec_df[sec_df['SECTOR'] != 'Unknown']
        
        top_3 = sec_df.head(3)
        for _, r in top_3.iterrows():
            with st.expander(f"🏆 {r['SECTOR']} (Avg Score: {r['SCORE']:.1f}/100)"):
                sec_stocks = inst_df[(inst_df['SECTOR'] == r['SECTOR']) & (~inst_df['VERDICT'].str.contains('AVOID', na=False))].sort_values('SCORE', ascending=False).head(3)
                if not sec_stocks.empty:
                    render_df_with_progress(sec_stocks, ['SYMBOL', 'VERDICT', 'SCORE', 'PATTERN', 'EST_PERIOD', 'PRICE', 'TARGET', 'UPSIDE_%'])
                else: st.write("No safe setups found in this sector today.")

        st.divider()
        with st.expander("📖 Comprehensive Dictionary: Candlesticks & Trading Actionables"):
            st.markdown("""
            ### 🕯️ Candlestick Patterns Decoded
            **1. ⚡ Pre-Breakout Squeeze:** Volatility is dead. A violent move is loading. Set a price alert at `Resistance`. Buy if crossed at 2:00 PM.
            **2. 🟢 Bullish Engulfing:** Strong reversal signal. Buy if score is high. Place Stop Loss below yesterday's low.
            **3. Uptrending / Consolidating:** Behaving normally. Buy near `Support`, Sell near `Target`. 
            """)
            
# ==========================================
# TAB 2: BREAKOUT WATCHLIST 
# ==========================================
with tabs[1]:
    st.subheader("⚡ Imminent Pre-Breakouts (> 50 Score)")
    if not df.empty:
        breakouts = df[(df['PATTERN'].str.contains('Squeeze', na=False)) & (df['SCORE'] > 50)]
        if not breakouts.empty:
            render_df_with_progress(breakouts, ['VERDICT', 'SCORE', 'SYMBOL', 'EST_PERIOD', 'PRICE', 'RESISTANCE', 'TARGET', 'UPSIDE_%', 'RVOL'])
            
            st.markdown("---")
            st.markdown("### 🎯 Top Actionable Setups")
            top_breakouts = breakouts.sort_values("SCORE", ascending=False).head(2)
            
            for _, b in top_breakouts.iterrows():
                vol_text = f"Massive volume spike ({b['RVOL']}x average)" if b['RVOL'] > 1.5 else "Waiting for volume confirmation"
                col_info, col_chart = st.columns([1, 1.5])
                
                with col_info:
                    st.markdown(f"""
                    <div class="action-card">
                        <b>{b['SYMBOL']}</b> | Crosses Resistance at <b>₹{b['RESISTANCE']:.2f}</b><br>
                        <i>Why:</i> Score is {b['SCORE']}/100. Upside is {b['UPSIDE_%']:.1f}%.<br>
                        <i>Status:</i> {vol_text}.<br>
                        <b>ACTION PLAN:</b> If CMP > ₹{b['RESISTANCE']:.2f} at 2:00 PM, Buy. Hold for {b['EST_PERIOD']}.
                    </div>
                    """, unsafe_allow_html=True)
                with col_chart:
                    with st.expander(f"📊 View {b['SYMBOL']} Chart"):
                        render_interactive_chart(b['SYMBOL'], "breakout")
        else:
            st.info("No imminent high-quality breakouts detected today.")

# ==========================================
# TAB 3: PORTFOLIO MANAGER & ACTION ENGINE
# ==========================================
with tabs[2]:
    all_owners = port_df['owner'].unique().tolist() if not port_df.empty else []
    if not all_owners: all_owners = ["My Portfolio"] 
    
    st.subheader("🏦 Active Portfolios")
    
    # 1. DYNAMIC EXPANDERS FOR ALL PORTFOLIOS
    for owner in sorted(all_owners):
        active_port = port_df[port_df['owner'] == owner] if not port_df.empty else pd.DataFrame()
        
        with st.expander(f"💼 {owner} Summary & Holdings", expanded=True):
            if not active_port.empty:
                port_calc = []
                for _, row in active_port.iterrows():
                    sym = row['symbol']
                    live_data = df[df['SYMBOL'] == sym] if not df.empty and 'SYMBOL' in df.columns else pd.DataFrame()
                        
                    cmp = float(live_data.iloc[0]['PRICE']) if not live_data.empty else float(row['entry_price'])
                    live_target = float(live_data.iloc[0]['TARGET']) if not live_data.empty else 0.0
                    entry = float(row['entry_price'])
                    
                    # FETCH LOCKED TARGET (Or fallback to live target if it's an old trade without the new DB column)
                    locked_target = float(row.get('entry_target', live_target)) 
                    if pd.isna(locked_target) or locked_target == 0: locked_target = live_target
                    
                    curr_score = float(live_data.iloc[0]['SCORE']) if not live_data.empty else 0
                    
                    try:
                        entry_date = pd.to_datetime(row['date']).date()
                        days_held = (datetime.date.today() - entry_date).days
                    except:
                        days_held = 0
                    
                    # 3-EMA vs 8-EMA Micro-Trend Logic for Momentum Exhaustion
                    momentum_exhausted = False
                    try:
                        hist_1mo = yf.download(f"{sym}.NS", period="1mo", progress=False, ignore_tz=True)
                        if not hist_1mo.empty:
                            close_px = hist_1mo['Close'] if isinstance(hist_1mo.columns, pd.Index) else hist_1mo['Close'].iloc[:, 0]
                            ema3 = close_px.ewm(span=3, adjust=False).mean().iloc[-1]
                            ema8 = close_px.ewm(span=8, adjust=False).mean().iloc[-1]
                            if ema3 < ema8: momentum_exhausted = True
                    except: pass

                    algo_sl = float(live_data.iloc[0]['STOP_LOSS']) if not live_data.empty else (entry * 0.90)
                    if cmp >= (entry * 1.10): trailing_sl = entry * 1.05 
                    elif cmp >= (entry * 1.05): trailing_sl = entry 
                    else: trailing_sl = algo_sl
                    
                    qty = int(row['qty'])
                    invested = entry * qty
                    cur_val = cmp * qty
                    pnl_perc = ((cmp - entry) / entry) * 100
                    cur_profit = qty * (cmp - entry)
                    
                    # --- THE HIERARCHY OF PORTFOLIO ACTIONS ---
                    if cmp <= trailing_sl:
                        action = "🚨 SELL ALL (STOP HIT)"
                    elif locked_target > 0 and cmp >= locked_target:
                        action = "🎯 SCALE OUT 50%"
                    elif locked_target > 0 and cmp >= (locked_target * 0.98):
                        action = "👀 PREPARE TO SELL"
                    elif momentum_exhausted and pnl_perc > 0:
                        action = "⚠️ MOMENTUM EXHAUSTION (TIGHTEN STOP)"
                    elif days_held > 14 and pnl_perc < 2.0:
                        action = "🕰️ TIME CAPITULATION (DEAD MONEY)"
                    else:
                        action = "⏳ HOLD"
                    
                    port_calc.append({
                        "🚨 ACTION": action, "Symbol": sym, "Qty": qty, "Avg Price": entry, "CMP": cmp, 
                        "P&L (%)": pnl_perc, "Profit/ Loss": cur_profit, "Locked Target": locked_target, "Trailing SL": trailing_sl,
                        "Days Held": days_held, "Invested (₹)": invested, "Current (₹)": cur_val
                    })
                    
                pdf = pd.DataFrame(port_calc)
                t_inv, t_cur = pdf['Invested (₹)'].sum(), pdf['Current (₹)'].sum()
                
                c1, c2, c3 = st.columns(3)
                c1.metric("💰 Total Invested", f"₹{t_inv:,.0f}")
                c2.metric("📈 Current Value", f"₹{t_cur:,.0f}", f"₹{t_cur - t_inv:,.0f}")
                c3.metric("🎯 Net P&L", f"{((t_cur - t_inv) / t_inv * 100) if t_inv > 0 else 0:.2f}%")
                
                def style_actions(val):
                    v = str(val).upper()
                    if 'SCALE OUT' in v: return 'color: #00FF88; font-weight: bold;'
                    if 'SELL ALL' in v: return 'color: #FF4B4B; font-weight: bold;'
                    if 'PREPARE' in v or 'MOMENTUM' in v: return 'color: #FFC107; font-weight: bold;'
                    if 'CAPITULATION' in v: return 'color: #A0AEC0; font-weight: bold;'
                    return ''
                    
                def style_pnl(val):
                    if pd.isna(val) or isinstance(val, str): return ''
                    return f"color: {'#00FF88' if val > 0 else '#FF4B4B' if val < 0 else 'white'}"
                    
                st.dataframe(pdf.drop(columns=['Invested (₹)', 'Current (₹)']).style.format({
                    "Avg Price": "{:.2f}", "CMP": "{:.2f}", "P&L (%)": "{:.1f}%", "Locked Target": "{:.2f}", "Trailing SL": "{:.2f}", "Profit/ Loss": "{:.0f}"
                }).map(style_pnl, subset=['P&L (%)']).map(style_actions, subset=['🚨 ACTION']), use_container_width=True, hide_index=True)
            else:
                st.info(f"No active holdings in {owner}.")

# 2. DEEP DIVE ANALYSIS SECTION (FIXED DOM RENDERING)
    st.markdown("---")
    st.subheader("🔍 Deep Dive Analysis")
    
    col_dd1, col_dd2 = st.columns(2)
    dd_owner = col_dd1.selectbox("1. Select Portfolio for Deep Dive", sorted(all_owners))
    dd_df = port_df[port_df['owner'] == dd_owner] if not port_df.empty else pd.DataFrame()
    
    if not dd_df.empty:
        dd_sym = col_dd2.selectbox("2. Select Holding to Analyze", ["-- Select a holding --"] + sorted(dd_df['symbol'].unique().tolist()))
        if dd_sym != "-- Select a holding --" and not df.empty:
            live_data = df[df['SYMBOL'] == dd_sym]
            if not live_data.empty:
                g = live_data.iloc[0]
                
                # --- UPGRADED DEEP DIVE UI CARD ---
                st.markdown(f"""
                <div class="gem-card">
                    <h3 style="margin-top:0px; margin-bottom:15px;">{g['SYMBOL']} <span style="font-size:16px; margin-left:10px;">{g['VERDICT']}</span><span style="font-size:14px; color:#A0AEC0;"> | Score: {g['SCORE']}/100</span></h3>
                    <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
                        <div><p style="margin:0; color:#A0AEC0; font-size:12px; text-transform:uppercase;">Sector</p><p style="margin:0; font-weight:600;">{g['SECTOR']}</p></div>
                        <div><p style="margin:0; color:#A0AEC0; font-size:12px; text-transform:uppercase;">Expected Hold</p><p style="margin:0; font-weight:600;">{g['EST_PERIOD']}</p></div>
                        <div><p style="margin:0; color:#A0AEC0; font-size:12px; text-transform:uppercase;">Volume Spike</p><p style="margin:0; font-weight:600;">{g['RVOL']}x Avg</p></div>
                        <div><p style="margin:0; color:#A0AEC0; font-size:12px; text-transform:uppercase;">Chart Pattern</p><p style="margin:0; font-weight:600;">{g['PATTERN']}</p></div>
                        <div><p style="margin:0; color:#A0AEC0; font-size:12px; text-transform:uppercase;">Algo Target</p><p style="margin:0; font-weight:600; color:#00FF88;">₹{g['TARGET']:.2f} (+{g['UPSIDE_%']:.2f}%)</p></div>
                        <div><p style="margin:0; color:#A0AEC0; font-size:12px; text-transform:uppercase;">Hard Stop Loss</p><p style="margin:0; font-weight:600; color:#FF4B4B;">₹{g['STOP_LOSS']:.2f}</p></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                st.write("") # Invisible buffer to protect the canvas
                render_interactive_chart(dd_sym, "deep_dive_fixed")
    else:
        col_dd2.info("Add stocks to this portfolio to unlock Deep Dive.")
        
    # 3. DYNAMIC ADD / SELL CONTROLS
    st.markdown("---")
    col_add, col_sell = st.columns(2)
    
    with col_add:
        st.markdown("### ➕ Add Trade")
        with st.form("add_trade"):
            a_sym = st.selectbox("Stock Symbol", sorted(df['SYMBOL'].unique().tolist()) if not df.empty else [])
            a_price, a_qty = st.number_input("Buy Price", min_value=0.0, format="%.2f"), st.number_input("Quantity", min_value=1, step=1)
            
            st.markdown("**Assign to Portfolio:**")
            combo_col1, combo_col2 = st.columns(2)
            existing_owner = combo_col1.selectbox("Select Existing", ["➕ Create New Portfolio"] + sorted(all_owners))
            new_owner = combo_col2.text_input("Or Type New Name (If creating new)", placeholder="e.g. Retirement Fund")
            
            if st.form_submit_button("Add to Portfolio"):
                final_add_owner = new_owner.strip() if existing_owner == "➕ Create New Portfolio" else existing_owner
                if final_add_owner and a_sym:
                    # FETCH TARGET TO LOCK IT IN
                    live_stock_data = df[df['SYMBOL'] == a_sym]
                    locked_target = float(live_stock_data['TARGET'].iloc[0]) if not live_stock_data.empty else (a_price * 1.15)
                    
                    supabase.table('portfolio').insert({
                        "symbol": a_sym, "entry_price": a_price, "qty": int(a_qty), 
                        "date": str(datetime.date.today()), "owner": final_add_owner,
                        "entry_target": locked_target  # <-- TARGET LOCKED
                    }).execute()
                    st.rerun()
                    
    with col_sell:
        st.markdown("### ➖ Register Sale")
        sell_owner = st.selectbox("Select Portfolio to Sell From", sorted(all_owners))
        sell_holdings = port_df[port_df['owner'] == sell_owner]['symbol'].unique().tolist() if not port_df.empty else []
        
        with st.form("sell_trade"):
            s_sym = st.selectbox("Stock to Sell", sell_holdings if sell_holdings else ["No Holdings"])
            s_price, s_qty = st.number_input("Sell Price", min_value=0.0, format="%.2f"), st.number_input("Qty to Sell", min_value=1, step=1)
            s_reason = st.selectbox("Reason for Exit", ["Target Hit (Partial/Runner) 🎯", "Trailing SL Hit 🛡️", "Momentum Exhaustion ⚠️", "Time Expiration (Dead Money) ⏳", "Cut Losses Early ✂️", "Manual Exit"])
            
            if st.form_submit_button("Execute Sale") and not port_df.empty and s_sym != "No Holdings":
                holding = port_df[(port_df['symbol'] == s_sym) & (port_df['owner'] == sell_owner)].iloc[0]
                if s_qty <= int(holding['qty']):
                    supabase.table('trade_history').insert({
                        "symbol": s_sym, "sell_price": float(s_price), "qty_sold": int(s_qty), "buy_price": float(holding['entry_price']),
                        "realized_pl": float((s_price - holding['entry_price']) * s_qty), "pl_percentage": float(((s_price - holding['entry_price'])/holding['entry_price'])*100), 
                        "sell_date": str(datetime.date.today()), "exit_reason": s_reason, "owner": sell_owner
                    }).execute()
                    
                    new_qty = int(holding['qty']) - int(s_qty)
                    if new_qty == 0: supabase.table('portfolio').delete().eq('id', holding['id']).execute()
                    else: supabase.table('portfolio').update({"qty": new_qty}).eq('id', holding['id']).execute()
                    st.rerun()

# ==========================================
# TAB 4: SWING GEMS
# ==========================================
with tabs[3]:
    st.subheader("💎 Institutional Swing Gems")
    if not df.empty:
        inst_df = df[df['CAP_CATEGORY'] != "Small/Penny Cap"]
        alpha_gems = inst_df[inst_df['VERDICT'].str.contains('💎', na=False)].sort_values("SCORE", ascending=False).head(10)
        
        if not alpha_gems.empty:
            for _, g in alpha_gems.iterrows():
                st.markdown(f"""
                <div class="gem-card">
                    <h3 style="margin-top:0px;">{g['SYMBOL']} <span style="font-size:14px; color:#A0AEC0;"> | Score: {g['SCORE']}/100 | Hold: {g['EST_PERIOD']}</span></h3>
                    <div style="display:flex; justify-content:space-between;">
                        <p><b>CMP:</b> ₹{g['PRICE']:.2f}</p>
                        <p style="color:#00FF88;"><b>Target:</b> ₹{g['TARGET']:.2f} (+{g['UPSIDE_%']:.2f}%)</p>
                        <p style="color:#FF4B4B;"><b>Stop Loss:</b> ₹{g['STOP_LOSS']:.2f}</p>
                        <p><b>Pattern:</b> {g['PATTERN']}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                with st.expander(f"📊 View {g['SYMBOL']} Chart"):
                    render_interactive_chart(g['SYMBOL'], "gem")
        else:
            st.info("⚠️ No Alpha Gems found right now. The market is currently lacking safe, high-conviction momentum setups.")

# ==========================================
# TAB 5: PENNY / MICRO SANDBOX
# ==========================================
with tabs[4]:
    st.subheader("🎰 High-Risk Penny Sandbox")
    if not df.empty:
        penny_df = df[df['CAP_CATEGORY'] == "Small/Penny Cap"]
        
        if not penny_df.empty:
            p_search = st.selectbox("🔍 Search Penny Symbol", ["ALL"] + sorted(penny_df['SYMBOL'].dropna().unique().tolist()))
            if p_search != "ALL": penny_df = penny_df[penny_df['SYMBOL'] == p_search]
            
            render_df_with_progress(penny_df, ['VERDICT', 'SCORE', 'SYMBOL', 'PATTERN', 'EST_PERIOD', 'PRICE', 'TARGET', 'UPSIDE_%', 'RVOL'])
            
            st.markdown("---")
            st.markdown("### ⚠️ Operator Alert (Actionables)")
            high_vol_penny = penny_df[penny_df['RVOL'] >= 2.0].sort_values("SCORE", ascending=False).head(2)
            
            if not high_vol_penny.empty:
                for _, p in high_vol_penny.iterrows():
                    st.markdown(f"""
                    <div class="action-card">
                        <b>{p['SYMBOL']}</b> is experiencing massive unnatural volume (<b>{p['RVOL']:.1f}x</b> normal activity).<br>
                        <i>Why it matters:</i> Penny stocks only move when operators step in. The algorithm detected heavy accumulation.<br>
                        <b>Action:</b> High risk. If you enter, use strict capital sizing and place a hard Stop Loss at ₹{p['SUPPORT']:.2f}.
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("No suspicious operator volume detected in penny stocks today. Stay out of this segment for now.")
        else:
            st.info("No Penny Stocks processed in the database currently.")

        st.divider()
        with st.expander("🛡️ Penny Stock Survival Guide (Read Before Trading)"):
            st.markdown("""
            ### 🚨 The Reality of Micro-Caps
            Penny stocks do not usually move based on fundamentals or retail buying. They move because **Operators (Whales)** accumulate them quietly and then create artificial volume to trap retail traders.
            * **Volume is Everything:** Never buy a penny stock that is quietly consolidating. Only enter when you see an explosive Volume Spike (`RVOL` > 2.0x).
            * **The Hit & Run Rule:** Do not marry penny stocks. If you get a 15% to 20% pop, secure your profits immediately. 
            * **The 5% Rule:** Penny stocks can gap down violently overnight. Never allocate more than 5% of your total capital to a single penny stock.
            """)

# ==========================================
# TAB 6: HISTORY (Advanced Analytics & Time Insights)
# ==========================================
with tabs[5]:
    hist_owners = hist_df['owner'].unique().tolist() if not hist_df.empty else []
    if not hist_owners: hist_owners = ["My Portfolio"]
    
    col_hist_1, col_hist_2 = st.columns([1, 1])
    owner_choice_hist = col_hist_1.selectbox("👤 Select Account History", sorted(hist_owners))
    active_hist = hist_df[hist_df['owner'] == owner_choice_hist] if not hist_df.empty else pd.DataFrame()

    st.subheader(f"🏆 {owner_choice_hist} Performance & Graveyard")
    
    if not active_hist.empty:
        # 1. Clean Dates for accurate filtering
        active_hist['sell_date'] = pd.to_datetime(active_hist['sell_date']).dt.date
        today = datetime.date.today()
        
        # 2. Dynamic Time Filter UI
        time_filter = col_hist_2.selectbox("📅 Select Time Period", ["All Time", "Today", "This Week (WTD)", "This Month (MTD)", "Financial Year (FYTD)", "Custom Date Range"])
        
        start_date, end_date = None, None
        
        if time_filter == "Today":
            start_date, end_date = today, today
        elif time_filter == "This Week (WTD)":
            start_date = today - datetime.timedelta(days=today.weekday())
            end_date = today
        elif time_filter == "This Month (MTD)":
            start_date = today.replace(day=1)
            end_date = today
        elif time_filter == "Financial Year (FYTD)":
            # Indian FY starts April 1st
            fy_start_year = today.year if today.month >= 4 else today.year - 1
            start_date = datetime.date(fy_start_year, 4, 1)
            end_date = today
        elif time_filter == "Custom Date Range":
            dates = st.date_input("Select Start and End Date", [today - datetime.timedelta(days=30), today])
            if len(dates) == 2:
                start_date, end_date = dates
                
        # 3. Apply the Filter
        filtered_hist = active_hist.copy()
        if start_date and end_date:
            filtered_hist = filtered_hist[(filtered_hist['sell_date'] >= start_date) & (filtered_hist['sell_date'] <= end_date)]
            
        # 4. Calculate Dynamic Metrics
        if not filtered_hist.empty:
            total_trades = len(filtered_hist)
            wins = filtered_hist[filtered_hist['realized_pl'] > 0]
            losses = filtered_hist[filtered_hist['realized_pl'] <= 0]
            
            net_profit = filtered_hist['realized_pl'].sum()
            win_rate = (len(wins) / total_trades) * 100
            avg_win = wins['pl_percentage'].mean() if not wins.empty else 0
            avg_loss = losses['pl_percentage'].mean() if not losses.empty else 0
            
            gross_wins = wins['realized_pl'].sum()
            gross_losses = abs(losses['realized_pl'].sum())
            profit_factor = (gross_wins / gross_losses) if gross_losses > 0 else (10.0 if gross_wins > 0 else 0)

            # 5. Render Metric Cards
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("💰 Net Profit", f"₹{net_profit:,.2f}")
            c2.metric("🎯 Win Rate", f"{win_rate:.1f}%", f"{total_trades} Trades")
            c3.metric("📈 Avg Win", f"{avg_win:+.2f}%")
            c4.metric("📉 Avg Loss", f"{avg_loss:.2f}%")
            c5.metric("⚖️ Profit Factor", f"{profit_factor:.2f}")

            st.markdown("---")
            if 'exit_reason' not in filtered_hist.columns: filtered_hist['exit_reason'] = "N/A"
            
            # Helper to color code the P&L column in the dataframe
            def style_realized_pl(val):
                if pd.isna(val): return ''
                return f"color: {'#00FF88' if val > 0 else '#FF4B4B' if val < 0 else 'white'}"

            # 6. Render Dataframe
            st.dataframe(filtered_hist[['symbol', 'buy_price', 'sell_price', 'pl_percentage', 'realized_pl', 'exit_reason', 'sell_date']].sort_values(by='sell_date', ascending=False).style.format({
                "sell_price": "{:.2f}", "buy_price": "{:.2f}", "realized_pl": "{:.2f}", "pl_percentage": "{:.2f}%"
            }).map(style_realized_pl, subset=['realized_pl']), use_container_width=True, hide_index=True)
            
        else:
            st.info(f"No trades closed during the selected period ({time_filter}).")
    else:
        st.info(f"No trade history available yet for {owner_choice_hist}.")
