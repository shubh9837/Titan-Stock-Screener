import streamlit as st
import pandas as pd
from supabase import create_client
import datetime
import numpy as np
import yfinance as yf
import pytz

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
    
    expected_cols = ['SECTOR', 'EARNINGS_RISK', 'CAP_CATEGORY', 'SUPPORT', 'RESISTANCE', 'PATTERN', 'RR_RATIO', 'RVOL']
    for col in expected_cols:
        if col not in df.columns: 
            if col == 'RVOL': df[col] = 0.0
            else: df[col] = "N/A" if "RISK" in col or "PATTERN" in col else "Unknown" if "SECTOR" in col else 0
            
    df['UPSIDE_%'] = ((df['TARGET'] - df['PRICE']) / df['PRICE'] * 100)
    df['VERDICT'] = df['SCORE'].apply(lambda x: "💎 ALPHA" if x >= 85 else "🟢 BUY" if x >= 70 else "🟡 HOLD" if x >= 40 else "🔴 AVOID")
    df['EST_PERIOD'] = df['SCORE'].apply(lambda x: "5-14 Days" if x >= 85 else "15-30 Days" if x >= 65 else "30-45 Days")
    return df

def get_index_data(ticker_symbol):
    try:
        # Fast 2-day pull to get yesterday's close and today's current
        idx = yf.Ticker(ticker_symbol)
        hist = idx.history(period="5d") # Pull 5 days just in case of holidays
        if len(hist) >= 2:
            close_tdy = hist['Close'].iloc[-1]
            close_yst = hist['Close'].iloc[-2]
            pct_change = ((close_tdy - close_yst) / close_yst) * 100
            return close_tdy, pct_change
        return None, None
    except: return None, None

