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

if not df.empty and 'UPDATED_AT' in df.columns:
    try:
        latest_update_str = df['UPDATED_AT'].max()
        latest_update = pd.to_datetime(latest_update_str)
        now_utc = datetime.datetime.utcnow()
        delta_hours = (now_utc - latest_update).total_seconds() / 3600
        is_market_hours = now_utc.weekday() < 5 and (4 <= now_utc.hour <= 10)
        
        if delta_hours > 24 and now_utc.weekday() < 5:
            st.error(f"🔴 CRITICAL ALARM: The Master EOD Scan failed to update! Data is {int(delta_hours)} hours old.", icon="🚨")
        elif is_market_hours and delta_hours > 1:
            st.warning(f"⚠️ INTRADAY WARNING: The 15-Minute Pulse missed its schedule. Prices may be delayed.", icon="⚠️")
    except:
        pass

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

# TAB 1: MARKET SCREENER 
with tabs[0]:
    if not df.empty:
        # BUG FIX: Match the exact string from master_scan.py
        inst_df = df[df['CAP_CATEGORY'] != "Small/Penny Cap"]
        
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
                sec_stocks = inst_df[(inst_df['SECTOR_STRENGTH'] == r['SECTOR_STRENGTH']) & (inst_df['VERDICT'] != '🔴 AVOID')].sort_values('SCORE', ascending=False).head(3)
                if not sec_stocks.empty:
                    render_df_with_progress(sec_stocks, ['SYMBOL', 'VERDICT', 'SCORE', 'PATTERN', 'PRICE', 'TARGET', 'UPSIDE_%'])
                else: st.write("No safe setups found in this sector today.")
        
        st.markdown("---")
        st.subheader(f"📋 Master Screener ({len(filtered_df)})")
        disp_cols = ['VERDICT', 'SCORE', 'SYMBOL', 'SECTOR_STRENGTH', 'PATTERN', 'PRICE', 'TARGET', 'UPSIDE_%', 'RR_RATIO', 'SUPPORT', 'RESISTANCE', 'EST_PERIOD']
        render_df_with_progress(filtered_df, disp_cols)
        
        st.divider()
        with st.expander("📖 Beginner's Guide: How to read the Screener"):
            st.markdown("""
            ### 🎯 1. The Total Score (0 to 100)
            * **80 to 100 (Alpha Gems):** High momentum. The stock has strong institutional backing and is ready to move. Look for entries near the 'Support' price.
            * **70 to 79 (Buy):** Solid setups, but wait for volume confirmation before entering.
            ### ⚖️ 2. R:R Ratio (Risk to Reward)
            * A ratio of **2.0** means you risk ₹1 to make ₹2. Never take a swing trade if the ratio is below **1.5**. 
            """)

# TAB 2: BREAKOUT WATCHLIST 
with tabs[1]:
    st.subheader("⚡ Imminent Pre-Breakouts")
    if not df.empty:
        breakouts = df[df['PATTERN'] == '⚡ Pre-Breakout Squeeze']
        if not breakouts.empty:
            st.write("These stocks are squeezing tightly below resistance. Watch them closely at 3:15 PM.")
            render_df_with_progress(breakouts, ['VERDICT', 'SCORE', 'SYMBOL', 'CAP_CATEGORY', 'PRICE', 'RESISTANCE', 'TARGET', 'UPSIDE_%'])
        else:
            st.info("No imminent breakouts detected today. The market is likely extended or choppy.")
            
        st.divider()
        with st.expander("📖 Beginner's Guide: How to Trade Pre-Breakouts"):
            st.markdown("""
            ### ⚡ What is a Pre-Breakout Squeeze?
            * The stock's volatility has shrunk to almost zero, and it is hovering just below a major Resistance level. 
            * **Do NOT buy blindly.** Set an alert at the 'Resistance' price. Buy only when it crosses that line with high volume.
            """)

