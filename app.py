import streamlit as st
import pandas as pd
import json, os, datetime

st.set_page_config(page_title="Quantum-Sentinel Pro", layout="wide")

# --- DATA HELPERS ---
def load_data():
    if not os.path.exists("daily_analysis.csv"): return None, pd.DataFrame()
    df = pd.read_csv("daily_analysis.csv")
    df['STOP-LOSS'] = (df['PRICE'] * 0.96).round(2) # 4% SL for Swing
    df['EXPECTED_%'] = (((df['TARGET'] - df['PRICE']) / df['PRICE']) * 100).round(2)
    
    def get_holding(row):
        if row['VOL_SURGE'] > 2: return "1-3 Days (Aggressive)"
        if row['RSI'] > 60: return "1-2 Weeks (Swing)"
        return "2-4 Weeks (Positional)"
    
    df['HOLDING_PERIOD'] = df.apply(get_holding, axis=1)
    
    hist = pd.read_csv("trade_history.csv") if os.path.exists("trade_history.csv") else pd.DataFrame(columns=["SYMBOL", "BUY_PRICE", "SELL_PRICE", "P&L_%", "DATE"])
    return df, hist

def get_verdict(row):
    if row['RSI'] > 78: return "🔴 EXIT (OVERBOUGHT)"
    if row['SCORE'] >= 8 and row['VOL_SURGE'] > 1.2: return "💎 ALPHA BUY"
    if row['SCORE'] >= 6: return "🟢 BUY"
    return "🟡 HOLD"

# --- INIT ---
analysis, history = load_data()

# --- APP LAYOUT ---
st.title("🛡️ Quantum-Sentinel: Titan Pro")

if analysis is not None:
    analysis['VERDICT'] = analysis.apply(get_verdict, axis=1)
    tabs = st.tabs(["🚀 Screener", "💼 Portfolio", "⚡ Actionables", "📊 Success Rate"])

    # --- TAB 1: SCREENER ---
    with tabs[0]:
        st.subheader("Industry Leaderboard")
        top_inds = analysis.groupby('SECTOR')['SCORE'].mean().sort_values(ascending=False).head(3)
        cols = st.columns(3)
        for i, (sector, val) in enumerate(top_inds.items()):
            cols[i].metric(sector, f"Score: {val:.1f}")
        
        st.divider()
        c1, c2, c3 = st.columns([2, 1, 1])
        ind_list = ["ALL"] + sorted(analysis['SECTOR'].unique().tolist())
        selected_ind = c1.selectbox("Filter Industry", ind_list)
        search = c2.text_input("🔍 Search Stock")
        alpha_only = c3.toggle("Show Alpha Only")
        
        disp_df = analysis.copy()
        if selected_ind != "ALL": disp_df = disp_df[disp_df['SECTOR'] == selected_ind]
        if search: disp_df = disp_df[disp_df['SYMBOL'].str.contains(search.upper())]
        if alpha_only: disp_df = disp_df[disp_df['VERDICT'] == "💎 ALPHA BUY"]
        
        st.dataframe(disp_df[["SYMBOL", "VERDICT", "SCORE", "PRICE", "TARGET", "STOP-LOSS", "EXPECTED_%", "HOLDING_PERIOD", "VOL_SURGE"]], use_container_width=True, hide_index=True)

    # --- TAB 2: PORTFOLIO ---
    with tabs[1]:
        if not os.path.exists("portfolio.json"): 
            with open("portfolio.json", "w") as f: json.dump({}, f)
            
        with st.expander("➕ Add New Trade"):
            f1, f2, f3 = st.columns(3)
            new_s = f1.selectbox("Symbol", analysis['SYMBOL'].unique())
            new_p = f2.number_input("Entry Price", format="%.2f")
            new_q = f3.number_input("Quantity", min_value=1)
            if st.button("Log Trade"):
                with open("portfolio.json", "r+") as f:
                    data = json.load(f)
                    data[new_s] = {"price": new_p, "qty": new_q}
                    f.seek(0); json.dump(data, f); f.truncate()
                st.rerun()

        with open("portfolio.json", "r") as f: port = json.load(f)
        if port:
            p_list = []
            for s, info in port.items():
                m = analysis[analysis['SYMBOL'] == s].iloc[0]
                p_list.append({"SYMBOL": s, "QTY": info['qty'], "AVG": info['price'], "CMP": m['PRICE'], "P&L %": round(((m['PRICE']-info['price'])/info['price'])*100, 2), "VERDICT": m['VERDICT'], "RSI": m['RSI']})
            
            st.dataframe(pd.DataFrame(p_list), use_container_width=True, hide_index=True)
            
            # CLEARANCE LOGIC
            st.divider()
            to_sell = st.selectbox("Select Stock to Exit", list(port.keys()))
            if st.button("Confirm Exit"):
                # 1. Add to history
                entry = port[to_sell]['price']
                exit_p = analysis[analysis['SYMBOL'] == to_sell].iloc[0]['PRICE']
                new_hist = pd.DataFrame([{"SYMBOL": to_sell, "BUY_PRICE": entry, "SELL_PRICE": exit_p, "P&L_%": round(((exit_p-entry)/entry)*100, 2), "DATE": str(datetime.date.today())}])
                history = pd.concat([history, new_hist], ignore_index=True)
                history.to_csv("trade_history.csv", index=False)
                # 2. Remove from portfolio
                del port[to_sell]
                with open("portfolio.json", "w") as f: json.dump(port, f)
                st.success(f"Exited {to_sell} at {exit_p}")
                st.rerun()

    # --- TAB 3: ACTIONABLES ---
    with tabs[2]:
        st.subheader("⚠️ Immediate Actions")
        # Check Portfolio for Exit Signals
        with open("portfolio.json", "r") as f: port = json.load(f)
        for s in port:
            row = analysis[analysis['SYMBOL'] == s].iloc[0]
            if "EXIT" in row['VERDICT']:
                st.error(f"SELL ALERT: {s} is Overbought (RSI: {row['RSI']}). Secure profits!")
            if row['PRICE'] <= row['STOP-LOSS']:
                st.warning(f"STOP LOSS HIT: {s} has touched SL. Protect capital.")

        st.subheader("🚀 High-Probability Swing Setup")
        st.table(analysis[analysis['VERDICT'] == "💎 ALPHA BUY"].sort_values("VOL_SURGE", ascending=False).head(5)[["SYMBOL", "PRICE", "EXPECTED_%", "HOLDING_PERIOD"]])

    # --- TAB 4: SUCCESS RATE ---
    with tabs[3]:
        if not history.empty:
            st.header(f"Total Trades: {len(history)}")
            win_rate = (len(history[history['P&L_%'] > 0]) / len(history)) * 100
            st.metric("Win Rate", f"{win_rate:.1f}%")
            st.dataframe(history, use_container_width=True)
        else:
            st.info("Exit a trade in the Portfolio tab to see performance history.")
else:
    st.error("Missing Data. Run engine.py first.")