@st.cache_data(ttl=300) # Fast 5-minute cache for live updates
def get_macro_weather():
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.datetime.now(ist)
        
        # PRE-MARKET: Before 9:30 AM IST (Show Global Cues)
        if now_ist.hour < 9 or (now_ist.hour == 9 and now_ist.minute < 30):
            # Try to get GIFT Nifty. yfinance symbol can sometimes be tricky.
            gift, gift_pct = get_index_data("GIFNIF.NS") 
            sp500, sp_pct = get_index_data("^GSPC")      # S&P 500
            nikkei, nik_pct = get_index_data("^N225")    # Nikkei Japan
            
            # Logic to determine the expectation. 
            # We prioritize GIFT Nifty if available, otherwise fallback to S&P 500.
            if gift_pct is not None:
                direction = gift_pct
            elif sp_pct is not None:
                direction = sp_pct
            else:
                direction = 0

            # Determine CSS Class and Status
            status = "🟢 PRE-MARKET: POSITIVE" if direction > 0.2 else "🔴 PRE-MARKET: NEGATIVE" if direction < -0.2 else "🟡 PRE-MARKET: FLAT / CHOPPY"
            css_class = "weather-green" if direction > 0.2 else "weather-red" if direction < -0.2 else "weather-yellow"
            
            # Format the indices string safely
            msg = "<b>Live Global Cues:</b> "
            msg += f"GIFT Nifty: {gift:.0f} ({gift_pct:+.2f}%) | " if gift else ""
            msg += f"S&P 500: {sp500:.0f} ({sp_pct:+.2f}%) | " if sp500 else ""
            msg += f"Nikkei: {nikkei:.0f} ({nik_pct:+.2f}%)" if nikkei else ""
            
            # Format the expectation line
            if direction > 0.4:
                expectation = "📈 Expectation: Strong Gap-Up opening for the Indian market today. Look for profit booking initially."
            elif direction > 0.1:
                expectation = "↗️ Expectation: Mildly positive opening. Market will look for direction in the first hour."
            elif direction < -0.4:
                expectation = "📉 Expectation: Heavy Gap-Down opening. Stay in cash and let the market settle."
            elif direction < -0.1:
                expectation = "↘️ Expectation: Mildly negative opening. Support levels will be tested early."
            else:
                expectation = "⚖️ Expectation: Flat opening expected. Wait for a clear trend to emerge after 10:00 AM."

            msg += f"<div class='market-expectation'>{expectation}</div>"
            
            return status, msg, css_class
            
        # LIVE MARKET: After 9:30 AM IST (Show Domestic Technicals)
        else:
            nifty_val, nifty_pct = get_index_data("^NSEI")
            sensex_val, sensex_pct = get_index_data("^BSESN")
            
            nifty_hist = yf.download("^NSEI", period="3mo", progress=False)
            if nifty_hist.empty: return "UNKNOWN", "Unable to fetch NIFTY data.", "white"
            
            close = float(nifty_hist['Close'].iloc[-1])
            ema20 = nifty_hist['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
            ema50 = nifty_hist['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
            
            idx_str = "<b>Live Indices:</b> "
            idx_str += f"NIFTY: {nifty_val:.0f} ({nifty_pct:+.2f}%) | " if nifty_val else "NIFTY: Data delayed | "
            idx_str += f"SENSEX: {sensex_val:.0f} ({sensex_pct:+.2f}%)" if sensex_val else "SENSEX: Data delayed"
            
            if close > ema20:
                return "🟢 RISK ON (Live Market)", f"{idx_str}<br><div class='market-expectation'>NIFTY is in a strong uptrend (Above 20 EMA). Safe to deploy full position sizes for Swing Trades today.</div>", "weather-green"
            elif close > ema50:
                return "🟡 CAUTION (Live Market)", f"{idx_str}<br><div class='market-expectation'>NIFTY is chopping below 20 EMA but holding 50 EMA. Cut position sizes by 50%. Focus on high-conviction setups only.</div>", "weather-yellow"
            else:
                return "🔴 RISK OFF (Live Market)", f"{idx_str}<br><div class='market-expectation'>NIFTY is below 50 EMA (Downtrend). Cash is king. DO NOT take new swing trades today until the trend reverses.</div>", "weather-red"
    except Exception as e:
        return "UNKNOWN", "Macro weather currently unavailable.", "weather-yellow"

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
    st.caption(f"Last Sync: {datetime.datetime.now().strftime('%H:%M:%S')}")

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
        is_market_hours = now_utc.weekday() < 5 and (4 <= now_utc.hour <= 10)
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
        if search_q != "ALL": filtered_df = filtered_df[filtered_df['SYMBOL'] == search_q]
        if show_alpha: filtered_df = filtered_df[filtered_df['VERDICT'] == '💎 ALPHA']
        
        # --- TOP 3 SECTORS ---
        st.markdown("---")
        st.subheader("🏢 Top Performing Industries")
        sec_df = inst_df.groupby('SECTOR')['SCORE'].mean().reset_index().sort_values('SCORE', ascending=False)
        sec_df = sec_df[sec_df['SECTOR'] != 'Unknown']
        
        top_3 = sec_df.head(3)
        for _, r in top_3.iterrows():
            with st.expander(f"🏆 {r['SECTOR']} (Avg Score: {r['SCORE']:.1f}/100)"):
                sec_stocks = inst_df[(inst_df['SECTOR'] == r['SECTOR']) & (inst_df['VERDICT'] != '🔴 AVOID')].sort_values('SCORE', ascending=False).head(3)
                if not sec_stocks.empty:
                    render_df_with_progress(sec_stocks, ['SYMBOL', 'VERDICT', 'SCORE', 'PATTERN', 'PRICE', 'TARGET', 'UPSIDE_%'])
                else: st.write("No safe setups found in this sector today.")
        
        st.markdown("---")
        st.subheader(f"📋 Master Screener ({len(filtered_df)})")
        disp_cols = ['VERDICT', 'SCORE', 'SYMBOL', 'SECTOR', 'PATTERN', 'PRICE', 'TARGET', 'UPSIDE_%', 'RVOL', 'RR_RATIO', 'SUPPORT', 'RESISTANCE']
        render_df_with_progress(filtered_df, disp_cols)

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
    st.subheader("⚡ Imminent Pre-Breakouts")
    if not df.empty:
        breakouts = df[df['PATTERN'] == '⚡ Pre-Breakout Squeeze']
        if not breakouts.empty:
            render_df_with_progress(breakouts, ['VERDICT', 'SCORE', 'SYMBOL', 'PRICE', 'RESISTANCE', 'TARGET', 'UPSIDE_%', 'RVOL'])
            
            st.markdown("---")
            st.markdown("### 🎯 High-Conviction Actionables (The 2:00 PM Strategy)")
            top_breakouts = breakouts.sort_values("SCORE", ascending=False).head(3)
            
            for _, b in top_breakouts.iterrows():
                vol_text = f"Massive volume spike ({b['RVOL']}x average)" if b['RVOL'] > 1.5 else "Waiting for volume confirmation"
                st.markdown(f"""
                <div class="action-card">
                    <b>{b['SYMBOL']}</b> | Crosses Resistance at <b>₹{b['RESISTANCE']:.2f}</b><br>
                    <i>Why:</i> Institutional momentum score is {b['SCORE']}/100. Upside potential is {b['UPSIDE_%']:.1f}%.<br>
                    <i>Status:</i> {vol_text}.<br>
                    <b>ACTION PLAN:</b> Look at this stock at 2:00 PM. If the CMP is higher than ₹{b['RESISTANCE']:.2f}, execute a Swing Buy. Hold for days until target hits.
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No imminent breakouts detected today. The market is likely extended or choppy.")

# ==========================================
# TAB 3: PORTFOLIO MANAGER
# ==========================================
with tabs[2]:
    if not port_df.empty:
        st.subheader("🏦 Portfolio Summary")
        port_calc = []
        for _, row in port_df.iterrows():
            sym = row['symbol']
            live_data = df[df['SYMBOL'] == sym]
            cmp = float(live_data.iloc[0]['PRICE']) if not live_data.empty else float(row['entry_price'])
            target = float(live_data.iloc[0]['TARGET']) if not live_data.empty else 0.0
            
            entry = float(row['entry_price'])
            original_sl = float(live_data.iloc[0]['STOP_LOSS']) if not live_data.empty else 0.0
            
            if cmp > (entry * 1.05): trailing_sl = entry
            elif cmp > (entry * 1.10): trailing_sl = entry * 1.05
            else: trailing_sl = original_sl
            
            qty = int(row['qty'])
            invested = entry * qty
            cur_val = cmp * qty
            target_val = target * qty 
            pnl_perc = ((cmp - entry) / entry) * 100
            
            action = "🚨 EXIT (SL)" if cmp <= trailing_sl else "✅ BOOK PROFIT" if cmp >= target else "⏳ HOLD"
            
            port_calc.append({
                "Action": action, "Symbol": sym, "Qty": qty, "Avg Price": entry,
                "CMP": cmp, "Invested (₹)": invested, "Current (₹)": cur_val, "Target Value (₹)": target_val,
                "P&L (%)": pnl_perc, "Target": target, "Trailing SL": trailing_sl
            })
            
        pdf = pd.DataFrame(port_calc)
        t_inv, t_cur, t_proj = pdf['Invested (₹)'].sum(), pdf['Current (₹)'].sum(), pdf['Target Value (₹)'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Invested", f"₹{t_inv:,.2f}")
        c2.metric("📈 Current Value", f"₹{t_cur:,.2f}", f"₹{t_cur - t_inv:,.2f}")
        c3.metric("🎯 P&L", f"{((t_cur - t_inv) / t_inv * 100) if t_inv > 0 else 0:.2f}%")
        c4.metric("🚀 Projected (At Target)", f"₹{t_proj:,.2f}")
        
        st.markdown("---")
        st.markdown("### 📋 Executive Action Plan")
        exits = pdf[pdf['Action'] == '🚨 EXIT (SL)']['Symbol'].tolist()
        profits = pdf[pdf['Action'] == '✅ BOOK PROFIT']['Symbol'].tolist()
        
        if not exits and not profits:
            st.success("✅ **STATUS CLEAR:** All portfolio stocks are safely within bounds. No action required today. Let the winners ride.")
        if profits:
            st.success(f"🎯 **TAKE PROFIT:** The following stocks have hit their algorithm targets: **{', '.join(profits)}**. Consider selling 50% to lock in gains.")
        if exits:
            st.error(f"🚨 **STOP LOSS BREACHED:** The following stocks have broken technical support: **{', '.join(exits)}**. Sell immediately to preserve capital.")

        st.markdown("---")
        st.subheader("📂 Current Holdings")
        
        total_row = pd.DataFrame([{"Action": "TOTAL", "Symbol": "-", "Qty": "-", "Avg Price": np.nan, "CMP": np.nan, "Invested (₹)": t_inv, "Current (₹)": t_cur, "Target Value (₹)": t_proj, "P&L (%)": ((t_cur - t_inv) / t_inv * 100) if t_inv else 0, "Target": np.nan, "Trailing SL": np.nan}])
        display_pdf = pd.concat([pdf, total_row], ignore_index=True)
        
        def style_pnl(val):
            if pd.isna(val) or isinstance(val, str): return ''
            return f"color: {'#00FF88' if val > 0 else '#FF4B4B' if val < 0 else 'white'}"
            
        st.dataframe(display_pdf.style.format({
            "Avg Price": "{:.2f}", "CMP": "{:.2f}", "Invested (₹)": "{:.2f}", 
            "Current (₹)": "{:.2f}", "Target Value (₹)": "{:.2f}", "P&L (%)": "{:.2f}%", "Target": "{:.2f}", "Trailing SL": "{:.2f}"
        }, na_rep="-").map(style_pnl, subset=['P&L (%)']), use_container_width=True, hide_index=True)

    else: 
        st.info("🏦 Portfolio is empty. Add a trade below to start tracking your progress.")

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
            if st.form_submit_button("Execute Sale") and not port_df.empty:
                holding = port_df[port_df['symbol'] == s_sym].iloc[0]
                if s_qty <= int(holding['qty']):
                    supabase.table('trade_history').insert({
                        "symbol": s_sym, "sell_price": float(s_price), "qty_sold": int(s_qty), "buy_price": float(holding['entry_price']),
                        "realized_pl": float((s_price - holding['entry_price']) * s_qty), "pl_percentage": float(((s_price - holding['entry_price'])/holding['entry_price'])*100), "sell_date": str(datetime.date.today())
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
        alpha_gems = inst_df[inst_df['VERDICT'] == '💎 ALPHA'].sort_values("SCORE", ascending=False).head(10)
        
        if not alpha_gems.empty:
            for _, g in alpha_gems.iterrows():
                st.markdown(f"""
                <div class="gem-card">
                    <h3 style="margin-top:0px;">{g['SYMBOL']} <span style="font-size:14px; color:#A0AEC0;"> | Score: {g['SCORE']}/100</span></h3>
                    <div style="display:flex; justify-content:space-between;">
                        <p><b>CMP:</b> ₹{g['PRICE']:.2f}</p>
                        <p style="color:#00FF88;"><b>Target:</b> ₹{g['TARGET']:.2f} (+{g['UPSIDE_%']:.2f}%)</p>
                        <p style="color:#FF4B4B;"><b>Stop Loss:</b> ₹{g['STOP_LOSS']:.2f}</p>
                        <p><b>Pattern:</b> {g['PATTERN']}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
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
            render_df_with_progress(penny_df, ['VERDICT', 'SCORE', 'SYMBOL', 'PATTERN', 'PRICE', 'TARGET', 'UPSIDE_%', 'RVOL'])
            
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

# ==========================================
# TAB 6: HISTORY
# ==========================================
with tabs[5]:
    st.subheader("🏆 History")
    if not hist_df.empty:
        st.dataframe(hist_df.style.format({
            "sell_price": "{:.2f}", "buy_price": "{:.2f}", "realized_pl": "{:.2f}", "pl_percentage": "{:.2f}%"
        }), use_container_width=True, hide_index=True)