# TAB 3: PORTFOLIO MANAGER
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
            pnl_perc = ((cmp - entry) / entry) * 100
            
            action = "🚨 EXIT (SL)" if cmp <= trailing_sl else "✅ BOOK PROFIT" if cmp >= target else "⏳ HOLD"
            
            port_calc.append({
                "Action": action, "Symbol": sym, "Qty": qty, "Avg Price": entry,
                "CMP": cmp, "Invested (₹)": invested, "Current (₹)": cur_val, 
                "P&L (%)": pnl_perc, "Target": target, "Trailing SL": trailing_sl
            })
            
        pdf = pd.DataFrame(port_calc)
        t_inv, t_cur = pdf['Invested (₹)'].sum(), pdf['Current (₹)'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Invested", f"₹{t_inv:,.2f}")
        c2.metric("📈 Current", f"₹{t_cur:,.2f}", f"₹{t_cur - t_inv:,.2f}")
        c3.metric("🎯 P&L", f"{((t_cur - t_inv) / t_inv * 100) if t_inv > 0 else 0:.2f}%")
        
        st.markdown("---")
        st.subheader("📂 Current Holdings")
        
        total_row = pd.DataFrame([{"Action": "TOTAL", "Symbol": "-", "Qty": "-", "Avg Price": np.nan, "CMP": np.nan, "Invested (₹)": t_inv, "Current (₹)": t_cur, "P&L (%)": ((t_cur - t_inv) / t_inv * 100) if t_inv else 0, "Target": np.nan, "Trailing SL": np.nan}])
        display_pdf = pd.concat([pdf, total_row], ignore_index=True)
        
        def style_pnl(val):
            if pd.isna(val) or isinstance(val, str): return ''
            return f"color: {'#00FF88' if val > 0 else '#FF4B4B' if val < 0 else 'white'}"
            
        st.dataframe(display_pdf.style.format({
            "Avg Price": "{:.2f}", "CMP": "{:.2f}", "Invested (₹)": "{:.2f}", 
            "Current (₹)": "{:.2f}", "P&L (%)": "{:.2f}%", "Target": "{:.2f}", "Trailing SL": "{:.2f}"
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
                    
    st.divider()
    with st.expander("📖 Beginner's Guide: Managing Risk"):
        st.markdown("""
        ### 🛡️ Trailing Stop Losses
        * **Risk-Free Trade:** When your stock goes up >5%, the app moves your Stop Loss to your Buy Price. 
        * **Locking Profits:** When the stock goes up >10%, the SL moves to +5%. Never let a green trade turn red!
        """)

# TAB 4: SWING GEMS
with tabs[3]:
    st.subheader("💎 Institutional Swing Gems")
    if not df.empty:
        # BUG FIX: Match exact string
        inst_df = df[df['CAP_CATEGORY'] != "Small/Penny Cap"]
        alpha_gems = inst_df[inst_df['VERDICT'] == '💎 ALPHA'].sort_values("SCORE", ascending=False).head(10)
        
        # BUG FIX: Added message if no gems are found instead of showing a blank page
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
            
    st.markdown("<div class='info-box'>💡 <b>Guidance:</b> These are the absolute top highest-scoring stocks. They possess perfect trend alignment and zero fundamental earnings risk.</div>", unsafe_allow_html=True)

# TAB 5: PENNY / MICRO SANDBOX
with tabs[4]:
    st.subheader("🎰 High-Risk Penny Sandbox")
    if not df.empty:
        # BUG FIX: Match exact string
        penny_df = df[df['CAP_CATEGORY'] == "Small/Penny Cap"]
        
        if not penny_df.empty:
            c1, c2 = st.columns([1.5, 1])
            p_search = c1.selectbox("Search Micro Cap", ["ALL"] + sorted(penny_df['SYMBOL'].unique().tolist()))
            if p_search != "ALL": penny_df = penny_df[penny_df['SYMBOL'] == p_search]
            render_df_with_progress(penny_df, ['VERDICT', 'SCORE', 'SYMBOL', 'PATTERN', 'PRICE', 'TARGET', 'UPSIDE_%', 'SUPPORT'])
        else:
            st.info("No Penny Stocks processed in the database currently.")
            
    st.divider()
    with st.expander("📖 Beginner's Guide: Surviving Penny Stocks"):
        st.markdown("""
        ### ⚠️ The Manipulation Reality
        * Penny stocks (prices < ₹50) are highly susceptible to manipulation by wealthy operators. Standard indicators often fail here.
        * Only consider trading a penny stock if you see a massive, unexplained explosion in trading volume. No volume = dead money.
        """)

# TAB 6: HISTORY
with tabs[5]:
    st.subheader("🏆 History")
    if not hist_df.empty:
        st.dataframe(hist_df.style.format({
            "sell_price": "{:.2f}", "buy_price": "{:.2f}", "realized_pl": "{:.2f}", "pl_percentage": "{:.2f}%"
        }), use_container_width=True, hide_index=True)
    else:
        st.info("No trades have been sold yet. Your history will appear here once you execute a sale from the Portfolio tab.")
