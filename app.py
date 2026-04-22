import streamlit as st
import pandas as pd
from supabase import create_client
import datetime
import numpy as np
import yfinance as yf
import pytz
import plotly.graph_objects as go

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

# BUG FIX: Added strict dynamic keys to prevent Streamlit rendering crashes in loops
def render_interactive_chart(symbol, unique_key_suffix=""):
    try:
        data = yf.download(f"{symbol}.NS", period="3mo", progress=False, ignore_tz=True)
        if data.empty: return st.error("Chart data unavailable.")
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)
            
        data['EMA20'] = data['Close'].ewm(span=20, adjust=False).mean()
        data['EMA50'] = data['Close'].ewm(span=50, adjust=False).mean()
        
        fig = go.Figure(data=[go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name='Price')])
        fig.add_trace(go.Scatter(x=data.index, y=data['EMA20'], line=dict(color='#00B8FF', width=1.5), name='20 EMA'))
        fig.add_trace(go.Scatter(x=data.index, y=data['EMA50'], line=dict(color='#FFC107', width=1.5), name='50 EMA'))
        
        fig.update_layout(title=f"{symbol} - Live Technicals", template='plotly_dark', height=400, margin=dict(l=0, r=0, t=40, b=0), xaxis_rangeslider_visible=False)
        
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{symbol}_{unique_key_suffix}")
    except Exception as e:
        st.error("Could not load chart.")

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
            
            if close > ema20: return "🟢 RISK ON (Live Market)", f"{idx_str}<br><div class='market-expectation'>NIFTY is in a strong uptrend. Safe to deploy full sizes.</div>", "weather-green"
            elif close > ema50: return "🟡 CAUTION (Live Market)", f"{idx_str}<br><div class='market-expectation'>NIFTY chopping below 20 EMA. Cut position sizes by 50%.</div>", "weather-yellow"
            else: return "🔴 RISK OFF (Live Market)", f"{idx_str}<br><div class='market-expectation'>NIFTY is below 50 EMA. Cash is king. DO NOT take new swing trades.</div>", "weather-red"
    except Exception as e:
        return "🟡 UNKNOWN", "Macro weather currently unavailable due to API limits.", "weather-yellow"

def load_table(table_name):
    res = supabase.table(table_name).select("*").execute()
    return pd.DataFrame(res.data)

