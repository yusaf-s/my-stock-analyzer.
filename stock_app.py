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

# --- AUTO-REFRESH (30 Seconds) ---
refresh_rate = 30

# 1. Header
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
st.title("🚀 India Alpha: Silverline Ultimate Tracker")
st.write(f"🕒 **Last Update (IST):** {current_time} | *Refreshing every {refresh_rate}s*")

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
else:
    # --- 4. CALCULATIONS ---
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['Vol_SMA'] = ta.sma(df['Volume'], length=20)

    # NEW: Buy/Sell Volume Logic (Intraday Pressure)
    # Uses the position of the Close relative to the High/Low range
    df['Range'] = (df['High'] - df['Low']).replace(0, 0.001) # Avoid division by zero
    df['Buy_Vol'] = df['Volume'] * (df['Close'] - df['Low']) / df['Range']
    df['Sell_Vol'] = df['Volume'] * (df['High'] - df['Close']) / df['Range']
    
    current_buy_vol = df['Buy_Vol'].iloc[-1]
    current_sell_vol = df['Sell_Vol'].iloc[-1]

    # Prediction Logic
    y_vals, x_vals = df['Close'].tail(10).values.flatten(), np.arange(10)
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

    # Prediction Star
    last_time = df.index[-1]
    star_color = "red" if df['RSI'].iloc[-1] > 85 else "yellow"
    fig.add_trace(go.Scatter(x=[last_time], y=[prediction], mode='markers+text',
        text=[f" Target: ₹{prediction:.2f}"], textposition="middle right",
        marker=dict(symbol='star', size=15, color=star_color), name='Target'), row=1, col=1)

    # Volume Chart (Stacked Buy/Sell)
    fig.add_trace(go.Bar(x=df.index, y=df['Buy_Vol'], name='Buy Vol', marker_color='#26a69a'), row=2, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Sell_Vol'], name='Sell Vol', marker_color='#ef5350'), row=2, col=1)
    
    # RSI Chart
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=2)), row=3, col=1)

    fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, barmode='stack')
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. DASHBOARD METRICS ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Live Price", f"₹{last_close:.2f}")
        st.write(f"RSI: {df['RSI'].iloc[-1]:.1f}")
    with c2:
        # Show Buy vs Sell Volume for the latest bar
        total_v = current_buy_vol + current_sell_vol
        b_pct = (current_buy_vol / total_v * 100) if total_v > 0 else 0
        st.metric("Buy Pressure", f"{b_pct:.1f}%", f"{current_buy_vol:,.0f} units")
    with c3:
        s_pct = (current_sell_vol / total_v * 100) if total_v > 0 else 0
        st.metric("Sell Pressure", f"{s_pct:.1f}%", f"-{current_sell_vol:,.0f}", delta_color="inverse")
    with c4:
        conf = "🚀 STRONG VOL" if df['Volume'].iloc[-1] > df['Vol_SMA'].iloc[-1] else "😴 LOW VOL"
        st.info(f"Signal: {conf}")

    time.sleep(refresh_rate)
    st.rerun()
