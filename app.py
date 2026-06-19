import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import datetime as dt
import plotly.graph_objects as go
import numpy_financial as npf
import os

st.set_page_config(page_title="專業級個人資產投資看板", layout="wide")
st.title("🚀 個人投資績效 vs 0050 PK 看板")

ASSET_FILE = "asset_history.csv"
FLOW_FILE = "cash_flow.csv"

def load_data():
    if os.path.exists(ASSET_FILE):
        df_a = pd.read_csv(ASSET_FILE)
        df_a['Date'] = pd.to_datetime(df_a['Date'])
    else:
        df_a = pd.DataFrame({
            'Date': pd.to_datetime(['2026-01-02', '2026-03-02', '2026-06-01']),
            'Stock': [50000, 60000, 80000], 'Bond': [30000, 30000, 25000], 'Cash': [20000, 15000, 15000]
        })
    if os.path.exists(FLOW_FILE):
        df_f = pd.read_csv(FLOW_FILE)
        df_f['Date'] = pd.to_datetime(df_f['Date'])
    else:
        df_f = pd.DataFrame({'Date': pd.to_datetime(['2026-01-02', '2026-04-15']), 'Amount': [100000, 10000]})
    return df_a.sort_values('Date').reset_index(drop=True), df_f.sort_values('Date').reset_index(drop=True)

df_asset, df_flow = load_data()

st.sidebar.header("✍️ 數據管理面板")
action = st.sidebar.selectbox("選擇操作項目：", ["紀錄每日資產市值", "紀錄入金/出金"])

if action == "紀錄每日資產市值":
    with st.sidebar.form("asset_form", clear_on_submit=True):
        a_date = st.date_input("選擇日期", dt.date.today())
        a_stock = st.number_input("股票總市值 (TWD)", min_value=0.0, step=1000.0)
        a_bond = st.number_input("債券總市值 (TWD)", min_value=0.0, step=1000.0)
        a_cash = st.number_input("現金/定存總額 (TWD)", min_value=0.0, step=1000.0)
        if st.form_submit_button("存檔資產紀錄"):
            new_date = pd.to_datetime(a_date)
            df_asset = df_asset[df_asset['Date'] != new_date]
            new_row = pd.DataFrame({'Date': [new_date], 'Stock': [a_stock], 'Bond': [a_bond], 'Cash': [a_cash]})
            df_asset = pd.concat([df_asset, new_row], ignore_index=True).sort_values('Date').reset_index(drop=True)
            df_asset.to_csv(ASSET_FILE, index=False)
            st.sidebar.success(f"🎉 {a_date} 資產已更新！")
            st.rerun()

elif action == "紀錄入金/出金":
    with st.sidebar.form("flow_form", clear_on_submit=True):
        f_date = st.date_input("選擇日期", dt.date.today())
        f_amount = st.number_input("金額 (TWD)", step=1000.0)
        if st.form_submit_button("存檔現金流"):
            new_date = pd.to_datetime(f_date)
            new_row = pd.DataFrame({'Date': [new_date], 'Amount': [f_amount]})
            df_flow = pd.concat([df_flow, new_row], ignore_index=True).sort_values('Date').reset_index(drop=True)
            df_flow.to_csv(FLOW_FILE, index=False)
            st.sidebar.success(f"💰 已記錄現金流：{f_amount:,.0f} 元")
            st.rerun()

df_asset['Total'] = df_asset['Stock'] + df_asset['Bond'] + df_asset['Cash']

@st.cache_data(ttl=86400)
def fetch_0050():
    start_str = df_asset['Date'].min().strftime('%Y-%m-%d') if not df_asset.empty else "2025-01-01"
    df = yf.download("0050.TW", start=start_str, end=(dt.date.today() + dt.timedelta(days=1)).strftime('%Y-%m-%d'))
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df = df[['Close']].reset_index()
    df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
    return df

try: df_0050 = fetch_0050()
except: df_0050 = pd.DataFrame()