df = load_market_data()
port_df = load_table('portfolio')
hist_df = load_table('trade_history')

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
# TAB 1: MARKET SCREENER 
# ==========================================
with tabs[0]:
    if not df.empty:
        inst_df = df[df['CAP_CATEGORY'] != "Small/Penny Cap"]
        
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
                
        # BUG FIX: Safely match partial string to avoid space/unicode issues
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
            The algorithm reads price action to assign a label. Here is exactly what to do when you see them:
            
            **1. ⚡ Pre-Breakout Squeeze**
            * **Meaning:** The stock's volatility is dead (Bollinger Bands are pinching tight). It is resting just below a major ceiling (Resistance). A violent move is loading.
            * **Actionable:** Do NOT buy immediately. Set a price alert on your broker at the exact `Resistance` price. If it crosses that price at 2:00 PM with volume, buy.
            
            **2. 🟢 Bullish Engulfing**
            * **Meaning:** The green candle body completely swallowed yesterday's red candle. Institutional buyers stepped in forcefully to stop the stock from falling further.
            * **Actionable:** This is a strong reversal signal. If the `Score` is above 70, this is a safe entry point. Place your Stop Loss exactly below yesterday's low.
            
            **3. Uptrending / Consolidating**
            * **Meaning:** The stock is behaving normally within its mathematical averages. No sudden shocks.
            * **Actionable:** Buy near the `Support` price. Sell near the `Target`. 
            
            ### ⏳ Intraday vs. Swing Trading
            * **Do NOT close these trades on the same day.** If an alert triggers at 2:00 PM, you are buying the *ignition* of a move. These setups are designed to be held for **3 to 15 days** (Swing Trading) to let the trend play out fully. Let the Trailing Stop Loss manage your exit.
            """)

# ==========================================
# TAB 2: BREAKOUT WATCHLIST 
# ==========================================
with tabs[1]:
    st.subheader("⚡ Imminent Pre-Breakouts (> 50 Score)")
    if not df.empty:
        breakouts = df[(df['PATTERN'] == '⚡ Pre-Breakout Squeeze') & (df['SCORE'] > 50)]
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
# TAB 3: PORTFOLIO MANAGER
# ==========================================
with tabs[2]:
    if not port_df.empty:
        st.subheader("🏦 Portfolio Summary & Dynamic Health")
        port_calc = []
        for _, row in port_df.iterrows():
            sym = row['symbol']
            live_data = df[df['SYMBOL'] == sym] if not df.empty and 'SYMBOL' in df.columns else pd.DataFrame()
                
            cmp = float(live_data.iloc[0]['PRICE']) if not live_data.empty else float(row['entry_price'])
            target = float(live_data.iloc[0]['TARGET']) if not live_data.empty else 0.0
            entry = float(row['entry_price'])
            
            health_status = "🟢 Healthy Uptrend"
            if not live_data.empty:
                curr_score = float(live_data.iloc[0]['SCORE'])
                pattern = live_data.iloc[0]['PATTERN']
                if curr_score < 40: health_status = "🔴 Momentum Dead (Consider Exit)"
                elif "Consolidating" in pattern: health_status = "🟡 Choppy/Sideways"

            algo_sl = float(live_data.iloc[0]['STOP_LOSS']) if not live_data.empty else (entry * 0.90)
            if cmp >= (entry * 1.10): trailing_sl = entry * 1.05 
            elif cmp >= (entry * 1.05): trailing_sl = entry 
            else: trailing_sl = algo_sl
            
            qty = int(row['qty'])
            invested = entry * qty
            cur_val = cmp * qty
            target_val = target * qty 
            pnl_perc = ((cmp - entry) / entry) * 100
            
            action = "🚨 EXIT (SL/Trend Broken)" if cmp <= trailing_sl or "Dead" in health_status else "✅ BOOK PROFIT" if cmp >= target else "⏳ HOLD"
            
            port_calc.append({
                "Action": action, "Symbol": sym, "Qty": qty, "Avg Price": entry, "CMP": cmp, 
                "Health Status": health_status, "P&L (%)": pnl_perc, "Target": target, "Trailing SL": trailing_sl,
                "Invested (₹)": invested, "Current (₹)": cur_val
            })
            
        pdf = pd.DataFrame(port_calc)
        t_inv, t_cur = pdf['Invested (₹)'].sum(), pdf['Current (₹)'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Total Invested", f"₹{t_inv:,.2f}")
        c2.metric("📈 Current Value", f"₹{t_cur:,.2f}", f"₹{t_cur - t_inv:,.2f}")
        c3.metric("🎯 Net P&L", f"{((t_cur - t_inv) / t_inv * 100) if t_inv > 0 else 0:.2f}%")
        
        st.markdown("---")
        def style_pnl(val):
            if pd.isna(val) or isinstance(val, str): return ''
            return f"color: {'#00FF88' if val > 0 else '#FF4B4B' if val < 0 else 'white'}"
            
        st.dataframe(pdf.drop(columns=['Invested (₹)', 'Current (₹)']).style.format({
            "Avg Price": "{:.2f}", "CMP": "{:.2f}", "P&L (%)": "{:.2f}%", "Target": "{:.2f}", "Trailing SL": "{:.2f}"
        }).map(style_pnl, subset=['P&L (%)']), use_container_width=True, hide_index=True)

    else: 
        st.info("🏦 Portfolio is empty.")

    st.markdown("---")
    col_add, col_sell = st.columns(2)
    with col_add:
        with st.form("add_trade"):
            a_sym = st.selectbox("➕ Add Stock Symbol", sorted(df['SYMBOL'].unique().tolist()) if not df.empty else [])
            a_price, a_qty = st.number_input("Buy Price", min_value=0.0, format="%.2f"), st.number_input("Quantity", min_value=1, step=1)
            if st.form_submit_button("Add to Portfolio") and a_sym:
                supabase.table('portfolio').insert({"symbol": a_sym, "entry_price": a_price, "qty": int(a_qty), "date": str(datetime.date.today())}).execute()
                st.rerun()
                    
    with col_sell:
        with st.form("sell_trade"):
            s_sym = st.selectbox("➖ Register Sale", port_df['symbol'].unique() if not port_df.empty else [])
            s_price, s_qty = st.number_input("Sell Price", min_value=0.0, format="%.2f"), st.number_input("Qty to Sell", min_value=1, step=1)
            s_reason = st.selectbox("Reason for Exit", ["Target Hit 🎯", "Trailing SL Hit 🛡️", "Trend/EMA Broken 📉", "Cut Losses Early ✂️", "Manual/Time Exit ⏳"])
            
            if st.form_submit_button("Execute Sale") and not port_df.empty:
                holding = port_df[port_df['symbol'] == s_sym].iloc[0]
                if s_qty <= int(holding['qty']):
                    supabase.table('trade_history').insert({
                        "symbol": s_sym, "sell_price": float(s_price), "qty_sold": int(s_qty), "buy_price": float(holding['entry_price']),
                        "realized_pl": float((s_price - holding['entry_price']) * s_qty), "pl_percentage": float(((s_price - holding['entry_price'])/holding['entry_price'])*100), 
                        "sell_date": str(datetime.date.today()), "exit_reason": s_reason
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
        
        # BUG FIX: Safe string match for Alpha Gems
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
            * **The 5% Rule:** Penny stocks can gap down violently overnight. Never allocate more than 5% of your total trading capital to a single penny stock.
            * **Respect the Stop Loss:** If a penny stock loses its technical support, the operators have abandoned it. Sell instantly without hesitation.
            """)

# ==========================================
# TAB 6: HISTORY (Advanced Analytics)
# ==========================================
with tabs[5]:
    st.subheader("🏆 Institutional Performance & Graveyard")
    if not hist_df.empty:
        total_trades = len(hist_df)
        wins = hist_df[hist_df['realized_pl'] > 0]
        losses = hist_df[hist_df['realized_pl'] <= 0]
        
        win_rate = (len(wins) / total_trades) * 100
        avg_win = wins['pl_percentage'].mean() if not wins.empty else 0
        avg_loss = losses['pl_percentage'].mean() if not losses.empty else 0
        profit_factor = abs(wins['realized_pl'].sum() / losses['realized_pl'].sum()) if not losses.empty else 10.0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Win Rate", f"{win_rate:.1f}%")
        c2.metric("Avg Win", f"{avg_win:+.1f}%")
        c3.metric("Avg Loss", f"{avg_loss:.1f}%")
        c4.metric("Profit Factor", f"{profit_factor:.2f}")

        st.markdown("---")
        if 'exit_reason' not in hist_df.columns: hist_df['exit_reason'] = "N/A"
        
        st.dataframe(hist_df[['symbol', 'buy_price', 'sell_price', 'pl_percentage', 'realized_pl', 'exit_reason', 'sell_date']].style.format({
            "sell_price": "{:.2f}", "buy_price": "{:.2f}", "realized_pl": "{:.2f}", "pl_percentage": "{:.2f}%"
        }), use_container_width=True, hide_index=True)
    else:
        st.info("No trade history available yet.")
