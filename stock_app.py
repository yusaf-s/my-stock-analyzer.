import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import pytz
import time

# --- CONFIG ---
st.set_page_config(layout="wide", page_title="India Alpha: Silverline Ultimate")

# --- AUTO-REFRESH CONFIG ---
refresh_rate = 30

# 1. Header
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
st.title("🚀 India Alpha: Silverline Ultimate Tracker")

timer_placeholder = st.empty()
st.write(f"🕒 **Last Update (IST):** {current_time}")

# 2. Sidebar
symbol = st.sidebar.text_input("Ticker", "silverline.BO")
period = st.sidebar.selectbox("Horizon", ["1d", "5d", "1mo", "1y"], index=0)

# 3. Data Engine
def get_live_data(ticker, pd_val):
    interval_map = {"1d": "1m", "5d": "5m", "1mo": "1d", "1y": "1d"}
    try:
        data = yf.download(ticker, period=pd_val, interval=interval_map[pd_val], progress=False)
        if pd_val == "1d" and (data is None or len(data) < 5):
            data = yf.download(ticker, period="4d", interval="1m", progress=False)
            if not data.empty:
                last_date = data.index[-1].date()
                data = data[data.index.date == last_date]
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except: return None

df = get_live_data(symbol, period)

if df is None or len(df) < 15:
    st.error("❌ Waiting for market data... Retrying soon.")
    time.sleep(5)
    st.rerun()
else:
    # --- 4. CALCULATIONS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)

    epsilon = 0.00001
    df['Range'] = (df['High'] - df['Low']) + epsilon
    df['Buy_Vol'] = df['Volume'] * (df['Close'] - df['Low']) / df['Range']
    df['Sell_Vol'] = df['Volume'] * (df['High'] - df['Close']) / df['Range']
    
    current_buy_vol = float(df['Buy_Vol'].iloc[-1])
    current_sell_vol = float(df['Sell_Vol'].iloc[-1])
    
    # Period Aggregates
    total_period_buy = df['Buy_Vol'].sum()
    total_period_sell = df['Sell_Vol'].sum()
    total_period_vol = total_period_buy + total_period_sell
    
    # Calculate percentage for the Horizontal Bar
    buy_percentage = (total_period_buy / total_period_vol * 100) if total_period_vol > 0 else 50
    sell_percentage = 100 - buy_percentage

    # Target Logic
    y_vals = df['Close'].tail(10).values.flatten()
    x_vals = np.arange(10)
    slope, intercept = np.polyfit(x_vals, y_vals, 1)
    raw_prediction = slope * 11 + intercept 
    last_close = float(df['Close'].iloc[-1])
    upper_circuit = round(last_close * 1.05, 2)
    prediction = min(raw_prediction, upper_circuit)

    # --- 5. CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=[df.index[-1]], y=[prediction],
        mode='markers+text',
        text=[f"  Target: ₹{prediction:.2f}"],
        textposition="middle right",
        marker=dict(symbol='star', size=18, color="yellow", line=dict(width=1, color="white")),
        name='Target'
    ), row=1, col=1)

    fig.add_trace(go.Bar(x=df.index, y=df['Buy_Vol'], name='Buy Vol', marker_color='#26a69a'), row=2, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Sell_Vol'], name='Sell Vol', marker_color='#ef5350'), row=2, col=1)
    
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=2), name='RSI'), row=3, col=1)
    fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, barmode='stack', showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. VISUAL VOLUME BAR (TUG OF WAR) ---
    st.markdown(f"### 📊 Cumulative Volume Sentiment ({period})")
    
    # Custom HTML for Horizontal Sentiment Bar
    bar_html = f"""
    <div style="width: 100%; background-color: #444; border-radius: 10px; display: flex; height: 30px; overflow: hidden; margin-bottom: 20px; border: 1px solid #666;">
        <div style="width: {buy_percentage}%; background-color: #26a69a; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 14px;">
            {buy_percentage:.1f}% BUY
        </div>
        <div style="width: {sell_percentage}%; background-color: #ef5350; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 14px;">
            {sell_percentage:.1f}% SELL
        </div>
    </div>
    """
    st.markdown(bar_html, unsafe_allow_html=True)

    # --- 7. DASHBOARD METRICS ---
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.metric("Live Price", f"₹{last_close:.2f}")
        st.metric("Target", f"₹{prediction:.2f}", f"{((prediction/last_close)-1)*100:.2f}%")

    with c2:
        total_v = current_buy_vol + current_sell_vol
        b_pct = (current_buy_vol / total_v * 100) if total_v > 0 else 0
        st.metric("Last Candle Buy", f"{b_pct:.1f}%", f"{current_buy_vol:,.0f}")
        st.write(f"**Total Period Buy:**")
        st.write(f"{total_period_buy:,.0f}")
        
    with c3:
        s_pct = (current_sell_vol / total_v * 100) if total_v > 0 else 0
        st.metric("Last Candle Sell", f"{s_pct:.1f}%", f"-{current_sell_vol:,.0f}", delta_color="inverse")
        st.write(f"**Total Period Sell:**")
        st.write(f"{total_period_sell:,.0f}")
        
    with c4:
        st.info(f"RSI: {df['RSI'].iloc[-1]:.1f}")
        st.write(f"📊 **Total Period Vol:**")
        st.subheader(f"{total_period_vol:,.0f}")

    # --- 8. COUNTDOWN ---
    for i in range(refresh_rate, -1, -1):
        timer_placeholder.markdown(f"⏳ **Next Refresh in:** `{i}s`")
        time.sleep(1)
        
    st.rerun()