if len(df_asset) >= 2 and not df_0050.empty:
    today = dt.datetime.today()
    range_map = {
        "年初至今 (YTD)": today.replace(month=1, day=1), "近 1 個月": today - dt.timedelta(days=30),
        "近 3 個月": today - dt.timedelta(days=90), "近 6 個月": today - dt.timedelta(days=180),
        "近 1 年": today - dt.timedelta(days=365), "全部歷史": df_asset['Date'].min()
    }
    selected_range = st.radio("比較區間：", list(range_map.keys()), horizontal=True)
    start_filter = pd.to_datetime(range_map[selected_range])
    
    f_asset = df_asset[df_asset['Date'] >= start_filter].copy()
    f_flow = df_flow[df_flow['Date'] >= start_filter].copy()
    f_0050 = df_0050[df_0050['Date'] >= start_filter].copy()
    
    if len(f_asset) >= 2:
        def calculate_xirr(cash_flows, end_date, end_value):
            dates = list(cash_flows['Date']) + [end_date]
            amounts = [-x for x in cash_flows['Amount']] + [end_value]
            try:
                years = (end_date - dates[0]).days / 365.0
                if years <= 0: return 0.0
                return ((1 + npf.xirr(dates, amounts)) ** years - 1) * 100
            except:
                total_invested = cash_flows['Amount'].sum() if not cash_flows.empty else end_value
                return ((end_value - total_invested) / max(total_invested, 1)) * 100

        base_asset_val = f_asset['Total'].iloc[0]
        f_asset['Net_Return_%'] = ((f_asset['Total'] - base_asset_val) / base_asset_val) * 100
        base_0050_val = f_0050['Close'].iloc[0] if not f_0050.empty else 1
        f_0050['Return_%'] = ((f_0050['Close'] - base_0050_val) / base_0050_val) * 100

        user_mdd = ((f_asset['Total'] - f_asset['Total'].cummax()) / f_asset['Total'].cummax()).min() * 100
        etf_mdd = ((f_0050['Close'] - f_0050['Close'].cummax()) / f_0050['Close'].cummax()).min() * 100
        user_final_perf = calculate_xirr(f_flow, f_asset['Date'].iloc[-1], f_asset['Total'].iloc[-1])
        etf_final_perf = f_0050['Return_%'].iloc[-1] if not f_0050.empty else 0.0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("👤 我的區間報酬率 (XIRR)", f"{user_final_perf:.2f}%")
        m2.metric("🎯 0050 同期報酬率", f"{etf_final_perf:.2f}%")
        perf_diff = user_final_perf - etf_final_perf
        m3.metric("🏆 績效對決結果", f"{perf_diff:+.2f}%", delta="戰勝 0050" if perf_diff > 0 else "落後 0050")
        m4.metric("📉 我的最大回撤 (MDD)", f"{user_mdd:.2f}%", delta=f"0050 MDD: {etf_mdd:.2f}%", delta_color="inverse")

        st.write("---")
        col_left, col_right = st.columns([2, 1])
        with col_left:
            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(x=f_asset['Date'], y=f_asset['Net_Return_%'], mode='lines+markers', name='我的資產走勢', line=dict(color='#2ca02c', width=3)))
            fig_line.add_trace(go.Scatter(x=f_0050['Date'], y=f_0050['Return_%'], mode='lines', name='0050 基準線', line=dict(color='#ff7f0e', width=2, dash='dash')))
            fig_line.update_layout(title="📈 績效 PK 走勢圖", template="plotly_white")
            st.plotly_chart(fig_line, use_container_width=True)
        with col_right:
            latest_asset = f_asset.iloc[-1]
            fig_pie = go.Figure(data=[go.Pie(labels=['股票', '債券', '現金'], values=[latest_asset['Stock'], latest_asset['Bond'], latest_asset['Cash']], hole=.4)])
            fig_pie.update_layout(title="🍕 最新資產配置比例")
            st.plotly_chart(fig_pie, use_container_width=True)
else:
    st.info("💡 請利用左側面板輸入至少「兩天不同日期」的資產市值紀錄，系統將會為您呈現 PK 看板！")