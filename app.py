import streamlit as st
import pandas as pd
from supabase import create_client
import datetime
import numpy as np
import plotly.express as px

# --- 1. CONFIG & CUSTOM UI STYLING ---
st.set_page_config(page_title="Titan Quantum Pro", layout="wide", page_icon="💎")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #0E1117; color: #FAFAFA;}
    div[data-testid="stMetric"] { background-color: #1A1C24; border: 1px solid #2D313A; border-radius: 12px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .gem-card { background: linear-gradient(145deg, #1A1C24, #12141A); border: 1px solid #2D313A; border-radius: 12px; padding: 20px; margin-bottom: 15px; transition: transform 0.2s;}
    .gem-card:hover { transform: translateY(-5px); border-color: #00FF88;}
    .action-card-red { background: rgba(255, 75, 75, 0.1); border-left: 4px solid #FF4B4B; padding: 15px; border-radius: 8px; margin-bottom: 10px;}
    .action-card-green { background: rgba(0, 255, 136, 0.1); border-left: 4px solid #00FF88; padding: 15px; border-radius: 8px; margin-bottom: 10px;}
    h1, h2, h3 { color: #FFFFFF !important; font-weight: 600 !important;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE CONNECTION ---
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# --- 3. DATA FETCHING (PAGINATED FOR 2000+ STOCKS) ---
@st.cache_data(ttl=300)
def load_market_data():
    all_data = []
    limit = 1000
    offset = 0
    
    # Loop to bypass Supabase's default 1,000 row API limit
    while True:
        res = supabase.table('market_scans').select("*").range(offset, offset + limit - 1).execute()
        if not res.data:
            break
        all_data.extend(res.data)
        if len(res.data) < limit:
            break
        offset += limit
        
    df = pd.DataFrame(all_data)
    if df.empty: return df
    
    df['SECTOR_STRENGTH'] = df['SECTOR_STRENGTH'].fillna("Unknown")
    df['EARNINGS_RISK'] = df['EARNINGS_RISK'].fillna("✅ Clear")
    df['CAP_CATEGORY'] = df['CAP_CATEGORY'].fillna("Unknown")
    
    df['UPSIDE_%'] = ((df['TARGET'] - df['PRICE']) / df['PRICE'] * 100)
    df['VERDICT'] = df['SCORE'].apply(lambda x: "💎 ALPHA" if x >= 85 else "🟢 BUY" if x >= 70 else "🟡 HOLD" if x >= 40 else "🔴 AVOID")
    df['EST_PERIOD'] = df['SCORE'].apply(lambda x: "1-2 Weeks" if x > 85 else "3-5 Weeks" if x > 65 else "6+ Weeks")
    
    # Strict 2-decimal formatting for all numerics
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].round(2)
    
    return df

def load_table(table_name):
    res = supabase.table(table_name).select("*").execute()
    return pd.DataFrame(res.data)

df = load_market_data()
port_df = load_table('portfolio')
hist_df = load_table('trade_history')

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.markdown("### ⚙️ System Controls")
    if st.button("🔄 Force Live Data Sync", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown("---")
    st.caption(f"Last Database Sync: {datetime.datetime.now().strftime('%H:%M:%S')}")

# --- 4. TABS SETUP ---
st.markdown("<h1 style='text-align: center; font-size: 45px; color: #00FF88; margin-bottom: 0px;'>💎 Swing Trading & Portfolio Management Dashboard</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 18px; color: #A0AEC0; margin-bottom: 30px;'>Institutional-Grade Algorithmic Execution System</p>", unsafe_allow_html=True)

tabs = st.tabs(["📊 Market Screener", "💼 Portfolio", "🚀 Swing Gems", "🎰 Penny / Micro Sandbox", "🏆 Success History"])

# ==========================================
# TAB 1: MARKET SCREENER (Institutional Only)
# ==========================================
with tabs[0]:
    if not df.empty:
        # Isolate Institutional Universe (Exclude Penny)
        inst_df = df[df['CAP_CATEGORY'] != "Penny / Micro Cap"]
        
        c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
        all_symbols = ["ALL"] + sorted(inst_df['SYMBOL'].dropna().unique().tolist())
        search_q = c1.selectbox("🔍 Search Stock Symbol", all_symbols)
        min_score = c2.slider("Minimum Confluence Score", 0, 100, 0)
        min_upside = c3.number_input("Min Expected Upside (%)", min_value=-100, value=-50) 
        show_alpha = c4.checkbox("💎 Show Only High Conviction", value=False)
        
        filtered_df = inst_df[(inst_df['SCORE'] >= min_score) & (inst_df['UPSIDE_%'] >= min_upside)]
        if search_q != "ALL": filtered_df = filtered_df[filtered_df['SYMBOL'] == search_q]
        if show_alpha: filtered_df = filtered_df[filtered_df['VERDICT'] == '💎 ALPHA']
        
        st.markdown("---")
        st.subheader("🏢 Institutional Industry Strength")
        ind_toggle = st.radio("View Top Industries as:", ["📊 Graph", "📋 Table"], horizontal=True)
        
        sec_df = inst_df.groupby('SECTOR_STRENGTH')['SCORE'].mean().reset_index().sort_values('SCORE', ascending=False).round(2)
        sec_df.columns = ['Industry / Sector', 'Avg Confluence Score']
        
        if "Graph" in ind_toggle:
            fig2 = px.bar(sec_df, x='Industry / Sector', y='Avg Confluence Score', color='Avg Confluence Score', 
                          color_continuous_scale='Viridis', height=350, template="plotly_dark")
            fig2.update_layout(margin=dict(l=0, r=0, t=0, b=0), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.dataframe(sec_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader(f"📋 Institutional Opportunities ({len(filtered_df)} found)")
        display_cols = ['VERDICT', 'SCORE', 'SYMBOL', 'CAP_CATEGORY', 'SECTOR_STRENGTH', 'PRICE', 'TARGET', 'UPSIDE_%', 'STOP_LOSS', 'EST_PERIOD', 'EARNINGS_RISK']
        st.dataframe(filtered_df[display_cols].sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Database empty. Awaiting Master Scan.")

# ==========================================
# TAB 2: PORTFOLIO MANAGER
# ==========================================
with tabs[1]:
    if not port_df.empty:
        st.subheader("🏦 Portfolio Summary")
        port_calc = []
        for _, row in port_df.iterrows():
            sym = row['symbol']
            live_data = df[df['SYMBOL'] == sym]
            cmp = live_data.iloc[0]['PRICE'] if not live_data.empty else row['entry_price']
            target = live_data.iloc[0]['TARGET'] if not live_data.empty else 0
            sl = live_data.iloc[0]['STOP_LOSS'] if not live_data.empty else 0
            score = live_data.iloc[0]['SCORE'] if not live_data.empty else "N/A"
            est_period = live_data.iloc[0]['EST_PERIOD'] if not live_data.empty else "N/A"
            
            qty = int(row['qty']) # Strict Whole Number
            invested = row['entry_price'] * qty
            cur_val = cmp * qty
            pnl_perc = ((cmp - row['entry_price']) / row['entry_price']) * 100
            
            if cmp <= sl: action = "🚨 EXIT (SL)"
            elif cmp >= target: action = "✅ BOOK PROFIT"
            else: action = "⏳ HOLD"
            
            port_calc.append({
                "Action": action, "Symbol": sym, "Score": score, "Qty": qty, "Avg Price": round(float(row['entry_price']), 2),
                "CMP": round(float(cmp), 2), "Invested (₹)": round(invested, 2), "Current (₹)": round(cur_val, 2), 
                "P&L (%)": round(pnl_perc, 2), "Target": round(float(target), 2), "Stop Loss": round(float(sl), 2), "Est. Period": est_period
            })
            
        pdf = pd.DataFrame(port_calc)
        t_inv, t_cur = pdf['Invested (₹)'].sum(), pdf['Current (₹)'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Total Invested", f"₹{t_inv:,.2f}")
        c2.metric("📈 Current Value", f"₹{t_cur:,.2f}", f"₹{t_cur - t_inv:,.2f}")
        c3.metric("🎯 Overall P&L", f"{((t_cur - t_inv) / t_inv * 100) if t_inv > 0 else 0:.2f}%")
        
        st.markdown("---")
        st.subheader("📂 Current Holdings")
        
        total_row = pd.DataFrame([{
            "Action": "TOTAL", "Symbol": "-", "Score": "-", "Qty": "-", "Avg Price": "-", "CMP": "-",
            "Invested (₹)": round(t_inv, 2), "Current (₹)": round(t_cur, 2), "P&L (%)": round(((t_cur - t_inv) / t_inv * 100), 2) if t_inv else 0,
            "Target": "-", "Stop Loss": "-", "Est. Period": "-"
        }])
        display_pdf = pd.concat([pdf, total_row], ignore_index=True)
        
        def style_pnl(val):
            if isinstance(val, str): return ''
            color = '#00FF88' if val > 0 else '#FF4B4B' if val < 0 else 'white'
            return f'color: {color}'
            
        st.dataframe(display_pdf.style.map(style_pnl, subset=['P&L (%)']), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("⚡ Urgent Portfolio Actions")
        action_found = False
        for _, r in pdf.iterrows():
            if r['Action'] == "🚨 EXIT (SL)":
                st.markdown(f"<div class='action-card-red'><b>{r['Symbol']}</b> has breached Stop Loss (₹{r['Stop Loss']}). Current Price: ₹{r['CMP']}. Exit recommended.</div>", unsafe_allow_html=True)
                action_found = True
            elif r['Action'] == "✅ BOOK PROFIT":
                st.markdown(f"<div class='action-card-green'><b>{r['Symbol']}</b> has reached Target (₹{r['Target']}). Consider booking profits!</div>", unsafe_allow_html=True)
                action_found = True
        if not action_found: st.success("All holdings are currently within safe zones.")
    else:
        st.info("Portfolio is empty. Add a trade below!")

    st.markdown("---")
    col_add, col_sell = st.columns(2)
    with col_add:
        with st.expander("➕ Add New Trade"):
            with st.form("add_trade"):
                available_symbols = sorted(df['SYMBOL'].unique().tolist()) if not df.empty else []
                a_sym = st.selectbox("Select Stock Symbol", available_symbols)
                a_price = st.number_input("Buy Price", min_value=0.0, format="%.2f")
                a_qty = st.number_input("Quantity", min_value=1, step=1)
                if st.form_submit_button("Add to Portfolio"):
                    if a_sym:
                        supabase.table('portfolio').insert({"symbol": a_sym, "entry_price": a_price, "qty": int(a_qty), "date": str(datetime.date.today())}).execute()
                        st.success("Trade Added!")
                        st.rerun()
                    
    with col_sell:
        with st.expander("➖ Register Sale (Full/Partial)"):
            if not port_df.empty:
                with st.form("sell_trade"):
                    s_sym = st.selectbox("Select Holding to Sell", port_df['symbol'].unique())
                    s_price = st.number_input("Selling Price", min_value=0.0, format="%.2f")
                    s_qty = st.number_input("Quantity to Sell", min_value=1, step=1)
                    if st.form_submit_button("Execute Sale"):
                        holding = port_df[port_df['symbol'] == s_sym].iloc[0]
                        if s_qty > int(holding['qty']): st.error("Cannot sell more than you own!")
                        else:
                            realized = round((s_price - holding['entry_price']) * s_qty, 2)
                            perc = round(((s_price - holding['entry_price'])/holding['entry_price'])*100, 2)
                            supabase.table('trade_history').insert({
                                "symbol": s_sym, "sell_price": s_price, "qty_sold": int(s_qty), "buy_price": round(holding['entry_price'], 2),
                                "realized_pl": realized, "pl_percentage": perc, "sell_date": str(datetime.date.today())
                            }).execute()
                            
                            new_qty = int(holding['qty']) - int(s_qty)
                            if new_qty == 0:
                                supabase.table('portfolio').delete().eq('id', holding['id']).execute()
                            else:
                                supabase.table('portfolio').update({"qty": new_qty}).eq('id', holding['id']).execute()
                            st.success("Sale Registered!")
                            st.rerun()

# ==========================================
# TAB 3: SWING GEMS
# ==========================================
with tabs[2]:
    st.subheader("💎 Institutional Market Gems")
    st.write("Highest confluence scores from Mid, Small, and Large Cap stocks.")
    if not df.empty:
        inst_df = df[df['CAP_CATEGORY'] != "Penny / Micro Cap"]
        gems = inst_df[inst_df['VERDICT'] == '💎 ALPHA'].sort_values("SCORE", ascending=False).head(10)
        if gems.empty:
            gems = inst_df.sort_values("SCORE", ascending=False).head(5) 
            
        for _, g in gems.iterrows():
            st.markdown(f"""
            <div class="gem-card">
                <h3 style="margin-top:0px;">{g['SYMBOL']} <span style="font-size:14px; color:#A0AEC0;"> | Score: {g['SCORE']}/100</span></h3>
                <div style="display:flex; justify-content:space-between;">
                    <p><b>CMP:</b> ₹{g['PRICE']}</p>
                    <p style="color:#00FF88;"><b>Target:</b> ₹{g['TARGET']} (+{g['UPSIDE_%']:.2f}%)</p>
                    <p style="color:#FF4B4B;"><b>Stop Loss:</b> ₹{g['STOP_LOSS']}</p>
                    <p><b>Expected Time:</b> {g['EST_PERIOD']}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            with st.expander(f"View Deep Dive for {g['SYMBOL']}"):
                st.write(f"**Market Cap:** {g['CAP_CATEGORY']}")
                st.write(f"**Sector Trend:** {g['SECTOR_STRENGTH']}")
                st.write(f"**Earnings Risk:** {g['EARNINGS_RISK']}")
                st.write(f"**RSI Momentum:** {g['RSI']}")
    else:
        st.info("Awaiting data to generate gems.")

# ==========================================
# TAB 4: PENNY / MICRO SANDBOX
# ==========================================
with tabs[3]:
    st.subheader("🎰 High-Risk Penny & Micro-Cap Sandbox")
    st.warning("These stocks are highly volatile, susceptible to manipulation, and carry severe illiquidity risks. Trade with strict capital allocation limits.")
    
    if not df.empty and 'CAP_CATEGORY' in df.columns:
        penny_df = df[df['CAP_CATEGORY'] == "Penny / Micro Cap"]
        
        c1, c2 = st.columns([1.5, 1])
        all_penny = ["ALL"] + sorted(penny_df['SYMBOL'].unique().tolist())
        p_search = c1.selectbox("Search Micro Cap", all_penny, key="penny_search")
        
        if p_search != "ALL": penny_df = penny_df[penny_df['SYMBOL'] == p_search]
        
        st.dataframe(penny_df[['VERDICT', 'SCORE', 'SYMBOL', 'SECTOR_STRENGTH', 'PRICE', 'TARGET', 'UPSIDE_%', 'STOP_LOSS']].sort_values("SCORE", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Awaiting Data Update...")

# ==========================================
# TAB 5: SUCCESS HISTORY
# ==========================================
with tabs[4]:
    st.subheader("🏆 Trading Performance History")
    if not hist_df.empty:
        wins = len(hist_df[hist_df['realized_pl'] > 0])
        total_trades = len(hist_df)
        win_rate = (wins / total_trades) * 100
        net_pl = hist_df['realized_pl'].sum()
        
        c1, c2 = st.columns(2)
        c1.metric("🎯 Historical Win Rate", f"{win_rate:.1f}%")
        c2.metric("💰 Total Realized P&L", f"₹{net_pl:,.2f}")
        
        st.markdown("---")
        st.write("**Closed Trades Log**")
        st.dataframe(hist_df.sort_values('sell_date', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("No closed trades yet. Sell a holding to start building your track record!")
