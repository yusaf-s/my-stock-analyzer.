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

# 1. Header & Time
IST = pytz.timezone('Asia/Kolkata')
current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
st.title("🚀 India Alpha: Silverline Ultimate Tracker")

timer_placeholder = st.empty()
st.write(f"🕒 **Last Update (IST):** {current_time}")

# 2. Sidebar - New Intervals Added
symbol = st.sidebar.text_input("Ticker", "silverline.BO")

# Mapping the display name to (yfinance_period, yfinance_interval)
horizon_options = {
    "1d (1m)": ("1d", "1m"),
    "15 mins": ("2d", "15m"),  # Fetching 2 days to ensure enough data for indicators
    "1 hour": ("7d", "60m"),
    "4 hours": ("1mo", "1h"), # Resampling or 1h is standard; 4h requires a resample
    "5 days (5m)": ("5d", "5m"),
    "1 month (1d)": ("1mo", "1d"),
    "1 year (1d)": ("1y", "1d")
}

choice = st.sidebar.selectbox("Horizon", list(horizon_options.keys()), index=0)
selected_period, selected_interval = horizon_options[choice]

# 3. Data Engine
def get_live_data(ticker, pd_val, int_val):
    try:
        data = yf.download(ticker, period=pd_val, interval=int_val, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        if data.empty: return None
        
        # If 4 hour was selected, resample the 1h data
        if "4 hours" in choice:
            data = data.resample('4H').agg({
                'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
            }).dropna()
            
        return data
    except Exception: return None

df = get_live_data(symbol, selected_period, selected_interval)

# Verification check to prevent crashing on empty data
if df is None or len(df) < 15:
    st.error("❌ Insufficient data for this interval. Try a longer Horizon.")
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
    
    total_period_buy = df['Buy_Vol'].sum()
    total_period_sell = df['Sell_Vol'].sum()
    total_period_vol = total_period_buy + total_period_sell
    
    buy_percentage = (total_period_buy / total_period_vol * 100) if total_period_vol > 0 else 50
    sell_percentage = 100 - buy_percentage

    # Robust Target Prediction
    lookback = 15
    y_vals = df['Close'].tail(lookback).values.flatten().astype(float)
    x_vals = np.arange(len(y_vals))
    slope, intercept = np.polyfit(x_vals, y_vals, 1)
    
    last_close = float(df['Close'].iloc[-1])
    raw_prediction = slope * (len(y_vals) + 1) + intercept 
    prediction = np.clip(raw_prediction, last_close * 0.95, last_close * 1.05)

    # RSI Safety Check
    last_rsi = df['RSI'].iloc[-1]
    rsi_display = f"{last_rsi:.1f}" if not np.isnan(last_rsi) else "N/A"

    # --- 5. CHARTING ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                 low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=[df.index[-1]], y=[prediction], mode='markers+text',
        text=[f"  Target: ₹{prediction:.2f}"], textposition="middle right",
        marker=dict(symbol='star', size=18, color="yellow", line=dict(width=1, color="white")),
        name='Target'
    ), row=1, col=1)

    fig.add_trace(go.Bar(x=df.index, y=df['Buy_Vol'], name='Buy Vol', marker_color='#26a69a'), row=2, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Sell_Vol'], name='Sell Vol', marker_color='#ef5350'), row=2, col=1)
    
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=2), name='RSI'), row=3, col=1)
    fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, barmode='stack', showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. VISUAL VOLUME BAR ---
    st.markdown(f"### 📊 Cumulative Sentiment ({choice})")
    st.markdown(f"""
    <div style="width: 100%; background-color: #444; border-radius: 10px; display: flex; height: 35px; overflow: hidden; border: 1px solid #666;">
        <div style="width: {buy_percentage}%; background-color: #26a69a; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">
            {buy_percentage:.1f}% BUY
        </div>
        <div style="width: {sell_percentage}%; background-color: #ef5350; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">
            {sell_percentage:.1f}% SELL
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- 7. DASHBOARD METRICS ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Live Price", f"₹{last_close:.2f}")
        st.metric("Target", f"₹{prediction:.2f}", f"{((prediction/last_close)-1)*100:+.2f}%")

    with c2:
        st.metric("Total Buy Vol", f"{total_period_buy:,.0f}")
        st.caption(f"Last Candle: {current_buy_vol:,.0f}")
        
    with c3:
        st.metric("Total Sell Vol", f"{total_period_sell:,.0f}", delta_color="inverse")
        st.caption(f"Last Candle: -{current_sell_vol:,.0f}")
        
    with c4:
        st.write(f"**RSI ({choice}):**")
        st.subheader(rsi_display)
        st.write(f"📊 **Total Period Vol:**")
        st.info(f"{total_period_vol:,.0f}")

    # --- 8. COUNTDOWN ---
    for i in range(refresh_rate, -1, -1):
        timer_placeholder.markdown(f"⏳ **Next Refresh in:** `{i}s`")
        time.sleep(1)
    st.rerun()
